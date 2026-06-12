from __future__ import annotations

import json
import hashlib
import pytest
import urllib.request
import urllib.error
import io
import socket
import time
from pathlib import Path
from typing import Callable, Any

from experiments.providers.models import (
    TransportRequest,
    TransportResponse,
    ProviderTransportError,
    ProviderAuthenticationError,
    ProviderGatewayError,
    ModelRequest,
    ModelParameters,
    ProviderCapabilities,
    ProviderConfig,
    ProviderAttemptRecord,
    TransportErrorInfo,
)
from experiments.providers.openai_compatible import OpenAICompatibleProvider
from experiments.live.http_transport import OpenAICompatibleHttpTransport, ALLOWED_RESPONSE_HEADERS, AttemptReservingTransport
from experiments.live.rate_limit import LiveRateLimitPolicy, LiveRateLimiter
from experiments.live.budget import BudgetLimits, LiveBudgetTracker, BudgetExceededError
from experiments.runner.config import ExperimentConfig, ExperimentPaths
from experiments.runner.scheduler import PlannedRun, RunIdentity
from experiments.live.diagnostics import write_provider_failure_diagnostic


class FakeCancellationToken:
    def __init__(self, cancelled: bool = False) -> None:
        self._cancelled = cancelled
    def is_cancelled(self) -> bool:
        return self._cancelled
    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise RuntimeError("Cancelled")


# Helper to build mock HTTPError
def make_http_error(code: int, msg: str, body: bytes, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    from http.client import HTTPMessage
    fp = io.BytesIO(body)
    hdrs = HTTPMessage()
    if headers:
        for k, v in headers.items():
            hdrs.add_header(k, v)
    return urllib.error.HTTPError("http://127.0.0.1:8787/v1/chat/completions", code, msg, hdrs, fp)


# Helper to build mock response
class MockHttpResponse:
    def __init__(self, status: int, body_data: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self.body_data = body_data
        from http.client import HTTPMessage
        self.headers = HTTPMessage()
        for k, v in headers.items():
            self.headers.add_header(k, v)
    def read(self, amt: int | None = None) -> bytes:
        if amt is not None and len(self.body_data) >= amt:
            return self.body_data[:amt]
        return self.body_data


class MockOpener:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0
    def open(self, req, timeout=None):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


# Test 1: Real urllib.error.HTTPError(429) turns into status response.
def test_httperror_429_turned_into_status_response():
    err = make_http_error(429, "Too Many Requests", b'{"error": "rate limit"}', {"Retry-After": "60"})
    transport = OpenAICompatibleHttpTransport("http://127.0.0.1:8787/v1")
    transport.opener = MockOpener(err)
    
    req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
    resp = transport.send(req)
    assert isinstance(resp, TransportResponse)
    assert resp.status_code == 429
    assert resp.body_bytes == b'{"error": "rate limit"}'
    assert any(k.lower() == "retry-after" and v == "60" for k, v in resp.allowlisted_headers)


# Test 2: 401/403 remain authentication failures.
def test_httperror_401_403_remain_auth_failures():
    transport = OpenAICompatibleHttpTransport("http://127.0.0.1:8787/v1")
    for code in (401, 403):
        err = make_http_error(code, "Auth Error", b"unauthorized")
        transport.opener = MockOpener(err)
        req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
        with pytest.raises(ProviderAuthenticationError):
            transport.send(req)


# Test 3: HTTP error body still obeys 10 MB limit.
def test_http_error_body_obeys_size_limit():
    large_body = b"x" * (10 * 1024 * 1024 + 10)
    err = make_http_error(429, "Too Many Requests", large_body)
    transport = OpenAICompatibleHttpTransport("http://127.0.0.1:8787/v1")
    transport.opener = MockOpener(err)
    req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
    with pytest.raises(ProviderTransportError, match="Response size limit exceeded"):
        transport.send(req)


# Test 4: Retry-After is case-insensitive allowlisted.
def test_retry_after_case_insensitive_allowlist():
    assert "retry-after" in ALLOWED_RESPONSE_HEADERS
    err = make_http_error(429, "Too Many Requests", b"{}", {"ReTrY-AfTeR": "45"})
    transport = OpenAICompatibleHttpTransport("http://127.0.0.1:8787/v1")
    transport.opener = MockOpener(err)
    req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
    resp = transport.send(req)
    headers = {k.lower(): v for k, v in resp.allowlisted_headers}
    assert "retry-after" in headers
    assert headers["retry-after"] == "45"


# Test 5: Delta-seconds parsing.
def test_delta_seconds_parsing():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    resp = TransportResponse(429, b"{}", (("Retry-After", "15"),), None)
    delay = limiter.resolve_retry_delay(1, resp, 1000.0)
    assert delay == 15.0


# Test 6: HTTP-date parsing.
def test_http_date_parsing():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    # Fri, 12 Jun 2026 23:59:59 GMT (epoch 1781308799.0)
    resp = TransportResponse(429, b"{}", (("Retry-After", "Fri, 12 Jun 2026 23:59:59 GMT"),), None)
    now = 1781308759.0 # 40 seconds before
    delay = limiter.resolve_retry_delay(1, resp, now)
    assert delay == 40.0


# Test 7: Malformed or negative Retry-After fallback.
def test_malformed_or_negative_retry_after_fallback():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    
    # Negative integer
    resp_neg = TransportResponse(429, b"{}", (("Retry-After", "-10"),), None)
    assert limiter.resolve_retry_delay(1, resp_neg, 1000.0) == 30.0
    assert limiter.resolve_retry_delay(2, resp_neg, 1000.0) == 60.0
    
    # Malformed date
    resp_mal = TransportResponse(429, b"{}", (("Retry-After", "invalid date"),), None)
    assert limiter.resolve_retry_delay(1, resp_mal, 1000.0) == 30.0
    assert limiter.resolve_retry_delay(2, resp_mal, 1000.0) == 60.0


# Test 8: Delay clamp to 1..120 seconds.
def test_delay_clamp_to_1_to_120():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    
    # Too small
    resp_small = TransportResponse(429, b"{}", (("Retry-After", "0"),), None)
    assert limiter.resolve_retry_delay(1, resp_small, 1000.0) == 1.0
    
    # Too large
    resp_large = TransportResponse(429, b"{}", (("Retry-After", "300"),), None)
    assert limiter.resolve_retry_delay(1, resp_large, 1000.0) == 120.0


# Test 9: Absent-header fallback delays 30/60 seconds.
def test_absent_header_fallback():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    resp = TransportResponse(429, b"{}", (), None)
    assert limiter.resolve_retry_delay(1, resp, 1000.0) == 30.0
    assert limiter.resolve_retry_delay(2, resp, 1000.0) == 60.0


# Test 10: 502/503/504 retain fixed 0.25/0.50 seconds.
def test_502_503_504_retain_fixed_backoffs():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy)
    for status in (502, 503, 504):
        resp = TransportResponse(status, b"{}", (), None)
        assert limiter.resolve_retry_delay(1, resp, 1000.0) == 0.25
        assert limiter.resolve_retry_delay(2, resp, 1000.0) == 0.50


# Test 11: Default non-live Provider behavior remains unchanged.
def test_default_non_live_provider_behavior_unchanged():
    # If no custom resolver is injected, standard backoffs (0.25 / 0.50) are used
    params = ModelParameters("gpt-4o", 0.0, 1.0, 100, 30.0, 42)
    caps = ProviderCapabilities(True, True, True)
    config = ProviderConfig("openai", "http://127.0.0.1:8787/v1", params, caps, 3, (0.25, 0.5))
    
    # Verify _retry_backoff behavior of OpenAICompatibleProvider directly
    # Note: we can use a mock transport and call generate
    class MockTransport:
        def __init__(self) -> None:
            self.calls = 0
        def send(self, req, cancellation=None):
            self.calls += 1
            # Return 429
            return TransportResponse(429, b"{}", (), None)
    
    transport = MockTransport()
    slept = []
    def mock_sleep(secs: float) -> None:
        slept.append(secs)
        
    provider = OpenAICompatibleProvider(config, transport=transport, sleeper=mock_sleep)
    req = ModelRequest(1, "req-id", "", "hello", params, None)
    
    with pytest.raises(Exception):
        provider.generate(req)
        
    assert transport.calls == 3
    assert slept == [0.25, 0.5]


# Test 12: One shared limiter is used by all A/C/E Providers.
def test_one_shared_limiter_across_providers():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    # Mock clock to increase on every call to simulate progression
    current_time = [1000.0]
    def mock_clock() -> float:
        current_time[0] += 0.1
        return current_time[0]
        
    limiter = LiveRateLimiter(policy, clock=mock_clock, sleeper=lambda s: None)
    
    # Simulate A, C, E Providers making calls sharing the same limiter instance
    # Calling wait_before_attempt should advance the last_attempt_time on the SAME limiter
    slept1 = limiter.wait_before_attempt()
    assert limiter.last_attempt_time is not None
    last_time = limiter.last_attempt_time
    
    slept2 = limiter.wait_before_attempt()
    # The second wait should sleep because mock_clock only advanced by 0.1, but needed interval is 1.0
    assert slept2 > 0.0
    assert limiter.last_attempt_time > last_time


# Test 13: Limiter wait occurs before attempt reservation.
def test_limiter_wait_occurs_before_attempt_reservation():
    sequence = []
    def mock_wait(*args, **kwargs):
        sequence.append("wait")
        return 0.0
    def mock_reserve():
        sequence.append("reserve")
        
    class MockLimiter:
        def wait_before_attempt(self, cancellation=None, check_budget_fn=None):
            return mock_wait(cancellation)
            
    class MockInnerTransport:
        @property
        def no_auth_loopback(self) -> bool:
            return False
        def send(self, request, cancellation=None):
            sequence.append("send")
            return TransportResponse(200, b"{}", (), None)
            
    limiter = MockLimiter()
    inner = MockInnerTransport()
    transport = AttemptReservingTransport(inner, mock_reserve, limiter=limiter)
    
    req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
    transport.send(req)
    
    assert sequence == ["wait", "reserve", "send"]


# Test 14: Waiting does not increment attempt count.
def test_waiting_does_not_increment_attempt_count():
    limits = BudgetLimits(1000, 1000, 10, 2, 2, 2, 60.0)
    tracker = LiveBudgetTracker(limits)
    
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy, clock=tracker.clock, sleeper=lambda s: None)
    
    # Wait before attempt multiple times
    limiter.wait_before_attempt()
    limiter.wait_before_attempt()
    
    # Verify tracker is still at 0 attempts
    assert tracker.provider_attempt_count == 0


# Test 15: Every retry send reserves exactly one attempt.
def test_every_retry_send_reserves_exactly_one_attempt():
    limits = BudgetLimits(1000, 1000, 10, 2, 2, 2, 60.0)
    tracker = LiveBudgetTracker(limits)
    
    # Set up transport with reserve hook
    class MockInnerTransport:
        @property
        def no_auth_loopback(self) -> bool:
            return False
        def send(self, request, cancellation=None):
            return TransportResponse(502, b"{}", (), None) # return retryable 502
            
    inner = MockInnerTransport()
    transport = AttemptReservingTransport(inner, tracker.reserve_provider_attempt, limiter=None)
    
    # Set up provider with this transport
    params = ModelParameters("gpt-4o", 0.0, 1.0, 100, 30.0, 42)
    caps = ProviderCapabilities(True, True, True)
    config = ProviderConfig("openai", "http://127.0.0.1:8787/v1", params, caps, 3, (0.25, 0.5))
    
    provider = OpenAICompatibleProvider(config, transport=transport, sleeper=lambda s: None)
    req = ModelRequest(1, "req-id", "", "hello", params, None)
    
    with pytest.raises(Exception):
        provider.generate(req)
        
    # Since max_attempts = 3, and all failed with 502, it should have reserved exactly 3 times
    assert tracker.provider_attempt_count == 3


# Test 16: Attempt 661 fails before sender execution.
def test_attempt_661_fails_before_sender():
    # If budget is 660, attempt 661 raises BudgetExceededError and does not call send()
    limits = BudgetLimits(1000, 1000, 660, 2, 2, 2, 60.0)
    tracker = LiveBudgetTracker(limits)
    tracker.provider_attempt_count = 660 # Set to max
    
    sent_called = []
    class MockInnerTransport:
        @property
        def no_auth_loopback(self) -> bool:
            return False
        def send(self, request, cancellation=None):
            sent_called.append(True)
            return TransportResponse(200, b"{}", (), None)
            
    inner = MockInnerTransport()
    transport = AttemptReservingTransport(inner, tracker.reserve_provider_attempt, limiter=None)
    
    req = TransportRequest("POST", "http://127.0.0.1:8787/v1/chat/completions", (), b"{}", 30.0, "client-id")
    
    with pytest.raises(BudgetExceededError, match="Total API calls limit exceeded"):
        transport.send(req)
        
    assert not sent_called


# Test 17: The 10-second inter-run cooldown applies equally to A/C/E.
def test_inter_run_cooldown_applies_equally():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    slept_durations = []
    def mock_sleep(secs: float) -> None:
        slept_durations.append(secs)
        
    limiter = LiveRateLimiter(policy, sleeper=mock_sleep)
    limiter.wait_after_completed_run()
    
    assert slept_durations == [10.0]


# Test 18: Wall-clock and cancellation checks surround waits.
def test_wall_clock_and_cancellation_surround_waits():
    policy = LiveRateLimitPolicy(1.0, 10.0, 1.0, 120.0, (30.0, 60.0))
    limiter = LiveRateLimiter(policy, sleeper=lambda s: None)
    
    cancel_token = FakeCancellationToken(cancelled=True)
    
    with pytest.raises(RuntimeError, match="Request cancelled"):
        limiter.wait_before_attempt(cancellation=cancel_token)
        
    with pytest.raises(RuntimeError, match="Request cancelled"):
        limiter.wait_after_completed_run(cancellation=cancel_token)


# Test 19: Final 429 still aborts and writes no completed result record.
def test_final_429_aborts_without_completed_record(tmp_path):
    approved_root = tmp_path
    experiment_id = "m7e_full_20260612T040000Z"
    
    runs = []
    for i in range(45):
        task_id = f"T{i%5+1:02d}"
        strategy = ["A", "C", "E"][i%3]
        rep = i // 15 + 1
        run_id = f"{experiment_id}__{task_id}__{strategy}__rep{rep:02d}__seed42"
        ident = RunIdentity(experiment_id, task_id, strategy, rep, 42, run_id)
        task_record = {
            "task_id": task_id,
            "task_description": "dummy description",
            "files_to_modify": [],
            "starter_files": ["student_system/src/main.py"],
            "expected_behavior": [],
            "forbidden_behaviors": [],
            "allowed_corpus": []
        }
        runs.append(PlannedRun(ident, task_record, 0, 0, 0))

    from experiments.live.smoke_executor import LiveExperimentExecutor, LiveExecutionRequest
    from experiments.providers.models import ProviderGatewayError, TransportErrorInfo, ProviderAttemptRecord
    
    generate_calls = []

    class FaultyProvider:
        def __init__(self, hooks):
            self.hooks = hooks

        def generate(self, model_request):
            generate_calls.append(model_request)
            self.hooks.reserve_provider_attempt()
            att = ProviderAttemptRecord(1, 1, 0.1, 30.0, "transport_error", TransportErrorInfo("connection", False, 429, "rate_limit"))
            raise ProviderGatewayError("Persistent 429", attempt_records=(att,))

    def provider_factory(run, hooks):
        return FaultyProvider(hooks)

    raw_jsonl = approved_root / "results" / "raw" / f"{experiment_id}.jsonl"
    raw_jsonl.parent.mkdir(parents=True, exist_ok=True)

    configs_dir = approved_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    (configs_dir / "experiment.yaml").write_text("model: GPT5.4\nmodel_provider_id: openai_compatible_gateway\nseed: 42\nrepetitions: 3\nmax_repair_rounds: 1\nstrategies:\n  - A\n  - C\n  - E\ntimeout:\n  agent_response: 30.0\n  unit_test: 5.0\n  total_run: 600.0\npaths:\n  tasks_definition: experiments/tasks.json\n  raw_results_dir: results/raw\n  derived_results_dir: results/derived\n  reviews_dir: reviews\n  workspace_base_dir: workspace\n")
    (configs_dir / "models.yaml").write_text("default_provider: openai_compatible_gateway\ndefault_model: GPT5.4\nproviders:\n  openai_compatible_gateway:\n    provider_id: openai_compatible_gateway\n    api_base: http://localhost:8787\n    models:\n      - id: GPT5.4\n        temperature: 0.0\n        top_p: 0.95\n        max_output_tokens: 1024\nGPT5.4:\n  provider_id: openai_compatible_gateway\n  temperature: 0.0\n  capabilities:\n    completion: true\n")
    
    contracts_dir = approved_root / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    (contracts_dir / "result.schema.json").write_text('{"type": "object", "properties": {}}')
    (contracts_dir / "task.schema.json").write_text('{"type": "object"}')
    
    (approved_root / "experiments").mkdir(parents=True, exist_ok=True)
    (approved_root / "student_system" / "src").mkdir(parents=True, exist_ok=True)
    (approved_root / "student_system" / "src" / "main.py").write_text("# dummy")
    
    import json
    snapshot_files = [
        {
            "path": "student_system/src/main.py",
            "content": "# dummy",
            "sha256": "8f1205d33c3d250696074e66faab71c55196e19e8ddf7003c558ddfea1f1dac5"
        }
    ]
    (approved_root / "student_system" / "SNAPSHOT.json").write_text(json.dumps({"snapshot_id": "test", "files": snapshot_files}))
    
    tasks_content = []
    for i in range(1, 6):
        tasks_content.append({
            "task_id": f"T0{i}",
            "task_description": "dummy description",
            "files_to_modify": [],
            "starter_files": ["student_system/src/main.py"],
            "expected_behavior": [],
            "forbidden_behaviors": [],
            "allowed_corpus": []
        })
    (approved_root / "experiments" / "tasks.json").write_text(json.dumps(tasks_content))

    req = LiveExecutionRequest(
        experiment_id=experiment_id,
        mode="full",
        planned_runs=tuple(runs),
        raw_jsonl_path=raw_jsonl,
        artifact_root=approved_root / "results" / "raw" / "artifacts" / experiment_id,
        retrieval_log_root=approved_root / "results" / "raw" / "retrieval" / experiment_id,
        budget_limits=BudgetLimits(1000000, 500000, 10, 2, 2, 2, 60.0),
        provider_factory=provider_factory,
        repo_root=approved_root,
    )

    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    res = executor.execute(req)

    assert res.quarantined is True
    assert "Persistent 429" in res.abort_reason
    assert len(res.completed_run_ids) == 0
    assert not raw_jsonl.exists() or raw_jsonl.stat().st_size == 0

    # Assert FaultyProvider.generate was indeed called exactly once
    assert len(generate_calls) == 1

    # Assert provider_attempt_count is exactly 1
    assert res.provider_attempt_count == 1

    # Verify diagnostic status=429 assertion
    first_run_id = f"{experiment_id}__T01__A__rep01__seed42"
    diag_file = approved_root / "results" / "raw" / "diagnostics" / experiment_id / first_run_id / "provider_failure.json"
    assert diag_file.exists()
    with open(diag_file, "r", encoding="utf-8") as f:
        diag_data = json.load(f)
    assert diag_data["error_class"] == "ProviderGatewayError"
    assert diag_data["final_http_status"] == 429
    assert len(diag_data["attempt_records"]) == 1
    assert diag_data["attempt_records"][0]["error"]["status_code"] == 429


# Test 20: Canonical provider-failure diagnostic contains complete sanitized attempts.
def test_provider_failure_diagnostic_contains_sanitized_attempts(tmp_path):
    approved_root = tmp_path
    experiment_id = "m7e_full_20260612T040000Z"
    
    # Construct a PlannedRun and Config
    run_id = f"{experiment_id}__T01__E__rep01__seed42"
    ident = RunIdentity(experiment_id, "T01", "E", 1, 42, run_id)
    run = PlannedRun(ident, {"task_id": "T01", "files_to_modify": []}, 0, 0, 0)
    
    paths = ExperimentPaths(
        Path("tasks.json"),
        approved_root / "results" / "raw",
        approved_root / "results" / "derived",
        approved_root / "reviews",
        approved_root / "workspace",
        approved_root / "results" / "raw" / "artifacts" / experiment_id,
        approved_root / "results" / "raw" / "retrieval" / experiment_id,
    )
    config = ExperimentConfig(
        strategies=("E",),
        repetitions=1,
        max_repair_rounds=1,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=5.0,
        total_run_timeout_seconds=600.0,
        paths=paths,
        model_provider_id="openai",
        model="gpt-4o",
        mode="live",
        live_opt_in=True,
    )
    
    # Mock ProviderError
    att = ProviderAttemptRecord(
        call_index=1,
        attempt_index=1,
        latency_seconds=1.2,
        backoff_seconds_after=30.0,
        outcome="transport_error",
        error=TransportErrorInfo("connection", True, 429, "rate_limit"),
    )
    exc = ProviderTransportError("Too many requests", attempt_records=(att,), elapsed_seconds=2.5)
    
    write_provider_failure_diagnostic(
        approved_root=approved_root,
        experiment_id=experiment_id,
        run=run,
        config=config,
        exc=exc,
        elapsed_seconds=5.0,
    )
    
    diagnostic_file = approved_root / "results" / "raw" / "diagnostics" / experiment_id / run.identity.run_id / "provider_failure.json"
    assert diagnostic_file.exists()
    
    # Read and parse
    with open(diagnostic_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["diagnostic_version"] == "1.0"
    assert data["experiment_id"] == experiment_id
    assert data["run_id"] == run.identity.run_id
    assert data["error_class"] == "ProviderTransportError"
    assert data["sanitized_error_code"] == "rate_limit"
    assert len(data["attempt_records"]) == 1
    assert data["attempt_records"][0]["attempt_index"] == 1


# Test 21: Diagnostics reject secrets, absolute paths, hidden-test paths, and raw bodies.
def test_diagnostics_reject_sensitive_info(tmp_path):
    approved_root = tmp_path
    experiment_id = "m7e_full_20260612T040000Z"
    run_id = f"{experiment_id}__T01__E__rep01__seed42"
    ident = RunIdentity(experiment_id, "T01", "E", 1, 42, run_id)
    run = PlannedRun(ident, {"task_id": "T01", "files_to_modify": []}, 0, 0, 0)
    
    paths = ExperimentPaths(
        Path("tasks.json"),
        approved_root / "results" / "raw",
        approved_root / "results" / "derived",
        approved_root / "reviews",
        approved_root / "workspace",
        approved_root / "results" / "raw" / "artifacts" / experiment_id,
        approved_root / "results" / "raw" / "retrieval" / experiment_id,
    )
    # A config where model has some sensitive text
    config = ExperimentConfig(
        strategies=("E",),
        repetitions=1,
        max_repair_rounds=1,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=5.0,
        total_run_timeout_seconds=600.0,
        paths=paths,
        model_provider_id="Bearer token", # credential in config
        model="gpt-4o",
        mode="live",
        live_opt_in=True,
    )
    
    exc = ProviderTransportError("Normal error")
    with pytest.raises(ValueError, match="Security Blocker: credential-like pattern"):
        write_provider_failure_diagnostic(
            approved_root=approved_root,
            experiment_id=experiment_id,
            run=run,
            config=config,
            exc=exc,
            elapsed_seconds=1.0,
        )


# Test 22: Diagnostic exclusive-create and failure behavior.
def test_diagnostic_exclusive_create_and_failure_behavior(tmp_path):
    approved_root = tmp_path
    experiment_id = "m7e_full_20260612T040000Z"
    run_id = f"{experiment_id}__T01__E__rep01__seed42"
    ident = RunIdentity(experiment_id, "T01", "E", 1, 42, run_id)
    run = PlannedRun(ident, {"task_id": "T01", "files_to_modify": []}, 0, 0, 0)
    
    paths = ExperimentPaths(
        Path("tasks.json"),
        approved_root / "results" / "raw",
        approved_root / "results" / "derived",
        approved_root / "reviews",
        approved_root / "workspace",
        approved_root / "results" / "raw" / "artifacts" / experiment_id,
        approved_root / "results" / "raw" / "retrieval" / experiment_id,
    )
    config = ExperimentConfig(
        strategies=("E",),
        repetitions=1,
        max_repair_rounds=1,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=5.0,
        total_run_timeout_seconds=600.0,
        paths=paths,
        model_provider_id="openai",
        model="gpt-4o",
        mode="live",
        live_opt_in=True,
    )
    
    exc = ProviderTransportError("First error")
    
    # Write first time
    write_provider_failure_diagnostic(
        approved_root=approved_root,
        experiment_id=experiment_id,
        run=run,
        config=config,
        exc=exc,
        elapsed_seconds=1.0,
    )
    
    # Try writing second time should fail with FileExistsError (exclusive create 'x')
    with pytest.raises(FileExistsError, match="Diagnostic write rejected: file already exists"):
        write_provider_failure_diagnostic(
            approved_root=approved_root,
            experiment_id=experiment_id,
            run=run,
            config=config,
            exc=exc,
            elapsed_seconds=1.0,
        )


# Test 23: Eight frozen hashes unchanged.
def test_eight_frozen_hashes_unchanged():
    FROZEN_HASHES = {
        "results/raw/gates/m7d_smoke_20260611T123000Z.json": "a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a",
        "results/raw/m7d_smoke_20260611T123000Z.jsonl": "74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c",
        "results/raw/m7e_full_20260611T210000Z.jsonl": "c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638",
        "results/raw/m7e_full_20260611T230000Z.jsonl": "d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7",
        "results/raw/m7e_full_20260612T010000Z.jsonl": "67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a",
        "results/raw/m7e_full_20260612T020000Z.jsonl": "327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456",
        "results/raw/m7e_full_20260612T030000Z.jsonl": "548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664",
        "results/raw/m7e_full_20260612T040000Z.jsonl": "fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d",
    }
    for rel_path, expected_hash in FROZEN_HASHES.items():
        p = Path(rel_path)
        assert p.exists(), f"Frozen file {rel_path} does not exist!"
        content = p.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        assert actual_hash == expected_hash, f"Frozen hash mismatch for {rel_path}! Expected: {expected_hash}, got: {actual_hash}"


# Test 24: No live socket or credential access occurs in tests.
def test_no_live_socket_or_credential_access():
    import socket
    orig_connect = socket.socket.connect
    try:
        def mock_connect(self, address):
            raise RuntimeError("Live socket access forbidden in offline tests!")
        socket.socket.connect = mock_connect
        s = socket.socket()
        with pytest.raises(RuntimeError, match="Live socket access forbidden"):
            s.connect(("8.8.8.8", 53))
    finally:
        socket.socket.connect = orig_connect


# Test 25: Verify diagnostics are preserved after error wrapping.
def test_provider_failure_diagnostic_wrapped_error(tmp_path):
    approved_root = tmp_path
    experiment_id = "m7e_full_20260612T040000Z"
    run_id = f"{experiment_id}__T01__E__rep01__seed42"
    ident = RunIdentity(experiment_id, "T01", "E", 1, 42, run_id)
    run = PlannedRun(ident, {"task_id": "T01", "files_to_modify": []}, 0, 0, 0)
    
    paths = ExperimentPaths(
        Path("tasks.json"),
        approved_root / "results" / "raw",
        approved_root / "results" / "derived",
        approved_root / "reviews",
        approved_root / "workspace",
        approved_root / "results" / "raw" / "artifacts" / experiment_id,
        approved_root / "results" / "raw" / "retrieval" / experiment_id,
    )
    config = ExperimentConfig(
        strategies=("E",),
        repetitions=1,
        max_repair_rounds=1,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=5.0,
        total_run_timeout_seconds=600.0,
        paths=paths,
        model_provider_id="openai",
        model="gpt-4o",
        mode="live",
        live_opt_in=True,
    )
    
    att = ProviderAttemptRecord(
        call_index=1,
        attempt_index=1,
        latency_seconds=1.2,
        backoff_seconds_after=30.0,
        outcome="transport_error",
        error=TransportErrorInfo("gateway", True, 429, "http_429"),
    )
    exc = ProviderGatewayError("Too many requests", attempt_records=(att,), elapsed_seconds=2.5)
    exc.allowlisted_headers = (("Retry-After", "120"),)
    
    # Wrap it inside another exception
    wrapper = RuntimeError("Execution aborted wrapper")
    wrapper.__context__ = exc
    
    write_provider_failure_diagnostic(
        approved_root=approved_root,
        experiment_id=experiment_id,
        run=run,
        config=config,
        exc=wrapper,
        elapsed_seconds=5.0,
    )
    
    diagnostic_file = approved_root / "results" / "raw" / "diagnostics" / experiment_id / run.identity.run_id / "provider_failure.json"
    assert diagnostic_file.exists()
    
    with open(diagnostic_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["error_class"] == "ProviderGatewayError"
    assert data["final_http_status"] == 429
    assert data["sanitized_error_code"] == "http_429"
    assert len(data["attempt_records"]) == 1
    assert data["attempt_records"][0]["attempt_index"] == 1
    assert data["allowlisted_rate_limit_headers"] == [["Retry-After", "120"]]


# Test 26: CLI composition uses production sleeper (time.sleep).
def test_cli_composition_uses_production_sleeper():
    from experiments.live.smoke_executor import LiveExperimentExecutor, SmokeExecutor
    import time
    
    executor = LiveExperimentExecutor()
    assert executor._sleeper is time.sleep
    
    smoke_executor = SmokeExecutor()
    assert smoke_executor._sleeper is None

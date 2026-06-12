from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import shutil
import socket
from pathlib import Path

import pytest

from experiments.evaluation.evaluator import Evaluator
from experiments.live.budget import BudgetExceededError, BudgetLimits
from experiments.live.smoke_executor import (
    ProviderAttemptHooks,
    SmokeExecutionRequest,
    SmokeExecutor,
)
from experiments.providers.models import (
    ModelResponse,
    ProviderAttemptRecord,
    ProviderTransportError,
    TransportErrorInfo,
    Usage,
)
from experiments.retrieval.service import RetrievalFacade
from experiments.runner.result_writer import ResultJsonlWriter
from experiments.runner.strategy_factory import StrategyFactory
from experiments.strategies.arag_multi_agent import ARAGMultiAgentStrategySession
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.multi_agent import MultiAgentStrategySession
from experiments.strategies.single_llm import SingleLLMStrategySession


MODEL = "google/gemini-3.5-flash"
EXPERIMENT_ID = "m7d_smoke_20260611T120000Z"
PLAN = json.dumps(
    {
        "files_to_modify": ["student_system/src/grade.py"],
        "implementation_steps": ["implement calculate_pass_rate"],
        "risks": [],
    },
    sort_keys=True,
    separators=(",", ":"),
)
REVIEW = '{"issues":[],"verdict":"pass"}'
SEARCH = '{"action":"retrieve","query":"get_grades_by_course","tool":"keyword_search","top_k":1}'
INITIAL_PATCH = """--- student_system/src/grade.py
+++ student_system/src/grade.py
@@ -11,2 +11,5 @@
 def get_grades_by_course(course_id: str) -> list[dict]:
     return [g.copy() for g in _GRADES if g["course_id"] == course_id]
+
+def calculate_pass_rate(course_id: str) -> float:
+    return 0.0
"""
REPAIR_1 = """--- student_system/src/grade.py
+++ student_system/src/grade.py
@@ -14,2 +14,2 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 0.0
+    return 1.0
"""
REPAIR_2 = """--- student_system/src/grade.py
+++ student_system/src/grade.py
@@ -14,2 +14,8 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 1.0
+    from student_system.src import course
+    course.get_course_by_id(course_id)
+    grades = get_grades_by_course(course_id)
+    if not grades:
+        return 0.0
+    pass_count = sum(1 for g in grades if g["score"] >= 60)
+    return round(pass_count / len(grades), 4)
"""


@pytest.fixture(autouse=True)
def _deterministic_offline_evaluator(monkeypatch):
    def evaluate(
        self,
        task_id,
        initial_patch,
        repair_patches=(),
        max_repair_rounds=2,
        **kwargs,
    ):
        repair_rounds = len(repair_patches)
        passed = repair_rounds >= 2
        return {
            "pass1_public": False,
            "pass1_hidden": False,
            "pass1_public_tests_passed": 0,
            "pass1_hidden_tests_passed": 0,
            "final_public": passed,
            "final_hidden": passed,
            "public_tests_passed": 1 if passed else 0,
            "public_tests_total": 1,
            "hidden_tests_passed": 1 if passed else 0,
            "hidden_tests_total": 1,
            "repair_rounds": repair_rounds,
            "patch_apply_failures": 0,
            "test_latency_seconds": 0.0,
        }

    monkeypatch.setattr(Evaluator, "evaluate_task", evaluate)


@dataclass
class ProviderTrace:
    providers: list["AttemptScriptedProvider"]
    logical_calls: list[tuple[str, int]]
    transport_attempts: list[tuple[str, int, int]]


class AttemptScriptedProvider:
    def __init__(
        self,
        *,
        strategy: str,
        responses: tuple[str, ...],
        hooks: ProviderAttemptHooks,
        trace: ProviderTrace,
        retry_on_logical_call: int | None = None,
        fail_on_logical_call: int | None = None,
    ) -> None:
        self.strategy = strategy
        self.responses = responses
        self.hooks = hooks
        self.trace = trace
        self.retry_on_logical_call = retry_on_logical_call
        self.fail_on_logical_call = fail_on_logical_call
        self.position = 0
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        logical_call = len(self.requests)
        self.trace.logical_calls.append((self.strategy, logical_call))
        attempts = []
        attempt_count = 2 if self.retry_on_logical_call == logical_call else 1
        for attempt_index in range(1, attempt_count + 1):
            self.hooks.reserve_provider_attempt()
            self.trace.transport_attempts.append((self.strategy, logical_call, attempt_index))
            if attempt_index < attempt_count:
                attempts.append(_attempt(request.call_index, attempt_index, "transport_error"))
                continue
            if self.fail_on_logical_call == logical_call:
                attempts.append(_attempt(request.call_index, attempt_index, "transport_error"))
                raise ProviderTransportError(
                    "offline scripted transport failure",
                    attempt_records=tuple(attempts),
                    elapsed_seconds=0.0,
                )
            response_text = self.responses[self.position]
            self.position += 1
            attempts.append(_attempt(request.call_index, attempt_index, "response"))
            return ModelResponse(
                text=response_text,
                finish_reason="stop",
                usage=Usage(10, 4, 14, "provider_normalized"),
                provider_request_id=f"offline-{self.strategy}-{logical_call}",
                model=MODEL,
                latency_seconds=0.0,
                retry_count=attempt_count - 1,
                seed_applied=True,
                sanitized_metadata=(
                    ("normalization_rule", "raw_plus_reasoning"),
                    ("normalized_output_tokens", "4"),
                    ("raw_completion_tokens", "1"),
                    ("reasoning_tokens", "3"),
                    ("usage_source", "provider_normalized"),
                ),
                attempt_records=tuple(attempts),
            )


def _attempt(call_index: int, attempt_index: int, outcome: str) -> ProviderAttemptRecord:
    return ProviderAttemptRecord(
        call_index,
        attempt_index,
        0.0,
        0.0,
        outcome,
        None
        if outcome == "response"
        else TransportErrorInfo("connection", True, None, "offline-retry"),
    )


def _responses(strategy: str) -> tuple[str, ...]:
    if strategy == "A":
        return (INITIAL_PATCH, REPAIR_1, REPAIR_2)
    if strategy == "C":
        return (PLAN, INITIAL_PATCH, REVIEW, REPAIR_1, REPAIR_2)
    return (
        SEARCH,
        SEARCH,
        PLAN,
        SEARCH,
        SEARCH,
        INITIAL_PATCH,
        SEARCH,
        REVIEW,
        SEARCH,
        SEARCH,
        REPAIR_1,
        SEARCH,
        SEARCH,
        REPAIR_2,
    )


def _copy_fixture_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    repo = tmp_path / "repo"
    for directory in ("configs", "contracts", "student_system"):
        shutil.copytree(source / directory, repo / directory)
    (repo / "experiments").mkdir(parents=True)
    shutil.copy2(source / "experiments" / "tasks.json", repo / "experiments" / "tasks.json")
    return repo


def _limits(**overrides) -> BudgetLimits:
    values = {
        "max_total_input_tokens": 120000,
        "max_total_output_tokens": 48000,
        "max_total_calls": 22,
        "max_infra_failures": 2,
        "max_consecutive_infra_failures": 2,
        "max_gateway_failures": 2,
        "max_wall_clock_seconds": 1800.0,
    }
    values.update(overrides)
    return BudgetLimits(**values)


def _request(
    tmp_path: Path,
    *,
    limits: BudgetLimits | None = None,
    retry_strategy: str | None = None,
    retry_call: int | None = None,
    fail_strategy: str | None = None,
    fail_call: int | None = None,
):
    repo = _copy_fixture_repo(tmp_path)
    trace = ProviderTrace([], [], [])

    def provider_factory(run, hooks):
        provider = AttemptScriptedProvider(
            strategy=run.identity.strategy,
            responses=_responses(run.identity.strategy),
            hooks=hooks,
            trace=trace,
            retry_on_logical_call=retry_call if run.identity.strategy == retry_strategy else None,
            fail_on_logical_call=fail_call if run.identity.strategy == fail_strategy else None,
        )
        trace.providers.append(provider)
        return provider

    raw_root = repo / "results" / "raw"
    return (
        SmokeExecutionRequest(
            experiment_id=EXPERIMENT_ID,
            repo_root=repo,
            raw_jsonl_path=raw_root / f"{EXPERIMENT_ID}.jsonl",
            artifact_root=raw_root / "artifacts" / EXPERIMENT_ID,
            retrieval_log_root=raw_root / "retrieval" / EXPERIMENT_ID,
            smoke_report_path=raw_root / "gates" / f"{EXPERIMENT_ID}.json",
            budget_limits=limits or _limits(),
            provider_factory=provider_factory,
        ),
        trace,
    )


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_executor_exercises_production_pipeline_for_a_c_e(tmp_path, monkeypatch):
    request, trace = _request(tmp_path)
    evidence = {
        "factory": [],
        "evaluator": [],
        "stores": 0,
        "retrieval_sessions": [],
        "manifests": [],
        "results": [],
        "result_builder": [],
        "finalized_manifests": {},
    }
    original_create = StrategyFactory.create
    original_evaluate = Evaluator.evaluate_task
    original_build_store = RetrievalFacade.build_store
    original_create_session = RetrievalFacade.create_session
    original_finalize = ArtifactBundleWriter.finalize
    original_append = ResultJsonlWriter.append
    import experiments.runner.orchestrator as orchestrator_module
    original_build_result = orchestrator_module.build_result_record

    def spy_create(self, *, run, config, repo_root):
        bundle = original_create(self, run=run, config=config, repo_root=repo_root)
        evidence["factory"].append((run.identity.strategy, type(bundle.session)))
        return bundle

    def spy_evaluate(self, task_id, initial_patch, repair_patches=(), max_repair_rounds=2, **kwargs):
        result = original_evaluate(
            self,
            task_id,
            initial_patch,
            repair_patches,
            max_repair_rounds,
            **kwargs,
        )
        evidence["evaluator"].append(
            (kwargs["strategy"], len(repair_patches), result["final_public"], result["final_hidden"])
        )
        return result

    def spy_build_store(self, **kwargs):
        evidence["stores"] += 1
        return original_build_store(self, **kwargs)

    def spy_create_session(self, **kwargs):
        evidence["retrieval_sessions"].append(kwargs["agent_role"])
        return original_create_session(self, **kwargs)

    def spy_finalize(self, metrics):
        result = original_finalize(self, metrics)
        evidence["manifests"].append((self.strategy, self.run_id))
        manifest_path = self.run_root / "manifest.json"
        evidence["finalized_manifests"][self.run_id] = (
            result.manifest_sha256,
            manifest_path.read_bytes(),
        )
        return result

    def spy_append(self, record):
        evidence["results"].append(record["strategy"])
        return original_append(self, record)

    def spy_build_result_record(**kwargs):
        record = original_build_result(**kwargs)
        evidence["result_builder"].append(record["strategy"])
        return record

    monkeypatch.setattr(StrategyFactory, "create", spy_create)
    monkeypatch.setattr(Evaluator, "evaluate_task", spy_evaluate)
    monkeypatch.setattr(RetrievalFacade, "build_store", spy_build_store)
    monkeypatch.setattr(RetrievalFacade, "create_session", spy_create_session)
    monkeypatch.setattr(ArtifactBundleWriter, "finalize", spy_finalize)
    monkeypatch.setattr(ResultJsonlWriter, "append", spy_append)
    monkeypatch.setattr(orchestrator_module, "build_result_record", spy_build_result_record)

    result = SmokeExecutor(sleeper=lambda s: None).execute(request)

    assert result.quarantined is False
    assert evidence["factory"] == [
        ("A", SingleLLMStrategySession),
        ("C", MultiAgentStrategySession),
        ("E", ARAGMultiAgentStrategySession),
    ]
    assert [(strategy, round_count) for strategy, round_count, _, _ in evidence["evaluator"]] == [
        ("A", 0),
        ("A", 1),
        ("A", 2),
        ("C", 0),
        ("C", 1),
        ("C", 2),
        ("E", 0),
        ("E", 1),
        ("E", 2),
    ]
    assert all(final_public and final_hidden for _, round_count, final_public, final_hidden in evidence["evaluator"] if round_count == 2)
    assert evidence["stores"] == 1
    assert evidence["retrieval_sessions"] == ["Planner", "Coder", "Reviewer"]
    assert evidence["manifests"] == [
        ("A", result.completed_run_ids[0]),
        ("C", result.completed_run_ids[1]),
        ("E", result.completed_run_ids[2]),
    ]
    assert evidence["results"] == ["A", "C", "E"]
    assert evidence["result_builder"] == ["A", "C", "E"]
    assert [len(provider.requests) for provider in trace.providers] == [3, 5, 14]
    assert all(
        "hidden" not in request.user_prompt.casefold()
        for provider in trace.providers
        for request in provider.requests
    )
    assert result.model_call_count == 22
    assert result.provider_attempt_count == 22
    records = _records(request.raw_jsonl_path)
    assert [record["strategy"] for record in records] == ["A", "C", "E"]
    assert all(record["valid_run"] and not record["infra_error"] for record in records)
    assert records[0]["tool_calls"] == records[1]["tool_calls"] == 0
    assert records[2]["tool_calls"] == 5
    assert len(list(request.retrieval_log_root.glob("*.jsonl"))) == 1
    assert len(next(request.retrieval_log_root.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()) == 5
    assert result.report is not None and result.report.automated_gate_passed is True
    for run_id in result.completed_run_ids:
        manifest_path = request.artifact_root / run_id / "manifest.json"
        expected_sha256, finalized_bytes = evidence["finalized_manifests"][run_id]
        current_bytes = manifest_path.read_bytes()
        assert current_bytes == finalized_bytes
        assert hashlib.sha256(current_bytes).hexdigest() == expected_sha256
        manifest = json.loads(current_bytes)
        assert manifest["provider_id"] == "hermes_vertex_gateway"
        for call_record in manifest["call_records"]:
            assert dict(call_record["audit_metadata"]) == {
                "normalization_rule": "raw_plus_reasoning",
                "normalized_output_tokens": "4",
                "raw_completion_tokens": "1",
                "reasoning_tokens": "3",
                "usage_source": "provider_normalized",
            }


def test_failed_provider_attempt_is_reserved_and_aborts_without_invalid_record(tmp_path):
    request, trace = _request(tmp_path, fail_strategy="C", fail_call=1)

    result = SmokeExecutor(sleeper=lambda s: None).execute(request)

    assert result.quarantined is True
    assert result.model_call_count == 4
    assert result.provider_attempt_count == 4
    assert [record["strategy"] for record in _records(request.raw_jsonl_path)] == ["A"]
    assert trace.transport_attempts[-1] == ("C", 1, 1)
    assert not request.smoke_report_path.exists()


def test_retry_attempts_are_each_reserved(tmp_path):
    request, trace = _request(
        tmp_path,
        retry_strategy="A",
        retry_call=1,
        limits=_limits(max_total_calls=23),
    )

    result = SmokeExecutor(sleeper=lambda s: None).execute(request)

    assert result.quarantined is False
    assert result.model_call_count == 22
    assert result.provider_attempt_count == 23
    assert trace.transport_attempts[:2] == [("A", 1, 1), ("A", 1, 2)]


def test_twenty_third_provider_attempt_is_rejected_before_transport(tmp_path):
    request, trace = _request(
        tmp_path,
        retry_strategy="E",
        retry_call=14,
    )

    result = SmokeExecutor(sleeper=lambda s: None).execute(request)

    assert result.quarantined is True
    assert result.model_call_count == 22
    assert result.provider_attempt_count == 22
    assert ("E", 14, 2) not in trace.transport_attempts
    assert [record["strategy"] for record in _records(request.raw_jsonl_path)] == ["A", "C"]
    assert not request.smoke_report_path.exists()


def test_production_pipeline_opens_no_network_or_credentials(tmp_path, monkeypatch):
    request, _ = _request(tmp_path)
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network opened")),
    )
    monkeypatch.setattr(
        "os.getenv",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("credential read")),
    )

    result = SmokeExecutor(sleeper=lambda s: None).execute(request)

    assert result.report is not None and result.report.automated_gate_passed is True


def test_executor_source_has_no_offline_session_or_handwritten_outputs():
    import experiments.live.smoke_executor as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "_OfflineSmokeStrategySession" not in source
    assert "_CALL_SCHEDULE" not in source
    assert "_bind_manifest_provider_id" not in source
    assert "_result_record" not in source
    assert "_write_retrieval_log" not in source
    assert '"manifest_version"' not in source

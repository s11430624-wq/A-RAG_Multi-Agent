from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
from pathlib import Path
import pytest

from experiments.cli import main
from experiments.live.smoke_executor import (
    LiveExecutionRequest,
    LiveExperimentExecutor,
    LiveExecutionAbort,
    _CompletedOnlyWriter,
)
from experiments.live.budget import BudgetLimits, BudgetExceededError
from experiments.runner.scheduler import build_scheduler_plan
from experiments.runner.config import load_experiment_config, ExperimentPaths
from experiments.runner.result_writer import ResultJsonlWriter
from experiments.providers.models import ProviderAttemptRecord, ModelResponse, Usage
from dataclasses import replace


@pytest.fixture(autouse=True)
def _mock_evaluator_always_passes(monkeypatch):
    from experiments.evaluation.evaluator import Evaluator
    def mock_evaluate(
        self,
        task_id,
        initial_patch,
        repair_patches=(),
        max_repair_rounds=2,
        **kwargs,
    ):
        return {
            "pass1_public": True,
            "pass1_hidden": True,
            "pass1_public_tests_passed": 1,
            "pass1_hidden_tests_passed": 1,
            "final_public": True,
            "final_hidden": True,
            "public_tests_passed": 1,
            "public_tests_total": 1,
            "hidden_tests_passed": 1,
            "hidden_tests_total": 1,
            "repair_rounds": len(repair_patches),
            "patch_apply_failures": 0,
            "test_latency_seconds": 0.0,
        }
    monkeypatch.setattr(Evaluator, "evaluate_task", mock_evaluate)


def _copy_real_frozen_files(dest_repo: Path) -> tuple[Path, str]:
    real_root = Path(__file__).resolve().parents[2]
    
    # Copy configs and contracts and tasks
    shutil.copytree(real_root / "configs", dest_repo / "configs")
    shutil.copytree(real_root / "contracts", dest_repo / "contracts")
    shutil.copytree(real_root / "student_system", dest_repo / "student_system")
    (dest_repo / "experiments").mkdir(parents=True)
    shutil.copy(real_root / "experiments" / "tasks.json", dest_repo / "experiments" / "tasks.json")
    
    # Create raw/gates/artifacts/retrieval directories
    raw_dir = dest_repo / "results" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "gates").mkdir()
    
    smoke_id = "m7d_smoke_20260611T123000Z"
    
    # Copy raw jsonl
    shutil.copy(
        real_root / "results" / "raw" / f"{smoke_id}.jsonl",
        raw_dir / f"{smoke_id}.jsonl"
    )
    
    # Copy report
    report_file = real_root / "results" / "raw" / "gates" / f"{smoke_id}.json"
    shutil.copy(report_file, raw_dir / "gates" / f"{smoke_id}.json")
    
    # Copy artifacts
    shutil.copytree(
        real_root / "results" / "raw" / "artifacts" / smoke_id,
        raw_dir / "artifacts" / smoke_id
    )
    
    # Copy retrieval logs
    shutil.copytree(
        real_root / "results" / "raw" / "retrieval" / smoke_id,
        raw_dir / "retrieval" / smoke_id
    )
    
    report_bytes = report_file.read_bytes()
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    
    return dest_repo, report_sha


def _valid_cli_args(repo: Path, report_sha: str) -> list[str]:
    smoke_id = "m7d_smoke_20260611T123000Z"
    full_id = "m7e_full_20260611T180000Z"
    return [
        "live-run",
        "--repo-root",
        str(repo),
        "--approved-smoke-report",
        str(repo / "results" / "raw" / "gates" / f"{smoke_id}.json"),
        "--approved-smoke-sha256",
        report_sha,
        "--full-experiment-id",
        full_id,
        "--human-approval",
        "FULL_RUN",
        "--approved-input-token-budget",
        "1000000",
        "--approved-output-token-budget",
        "500000",
        "--approved-wall-clock-seconds",
        "3600",
        "--allow-unknown-cost",
    ]


@pytest.fixture(autouse=True)
def isolate_cli_sleeper(monkeypatch):
    from experiments.live.smoke_executor import LiveExperimentExecutor
    
    sleep_calls = []
    spy_sleeper = lambda s: sleep_calls.append(s)
    
    original_init = LiveExperimentExecutor.__init__
    def patched_init(self, *args, **kwargs):
        kwargs["sleeper"] = spy_sleeper
        original_init(self, *args, **kwargs)
        
    monkeypatch.setattr(LiveExperimentExecutor, "__init__", patched_init)
    
    class SleeperSpy:
        def __init__(self, orig_init, calls):
            self.original_init = orig_init
            self.calls = calls
            
    return SleeperSpy(original_init, sleep_calls)


def test_full_run_dry_activation_pipeline(tmp_path, monkeypatch, isolate_cli_sleeper):
    # Assert production LiveExperimentExecutor default sleeper is indeed time.sleep
    import time
    prod_executor = LiveExperimentExecutor.__new__(LiveExperimentExecutor)
    isolate_cli_sleeper.original_init(prod_executor)
    assert prod_executor._sleeper is time.sleep

    # 25. Monkeypatch socket to raise if anyone opens a socket
    def block_socket(*args, **kwargs):
        raise AssertionError("Network socket connection attempted!")
    monkeypatch.setattr(socket, "socket", block_socket)

    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    # Record original frozen smoke files to check 26 (unchanged)
    smoke_id = "m7d_smoke_20260611T123000Z"
    original_jsonl = (repo / "results" / "raw" / f"{smoke_id}.jsonl").read_bytes()
    original_report = (repo / "results" / "raw" / "gates" / f"{smoke_id}.json").read_bytes()
    
    args = _valid_cli_args(repo, report_sha)
    
    # Enable dry execution mode
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")
    
    # Execute full run
    exit_code = main(args)
    assert exit_code == 0

    # Verify results
    full_id = "m7e_full_20260611T180000Z"
    jsonl_path = repo / "results" / "raw" / f"{full_id}.jsonl"
    assert jsonl_path.is_file()
    
    # 3. Read written JSONL records
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
                
    # Exactly 45 records (1)
    assert len(records) == 45
    
    # 4. Strategies distribution
    count_A = sum(1 for r in records if r["strategy"] == "A")
    count_C = sum(1 for r in records if r["strategy"] == "C")
    count_E = sum(1 for r in records if r["strategy"] == "E")
    assert count_A == 15
    assert count_C == 15
    assert count_E == 15
    
    # 5. Tasks distribution
    for i in range(1, 6):
        task_id = f"T0{i}"
        count_t = sum(1 for r in records if r["task_id"] == task_id)
        assert count_t == 9
        
    # 6. valid_run=True, 7. infra_error=0
    for r in records:
        assert r["valid_run"] is True
        assert r["infra_error"] is False
        
    # 8. A/C tool_calls = 0, 9. E tool_calls > 0
    for r in records:
        if r["strategy"] in ("A", "C"):
            assert r["tool_calls"] == 0
        elif r["strategy"] == "E":
            assert r["tool_calls"] > 0
            
    # 10. artifact manifests = 45
    artifact_dir = repo / "results" / "raw" / "artifacts" / full_id
    assert artifact_dir.is_dir()
    manifests = list(artifact_dir.glob("*/manifest.json"))
    assert len(manifests) == 45
    
    # 11. retrieval logs only for E runs
    retrieval_dir = repo / "results" / "raw" / "retrieval" / full_id
    assert retrieval_dir.is_dir()
    # E runs should have retrieval logs, let's verify filenames match E runs
    log_files = list(retrieval_dir.glob("*.jsonl"))
    assert len(log_files) == 15  # 15 E runs
    for log_f in log_files:
        assert "_E_" in log_f.name
        
    # 26. Frozen smoke files unchanged after dry full-run test
    assert (repo / "results" / "raw" / f"{smoke_id}.jsonl").read_bytes() == original_jsonl
    assert (repo / "results" / "raw" / "gates" / f"{smoke_id}.json").read_bytes() == original_report

    # Verify spy: offline dry activation does not call real time.sleep but records the calls
    assert isolate_cli_sleeper.calls == [10.0] * 44


def test_pilot15_fake_activation_runs_canonical_first_15(
    tmp_path,
    monkeypatch,
    isolate_cli_sleeper,
):
    def block_socket(*args, **kwargs):
        raise AssertionError("Network socket connection attempted!")

    monkeypatch.setattr(socket, "socket", block_socket)
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--pilot-run-count", "15"]

    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")

    assert main(args) == 0

    full_id = "m7e_full_20260611T180000Z"
    jsonl_path = repo / "results" / "raw" / f"{full_id}.jsonl"
    records = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [
        (record["task_id"], record["strategy"], record["repetition"])
        for record in records
    ] == [
        ("T01", strategy, repetition)
        for strategy in ("A", "C", "E")
        for repetition in (1, 2, 3)
    ] + [
        ("T02", strategy, repetition)
        for strategy in ("A", "C")
        for repetition in (1, 2, 3)
    ]
    assert isolate_cli_sleeper.calls == [10.0] * 14


@pytest.mark.parametrize("pilot_count", ["1", "14", "16", "45"])
def test_pilot_run_count_rejects_any_value_other_than_15(
    tmp_path,
    monkeypatch,
    capsys,
    pilot_count,
):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--pilot-run-count", pilot_count]
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")

    assert main(args) == 2
    assert "--pilot-run-count must be exactly 15" in capsys.readouterr().out


def test_pilot15_rejects_real_provider_execution(tmp_path, monkeypatch, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--pilot-run-count", "15"]
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.delenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", raising=False)

    assert main(args) == 2
    assert "15-run pilot live execution is blocked" in capsys.readouterr().out


def test_pilot15_real_provider_requires_dedicated_one_shot_approval(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--pilot-run-count", "15"]
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.delenv("ARAG_EXECUTE_PILOT15_ONCE", raising=False)
    monkeypatch.delenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", raising=False)

    assert main(args) == 2
    assert "ARAG_EXECUTE_PILOT15_ONCE=1" in capsys.readouterr().out


def test_pilot15_real_provider_approval_builds_exact_15_without_execution(
    tmp_path,
    monkeypatch,
):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--pilot-run-count", "15"]
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.delenv("ARAG_EXECUTE_FULL_RUN_ONCE", raising=False)
    monkeypatch.setenv("ARAG_EXECUTE_PILOT15_ONCE", "1")
    monkeypatch.delenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", raising=False)

    captured = {}

    def fake_execute(self, request):
        captured["request"] = request
        from experiments.live.smoke_executor import LiveExecutionResult

        return LiveExecutionResult(
            completed_run_ids=tuple(run.identity.run_id for run in request.planned_runs),
            attempted_run_count=15,
            written_record_count=15,
            model_call_count=0,
            provider_attempt_count=0,
            total_input_tokens=0,
            total_output_tokens=0,
            quarantined=False,
            abort_reason=None,
            raw_jsonl_path=request.raw_jsonl_path,
            artifact_root=request.artifact_root,
            retrieval_log_root=request.retrieval_log_root,
        )

    monkeypatch.setattr(LiveExperimentExecutor, "execute", fake_execute)

    assert main(args) == 0
    request = captured["request"]
    assert request.mode == "pilot15"
    assert len(request.planned_runs) == 15
    assert [
        (run.identity.task_id, run.identity.strategy, run.identity.repetition)
        for run in request.planned_runs
    ] == [
        ("T01", strategy, repetition)
        for strategy in ("A", "C", "E")
        for repetition in (1, 2, 3)
    ] + [
        ("T02", strategy, repetition)
        for strategy in ("A", "C")
        for repetition in (1, 2, 3)
    ]


def test_completed_only_writer_rejects_unknown_terminal_failure_record(tmp_path):
    schema_path = Path(__file__).resolve().parents[2] / "contracts" / "result.schema.json"
    raw_root = tmp_path / "raw"
    jsonl_path = raw_root / "out.jsonl"
    writer = _CompletedOnlyWriter(
        ResultJsonlWriter(
            approved_raw_root=raw_root,
            jsonl_path=jsonl_path,
            schema_path=schema_path,
        )
    )
    active_exc = RuntimeError("synthetic terminal failure")
    writer.set_active_exception(active_exc)

    record = {
        "run_id": "m7e_full_20260611T180000Z__T01__E__rep01__seed42",
        "task_id": "T01",
        "strategy": "E",
        "repetition": 1,
        "model": "google/gemini-3.5-flash",
        "seed": 42,
        "tool_calls": 0,
        "retrieved_tokens": 0,
        "retrieval_success": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": None,
        "model_latency_seconds": 0.0,
        "infra_error": False,
        "error_type": "unknown",
        "stop_reason": "repair_limit",
        "artifact_path": None,
        "valid_run": True,
        "pass1_public": False,
        "pass1_hidden": False,
        "pass1_public_tests_passed": 0,
        "pass1_hidden_tests_passed": 0,
        "final_public": False,
        "final_hidden": False,
        "public_tests_passed": 0,
        "public_tests_total": 0,
        "hidden_tests_passed": 0,
        "hidden_tests_total": 0,
        "repair_rounds": 0,
        "patch_apply_failures": 0,
        "test_latency_seconds": 0.0,
        "latency_seconds": 0.0,
        "api_correct": None,
        "hallucinated_api": None,
        "requirement_score": None,
        "quality_score": None,
        "manual_review_status": "pending",
    }

    with pytest.raises(LiveExecutionAbort, match="synthetic terminal failure"):
        writer.append(record)

    assert not jsonl_path.exists()




def test_cli_gate_behaviors(tmp_path, monkeypatch, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    
    # 22. CLI without ARAG_EXECUTE_FULL_RUN_ONCE stays code 2 and does not execute
    monkeypatch.delenv("ARAG_EXECUTE_FULL_RUN_ONCE", raising=False)
    exit_code = main(args)
    assert exit_code == 2
    assert "execution requires M7-E.3 approval" in capsys.readouterr().out
    
    # 23. CLI with ARAG_EXECUTE_FULL_RUN_ONCE but without fake provider flag stays code 2
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.delenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", raising=False)
    exit_code = main(args)
    assert exit_code == 2
    assert "full-run live execution is blocked until M7-E.3" in capsys.readouterr().out


def test_output_path_collision_fails_closed(tmp_path, monkeypatch):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")
    
    # 2. Touch output path collision
    full_id = "m7e_full_20260611T180000Z"
    jsonl_path = repo / "results" / "raw" / f"{full_id}.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.touch()
    
    # Fails closed because it already exists
    exit_code = main(args)
    assert exit_code == 2


def test_budget_enforcement_and_block_attempt_331(tmp_path, monkeypatch):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    # Setup LiveExecutionRequest with lower budget to trigger error
    from experiments.providers.fake import ScriptedProvider
    from experiments.providers.models import ProviderAttemptRecord, ModelResponse, Usage
    
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_budget").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_budget").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_budget").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    # We restrict max attempts to 5
    budget_limits = BudgetLimits(
        max_total_input_tokens=1000000,
        max_total_output_tokens=500000,
        max_total_calls=5, # 13, 14, 15: block before 6th attempt (attempt 331 in real run)
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=3600.0,
    )
    
    class FakeProv:
        def __init__(self, run, hooks):
            self.run = run
            self.hooks = hooks
            self.call_index = 0
            
        def generate(self, request):
            self.call_index += 1
            self.hooks.reserve_provider_attempt()
            
            strategy = self.run.identity.strategy
            files_to_modify = self.run.task_record["files_to_modify"]
            target_file = files_to_modify[0]
            
            valid_patch = f"""--- {target_file}
+++ {target_file}
@@ -1,1 +1,2 @@
 # comment
+def f(): pass
"""
            text = ""
            if strategy == "A":
                text = valid_patch
            elif strategy == "C":
                if self.call_index == 1:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 2:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'
            elif strategy == "E":
                if self.call_index == 1:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "criteria", "top_k": 2}'
                elif self.call_index == 2:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 3:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "solution help", "top_k": 1}'
                elif self.call_index == 4:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'
                    
            attempt = ProviderAttemptRecord(self.call_index, 1, 0.0, 0.0, "response", None)
            return ModelResponse(
                text=text,
                finish_reason="stop",
                usage=Usage(100, 50, 150, "provider"),
                provider_request_id="fake",
                model="model",
                latency_seconds=0.0,
                retry_count=0,
                seed_applied=True,
                sanitized_metadata=(),
                attempt_records=(attempt,),
            )
            
    req = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T190000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=repo / "results" / "raw" / "m7e_full_20260611T190000Z.jsonl",
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T190000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T190000Z",
        budget_limits=budget_limits,
        provider_factory=lambda r, h: FakeProv(r, h),
        mode="full",
    )
    
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    result = executor.execute(req)
    
    # 16. Abort preserves completed valid records
    assert result.quarantined is True
    assert "BudgetExceededError" in result.abort_reason
    assert result.written_record_count == 3  # completed 3 runs of Strategy A (1 call each) before Strategy C hits the budget limit
    assert result.raw_jsonl_path.is_file()
    
    # No incomplete/partial record written
    with open(result.raw_jsonl_path, "r") as f:
        lines = [line for line in f if line.strip()]
    assert len(lines) == 3


def test_abort_on_infra_error_and_preserves_completed(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_abort").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_abort").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_abort").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    budget_limits = BudgetLimits(
        max_total_input_tokens=1000000,
        max_total_output_tokens=500000,
        max_total_calls=330,
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=3600.0,
    )
    
    # Fake provider that raises exception on the 3rd run
    class FailingProv:
        def __init__(self, run, hooks):
            self.run = run
            self.hooks = hooks
            self.call_index = 0
            
        def generate(self, request):
            self.call_index += 1
            self.hooks.reserve_provider_attempt()
            if self.run.identity.run_id.endswith("__T01__A__rep03__seed42"):
                # Simulate provider exception
                from experiments.providers.models import ProviderError
                raise ProviderError("Infrastructure failure!")
                
            strategy = self.run.identity.strategy
            files_to_modify = self.run.task_record["files_to_modify"]
            target_file = files_to_modify[0]
            
            valid_patch = f"""--- {target_file}
+++ {target_file}
@@ -1,1 +1,2 @@
 # comment
+def f(): pass
"""
            text = ""
            if strategy == "A":
                text = valid_patch
            elif strategy == "C":
                if self.call_index == 1:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 2:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'
            elif strategy == "E":
                if self.call_index == 1:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "criteria", "top_k": 2}'
                elif self.call_index == 2:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 3:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "solution help", "top_k": 1}'
                elif self.call_index == 4:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'

            attempt = ProviderAttemptRecord(self.call_index, 1, 0.0, 0.0, "response", None)
            return ModelResponse(
                text=text,
                finish_reason="stop",
                usage=Usage(100, 50, 150, "provider"),
                provider_request_id="fake",
                model="model",
                latency_seconds=0.0,
                retry_count=0,
                seed_applied=True,
                sanitized_metadata=(),
                attempt_records=(attempt,),
            )
            
    req = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T200000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=repo / "results" / "raw" / "m7e_full_20260611T200000Z.jsonl",
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T200000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T200000Z",
        budget_limits=budget_limits,
        provider_factory=lambda r, h: FailingProv(r, h),
        mode="full",
    )
    
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    result = executor.execute(req)
    
    # 16. Abort preserves completed valid records (first 2 runs pass)
    assert result.quarantined is True
    assert result.written_record_count == 2
    assert "Infrastructure failure" in result.abort_reason
    assert result.raw_jsonl_path.is_file()


def test_resume_valid_completed_records(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_resume").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_resume").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_resume").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    budget_limits = BudgetLimits(
        max_total_input_tokens=1000000,
        max_total_output_tokens=500000,
        max_total_calls=330,
        max_infra_failures=2,
        max_consecutive_infra_failures=2,
        max_gateway_failures=2,
        max_wall_clock_seconds=3600.0,
    )
    
    class FakeProv:
        def __init__(self, run, hooks):
            self.run = run
            self.hooks = hooks
            self.call_index = 0
            
        def generate(self, request):
            self.call_index += 1
            self.hooks.reserve_provider_attempt()
            
            strategy = self.run.identity.strategy
            files_to_modify = self.run.task_record["files_to_modify"]
            target_file = files_to_modify[0]
            
            valid_patch = f"""--- {target_file}
+++ {target_file}
@@ -1,1 +1,2 @@
 # comment
+def f(): pass
"""
            text = ""
            if strategy == "A":
                text = valid_patch
            elif strategy == "C":
                if self.call_index == 1:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 2:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'
            elif strategy == "E":
                if self.call_index == 1:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "criteria", "top_k": 2}'
                elif self.call_index == 2:
                    text = json.dumps({
                        "implementation_steps": ["step 1"],
                        "risks": ["risk 1"],
                        "files_to_modify": files_to_modify
                    })
                elif self.call_index == 3:
                    text = '{"action": "retrieve", "tool": "keyword_search", "query": "solution help", "top_k": 1}'
                elif self.call_index == 4:
                    text = valid_patch
                else:
                    text = '{"verdict": "pass", "issues": []}'

            attempt = ProviderAttemptRecord(self.call_index, 1, 0.0, 0.0, "response", None)
            return ModelResponse(
                text=text,
                finish_reason="stop",
                usage=Usage(100, 50, 150, "provider"),
                provider_request_id="fake",
                model="model",
                latency_seconds=0.0,
                retry_count=0,
                seed_applied=True,
                sanitized_metadata=(),
                attempt_records=(attempt,),
            )

    # 17. Resume skips completed valid records. Let's first create 2 valid records in JSONL.
    jsonl_path = repo / "results" / "raw" / "m7e_full_20260611T210000Z.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    
    # We will run the executor first with low attempt limit to get 2 records
    limited_limits = replace(budget_limits, max_total_calls=2)
    req_pre = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T210000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=jsonl_path,
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T210000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T210000Z",
        budget_limits=limited_limits,
        provider_factory=lambda r, h: FakeProv(r, h),
        mode="full",
    )
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    res_pre = executor.execute(req_pre)
    assert res_pre.written_record_count == 2
    
    # Now run resume with full limits
    req_res = replace(req_pre, budget_limits=budget_limits)
    res_final = executor.execute(req_res)
    assert res_final.quarantined is False
    assert res_final.written_record_count == 45
    # The attempted count on second pass should be 43 pending runs
    assert res_final.attempted_run_count == 43


def test_resume_fails_closed_on_invalid_jsonl(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    jsonl_path = repo / "results" / "raw" / "m7e_full_20260611T220000Z.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 18. Malformed JSONL
    jsonl_path.write_text("invalid json lines here", encoding="utf-8")
    
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_resume_fail1").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_resume_fail1").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_resume_fail1").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    req = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T220000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=jsonl_path,
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T220000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T220000Z",
        budget_limits=BudgetLimits(1000000, 500000, 330, 2, 2, 2, 3600.0),
        provider_factory=lambda r, h: None,
        mode="full",
    )
    
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    with pytest.raises(ValueError, match="Resume validation failed"):
        executor.execute(req)


def test_resume_fails_closed_on_duplicate_run_id(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    jsonl_path = repo / "results" / "raw" / "m7e_full_20260611T230000Z.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 19. Duplicate run_ids
    record = {
        "run_id": "m7e_full_20260611T230000Z_T01_A_1_42",
        "task_id": "T01",
        "strategy": "A",
        "repetition": 1,
        "model": "google/gemini-3.5-flash",
        "seed": 42,
        "valid_run": True,
        "pass1_public": True,
        "pass1_hidden": True,
        "pass1_public_tests_passed": 1,
        "pass1_hidden_tests_passed": 1,
        "final_public": True,
        "final_hidden": True,
        "public_tests_passed": 1,
        "public_tests_total": 1,
        "hidden_tests_passed": 1,
        "hidden_tests_total": 1,
        "repair_rounds": 0,
        "patch_apply_failures": 0,
        "api_correct": True,
        "hallucinated_api": False,
        "requirement_score": 1.0,
        "quality_score": 1.0,
        "tool_calls": 0,
        "retrieved_tokens": 0,
        "retrieval_success": True,
        "input_tokens": 100,
        "output_tokens": 50,
        "estimated_cost": 0.0,
        "latency_seconds": 1.0,
        "model_latency_seconds": 1.0,
        "test_latency_seconds": 0.0,
        "infra_error": False,
        "error_type": None,
        "stop_reason": "stop",
        "manual_review_status": "pass",
        "artifact_path": "results/raw/artifacts/m7e_full_20260611T230000Z/m7e_full_20260611T230000Z_T01_A_1_42"
    }
    
    # Write duplicate lines
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
        f.write(json.dumps(record) + "\n")
        
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_resume_fail2").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_resume_fail2").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_resume_fail2").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    req = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T230000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=jsonl_path,
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T230000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T230000Z",
        budget_limits=BudgetLimits(1000000, 500000, 330, 2, 2, 2, 3600.0),
        provider_factory=lambda r, h: None,
        mode="full",
    )
    
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    with pytest.raises(ValueError, match="Resume validation failed"):
        executor.execute(req)


def test_base_exception_not_swallowed(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    # 21. BaseException (like KeyboardInterrupt) must not be caught/swallowed
    class InterruptProv:
        def __init__(self, run, hooks):
            pass
        def generate(self, request):
            raise KeyboardInterrupt("Stop immediately!")
            
    base_config = load_experiment_config(
        experiment_path=repo / "configs" / "experiment.yaml",
        models_path=repo / "configs" / "models.yaml",
        repo_root=repo,
        mode="mock_run",
        env={},
    )
    paths = ExperimentPaths(
        tasks_definition=(repo / "experiments" / "tasks.json").resolve(),
        raw_results_dir=(repo / "results" / "raw").resolve(),
        derived_results_dir=(repo / "results" / "derived").resolve(),
        reviews_dir=(repo / "results" / "reviews").resolve(),
        workspace_base_dir=(repo / "workspaces" / "m7e_full_interrupt").resolve(),
        artifact_root=(repo / "results" / "raw" / "artifacts" / "m7e_full_interrupt").resolve(),
        retrieval_log_root=(repo / "results" / "raw" / "retrieval" / "m7e_full_interrupt").resolve(),
    )
    config = replace(base_config, repetitions=3, paths=paths)
    plan = build_scheduler_plan(config=config, repo_root=repo, today="20260611")
    
    req = LiveExecutionRequest(
        experiment_id="m7e_full_20260611T240000Z",
        repo_root=repo,
        planned_runs=plan.runs,
        raw_jsonl_path=repo / "results" / "raw" / "m7e_full_20260611T240000Z.jsonl",
        artifact_root=repo / "results" / "raw" / "artifacts" / "m7e_full_20260611T240000Z",
        retrieval_log_root=repo / "results" / "raw" / "retrieval" / "m7e_full_20260611T240000Z",
        budget_limits=BudgetLimits(1000000, 500000, 330, 2, 2, 2, 3600.0),
        provider_factory=lambda r, h: InterruptProv(r, h),
        mode="full",
    )
    
    executor = LiveExperimentExecutor(sleeper=lambda s: None)
    with pytest.raises(KeyboardInterrupt):
        executor.execute(req)

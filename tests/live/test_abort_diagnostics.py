from __future__ import annotations

import json
from pathlib import Path
import pytest

from experiments.live.diagnostics import AbortDiagnosticWriter, AbortDiagnosticRecord


def test_write_synthetic_failed_response_creates_file(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    
    # Write record
    record = writer.write_raw_response(
        experiment_id="m7e_full_test",
        run_id="m7e_full_test__T01__E__rep01__seed42",
        role="reviewer",
        error_type="StrategyResponseError",
        error_message="Reviewer envelope is invalid",
        raw_response='{"invalid_field": true}'
    )
    
    # Assert return type and values
    assert isinstance(record, AbortDiagnosticRecord)
    assert record.experiment_id == "m7e_full_test"
    assert record.run_id == "m7e_full_test__T01__E__rep01__seed42"
    assert record.role == "reviewer"
    assert record.error_type == "StrategyResponseError"
    assert record.error_message == "Reviewer envelope is invalid"
    assert record.response_sha256 == "f0bc9f13441992a2a39c2d25505789846607d6ea73cad807829058ff210b0ea8"
    assert record.relative_path == "results/raw/diagnostics/m7e_full_test/m7e_full_test__T01__E__rep01__seed42/raw_response.json"
    
    # Check physical file exists and read content
    phys_file = tmp_path / record.relative_path
    assert phys_file.exists()
    
    content = json.loads(phys_file.read_text(encoding="utf-8"))
    assert content["experiment_id"] == "m7e_full_test"
    assert content["run_id"] == "m7e_full_test__T01__E__rep01__seed42"
    assert content["role"] == "reviewer"
    assert content["error_type"] == "StrategyResponseError"
    assert content["error_message"] == "Reviewer envelope is invalid"
    assert content["response_sha256"] == record.response_sha256
    assert content["raw_response"] == '{"invalid_field": true}'
    assert "created_at" in content


def test_exclusive_create_rejects_overwrite(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    
    # First write
    writer.write_raw_response(
        experiment_id="m7e_test",
        run_id="run_1",
        role="reviewer",
        error_type="StrategyResponseError",
        error_message="Error",
        raw_response='{"a": 1}'
    )
    
    # Second write to same target should fail
    with pytest.raises(FileExistsError):
        writer.write_raw_response(
            experiment_id="m7e_test",
            run_id="run_1",
            role="reviewer",
            error_type="StrategyResponseError",
            error_message="Error",
            raw_response='{"a": 2}'
        )


def test_path_traversal_mischief_is_rejected(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    
    # Run ID traversal
    with pytest.raises(ValueError):
        writer.write_raw_response(
            experiment_id="m7e_test",
            run_id="../attacker_run",
            role="reviewer",
            error_type="Error",
            error_message="Error",
            raw_response="{}"
        )
        
    # Experiment ID traversal
    with pytest.raises(ValueError):
        writer.write_raw_response(
            experiment_id="../../attacker_exp",
            run_id="run_1",
            role="reviewer",
            error_type="Error",
            error_message="Error",
            raw_response="{}"
        )


def test_diagnostics_isolation_from_artifacts_and_retrieval(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    record = writer.write_raw_response(
        experiment_id="m7e_test",
        run_id="run_1",
        role="reviewer",
        error_type="Error",
        error_message="Msg",
        raw_response="{}"
    )
    
    # Diagnostic file must NOT reside under results/raw/artifacts or results/raw/retrieval
    p = Path(record.relative_path)
    assert not any(part == "artifacts" for part in p.parts)
    assert not any(part == "retrieval" for part in p.parts)


def test_no_hidden_test_path_or_content_leaked(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    
    # Ensure hidden test paths/content (like gold_standard) are not written into diagnostics.
    # The writer only saves what is explicitly passed as raw_response, so we ensure standard inputs are sanitised.
    record = writer.write_raw_response(
        experiment_id="m7e_test",
        run_id="run_1",
        role="reviewer",
        error_type="Error",
        error_message="Msg",
        raw_response="clean_output"
    )
    phys_file = tmp_path / record.relative_path
    text = phys_file.read_text(encoding="utf-8")
    assert "hidden" not in text
    assert "gold" not in text


def test_reviewer_extra_key_fails_and_exception_carries_response(tmp_path):
    from experiments.providers.fake import FakeProvider
    from experiments.providers.models import ModelParameters, Usage
    from experiments.strategies.artifacts import ArtifactBundleWriter
    from experiments.strategies.models import ModelVisibleTask, StarterFile
    from experiments.strategies.multi_agent import MultiAgentStrategySession
    from experiments.strategies.parsers import StrategyResponseError
    
    PLAN = '{"files_to_modify":["student_system/src/main.py"],"implementation_steps":["change"],"risks":[]}'
    DIFF = "--- a/student_system/src/main.py\n+++ b/student_system/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"
    # Reviewer response with an invalid extra key "thoughts"
    REVIEW_EXTRA_KEY = '{"issues":[],"verdict":"pass","thoughts":"this should be rejected!"}'
    
    task = ModelVisibleTask(
        "T01",
        "change",
        (StarterFile("student_system/src/main.py", "old\n", "a" * 64),),
        ("student_system/src/main.py",),
        ("new",),
        (),
    )
    
    provider = FakeProvider(responses=(PLAN, DIFF, REVIEW_EXTRA_KEY), usage=Usage(1, 1, 2, "provider"))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-c", task_id="T01", strategy="C", model="m", provider_id="provider", seed=42)
    session = MultiAgentStrategySession(
        run_id="run-c",
        task=task,
        provider=provider,
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
    )
    
    with pytest.raises(StrategyResponseError) as exc_info:
        session.generate_initial_patch()
        
    assert exc_info.value.role == "Reviewer"
    assert exc_info.value.raw_response == REVIEW_EXTRA_KEY


def test_blocker_1_no_raw_response_printed_to_stdout_or_stderr(tmp_path, capsys):
    from experiments.providers.fake import FakeProvider
    from experiments.providers.models import ModelParameters, Usage
    from experiments.strategies.artifacts import ArtifactBundleWriter
    from experiments.strategies.models import ModelVisibleTask, StarterFile
    from experiments.strategies.multi_agent import MultiAgentStrategySession
    from experiments.strategies.parsers import StrategyResponseError
    
    PLAN = '{"files_to_modify":["student_system/src/main.py"],"implementation_steps":["change"],"risks":[]}'
    DIFF = "--- a/student_system/src/main.py\n+++ b/student_system/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"
    # Reviewer response with an invalid extra key "thoughts"
    SECRET_KEY_MESSAGE = "SECRET_KEY_123456"
    REVIEW_EXTRA_KEY = f'{{"issues":[],"verdict":"pass","thoughts":"{SECRET_KEY_MESSAGE}"}}'
    
    task = ModelVisibleTask(
        "T01",
        "change",
        (StarterFile("student_system/src/main.py", "old\n", "a" * 64),),
        ("student_system/src/main.py",),
        ("new",),
        (),
    )
    
    provider = FakeProvider(responses=(PLAN, DIFF, REVIEW_EXTRA_KEY), usage=Usage(1, 1, 2, "provider"))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-c", task_id="T01", strategy="C", model="m", provider_id="provider", seed=42)
    session = MultiAgentStrategySession(
        run_id="run-c",
        task=task,
        provider=provider,
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
    )
    
    with pytest.raises(StrategyResponseError):
        session.generate_initial_patch()
        
    captured = capsys.readouterr()
    # Check stdout + stderr do not contain raw response text, "RAW REVIEWER RESPONSE", or "CLASSIFICATION FAILED"
    assert SECRET_KEY_MESSAGE not in captured.out
    assert SECRET_KEY_MESSAGE not in captured.err
    assert "RAW REVIEWER RESPONSE" not in captured.out
    assert "RAW REVIEWER RESPONSE" not in captured.err
    assert "CLASSIFICATION FAILED" not in captured.out
    assert "CLASSIFICATION FAILED" not in captured.err


def test_blocker_2_diagnostics_root_isolation_from_cwd(tmp_path, monkeypatch):
    # Establish a separate directory representing outside CWD
    outside_dir = tmp_path / "outside_cwd"
    outside_dir.mkdir()
    
    repo_root = tmp_path / "my_project_repo"
    repo_root.mkdir()
    
    writer = AbortDiagnosticWriter(repo_root)
    
    # Change current working directory to outside_cwd
    monkeypatch.chdir(outside_dir)
    
    record = writer.write_raw_response(
        experiment_id="m7e_test",
        run_id="run_cwd_test",
        role="reviewer",
        error_type="Error",
        error_message="Msg",
        raw_response="{}"
    )
    
    # Assert physical diagnostic log resides in the specified repo_root, NOT the outside_dir (cwd)
    expected_file = repo_root / "results" / "raw" / "diagnostics" / "m7e_test" / "run_cwd_test" / "raw_response.json"
    assert expected_file.exists()
    assert not (outside_dir / "results").exists()


def test_blocker_3_diagnostics_write_failure_does_not_leak_details(tmp_path, capsys, monkeypatch):
    from experiments.runner.orchestrator import ExperimentOrchestrator
    from experiments.runner.scheduler import PlannedRun, RunIdentity
    from dataclasses import dataclass
    
    @dataclass
    class FakeConfig:
        model: str = "m"
        seed: int = 42
        total_run_timeout_seconds: float = 60.0
        
    config = FakeConfig()
    
    class BrokenWriter:
        def set_active_exception(self, exc):
            pass
        def append(self, record):
            pass
            
    class FakeException(Exception):
        raw_response = "SECRET_RAW_RESPONSE_ABC"
        role = "Reviewer"
        
    class FakeStrategyFactory:
        def create(self, *args, **kwargs):
            raise FakeException("Mock Exception")
            
    orchestrator = ExperimentOrchestrator(
        config=config,
        repo_root=tmp_path,
        evaluator=None,
        strategy_factory=FakeStrategyFactory(),
        writer=BrokenWriter()
    )
    
    import experiments.live.diagnostics
    def broken_write(self, *args, **kwargs):
        raise RuntimeError("Disk Failure: /absolute/path/to/my/private/directory")
        
    monkeypatch.setattr(experiments.live.diagnostics.AbortDiagnosticWriter, "write_raw_response", broken_write)
    
    run_identity = RunIdentity("m7e_test_abort", "T01", "C", 1, 42, "run_cwd_test")
    run = PlannedRun(
        identity=run_identity,
        task_record={"files_to_modify": ["student_system/src/main.py"]},
        task_index=0,
        strategy_index=0,
        repetition_index=0
    )
    
    # Execute run (it catches the exception, attempts to write diagnostics, triggers broken_write, which is caught and ignored)
    orchestrator.execute_run(run)
    
    # Verify no traceback, absolute path, or raw response leaked to stdout/stderr
    captured = capsys.readouterr()
    assert "/absolute/path/to/my/private/directory" not in captured.out
    assert "/absolute/path/to/my/private/directory" not in captured.err
    assert "SECRET_RAW_RESPONSE_ABC" not in captured.out
    assert "SECRET_RAW_RESPONSE_ABC" not in captured.err
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_blocker_4_canonical_and_denylist_checks(tmp_path):
    writer = AbortDiagnosticWriter(tmp_path)
    
    # 1. Canonical bytes deterministic check, no pretty indent
    record = writer.write_raw_response(
        experiment_id="m7e_test",
        run_id="run_1",
        role="reviewer",
        error_type="Error",
        error_message="Msg",
        raw_response='{"a":1}'
    )
    phys_file = tmp_path / record.relative_path
    content_bytes = phys_file.read_bytes()
    content_str = content_bytes.decode("utf-8")
    
    # Must have compact canonical JSON format, no extra spaces/newlines inside, but sorting is deterministic
    assert " " not in content_str
    # 2. File ends with exactly one LF character
    assert content_bytes.endswith(b"}\n")
    assert not content_bytes.endswith(b"}\n\n")
    
    # 3. Reject raw_response containing denylisted path
    with pytest.raises(ValueError, match="Security Blocker"):
        writer.write_raw_response(
            experiment_id="m7e_test",
            run_id="run_reject_1",
            role="reviewer",
            error_type="Error",
            error_message="Msg",
            raw_response="some response with evaluation/hidden_tests/my_test.py inside"
        )
    # Ensure no file is created
    assert not (tmp_path / "results" / "raw" / "diagnostics" / "m7e_test" / "run_reject_1").exists()
        
    # 4. Reject error_message containing denylisted path
    with pytest.raises(ValueError, match="Security Blocker"):
        writer.write_raw_response(
            experiment_id="m7e_test",
            run_id="run_reject_2",
            role="reviewer",
            error_type="Error",
            error_message="Failed on evaluation\\reference_patches/T01.diff",
            raw_response="{}"
        )
    assert not (tmp_path / "results" / "raw" / "diagnostics" / "m7e_test" / "run_reject_2").exists()

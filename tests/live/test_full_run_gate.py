from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path
import pytest

from experiments.cli import main
from experiments.live.smoke_gate import FullRunApproval, FullRunApprovalValidator

@pytest.fixture(autouse=True)
def setup_gateway_env(monkeypatch):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")


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


def _copy_real_frozen_files(dest_repo: Path) -> tuple[Path, str]:
    real_root = Path(__file__).resolve().parents[2]
    
    # Copy configs and contracts and tasks
    shutil.copytree(real_root / "configs", dest_repo / "configs")
    shutil.copytree(real_root / "contracts", dest_repo / "contracts")
    (dest_repo / "experiments").mkdir(exist_ok=True)
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


def test_valid_approval_gate_returns_code_2_and_does_not_execute(tmp_path, monkeypatch, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    monkeypatch.delenv("ARAG_EXECUTE_FULL_RUN_ONCE", raising=False)
    
    # Monkeypatch to ensure no execute / network / strategy is called
    def fail_if_called(*args, **kwargs):
        pytest.fail("Should not execute scheduler, orchestrator or provider!")
        
    monkeypatch.setattr("experiments.runner.orchestrator.ExperimentOrchestrator.execute_run", fail_if_called)
    monkeypatch.setattr("experiments.live.http_transport.AttemptReservingTransport.send", fail_if_called)
    
    args = _valid_cli_args(repo, report_sha)
    
    exit_code = main(args)
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "full-run approval validated, execution requires M7-E.3 approval." in out


def test_missing_full_run_token_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    args[args.index("FULL_RUN")] = "SMOKE_RUN"
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Validation failed: human_approval must be FULL_RUN" in capsys.readouterr().out


def test_missing_allow_unknown_cost_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    args.remove("--allow-unknown-cost")
    
    exit_code = main(args)
    assert exit_code == 2
    assert "allow_unknown_cost must be explicitly True" in capsys.readouterr().out


def test_wrong_smoke_sha_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    args[args.index(report_sha)] = "a" * 64
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Validation failed: Report hash mismatch" in capsys.readouterr().out


def test_tampered_report_copy_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    report_file = repo / "results" / "raw" / "gates" / "m7d_smoke_20260611T123000Z.json"
    
    # Append space to report to tamper it
    report_file.write_bytes(report_file.read_bytes() + b" ")
    
    args = _valid_cli_args(repo, report_sha)
    exit_code = main(args)
    assert exit_code == 2
    assert "Validation failed: Report hash mismatch" in capsys.readouterr().out


def test_tampered_raw_jsonl_copy_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    jsonl_file = repo / "results" / "raw" / "m7d_smoke_20260611T123000Z.jsonl"
    jsonl_file.write_bytes(jsonl_file.read_bytes() + b"\n")
    
    args = _valid_cli_args(repo, report_sha)
    exit_code = main(args)
    assert exit_code == 2
    assert "Validation failed: Source JSONL tampered" in capsys.readouterr().out


def test_tampered_manifest_copy_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    manifest_file = repo / "results" / "raw" / "artifacts" / "m7d_smoke_20260611T123000Z" / "m7d_smoke_20260611T123000Z__T01__A__rep01__seed42" / "manifest.json"
    manifest_file.write_bytes(manifest_file.read_bytes() + b" ")
    
    args = _valid_cli_args(repo, report_sha)
    exit_code = main(args)
    assert exit_code == 2
    assert "Artifact manifest set tampered" in capsys.readouterr().out or "hash mismatch" in capsys.readouterr().out


def test_tampered_retrieval_log_copy_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    log_file = repo / "results" / "raw" / "retrieval" / "m7d_smoke_20260611T123000Z" / "m7d_smoke_20260611T123000Z__T01__E__rep01__seed42.jsonl"
    log_file.write_bytes(log_file.read_bytes() + b" ")
    
    args = _valid_cli_args(repo, report_sha)
    exit_code = main(args)
    assert exit_code == 2
    assert "Retrieval log set tampered" in capsys.readouterr().out or "hash mismatch" in capsys.readouterr().out


def test_id_collision_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    args[args.index("m7e_full_20260611T180000Z")] = "m7d_smoke_20260611T123000Z"
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Smoke and Full experiment IDs must be different" in capsys.readouterr().out


def test_noncanonical_full_experiment_id_fails(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    args[args.index("m7e_full_20260611T180000Z")] = "m7e_full_invalid_id"
    
    exit_code = main(args)
    assert exit_code == 2
    assert "full_experiment_id must match format" in capsys.readouterr().out


@pytest.mark.parametrize(
    "relative_exists_path",
    [
        "results/raw/m7e_full_20260611T180000Z.jsonl",
        "results/raw/artifacts/m7e_full_20260611T180000Z",
        "results/raw/retrieval/m7e_full_20260611T180000Z",
        "results/derived/m7e_full_20260611T180000Z.csv",
        "results/derived/m7e_full_20260611T180000Z_summary.md",
    ]
)
def test_existing_future_output_path_fails(tmp_path, capsys, relative_exists_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    target_path = repo / relative_exists_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if relative_exists_path.endswith("/") or "artifacts" in relative_exists_path or "retrieval" in relative_exists_path:
        target_path.mkdir(exist_ok=True)
    else:
        target_path.touch()
        
    args = _valid_cli_args(repo, report_sha)
    exit_code = main(args)
    assert exit_code == 2
    assert "Preflight check failed: target output path already exists" in capsys.readouterr().out


def test_credential_like_args_fail(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["--api_key=sk-12345"]
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Plaintext credential-like content is forbidden" in capsys.readouterr().out


def test_credential_like_bearer_fail(tmp_path, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + ["Bearer secret_key"]
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Plaintext credential-like content is forbidden" in capsys.readouterr().out


def test_base_exception_not_swallowed(tmp_path, monkeypatch):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    
    def raise_base_exception(*args, **kwargs):
        raise KeyboardInterrupt("Stop immediately!")
        
    monkeypatch.setattr(FullRunApprovalValidator, "validate_approval", raise_base_exception)
    
    args = _valid_cli_args(repo, report_sha)
    with pytest.raises(KeyboardInterrupt):
        main(args)


def test_validator_reread_physical_mismatch(tmp_path):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    report_file = repo / "results" / "raw" / "gates" / "m7d_smoke_20260611T123000Z.json"
    valid_report_bytes = report_file.read_bytes()
    
    tampered_bytes = valid_report_bytes + b" "
    tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
    
    approval = FullRunApproval(
        approved_smoke_report_path=str(report_file),
        smoke_report_sha256=tampered_sha,  # matches tampered_bytes hash
        smoke_experiment_id="m7d_smoke_20260611T123000Z",
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=1000000,
        approved_token_budget_output=500000,
        approved_wall_clock_seconds=3600,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    
    # 1. Calling validator with different report_bytes parameter but untampered physical file must fail ValueError
    with pytest.raises(ValueError, match="Report bytes mismatch"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=tampered_bytes,
            approval=approval,
            repo_root=repo,
        )
        
    # 2. Modify physical file to make it tampered, and test physical hash failure
    report_file.write_bytes(valid_report_bytes + b" ")
    # Reset approval to expect the valid report hash
    approval = FullRunApproval(
        approved_smoke_report_path=str(report_file),
        smoke_report_sha256=report_sha,
        smoke_experiment_id="m7d_smoke_20260611T123000Z",
        full_experiment_id="m7e_full_20260611T180000Z",
        approved_token_budget_input=1000000,
        approved_token_budget_output=500000,
        approved_wall_clock_seconds=3600,
        allow_unknown_cost=True,
        human_approval="FULL_RUN",
    )
    with pytest.raises(ValueError, match="Report hash mismatch"):
        FullRunApprovalValidator.validate_approval(
            report_bytes=None,
            approval=approval,
            repo_root=repo,
        )


@pytest.mark.parametrize(
    "flag, value",
    [
        ("--api-key", "sk-test"),
        ("--credential", "secret"),
        ("--authorization", "Bearer x"),
        ("--api_key", "sk-test"),
        ("--apikey", "sk-test"),
        ("--credentials", "secret"),
        ("--secret", "secret"),
        ("--token", "secret"),
    ]
)
def test_credential_standalone_flags_fail(tmp_path, capsys, flag, value):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha) + [flag, value]
    
    exit_code = main(args)
    assert exit_code == 2
    assert "Plaintext credential-like content is forbidden" in capsys.readouterr().out


def test_traceback_and_path_leakage_on_missing_env_vars(tmp_path, monkeypatch, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    args = _valid_cli_args(repo, report_sha)
    
    # 1. Missing ARAG_RUN_LIVE_GATEWAY
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")
    
    exit_code = main(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Traceback" not in output
    assert "File \"" not in output
    assert str(tmp_path) not in output
    assert "experiments" not in output

    # 2. Missing ARAG_EXECUTE_FULL_RUN_ONCE
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.delenv("ARAG_EXECUTE_FULL_RUN_ONCE", raising=False)
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")
    
    exit_code = main(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Traceback" not in output
    assert "File \"" not in output
    assert str(tmp_path) not in output
    assert "experiments" not in output

    # 3. Missing ARAG_USE_FAKE_FULL_RUN_PROVIDER
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.delenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", raising=False)
    
    exit_code = main(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Traceback" not in output
    assert "File \"" not in output
    assert str(tmp_path) not in output
    assert "experiments" not in output


def test_traceback_and_path_leakage_on_malformed_args(tmp_path, monkeypatch, capsys):
    repo, report_sha = _copy_real_frozen_files(tmp_path / "repo")
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_EXECUTE_FULL_RUN_ONCE", "1")
    monkeypatch.setenv("ARAG_USE_FAKE_FULL_RUN_PROVIDER", "1")
    
    # Malformed approval args
    args = [
        "live-run",
        "--repo-root", str(repo),
        "--approved-smoke-report", "non_existent_file.json",
        "--approved-smoke-sha256", report_sha,
        "--full-experiment-id", "m7e_full_20260611T180000Z",
        "--approved-input-token-budget", "1000000",
        "--approved-output-token-budget", "500000",
        "--approved-wall-clock-seconds", "3600",
        "--allow-unknown-cost",
        "--human-approval", "FULL_RUN",
    ]
    exit_code = main(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "Traceback" not in output
    assert "File \"" not in output
    assert str(tmp_path) not in output


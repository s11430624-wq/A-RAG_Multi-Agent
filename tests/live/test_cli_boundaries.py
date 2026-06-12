from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from experiments.cli import main


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



def _prepare_smoke_repo(repo: Path) -> None:
    source = Path(__file__).resolve().parents[2]
    if not (repo / "configs").exists():
        shutil.copytree(source / "configs", repo / "configs")
    (repo / "experiments").mkdir(parents=True, exist_ok=True)
    tasks = repo / "experiments" / "tasks.json"
    if not tasks.exists():
        shutil.copy2(source / "experiments" / "tasks.json", tasks)


def _smoke_args(tmp_path: Path) -> list[str]:
    _prepare_smoke_repo(tmp_path)
    experiment_id = "m7d_smoke_20260611T120000Z"
    return [
        "live-smoke",
        "--repo-root",
        str(tmp_path),
        "--experiment-id",
        experiment_id,
        "--human-approval",
        "SMOKE_RUN",
        "--raw-jsonl",
        str(tmp_path / "results" / "raw" / f"{experiment_id}.jsonl"),
        "--artifact-root",
        str(tmp_path / "results" / "raw" / "artifacts" / experiment_id),
        "--retrieval-log-root",
        str(tmp_path / "results" / "raw" / "retrieval" / experiment_id),
        "--smoke-report",
        str(tmp_path / "results" / "raw" / "gates" / f"{experiment_id}.json"),
        "--max-provider-calls",
        "22",
        "--max-input-tokens",
        "120000",
        "--max-output-tokens",
        "48000",
        "--max-wall-clock-seconds",
        "1800",
        "--consecutive-infra-failure-threshold",
        "2",
    ]


def test_cli_live_commands_fail_closed(capsys):
    exit_code_probe = main(["live-probe", "--repo-root", "."])
    assert exit_code_probe != 0

    exit_code_smoke = main(["live-smoke", "--repo-root", "."])
    assert exit_code_smoke != 0

    exit_code_audit = main(["smoke-audit", "--repo-root", "."])
    assert exit_code_audit != 0

    exit_code_run = main(["live-run", "--repo-root", "."])
    assert exit_code_run != 0

    exit_code_exp_audit = main(["experiment-audit", "--repo-root", "."])
    assert exit_code_exp_audit != 0


def test_live_smoke_requires_env_and_human_approval(tmp_path, monkeypatch, capsys):
    args = _smoke_args(tmp_path)
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    monkeypatch.delenv("ARAG_ALLOW_SMOKE_RUN", raising=False)

    assert main(args) == 2
    assert "ARAG_RUN_LIVE_GATEWAY=1" in capsys.readouterr().out

    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    assert main(args) == 2
    assert "ARAG_ALLOW_SMOKE_RUN=1" in capsys.readouterr().out

    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    wrong_approval = list(args)
    wrong_approval[wrong_approval.index("SMOKE_RUN")] = "FULL_RUN"
    assert main(wrong_approval) == 2
    assert "--human-approval SMOKE_RUN" in capsys.readouterr().out

    assert main(args) == 2
    assert "live-smoke composition validated, execution requires M7-D.2 approval." in capsys.readouterr().out


def test_live_smoke_rejects_without_smoke_experiment_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = [
        value.replace("m7d_smoke_20260611T120000Z", "exp_20260611_full")
        for value in _smoke_args(tmp_path)
    ]

    assert main(args) == 2
    assert "canonical format" in capsys.readouterr().out


def test_live_smoke_rejects_full_run_flags(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path) + [
        "--approved-smoke-report",
        "report.json",
        "--approved-smoke-sha256",
        "0" * 64,
    ]

    assert main(args) == 2
    assert "full-run-only flags are forbidden" in capsys.readouterr().out


def test_live_smoke_does_not_start_from_env_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")

    assert main(["live-smoke", "--repo-root", str(tmp_path)]) == 2
    assert "--human-approval SMOKE_RUN" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("flag", "replacement"),
    [
        ("--raw-jsonl", "results/raw/full_experiment.jsonl"),
        ("--artifact-root", "results/raw/artifacts/full_experiment"),
        ("--retrieval-log-root", "results/raw/retrieval/full_experiment"),
        ("--smoke-report", "results/raw/gates/full_experiment.json"),
    ],
)
def test_smoke_plan_paths_are_isolated(
    tmp_path,
    monkeypatch,
    capsys,
    flag,
    replacement,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index(flag) + 1] = str(tmp_path / replacement)

    assert main(args) == 2
    assert "smoke-specific" in capsys.readouterr().out


def test_live_smoke_rejects_traversal_experiment_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    malicious_id = "m7d_smoke_../../../../../../escaped"
    args[args.index("--experiment-id") + 1] = malicious_id
    args[args.index("--raw-jsonl") + 1] = str(tmp_path / "results" / "raw" / f"{malicious_id}.jsonl")

    assert main(args) == 2
    assert "canonical format" in capsys.readouterr().out


def test_live_smoke_rejects_slash_in_experiment_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index("--experiment-id") + 1] = "m7d_smoke_20260611/T120000Z"

    assert main(args) == 2
    assert "canonical format" in capsys.readouterr().out


@pytest.mark.parametrize(
    "experiment_id",
    [
        "smoke",
        "m7d_smoke_20260611",
        "M7D_SMOKE_20260611T120000Z",
        "m7d_smoke_20260611T120000Z_extra",
        "m7d_smoke_%2e%2e%2fescaped",
        r"C:\m7d_smoke_20260611T120000Z",
    ],
)
def test_live_smoke_rejects_noncanonical_smoke_id(
    tmp_path,
    monkeypatch,
    capsys,
    experiment_id,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index("--experiment-id") + 1] = experiment_id

    assert main(args) == 2
    assert "canonical format" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("flag", "outside_path"),
    [
        ("--raw-jsonl", "results/m7d_smoke_20260611T120000Z.jsonl"),
        ("--artifact-root", "results/raw/not-artifacts/m7d_smoke_20260611T120000Z"),
        ("--retrieval-log-root", "results/raw/not-retrieval/m7d_smoke_20260611T120000Z"),
        ("--smoke-report", "results/raw/not-gates/m7d_smoke_20260611T120000Z.json"),
    ],
)
def test_live_smoke_paths_must_remain_under_exact_roots(
    tmp_path,
    monkeypatch,
    capsys,
    flag,
    outside_path,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index(flag) + 1] = str(tmp_path / outside_path)

    assert main(args) == 2
    assert "approved root" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--max-provider-calls", "23"),
        ("--max-input-tokens", "120001"),
        ("--max-output-tokens", "48001"),
        ("--max-wall-clock-seconds", "1801"),
        ("--consecutive-infra-failure-threshold", "3"),
    ],
)
def test_live_smoke_rejects_budget_above_approved_limits(
    tmp_path,
    monkeypatch,
    capsys,
    flag,
    value,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index(flag) + 1] = value

    assert main(args) == 2
    assert "exact approved budget" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--max-provider-calls", "21"),
        ("--max-input-tokens", "119999"),
        ("--max-output-tokens", "47999"),
        ("--max-wall-clock-seconds", "1799"),
        ("--consecutive-infra-failure-threshold", "1"),
    ],
)
def test_live_smoke_rejects_budget_below_approved_limits(
    tmp_path,
    monkeypatch,
    capsys,
    flag,
    value,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    args = _smoke_args(tmp_path)
    args[args.index(flag) + 1] = value

    assert main(args) == 2
    assert "exact approved budget" in capsys.readouterr().out


def test_live_smoke_accepts_exact_approved_budget_but_execution_remains_disabled(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")

    assert main(_smoke_args(tmp_path)) == 2
    assert "live-smoke composition validated, execution requires M7-D.2 approval." in capsys.readouterr().out
    assert not (tmp_path / "results").exists()
    assert not (tmp_path / "workspaces").exists()


def test_smoke_provider_call_budget_matches_a_c_e_maximum_schedule(tmp_path):
    maximum_schedule = {"A": 3, "C": 5, "E": 14}
    args = _smoke_args(tmp_path)

    assert sum(maximum_schedule.values()) == 22
    assert args[args.index("--max-provider-calls") + 1] == str(sum(maximum_schedule.values()))


def test_live_smoke_execute_success_with_gate(tmp_path, monkeypatch, capsys):
    from experiments.live.smoke_executor import SmokeExecutionResult
    from experiments.live.smoke_gate import SmokeGateReport

    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    monkeypatch.setenv("ARAG_EXECUTE_LIVE_SMOKE_ONCE", "1")

    called = []

    # Mock SmokeGateReport
    class FakeReport:
        automated_gate_passed = True

    def mock_execute(self, request):
        called.append(request)
        request.smoke_report_path.parent.mkdir(parents=True, exist_ok=True)
        request.smoke_report_path.write_bytes(b"{}")
        return SmokeExecutionResult(
            completed_run_ids=("m7d_smoke_20260611T120000Z_T01_A",),
            model_call_count=1,
            provider_attempt_count=1,
            total_input_tokens=100,
            total_output_tokens=50,
            quarantined=False,
            abort_reason=None,
            report=FakeReport(),
            leakage_evidence=None,
            resume_evidence=None,
        )

    from experiments.live.smoke_executor import SmokeExecutor
    monkeypatch.setattr(SmokeExecutor, "execute", mock_execute)

    args = _smoke_args(tmp_path)
    exit_code = main(args)

    assert exit_code == 0
    assert len(called) == 1
    out_err = capsys.readouterr()
    assert "smoke-run completed successfully." in out_err.out
    assert "report_path:" in out_err.out
    assert "report_sha256:" in out_err.out


def test_live_smoke_execute_failed_quarantined(tmp_path, monkeypatch, capsys):
    from experiments.live.smoke_executor import SmokeExecutionResult

    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    monkeypatch.setenv("ARAG_EXECUTE_LIVE_SMOKE_ONCE", "1")

    def mock_execute_fail(self, request):
        return SmokeExecutionResult(
            completed_run_ids=(),
            model_call_count=0,
            provider_attempt_count=0,
            total_input_tokens=0,
            total_output_tokens=0,
            quarantined=True,
            abort_reason="something went horribly wrong",
            report=None,
            leakage_evidence=None,
            resume_evidence=None,
        )

    from experiments.live.smoke_executor import SmokeExecutor
    monkeypatch.setattr(SmokeExecutor, "execute", mock_execute_fail)

    args = _smoke_args(tmp_path)
    exit_code = main(args)

    assert exit_code != 0
    out_err = capsys.readouterr()
    assert "smoke execution failed or quarantined" in out_err.out
    assert "something went horribly wrong" in out_err.out


def test_live_smoke_preflight_paths_existence_rejection(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ARAG_RUN_LIVE_GATEWAY", "1")
    monkeypatch.setenv("ARAG_ALLOW_SMOKE_RUN", "1")
    monkeypatch.setenv("ARAG_EXECUTE_LIVE_SMOKE_ONCE", "1")

    args = _smoke_args(tmp_path)
    # create the raw JSONL file to trigger exists() check
    jsonl_path = Path(args[args.index("--raw-jsonl") + 1])
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.touch()

    exit_code = main(args)
    assert exit_code == 2
    out_err = capsys.readouterr()
    assert "already exists" in out_err.out


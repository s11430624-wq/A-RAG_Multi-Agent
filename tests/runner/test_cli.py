from __future__ import annotations

import json
from pathlib import Path
import shutil

from jsonschema import Draft202012Validator

from experiments.cli import MockRunSummary, main, run_mock_runs
from experiments.runner.errors import ResultWriteError
from experiments.strategies.artifacts import ArtifactWriteError


def test_cli_dry_run_prints_plan_without_creating_result_jsonl(project_root, capsys):
    before = set((project_root / "results" / "raw").glob("*.jsonl")) if (project_root / "results" / "raw").exists() else set()

    exit_code = main(["dry-run", "--repo-root", str(project_root)])

    after = set((project_root / "results" / "raw").glob("*.jsonl")) if (project_root / "results" / "raw").exists() else set()
    assert exit_code == 0
    assert "45 planned runs" in capsys.readouterr().out
    assert after == before


def test_cli_mock_run_uses_mock_mode_without_credentials(project_root, monkeypatch, capsys):
    calls = []

    def fake_run_mock_runs(*, repo_root, limit):
        calls.append((repo_root, limit))
        return MockRunSummary(
            attempted=2,
            written=2,
            valid_runs=2,
            experimental_failures=1,
            infra_failures=0,
            skipped_existing=0,
            writer_failures=0,
            execution_failures=0,
        )

    monkeypatch.setattr("experiments.cli.run_mock_runs", fake_run_mock_runs)
    monkeypatch.delenv("ARAG_RUN_LIVE_GATEWAY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-read")

    exit_code = main(["mock-run", "--repo-root", str(project_root), "--limit", "1"])

    assert exit_code == 0
    assert calls == [(project_root, 1)]
    output = capsys.readouterr().out
    assert "attempted=2" in output
    assert "written=2" in output
    assert "valid=2" in output
    assert "experimental_failures=1" in output
    assert "infra_failures=0" in output
    assert "execution_failures=0" in output


def test_cli_returns_nonzero_when_writer_fails(project_root, monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.cli.run_mock_runs",
        lambda **kwargs: MockRunSummary(1, 0, 0, 0, 1, 0, 1),
    )

    exit_code = main(["mock-run", "--repo-root", str(project_root), "--limit", "1"])

    assert exit_code != 0
    assert "writer_failures=1" in capsys.readouterr().out


def test_cli_returns_nonzero_for_execution_cleanup_failure(project_root, monkeypatch, capsys):
    monkeypatch.setattr(
        "experiments.cli.run_mock_runs",
        lambda **kwargs: MockRunSummary(1, 0, 0, 0, 1, 0, 0, 1),
    )

    exit_code = main(["mock-run", "--repo-root", str(project_root), "--limit", "1"])

    assert exit_code != 0
    output = capsys.readouterr().out
    assert "execution_failures=1" in output
    assert "writer_failures=0" in output


def test_run_mock_runs_does_not_count_failed_append_as_written(project_root, monkeypatch):
    calls = 0

    def fail_append(self, run):
        nonlocal calls
        calls += 1
        raise ResultWriteError("result_integrity_unknown=True")

    monkeypatch.setattr("experiments.cli.ExperimentOrchestrator.execute_run", fail_append)

    summary = run_mock_runs(repo_root=project_root, limit=1)

    assert calls == 1
    assert summary.attempted == 1
    assert summary.written == 0
    assert summary.writer_failures == 1
    assert summary.infra_failures == 1


def test_run_mock_runs_counts_artifact_close_failure_as_execution_failure(project_root, monkeypatch):
    calls = 0

    def fail_cleanup(self, run):
        nonlocal calls
        calls += 1
        raise ArtifactWriteError("artifact_integrity_unknown=True")

    monkeypatch.setattr("experiments.cli.ExperimentOrchestrator.execute_run", fail_cleanup)

    summary = run_mock_runs(repo_root=project_root, limit=1)

    assert calls == 1
    assert summary.attempted == 1
    assert summary.written == 0
    assert summary.infra_failures == 1
    assert summary.execution_failures == 1
    assert summary.writer_failures == 0
    assert [p for p in (project_root / "results" / "raw").glob("*.jsonl") if not p.name.startswith("m7d_smoke_") and not p.name.startswith("m7e_full_")] == []


def test_real_run_mock_runs_covers_t01_a_c_e_with_valid_artifacts(project_root, tmp_path):
    repo = _copy_mock_repo(project_root, tmp_path / "repo")

    summary = run_mock_runs(repo_root=repo, limit=7)

    assert summary == MockRunSummary(
        attempted=7,
        written=7,
        valid_runs=7,
        experimental_failures=7,
        infra_failures=0,
        skipped_existing=0,
        writer_failures=0,
        execution_failures=0,
    )
    raw_path = next((repo / "results" / "raw").glob("*.jsonl"))
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    schema = json.loads((repo / "contracts" / "result.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    assert len(records) == 7
    assert {record["strategy"] for record in records} == {"A", "C", "E"}
    for record in records:
        assert list(validator.iter_errors(record)) == []
        assert record["valid_run"] is True
        assert record["infra_error"] is False
        assert record["error_type"] == "none"
        assert record["stop_reason"] in {"repair_limit", "public_pass"}
        assert record["artifact_path"] is not None
        assert record["input_tokens"] > 0
        assert record["output_tokens"] > 0
        assert record["latency_seconds"] > 0.0
        assert record["test_latency_seconds"] > 0.0
        assert (repo / "results" / "raw" / "artifacts" / record["artifact_path"] / "manifest.json").exists()


def test_cli_derive_writes_outputs_from_raw_jsonl(tmp_path, valid_result_record, result_schema_path, capsys):
    experiment_id = valid_result_record["run_id"].split("__", 1)[0]
    raw_path = tmp_path / "results" / "raw" / f"{experiment_id}.jsonl"
    derived_root = tmp_path / "results" / "derived"
    csv_path = derived_root / "exp.csv"
    summary_path = derived_root / "exp_summary.md"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    exit_code = main(
        [
            "derive",
            "--raw-jsonl",
            str(raw_path),
            "--csv",
            str(csv_path),
            "--summary",
            str(summary_path),
            "--derived-root",
            str(derived_root),
            "--schema",
            str(result_schema_path),
        ]
    )

    assert exit_code == 0
    assert csv_path.exists()
    assert summary_path.exists()
    assert "derived outputs written" in capsys.readouterr().out


def _copy_mock_repo(project_root: Path, destination: Path) -> Path:
    destination.mkdir()
    for directory in ("configs", "contracts", "student_system", "evaluation"):
        shutil.copytree(project_root / directory, destination / directory)
    (destination / "experiments").mkdir()
    shutil.copy2(project_root / "experiments" / "tasks.json", destination / "experiments" / "tasks.json")
    return destination

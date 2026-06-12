from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.retrieval.models import DenylistedCorpusError, RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade
from experiments.runner.config import load_experiment_config
from experiments.runner.failure import build_result_record, classify_runner_exception
from experiments.runner.orchestrator import merge_evaluator_snapshots
from experiments.runner.scheduler import build_scheduler_plan
from experiments.runner.strategy_factory import StrategyFactory


def test_runner_visible_task_drops_hidden_grading_and_required_evidence():
    project_root, a_planned_run = _planned_run()
    poisoned = dict(a_planned_run.task_record)
    poisoned["required_evidence"] = "SECRET_REQUIRED_EVIDENCE"
    poisoned["grading"] = {"rubric": "SECRET_GRADING_SENTINEL"}
    poisoned["hidden_test_id"] = "SECRET_HIDDEN_TEST_ID"

    visible = StrategyFactory(repo_root=project_root)._create_visible_task(poisoned)

    rendered = repr(visible)
    assert "SECRET_REQUIRED_EVIDENCE" not in rendered
    assert "SECRET_GRADING_SENTINEL" not in rendered
    assert "SECRET_HIDDEN_TEST_ID" not in rendered


@pytest.mark.parametrize("path", ["results/raw/data.jsonl", "results/derived/summary.md"])
def test_results_outputs_remain_retrieval_denied(tmp_path, path):
    content = b"public-but-derived"
    file_path = tmp_path / path
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(content)
    snapshot_path = tmp_path / "student_system" / "SNAPSHOT.json"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "snapshot_id": "synthetic",
                "created_at": "2026-06-11T00:00:00Z",
                "files": [{"path": path, "sha256": hashlib.sha256(content).hexdigest()}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(DenylistedCorpusError):
        RetrievalFacade().build_store(
            spec=RetrievalTaskSpec(task_id="T01", allowed_corpus=(path,)),
            repo_root=tmp_path,
            strategy="E",
        )


def test_failure_result_record_contains_no_private_or_prompt_fields():
    _, a_planned_run = _planned_run()
    record = build_result_record(
        run=a_planned_run,
        merged=merge_evaluator_snapshots(pass1=None, final_or_latest=None),
        projection=None,
        terminal_failure=classify_runner_exception(RuntimeError("terminal failure")),
    )

    serialized = json.dumps(record, sort_keys=True)
    forbidden = [
        "prompt",
        "response",
        "evaluation/hidden_tests",
        "hidden test output",
        "reference_patches",
        "private_audit",
        "SECRET",
    ]
    assert all(token not in serialized for token in forbidden)


def test_previous_raw_results_and_artifacts_are_not_strategy_inputs(monkeypatch):
    project_root, a_planned_run = _planned_run()
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        text = str(self).replace("\\", "/")
        if "/results/raw/" in text or "/results/derived/" in text:
            raise AssertionError(f"runner must not read previous result output as strategy input: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    visible = StrategyFactory(repo_root=project_root)._create_visible_task(a_planned_run.task_record)

    assert visible.task_id == "T01"


def _planned_run():
    project_root = Path(__file__).resolve().parents[2]
    config = load_experiment_config(
        experiment_path=project_root / "configs" / "experiment.yaml",
        models_path=project_root / "configs" / "models.yaml",
        repo_root=project_root,
        mode="mock_run",
        env={},
    )
    plan = build_scheduler_plan(config=config, repo_root=project_root, today="20260611")
    return project_root, next(run for run in plan.runs if run.identity.task_id == "T01" and run.identity.strategy == "A")

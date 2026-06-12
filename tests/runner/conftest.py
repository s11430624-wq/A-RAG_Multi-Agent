from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.runner.config import load_experiment_config
from experiments.runner.scheduler import build_scheduler_plan


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def result_schema_path(project_root: Path) -> Path:
    return project_root / "contracts" / "result.schema.json"


@pytest.fixture
def valid_result_record() -> dict:
    return {
        "run_id": "exp-20260611-GPT5.4-seed42-r3__T01__A__rep01__seed42",
        "task_id": "T01",
        "strategy": "A",
        "repetition": 1,
        "model": "GPT5.4",
        "seed": 42,
        "valid_run": True,
        "pass1_public": True,
        "pass1_hidden": True,
        "pass1_public_tests_passed": 3,
        "pass1_hidden_tests_passed": 2,
        "final_public": True,
        "final_hidden": True,
        "public_tests_passed": 3,
        "public_tests_total": 3,
        "hidden_tests_passed": 2,
        "hidden_tests_total": 2,
        "repair_rounds": 0,
        "patch_apply_failures": 0,
        "api_correct": None,
        "hallucinated_api": None,
        "requirement_score": None,
        "quality_score": None,
        "tool_calls": 0,
        "retrieved_tokens": 0,
        "retrieval_success": None,
        "input_tokens": 10,
        "output_tokens": 5,
        "estimated_cost": None,
        "latency_seconds": 1.0,
        "model_latency_seconds": 0.25,
        "test_latency_seconds": 0.75,
        "infra_error": False,
        "error_type": "none",
        "stop_reason": "public_pass",
        "manual_review_status": "pending",
        "artifact_path": "exp-20260611-GPT5.4-seed42-r3__T01__A__rep01__seed42",
    }


@pytest.fixture
def experiment_config(project_root: Path):
    return load_experiment_config(
        experiment_path=project_root / "configs" / "experiment.yaml",
        models_path=project_root / "configs" / "models.yaml",
        repo_root=project_root,
        mode="mock_run",
        env={},
    )


@pytest.fixture
def scheduler_plan(project_root: Path, experiment_config):
    return build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")


@pytest.fixture
def planned_runs(scheduler_plan):
    return scheduler_plan.runs


@pytest.fixture
def a_planned_run(planned_runs):
    return next(run for run in planned_runs if run.identity.task_id == "T01" and run.identity.strategy == "A")


@pytest.fixture
def c_planned_run(planned_runs):
    return next(run for run in planned_runs if run.identity.task_id == "T01" and run.identity.strategy == "C")


@pytest.fixture
def e_planned_run(planned_runs):
    return next(run for run in planned_runs if run.identity.task_id == "T01" and run.identity.strategy == "E")


@pytest.fixture
def write_jsonl(tmp_path):
    def _write(records: list[dict]) -> Path:
        path = tmp_path / "results" / "raw" / "exp.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
            encoding="utf-8",
        )
        return path

    return _write

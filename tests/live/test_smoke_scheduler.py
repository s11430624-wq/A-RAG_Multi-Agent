from __future__ import annotations

import json
import pytest
from pathlib import Path
from experiments.runner.config import ExperimentConfig, ExperimentPaths
from experiments.live.smoke_scheduler import build_smoke_scheduler_plan

def create_base_paths(tmp_path: Path) -> ExperimentPaths:
    tasks_file = tmp_path / "tasks.json"
    dummy_tasks = [
        {"task_id": "T01", "title": "T01 task"},
        {"task_id": "T02", "title": "T02 task"},
    ]
    tasks_file.write_text(json.dumps(dummy_tasks), encoding="utf-8")
    
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "derived").mkdir(parents=True, exist_ok=True)
    
    return ExperimentPaths(
        tasks_definition=tasks_file,
        raw_results_dir=tmp_path / "raw",
        derived_results_dir=tmp_path / "derived",
        reviews_dir=tmp_path / "reviews",
        workspace_base_dir=tmp_path / "workspaces",
        artifact_root=tmp_path / "raw" / "artifacts",
        retrieval_log_root=tmp_path / "raw" / "retrieval",
    )


def test_smoke_scheduler_generates_exact_three_runs(tmp_path):
    paths = create_base_paths(tmp_path)
    
    config = ExperimentConfig(
        strategies=("A", "C", "E"),
        repetitions=3,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    plan = build_smoke_scheduler_plan(config, repo_root=tmp_path, today="20260611")
    
    assert len(plan.runs) == 3
    assert "-smoke-" in plan.experiment_id
    
    strategies = [run.identity.strategy for run in plan.runs]
    assert strategies == ["A", "C", "E"]


def test_smoke_scheduler_normalizes_order(tmp_path):
    paths = create_base_paths(tmp_path)
    
    config = ExperimentConfig(
        strategies=("E", "C", "A"),
        repetitions=3,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    plan = build_smoke_scheduler_plan(config, repo_root=tmp_path, today="20260611")
    
    strategies = [run.identity.strategy for run in plan.runs]
    assert strategies == ["A", "C", "E"]


def test_smoke_scheduler_rejects_missing_strategy(tmp_path):
    paths = create_base_paths(tmp_path)
    
    config = ExperimentConfig(
        strategies=("A", "C"),
        repetitions=3,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    with pytest.raises(ValueError, match="Smoke scheduler requires exactly strategies"):
        build_smoke_scheduler_plan(config, repo_root=tmp_path, today="20260611")


def test_smoke_scheduler_rejects_duplicate_strategies(tmp_path):
    paths = create_base_paths(tmp_path)
    
    config = ExperimentConfig(
        strategies=("A", "C", "E", "E"),
        repetitions=3,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    with pytest.raises(ValueError, match="no duplicate/extra strategies"):
        build_smoke_scheduler_plan(config, repo_root=tmp_path, today="20260611")


def test_smoke_scheduler_rejects_extra_strategy(tmp_path):
    paths = create_base_paths(tmp_path)
    
    config = ExperimentConfig(
        strategies=("A", "C", "E", "D"),
        repetitions=3,
        max_repair_rounds=2,
        seed=42,
        agent_timeout_seconds=30.0,
        unit_test_timeout_seconds=30.0,
        total_run_timeout_seconds=300.0,
        paths=paths,
        model_provider_id="hermes_vertex_gateway",
        model="google/gemini-3.5-flash",
        mode="live",
        live_opt_in=True,
    )
    
    with pytest.raises(ValueError, match="Smoke scheduler requires exactly strategies"):
        build_smoke_scheduler_plan(config, repo_root=tmp_path, today="20260611")

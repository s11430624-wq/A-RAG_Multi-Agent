from __future__ import annotations

from experiments.runner.scheduler import build_scheduler_plan


def test_scheduler_builds_deterministic_45_run_plan(project_root, experiment_config):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")

    assert len(plan.runs) == 45
    assert plan.runs[0].identity.run_id.endswith("__T01__A__rep01__seed42")
    assert plan.runs[-1].identity.run_id.endswith("__T05__E__rep03__seed42")
    assert [run.identity.run_id for run in plan.runs] == sorted(run.identity.run_id for run in plan.runs)


def test_run_ids_are_windows_safe_and_unique(experiment_config, project_root):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")
    run_ids = [run.identity.run_id for run in plan.runs]

    assert len(run_ids) == len(set(run_ids))
    assert all("/" not in value and "\\" not in value and ":" not in value for value in run_ids)
    assert all(".." not in value.split("__") for value in run_ids)
    assert all(value.startswith(plan.experiment_id + "__") for value in run_ids)


def test_scheduler_derives_exact_output_paths(project_root, experiment_config):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")

    assert plan.raw_jsonl_path == experiment_config.paths.raw_results_dir / f"{plan.experiment_id}.jsonl"
    assert plan.derived_csv_path == experiment_config.paths.derived_results_dir / f"{plan.experiment_id}.csv"
    assert plan.summary_path == experiment_config.paths.derived_results_dir / f"{plan.experiment_id}_summary.md"


def test_scheduler_dry_plan_does_not_create_outputs(project_root, experiment_config):
    plan = build_scheduler_plan(config=experiment_config, repo_root=project_root, today="20260611")

    assert not plan.raw_jsonl_path.exists()
    assert not plan.derived_csv_path.exists()
    assert not plan.summary_path.exists()

from __future__ import annotations

import re
from pathlib import Path
from experiments.runner.config import ExperimentConfig
from experiments.runner.scheduler import PlannedRun, SchedulerPlan, _load_tasks
from experiments.runner.identity import RunIdentity, make_run_id

def build_smoke_scheduler_plan(config: ExperimentConfig, repo_root: Path, today: str) -> SchedulerPlan:
    root = Path(repo_root).resolve()
    tasks = _load_tasks(config.paths.tasks_definition)
    
    t01_task = next((task for task in tasks if task["task_id"] == "T01"), None)
    if t01_task is None:
        raise ValueError("T01 task definition not found")

    # Validate strategies set: must contain exactly {"A", "C", "E"} with no duplicates
    strategies_set = set(config.strategies)
    if strategies_set != {"A", "C", "E"}:
        raise ValueError(f"Smoke scheduler requires exactly strategies {{'A', 'C', 'E'}}, got {config.strategies}")
    if len(config.strategies) != 3:
        raise ValueError(f"Smoke scheduler requires no duplicate/extra strategies, got {config.strategies}")
        
    slug = re.sub(r"[^a-z0-9]+", "-", config.model.casefold()).strip("-")[:48].strip("-")
    experiment_id = f"exp-{today}-smoke-{slug}-seed{config.seed}"
    
    runs: list[PlannedRun] = []
    
    # Fixed output order A, C, E
    ordered_strategies = ["A", "C", "E"]
    
    for strategy_index, strategy in enumerate(ordered_strategies):
        identity = RunIdentity(
            experiment_id=experiment_id,
            task_id="T01",
            strategy=strategy,
            repetition=1,
            seed=config.seed,
            run_id=make_run_id(
                experiment_id=experiment_id,
                task_id="T01",
                strategy=strategy,
                repetition=1,
                seed=config.seed,
            ),
        )
        runs.append(
            PlannedRun(
                identity=identity,
                task_record=dict(t01_task),
                task_index=0,
                strategy_index=strategy_index,
                repetition_index=0,
            )
        )
        
    raw_jsonl = (config.paths.raw_results_dir / f"{experiment_id}.jsonl").resolve()
    derived_csv = (config.paths.derived_results_dir / f"{experiment_id}.csv").resolve()
    summary = (config.paths.derived_results_dir / f"{experiment_id}_summary.md").resolve()
    
    for path, root_path in (
        (raw_jsonl, config.paths.raw_results_dir),
        (derived_csv, config.paths.derived_results_dir),
        (summary, config.paths.derived_results_dir),
    ):
        try:
            path.relative_to(root_path)
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"derived output path escapes approved root: {path}") from exc
            
    return SchedulerPlan(experiment_id, tuple(runs), raw_jsonl, derived_csv, summary)

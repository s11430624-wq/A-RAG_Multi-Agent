from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from experiments.runner.config import ExperimentConfig
from experiments.runner.identity import RunIdentity, make_experiment_id, make_run_id


@dataclass(frozen=True)
class PlannedRun:
    identity: RunIdentity
    task_record: dict
    task_index: int
    strategy_index: int
    repetition_index: int


@dataclass(frozen=True)
class SchedulerPlan:
    experiment_id: str
    runs: tuple[PlannedRun, ...]
    raw_jsonl_path: Path
    derived_csv_path: Path
    summary_path: Path


def build_scheduler_plan(*, config: ExperimentConfig, repo_root: Path, today: str) -> SchedulerPlan:
    root = Path(repo_root).resolve()
    tasks = _load_tasks(config.paths.tasks_definition)
    experiment_id = make_experiment_id(
        today=today,
        model=config.model,
        seed=config.seed,
        repetitions=config.repetitions,
    )
    runs: list[PlannedRun] = []
    for task_index, task in enumerate(tasks):
        task_id = task["task_id"]
        for strategy_index, strategy in enumerate(config.strategies):
            for repetition in range(1, config.repetitions + 1):
                identity = RunIdentity(
                    experiment_id=experiment_id,
                    task_id=task_id,
                    strategy=strategy,
                    repetition=repetition,
                    seed=config.seed,
                    run_id=make_run_id(
                        experiment_id=experiment_id,
                        task_id=task_id,
                        strategy=strategy,
                        repetition=repetition,
                        seed=config.seed,
                    ),
                )
                runs.append(
                    PlannedRun(
                        identity=identity,
                        task_record=dict(task),
                        task_index=task_index,
                        strategy_index=strategy_index,
                        repetition_index=repetition - 1,
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


def _load_tasks(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("tasks must be a list")
    tasks = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("task_id"), str):
            raise ValueError("task record must contain task_id")
        if item["task_id"] in seen:
            raise ValueError("duplicate task_id")
        seen.add(item["task_id"])
        tasks.append(item)
    return sorted(tasks, key=lambda task: task["task_id"])

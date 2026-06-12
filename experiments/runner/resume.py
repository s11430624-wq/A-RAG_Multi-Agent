from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jsonschema import Draft202012Validator

from experiments.runner.errors import ResultValidationError
from experiments.runner.scheduler import PlannedRun


@dataclass(frozen=True)
class CompletedRunIndex:
    run_ids: frozenset[str]


def load_completed_run_index(*, raw_path: Path, schema_path: Path) -> CompletedRunIndex:
    validator = _load_validator(Path(schema_path))
    path = Path(raw_path)
    if not path.exists():
        return CompletedRunIndex(run_ids=frozenset())

    completed: set[str] = set()
    with path.open("rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ResultValidationError(f"malformed result JSONL line {line_number}") from exc
            errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
            if errors:
                raise ResultValidationError(f"invalid result JSONL line {line_number}: {errors[0].message}")
            run_id = record["run_id"]
            if run_id in completed:
                raise ResultValidationError(f"duplicate run_id: {run_id}")
            completed.add(run_id)
    return CompletedRunIndex(run_ids=frozenset(completed))


def filter_pending_runs(runs: Iterable[PlannedRun], completed: CompletedRunIndex) -> tuple[PlannedRun, ...]:
    return tuple(run for run in runs if run.identity.run_id not in completed.run_ids)


def _load_validator(schema_path: Path) -> Draft202012Validator:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class DerivedOutputError(ValueError):
    pass


CSV_COLUMNS = (
    "experiment_id",
    "run_id",
    "task_id",
    "strategy",
    "repetition",
    "model",
    "seed",
    "valid_run",
    "pass1_public",
    "pass1_hidden",
    "final_public",
    "final_hidden",
    "public_tests_passed",
    "public_tests_total",
    "hidden_tests_passed",
    "hidden_tests_total",
    "repair_rounds",
    "tool_calls",
    "retrieved_tokens",
    "retrieval_success",
    "input_tokens",
    "output_tokens",
    "estimated_cost",
    "latency_seconds",
    "model_latency_seconds",
    "test_latency_seconds",
    "infra_error",
    "error_type",
    "stop_reason",
    "artifact_path",
)


def generate_derived_outputs(
    *,
    raw_jsonl_path: Path,
    derived_csv_path: Path,
    summary_path: Path,
    approved_derived_root: Path,
    schema_path: Path,
) -> None:
    derived_root = Path(approved_derived_root).resolve(strict=False)
    csv_path = _resolve_output_path(Path(derived_csv_path), derived_root, ".csv")
    md_path = _resolve_output_path(Path(summary_path), derived_root, ".md")
    raw_path = Path(raw_jsonl_path)
    experiment_id = raw_path.stem
    records = _load_raw_records(raw_path, Path(schema_path), experiment_id=experiment_id)
    records = sorted(records, key=lambda record: record["run_id"])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(csv_path, records)
    _write_summary(md_path, records)


def _resolve_output_path(path: Path, root: Path, suffix: str) -> Path:
    if path.suffix != suffix:
        raise DerivedOutputError(f"derived output must end with {suffix}")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise DerivedOutputError("derived output path escapes approved root") from exc
    return resolved


def _load_raw_records(raw_path: Path, schema_path: Path, *, experiment_id: str) -> list[dict[str, Any]]:
    validator = _load_validator(schema_path)
    records: list[dict[str, Any]] = []
    with raw_path.open("rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DerivedOutputError(f"malformed raw JSONL line {line_number}") from exc
            errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
            if errors:
                raise DerivedOutputError(f"invalid raw JSONL line {line_number}: {errors[0].message}")
            if not record["run_id"].startswith(f"{experiment_id}__"):
                raise DerivedOutputError(
                    f"run_id on line {line_number} does not match raw experiment_id {experiment_id}"
                )
            record = {"experiment_id": experiment_id, **record}
            records.append(record)
    return records


def _load_validator(schema_path: Path) -> Draft202012Validator:
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column) for column in CSV_COLUMNS})


def _write_summary(path: Path, records: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["task_id"], record["strategy"])].append(record)
    lines = [
        "# Experiment Summary",
        "",
        f"- Total runs: {len(records)}",
        "",
        "## By Task And Strategy",
        "",
        "| Task | Strategy | Runs | Valid | Final Public Passes | Final Hidden Passes |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for (task_id, strategy), group in sorted(grouped.items()):
        valid = sum(1 for record in group if record["valid_run"])
        public_passes = sum(1 for record in group if record["final_public"])
        hidden_passes = sum(1 for record in group if record["final_hidden"])
        lines.append(f"| {task_id} | {strategy} | {len(group)} | {valid} | {public_passes} | {hidden_passes} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

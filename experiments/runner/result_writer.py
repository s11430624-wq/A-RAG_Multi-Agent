from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from experiments.runner.errors import ResultValidationError, ResultWriteError


class ResultJsonlWriter:
    """Single-process, single-writer JSONL appender for result records."""

    def __init__(self, *, approved_raw_root: Path, jsonl_path: Path, schema_path: Path) -> None:
        self.approved_raw_root = Path(approved_raw_root).resolve(strict=False)
        self.jsonl_path = self._validate_jsonl_path(Path(jsonl_path))
        self.schema_path = Path(schema_path)
        self._validator = self._load_validator()

    def append(self, record: dict[str, Any]) -> None:
        line = self._serialize_valid_record(record)
        self._reject_duplicate_run_id(record["run_id"])

        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.jsonl_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            original_size = handle.tell()
            try:
                self._write_line_once(handle, line)
                handle.flush()
                os.fsync(handle.fileno())
            except Exception as exc:
                try:
                    self._rollback_to_size(handle, original_size)
                except Exception as rollback_exc:
                    raise ResultWriteError(
                        f"failed to write result and rollback failed; result_integrity_unknown=True: {rollback_exc}"
                    ) from exc
                raise ResultWriteError(f"failed to write result: {exc}") from exc

    def _validate_jsonl_path(self, jsonl_path: Path) -> Path:
        if jsonl_path.suffix != ".jsonl":
            raise ResultValidationError("result path must end with .jsonl")
        resolved = jsonl_path.resolve(strict=False)
        try:
            resolved.relative_to(self.approved_raw_root)
        except ValueError as exc:
            raise ResultValidationError("result path must stay inside approved raw root") from exc
        return resolved

    def _load_validator(self) -> Draft202012Validator:
        with self.schema_path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def _serialize_valid_record(self, record: dict[str, Any]) -> bytes:
        errors = sorted(self._validator.iter_errors(record), key=lambda error: error.path)
        if errors:
            raise ResultValidationError(errors[0].message)
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"

    def _reject_duplicate_run_id(self, run_id: str) -> None:
        if not self.jsonl_path.exists():
            return
        with self.jsonl_path.open("rb") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ResultValidationError(f"malformed existing result JSONL line {line_number}") from exc
                errors = sorted(self._validator.iter_errors(record), key=lambda error: error.path)
                if errors:
                    raise ResultValidationError(f"invalid existing result JSONL line {line_number}: {errors[0].message}")
                if record["run_id"] == run_id:
                    raise ResultValidationError(f"duplicate run_id: {run_id}")

    def _write_line_once(self, handle, line: bytes) -> None:
        written = handle.write(line)
        if written != len(line):
            raise OSError("short result write")

    def _rollback_to_size(self, handle, original_size: int) -> None:
        handle.truncate(original_size)
        handle.flush()
        os.fsync(handle.fileno())

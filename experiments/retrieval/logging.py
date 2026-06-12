from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from experiments.retrieval.models import (
    ChunkReadResult,
    RetrievalInputError,
    RetrievalLogRecord,
    RetrievalLogValidationError,
    RetrievalLogWriteError,
    SearchResult,
)


_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "retrieval-log.schema.json"


class RetrievalLogWriter:
    """Single-process, single-writer JSONL appender for caller-approved roots."""

    def __init__(self, *, approved_log_root: Path, log_file_path: Path) -> None:
        root = Path(approved_log_root).resolve()
        path = Path(log_file_path)
        if path.suffix != ".jsonl":
            raise RetrievalInputError("log_file_path must use .jsonl suffix")
        resolved_path = path.resolve(strict=False)
        try:
            resolved_path.relative_to(root)
        except ValueError as exc:
            raise RetrievalInputError("log_file_path must be inside approved_log_root") from exc
        if _escapes_through_existing_symlink(root, path):
            raise RetrievalInputError("log_file_path must not escape approved_log_root through a symlink or junction")
        self.approved_log_root = root
        self.log_file_path = resolved_path
        self._validator = Draft202012Validator(_load_schema())

    def append(self, record: RetrievalLogRecord | dict[str, Any]) -> None:
        payload = _to_payload(record)
        self._validator.validate(payload)
        try:
            line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        except (TypeError, ValueError) as exc:
            raise RetrievalLogValidationError(f"retrieval log serialization failed: {exc}") from exc

        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            original_size = handle.tell()
            try:
                self._write_line_once(handle, line)
                handle.flush()
                os.fsync(handle.fileno())
            except Exception as write_exc:
                try:
                    self._rollback_to_size(handle, original_size)
                except Exception as rollback_exc:
                    raise RetrievalLogWriteError(
                        f"retrieval log write failed and rollback failed; log_integrity_unknown=True: {rollback_exc}"
                    ) from write_exc
                raise RetrievalLogWriteError(f"retrieval log write failed and was rolled back: {write_exc}") from write_exc

    def _write_line_once(self, handle, line_bytes: bytes) -> None:
        handle.write(line_bytes)

    def _rollback_to_size(self, handle, original_size: int) -> None:
        handle.truncate(original_size)
        handle.flush()
        os.fsync(handle.fileno())


def make_log_record(
    *,
    run_id: str,
    task_id: str,
    strategy: str,
    agent_role: str,
    result: SearchResult | ChunkReadResult,
) -> RetrievalLogRecord:
    if isinstance(result, SearchResult):
        returned_files = result.returned_files
        returned_chunk_ids = result.returned_chunk_ids
        content_hash = result.content_hash
        excerpt = result.excerpt
        token_count = result.token_count
    else:
        returned_files = (result.file_path,)
        returned_chunk_ids = (result.chunk_id,)
        content_hash = result.content_hash
        excerpt = result.excerpt
        token_count = result.token_count
    return RetrievalLogRecord(
        run_id=run_id,
        task_id=task_id,
        strategy=strategy,  # type: ignore[arg-type]
        agent_role=agent_role,  # type: ignore[arg-type]
        tool_name=result.tool_name,
        query=result.query,
        returned_files=returned_files,
        returned_chunk_ids=returned_chunk_ids,
        content_hash=content_hash,
        excerpt=excerpt,
        timestamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        token_count=token_count,
    )


def _load_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def _to_payload(record: RetrievalLogRecord | dict[str, Any]) -> dict[str, Any]:
    if is_dataclass(record):
        payload = asdict(record)
    elif isinstance(record, dict):
        payload = dict(record)
    else:
        raise RetrievalLogValidationError("retrieval log record must be a dict or RetrievalLogRecord")
    for key in ("returned_files", "returned_chunk_ids"):
        if isinstance(payload.get(key), tuple):
            payload[key] = list(payload[key])
    try:
        Draft202012Validator(_load_schema()).validate(payload)
    except ValidationError as exc:
        raise RetrievalLogValidationError(f"retrieval log schema validation failed: {exc.message}") from exc
    return payload


def _escapes_through_existing_symlink(root: Path, path: Path) -> bool:
    current = root
    try:
        relative_parts = path.resolve(strict=False).relative_to(root).parts
    except ValueError:
        return True
    for part in relative_parts[:-1]:
        current = current / part
        if current.exists() and current.resolve(strict=True).is_relative_to(root) is False:
            return True
    return False

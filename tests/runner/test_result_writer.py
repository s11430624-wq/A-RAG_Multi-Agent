from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from experiments.runner.errors import ResultValidationError, ResultWriteError
from experiments.runner.result_writer import ResultJsonlWriter


def test_result_writer_appends_canonical_schema_valid_jsonl(tmp_path, valid_result_record, result_schema_path):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    writer = ResultJsonlWriter(
        approved_raw_root=raw_root,
        jsonl_path=path,
        schema_path=result_schema_path,
    )

    writer.append(valid_result_record)

    line = path.read_bytes()
    assert line.endswith(b"\n")
    assert line == json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    assert json.loads(line) == valid_result_record


def test_result_writer_documents_single_process_single_writer_boundary(tmp_path, result_schema_path):
    writer = ResultJsonlWriter(
        approved_raw_root=tmp_path / "raw",
        jsonl_path=tmp_path / "raw" / "exp.jsonl",
        schema_path=result_schema_path,
    )

    assert "Single-process, single-writer" in type(writer).__doc__


def test_result_writer_validates_before_creating_file(tmp_path, valid_result_record, result_schema_path):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    invalid = dict(valid_result_record)
    invalid["strategy"] = "B"
    writer = ResultJsonlWriter(
        approved_raw_root=raw_root,
        jsonl_path=path,
        schema_path=result_schema_path,
    )

    with pytest.raises(ResultValidationError):
        writer.append(invalid)

    assert not path.exists()


def test_result_writer_fsyncs_after_append(tmp_path, valid_result_record, result_schema_path, monkeypatch):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    writer = ResultJsonlWriter(
        approved_raw_root=raw_root,
        jsonl_path=path,
        schema_path=result_schema_path,
    )
    calls: list[int] = []

    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))

    writer.append(valid_result_record)

    assert len(calls) == 1


def test_result_writer_rejects_duplicate_run_id(tmp_path, valid_result_record, result_schema_path):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    writer = ResultJsonlWriter(
        approved_raw_root=raw_root,
        jsonl_path=path,
        schema_path=result_schema_path,
    )
    writer.append(valid_result_record)

    with pytest.raises(ResultValidationError, match="duplicate run_id"):
        writer.append(valid_result_record)


def test_result_writer_rejects_path_escape_and_sibling_prefix(tmp_path, result_schema_path):
    raw_root = tmp_path / "results" / "raw"

    with pytest.raises(ResultValidationError):
        ResultJsonlWriter(
            approved_raw_root=raw_root,
            jsonl_path=raw_root / ".." / "escape.jsonl",
            schema_path=result_schema_path,
        )

    with pytest.raises(ResultValidationError):
        ResultJsonlWriter(
            approved_raw_root=raw_root,
            jsonl_path=tmp_path / "results" / "raw_sibling" / "exp.jsonl",
            schema_path=result_schema_path,
        )


def test_result_writer_rejects_symlink_escape(tmp_path, result_schema_path):
    raw_root = tmp_path / "results" / "raw"
    raw_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = raw_root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(ResultValidationError):
        ResultJsonlWriter(
            approved_raw_root=raw_root,
            jsonl_path=link / "exp.jsonl",
            schema_path=result_schema_path,
        )


def test_partial_result_write_rolls_back_to_original_bytes(tmp_path, valid_result_record, result_schema_path, monkeypatch):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    raw_root.mkdir(parents=True)
    original = json.dumps({**valid_result_record, "run_id": "exp-20260611-google-gemini-3-5-flash-seed42-r3__T02__A__rep01__seed42"}, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    path.write_bytes(original)
    writer = ResultJsonlWriter(approved_raw_root=raw_root, jsonl_path=path, schema_path=result_schema_path)

    def partial_write(handle, line):
        handle.write(line[:7])
        raise OSError("boom")

    monkeypatch.setattr(writer, "_write_line_once", partial_write)

    with pytest.raises(ResultWriteError):
        writer.append(valid_result_record)

    assert path.read_bytes() == original


def test_rollback_failure_reports_integrity_unknown(tmp_path, valid_result_record, result_schema_path, monkeypatch):
    raw_root = tmp_path / "results" / "raw"
    path = raw_root / "exp.jsonl"
    raw_root.mkdir(parents=True)
    path.write_bytes(b"")
    writer = ResultJsonlWriter(approved_raw_root=raw_root, jsonl_path=path, schema_path=result_schema_path)

    def partial_write(handle, line):
        handle.write(line[:7])
        raise OSError("boom")

    monkeypatch.setattr(writer, "_write_line_once", partial_write)
    monkeypatch.setattr(writer, "_rollback_to_size", lambda handle, size: (_ for _ in ()).throw(OSError("truncate boom")))

    with pytest.raises(ResultWriteError, match="result_integrity_unknown=True"):
        writer.append(valid_result_record)

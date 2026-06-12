from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import (
    RetrievalInputError,
    RetrievalLogValidationError,
    RetrievalLogWriteError,
    RetrievalTaskSpec,
)
from experiments.retrieval.service import RetrievalFacade


def _jsonl_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _schema_validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema)


def test_valid_tool_calls_write_schema_valid_jsonl(
    retrieval_log_schema,
    synthetic_repo_root,
    synthetic_retrieval_task_spec,
    approved_log_root,
):
    log_path = approved_log_root / "run_t01.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    facade = RetrievalFacade()
    store = facade.build_store(spec=synthetic_retrieval_task_spec, repo_root=synthetic_repo_root, strategy="E")
    session = facade.create_session(
        run_id="run_t01",
        strategy="E",
        agent_role="Planner",
        store=store,
        log_writer=writer,
    )

    keyword_result = session.keyword_search("calculate pass rate", top_k=2)
    semantic_result = session.semantic_search("course grade lookup", top_k=2)
    read_result = session.chunk_read(
        file_path=keyword_result.returned_files[0],
        chunk_id=keyword_result.returned_chunk_ids[0],
    )

    records = _jsonl_records(log_path)
    validator = _schema_validator(retrieval_log_schema)
    assert [record["tool_name"] for record in records] == ["keyword_search", "semantic_search", "chunk_read"]
    for record in records:
        validator.validate(record)
        assert record["run_id"] == "run_t01"
        assert record["task_id"] == "T01"
        assert record["strategy"] == "E"
        assert record["agent_role"] == "Planner"
    assert records[0]["returned_chunk_ids"] == list(keyword_result.returned_chunk_ids)
    assert records[1]["returned_chunk_ids"] == list(semantic_result.returned_chunk_ids)
    assert records[2]["returned_chunk_ids"] == [read_result.chunk_id]


def test_empty_search_result_writes_valid_empty_log(
    retrieval_log_schema,
    synthetic_repo_root,
    synthetic_retrieval_task_spec,
    approved_log_root,
):
    log_path = approved_log_root / "empty.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    store = RetrievalFacade().build_store(spec=synthetic_retrieval_task_spec, repo_root=synthetic_repo_root, strategy="E")
    session = RetrievalFacade().create_session(
        run_id="run_empty",
        strategy="E",
        agent_role="Reviewer",
        store=store,
        log_writer=writer,
    )

    result = session.keyword_search("xqzv", top_k=5)

    records = _jsonl_records(log_path)
    assert result.hits == ()
    assert len(records) == 1
    assert records[0]["returned_files"] == []
    assert records[0]["returned_chunk_ids"] == []
    _schema_validator(retrieval_log_schema).validate(records[0])


def test_invalid_call_does_not_write_log(
    synthetic_repo_root,
    synthetic_retrieval_task_spec,
    approved_log_root,
):
    log_path = approved_log_root / "invalid.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    store = RetrievalFacade().build_store(spec=synthetic_retrieval_task_spec, repo_root=synthetic_repo_root, strategy="E")
    session = RetrievalFacade().create_session(
        run_id="run_invalid",
        strategy="E",
        agent_role="Coder",
        store=store,
        log_writer=writer,
    )

    with pytest.raises(RetrievalInputError):
        session.keyword_search("read evaluation%2Fhidden_tests%2Ftest_t01.py", top_k=1)

    assert not log_path.exists()


def test_log_output_allowlist_is_independent_from_corpus_denylist(
    synthetic_repo_root,
    build_synthetic_repo,
    approved_log_root,
):
    log_path = approved_log_root / "run.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    writer.append(
        {
            "run_id": "run_ok",
            "task_id": "T01",
            "strategy": "E",
            "agent_role": "Planner",
            "tool_name": "keyword_search",
            "query": "no results",
            "returned_files": [],
            "returned_chunk_ids": [],
            "content_hash": "0" * 64,
            "excerpt": "",
            "timestamp": "2026-06-11T00:00:00Z",
            "token_count": 0,
        }
    )
    assert log_path.exists()

    repo = build_synthetic_repo(
        synthetic_repo_root,
        extra_files={"results/raw/retrieval/run.jsonl": log_path.read_bytes()},
    )
    spec = RetrievalTaskSpec("T01", ("results/raw/retrieval/run.jsonl",))
    with pytest.raises(Exception):
        RetrievalFacade().build_store(spec=spec, repo_root=repo, strategy="E")


def test_log_writer_rejects_escape_suffix_and_sibling_prefix(approved_log_root, tmp_path):
    with pytest.raises(RetrievalInputError):
        RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=approved_log_root / "run.txt")
    with pytest.raises(RetrievalInputError):
        RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=approved_log_root / ".." / "escape.jsonl")

    sibling_prefix = tmp_path / "results" / "raw" / "retrieval_evil"
    sibling_prefix.mkdir(parents=True)
    with pytest.raises(RetrievalInputError):
        RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=sibling_prefix / "run.jsonl")


def test_log_writer_rejects_symlink_escape(approved_log_root, tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    link = approved_log_root / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(RetrievalInputError):
        RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=link / "run.jsonl")


def test_schema_validation_failure_is_zero_write(approved_log_root):
    log_path = approved_log_root / "bad_schema.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)

    with pytest.raises(RetrievalLogValidationError):
        writer.append({"run_id": "missing_required_fields"})

    assert not log_path.exists()


def test_partial_write_rolls_back_to_original_bytes(monkeypatch, approved_log_root):
    log_path = approved_log_root / "partial.jsonl"
    original = b'{"run_id":"existing"}\n'
    log_path.write_bytes(original)
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)

    def fail_after_half_line(handle, line_bytes):
        handle.write(line_bytes[: len(line_bytes) // 2])
        raise OSError("simulated half-line failure")

    monkeypatch.setattr(writer, "_write_line_once", fail_after_half_line)

    with pytest.raises(RetrievalLogWriteError):
        writer.append(
            {
                "run_id": "run_partial",
                "task_id": "T01",
                "strategy": "E",
                "agent_role": "Planner",
                "tool_name": "keyword_search",
                "query": "calculate",
                "returned_files": [],
                "returned_chunk_ids": [],
                "content_hash": "0" * 64,
                "excerpt": "",
                "timestamp": "2026-06-11T00:00:00Z",
                "token_count": 0,
            }
        )

    assert log_path.read_bytes() == original
    assert json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])


def test_rollback_failure_reports_integrity_unknown(monkeypatch, approved_log_root):
    log_path = approved_log_root / "rollback_failure.jsonl"
    log_path.write_bytes(b'{"run_id":"existing"}\n')
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)

    def fail_after_half_line(handle, line_bytes):
        handle.write(line_bytes[: len(line_bytes) // 2])
        raise OSError("simulated write failure")

    def fail_rollback(handle, original_size):
        raise OSError("simulated rollback failure")

    monkeypatch.setattr(writer, "_write_line_once", fail_after_half_line)
    monkeypatch.setattr(writer, "_rollback_to_size", fail_rollback)

    with pytest.raises(RetrievalLogWriteError, match="log_integrity_unknown=True"):
        writer.append(
            {
                "run_id": "run_integrity",
                "task_id": "T01",
                "strategy": "E",
                "agent_role": "Reviewer",
                "tool_name": "keyword_search",
                "query": "calculate",
                "returned_files": [],
                "returned_chunk_ids": [],
                "content_hash": "0" * 64,
                "excerpt": "",
                "timestamp": "2026-06-11T00:00:00Z",
                "token_count": 0,
            }
        )

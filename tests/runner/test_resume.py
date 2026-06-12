from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.runner.errors import ResultValidationError
from experiments.runner.resume import filter_pending_runs, load_completed_run_index


def test_resume_skips_only_schema_valid_completed_run_ids(
    tmp_path,
    valid_result_record,
    scheduler_plan,
    result_schema_path,
):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    index = load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)
    pending = filter_pending_runs(scheduler_plan.runs, index)

    assert valid_result_record["run_id"] in index.run_ids
    assert valid_result_record["run_id"] not in {run.identity.run_id for run in pending}
    assert len(pending) == len(scheduler_plan.runs) - 1


def test_resume_missing_raw_file_has_empty_completed_index(tmp_path, scheduler_plan, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "missing.jsonl"

    index = load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)
    pending = filter_pending_runs(scheduler_plan.runs, index)

    assert index.run_ids == frozenset()
    assert tuple(pending) == scheduler_plan.runs


def test_resume_fails_closed_on_malformed_existing_line(tmp_path, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text('{"run_id": "broken"\n', encoding="utf-8")

    with pytest.raises(ResultValidationError, match="malformed"):
        load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)


def test_resume_fails_closed_on_schema_invalid_existing_line(tmp_path, valid_result_record, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    invalid = dict(valid_result_record)
    invalid["strategy"] = "B"
    raw_path.write_text(json.dumps(invalid, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    with pytest.raises(ResultValidationError, match="invalid"):
        load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)


def test_resume_rejects_duplicate_completed_run_id(tmp_path, valid_result_record, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    line = json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n"
    raw_path.write_text(line + line, encoding="utf-8")

    with pytest.raises(ResultValidationError, match="duplicate run_id"):
        load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)


def test_resume_never_reads_artifacts_or_retrieval_logs(tmp_path, valid_result_record, result_schema_path, monkeypatch):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "results" / "raw" / "artifacts").mkdir()
    (tmp_path / "results" / "raw" / "artifacts" / "shadow.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "results" / "raw" / "retrieval").mkdir()
    (tmp_path / "results" / "raw" / "retrieval" / "shadow.jsonl").write_text("{}", encoding="utf-8")
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        text = str(self)
        if "artifacts" in text or "retrieval" in text:
            raise AssertionError(f"resume must not read side artifact: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    index = load_completed_run_index(raw_path=raw_path, schema_path=result_schema_path)

    assert index.run_ids == frozenset({valid_result_record["run_id"]})

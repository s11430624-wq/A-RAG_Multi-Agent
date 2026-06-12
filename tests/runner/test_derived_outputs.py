from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from experiments.runner.derived import DerivedOutputError, generate_derived_outputs


def test_derived_outputs_generate_deterministic_csv_and_summary_from_raw_only(
    tmp_path,
    valid_result_record,
    result_schema_path,
    monkeypatch,
):
    experiment_id = valid_result_record["run_id"].split("__", 1)[0]
    raw_path = tmp_path / "results" / "raw" / f"{experiment_id}.jsonl"
    derived_root = tmp_path / "results" / "derived"
    csv_path = derived_root / "exp.csv"
    summary_path = derived_root / "exp_summary.md"
    raw_path.parent.mkdir(parents=True)
    record_b = dict(valid_result_record)
    record_b["run_id"] = valid_result_record["run_id"].replace("__T01__", "__T02__")
    record_b["task_id"] = "T02"
    raw_path.write_text(
        json.dumps(record_b, sort_keys=True, separators=(",", ":")) + "\n"
        + json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (raw_path.parent / "artifacts").mkdir()
    (raw_path.parent / "artifacts" / "must-not-read.txt").write_text("secret", encoding="utf-8")
    original_open = Path.open

    def guarded_open(self, *args, **kwargs):
        if "artifacts" in str(self) or "retrieval" in str(self):
            raise AssertionError(f"derived outputs must not read side artifact: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    generate_derived_outputs(
        raw_jsonl_path=raw_path,
        derived_csv_path=csv_path,
        summary_path=summary_path,
        approved_derived_root=derived_root,
        schema_path=result_schema_path,
    )
    first_hash = hashlib.sha256(csv_path.read_bytes() + summary_path.read_bytes()).hexdigest()
    generate_derived_outputs(
        raw_jsonl_path=raw_path,
        derived_csv_path=csv_path,
        summary_path=summary_path,
        approved_derived_root=derived_root,
        schema_path=result_schema_path,
    )
    second_hash = hashlib.sha256(csv_path.read_bytes() + summary_path.read_bytes()).hexdigest()

    csv_text = csv_path.read_text(encoding="utf-8")
    assert csv_text.splitlines()[0].startswith("experiment_id,run_id,task_id,strategy,repetition,model,seed,valid_run")
    assert csv_text.splitlines()[1].split(",")[0] == experiment_id
    assert csv_text.splitlines()[1].split(",")[2] == "T01"
    assert "## By Task And Strategy" in summary_path.read_text(encoding="utf-8")
    assert first_hash == second_hash


def test_derived_outputs_reject_malformed_raw_jsonl(tmp_path, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    derived_root = tmp_path / "results" / "derived"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text("{broken\n", encoding="utf-8")

    with pytest.raises(DerivedOutputError, match="malformed"):
        generate_derived_outputs(
            raw_jsonl_path=raw_path,
            derived_csv_path=derived_root / "exp.csv",
            summary_path=derived_root / "exp_summary.md",
            approved_derived_root=derived_root,
            schema_path=result_schema_path,
        )


def test_derived_outputs_reject_escape_and_sibling_prefix(tmp_path, valid_result_record, result_schema_path):
    raw_path = tmp_path / "results" / "raw" / "exp.jsonl"
    derived_root = tmp_path / "results" / "derived"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    with pytest.raises(DerivedOutputError):
        generate_derived_outputs(
            raw_jsonl_path=raw_path,
            derived_csv_path=derived_root / ".." / "escape.csv",
            summary_path=derived_root / "exp_summary.md",
            approved_derived_root=derived_root,
            schema_path=result_schema_path,
        )


def test_derived_outputs_reject_run_id_not_matching_raw_experiment_id(
    tmp_path,
    valid_result_record,
    result_schema_path,
):
    raw_path = tmp_path / "results" / "raw" / "expected-experiment.jsonl"
    derived_root = tmp_path / "results" / "derived"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        json.dumps(valid_result_record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DerivedOutputError, match="experiment_id"):
        generate_derived_outputs(
            raw_jsonl_path=raw_path,
            derived_csv_path=derived_root / "exp.csv",
            summary_path=derived_root / "exp_summary.md",
            approved_derived_root=derived_root,
            schema_path=result_schema_path,
        )

    with pytest.raises(DerivedOutputError):
        generate_derived_outputs(
            raw_jsonl_path=raw_path,
            derived_csv_path=derived_root / "exp.csv",
            summary_path=tmp_path / "results" / "derived_sibling" / "exp_summary.md",
            approved_derived_root=derived_root,
            schema_path=result_schema_path,
        )

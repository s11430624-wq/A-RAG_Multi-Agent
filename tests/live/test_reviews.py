from __future__ import annotations

import json
import pytest
import random
import builtins
from pathlib import Path
from experiments.live.reviews import (
    generate_blind_review_package,
    record_review_score,
    evaluate_reviewed_results,
)

def test_blind_reviewer_package_removes_sensitive_metadata(tmp_path):
    raw_jsonl = tmp_path / "raw.jsonl"
    mapping_file = tmp_path / "mapping.jsonl"
    package_file = tmp_path / "reviewer_package.json"
    
    dummy_records = [
        {
            "run_id": "exp-test-r1__T01__A__rep01__seed42",
            "task_id": "T01",
            "strategy": "A",
            "input_tokens": 100,
            "output_tokens": 50,
            "valid_run": True,
            "tool_calls": 0,
            "retrieved_tokens": 0,
            "artifact_path": "results/raw/artifacts/exp-test-r1__T01__A__rep01__seed42",
            "final_submitted_diff": "diff A",
        },
        {
            "run_id": "exp-test-r1__T01__C__rep01__seed42",
            "task_id": "T01",
            "strategy": "C",
            "input_tokens": 150,
            "output_tokens": 80,
            "valid_run": True,
            "tool_calls": 0,
            "retrieved_tokens": 0,
            "artifact_path": "results/raw/artifacts/exp-test-r1__T01__C__rep01__seed42",
            "final_submitted_diff": "diff C",
        },
        {
            "run_id": "exp-test-r1__T01__E__rep01__seed42",
            "task_id": "T01",
            "strategy": "E",
            "input_tokens": 200,
            "output_tokens": 120,
            "valid_run": True,
            "tool_calls": 5,
            "retrieved_tokens": 300,
            "artifact_path": "results/raw/artifacts/exp-test-r1__T01__E__rep01__seed42",
            "final_submitted_diff": "diff E",
        },
    ]
    raw_jsonl.write_text("\n".join(json.dumps(r) for r in dummy_records) + "\n", encoding="utf-8")
    
    rng = random.Random(42)
    generate_blind_review_package(
        raw_jsonl_path=raw_jsonl,
        package_output_path=package_file,
        mapping_output_path=mapping_file,
        rng=rng,
    )
    
    package_data = json.loads(package_file.read_text(encoding="utf-8"))
    assert len(package_data) == 3
    
    for item in package_data:
        assert "blind_id" in item
        assert "task_id" in item
        assert "final_submitted_diff" in item
        for forbidden in ("strategy", "run_id", "artifact_path", "tool_calls", "retrieved_tokens", "input_tokens", "output_tokens"):
            assert forbidden not in item
            
    mapping_data = [json.loads(line) for line in mapping_file.read_text(encoding="utf-8").strip().split("\n")]
    assert len(mapping_data) == 3
    
    original_runs = [r["run_id"] for r in dummy_records]
    mapping_runs = [m["run_id"] for m in mapping_data]
    
    assert len(mapping_runs) == len(original_runs)

    reviews_file = tmp_path / "reviews.jsonl"
    
    record_review_score(
        reviews_path=reviews_file,
        mapping_path=mapping_file,
        blind_id=mapping_data[0]["blind_id"],
        api_correct=True,
        hallucinated_api=False,
        requirement_score=2,
        quality_score=4,
    )
    
    with pytest.raises(ValueError, match="Duplicate review score"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id=mapping_data[0]["blind_id"],
            api_correct=True,
            hallucinated_api=False,
            requirement_score=2,
            quality_score=4,
        )

    with pytest.raises(ValueError, match="requirement_score must be an integer in 0..2"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id=mapping_data[1]["blind_id"],
            api_correct=True,
            hallucinated_api=False,
            requirement_score=5,
            quality_score=4,
        )

    with pytest.raises(ValueError, match="quality_score must be an integer in 1..5"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id=mapping_data[1]["blind_id"],
            api_correct=True,
            hallucinated_api=False,
            requirement_score=2,
            quality_score=6,
        )

    with pytest.raises(ValueError, match="requirement_score must be an integer"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id=mapping_data[1]["blind_id"],
            api_correct=True,
            hallucinated_api=False,
            requirement_score=True,
            quality_score=4,
        )

    with pytest.raises(ValueError, match="Unknown blind ID"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id="unknown_id",
            api_correct=True,
            hallucinated_api=False,
            requirement_score=2,
            quality_score=4,
        )

def test_reviews_rollback_on_write_failure(tmp_path, monkeypatch):
    mapping_file = tmp_path / "mapping.jsonl"
    reviews_file = tmp_path / "reviews.jsonl"
    
    mapping_file.write_text(
        json.dumps({"blind_id": "blind-1", "run_id": "run-1"}) + "\n" +
        json.dumps({"blind_id": "blind-2", "run_id": "run-2"}) + "\n"
    )
    
    record_review_score(
        reviews_path=reviews_file,
        mapping_path=mapping_file,
        blind_id="blind-1",
        api_correct=True,
        hallucinated_api=False,
        requirement_score=1,
        quality_score=3,
    )
    
    original_data = reviews_file.read_bytes()
    
    # Save reference to original builtins.open
    real_open = builtins.open
    
    class FailFile:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def write(self, *args, **kwargs):
            raise IOError("Disk Full")

    # Use original_open internally to prevent recursion error
    def mock_open(path, mode, *args, **kwargs):
        if "reviews.jsonl" in str(path) and "a" in mode:
            return FailFile()
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", mock_open)
    
    with pytest.raises(RuntimeError, match="Failed to record review score, rolled back"):
        record_review_score(
            reviews_path=reviews_file,
            mapping_path=mapping_file,
            blind_id="blind-2",
            api_correct=True,
            hallucinated_api=False,
            requirement_score=2,
            quality_score=4,
        )
        
    assert reviews_file.read_bytes() == original_data


class NoOpRNG(random.Random):
    def shuffle(self, x):
        pass


def test_reviews_rotation_on_no_op_rng(tmp_path):
    raw_jsonl = tmp_path / "raw.jsonl"
    mapping_file = tmp_path / "mapping.jsonl"
    package_file = tmp_path / "reviewer_package.json"
    
    dummy_records = [
        {"run_id": "run-1", "task_id": "T01"},
        {"run_id": "run-2", "task_id": "T01"},
        {"run_id": "run-3", "task_id": "T01"},
    ]
    raw_jsonl.write_text("\n".join(json.dumps(r) for r in dummy_records) + "\n", encoding="utf-8")
    
    rng = NoOpRNG()
    generate_blind_review_package(
        raw_jsonl_path=raw_jsonl,
        package_output_path=package_file,
        mapping_output_path=mapping_file,
        rng=rng,
    )
    
    mapping_data = [json.loads(line) for line in mapping_file.read_text(encoding="utf-8").strip().split("\n")]
    original_runs = ["run-1", "run-2", "run-3"]
    mapping_runs = [m["run_id"] for m in mapping_data]
    
    assert mapping_runs != original_runs


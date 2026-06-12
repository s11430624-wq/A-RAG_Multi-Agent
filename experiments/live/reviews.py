from __future__ import annotations

import os
import json
import uuid
import random
from pathlib import Path
from experiments.live.smoke_gate import check_symlinks_and_escapes

def generate_blind_review_package(
    raw_jsonl_path: Path,
    package_output_path: Path,
    mapping_output_path: Path,
    *,
    rng: random.Random | None = None,
) -> None:
    # Resolve and verify paths
    raw_jsonl_path = Path(raw_jsonl_path)
    package_output_path = Path(package_output_path)
    mapping_output_path = Path(mapping_output_path)

    check_symlinks_and_escapes(raw_jsonl_path, raw_jsonl_path.parent)
    check_symlinks_and_escapes(package_output_path.parent, package_output_path.parent)
    check_symlinks_and_escapes(mapping_output_path.parent, mapping_output_path.parent)

    if rng is None:
        rng = random.Random()

    # 1. Read raw jsonl records
    records = []
    with open(raw_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    package_items = []
    mapping_items = []

    for r in records:
        run_id = r.get("run_id")
        if not run_id:
            continue
            
        # Generate safe random blind_id
        blind_id = f"blind-{uuid.UUID(int=rng.getrandbits(128)).hex}"
        
        # Build reviewer package item removing all forbidden metadata
        item = {
            "blind_id": blind_id,
            "task_id": r.get("task_id"),
            "task_description": r.get("task_description", ""),
            "expected_behavior": r.get("expected_behavior", []),
            "forbidden_behaviors": r.get("forbidden_behaviors", []),
            "starter_context": r.get("starter_context", {}),
            "final_submitted_diff": r.get("final_submitted_diff", ""),
        }
        package_items.append(item)
        mapping_items.append({"blind_id": blind_id, "run_id": run_id})

    # Shuffle reviewer package and mapping independently to completely break positional order correlation
    rng.shuffle(package_items)
    rng.shuffle(mapping_items)

    original_run_ids = [r.get("run_id") for r in records if r.get("run_id")]
    if len(original_run_ids) > 1:
        shuffled_run_ids = [m["run_id"] for m in mapping_items]
        if shuffled_run_ids == original_run_ids:
            mapping_items = mapping_items[1:] + [mapping_items[0]]
        
        # Recalculate blind_to_run mapping after potential mapping rotation
        blind_to_run = {m["blind_id"]: m["run_id"] for m in mapping_items}
        package_run_ids = [blind_to_run[item["blind_id"]] for item in package_items]
        if package_run_ids == original_run_ids:
            package_items = package_items[1:] + [package_items[0]]

    # Exclusive-create write for package
    with open(package_output_path, "x", encoding="utf-8") as f:
        json.dump(package_items, f, indent=2, ensure_ascii=False)

    # Exclusive-create write for mapping
    with open(mapping_output_path, "x", encoding="utf-8") as f:
        for m in mapping_items:
            f.write(json.dumps(m, sort_keys=True) + "\n")


def record_review_score(
    reviews_path: Path,
    mapping_path: Path,
    blind_id: str,
    api_correct: bool,
    hallucinated_api: bool,
    requirement_score: int,
    quality_score: int,
) -> None:
    # Resolve and check safety
    reviews_path = Path(reviews_path)
    mapping_path = Path(mapping_path)

    check_symlinks_and_escapes(mapping_path, mapping_path.parent)
    if reviews_path.exists():
        check_symlinks_and_escapes(reviews_path, reviews_path.parent)
    else:
        check_symlinks_and_escapes(reviews_path.parent, reviews_path.parent)

    # Validate score types and ranges
    if not isinstance(api_correct, bool):
        raise ValueError("api_correct must be a boolean")
    if not isinstance(hallucinated_api, bool):
        raise ValueError("hallucinated_api must be a boolean")

    if isinstance(requirement_score, bool) or not isinstance(requirement_score, int) or requirement_score not in (0, 1, 2):
        raise ValueError(f"requirement_score must be an integer in 0..2, got {requirement_score}")

    if isinstance(quality_score, bool) or not isinstance(quality_score, int) or quality_score not in (1, 2, 3, 4, 5):
        raise ValueError(f"quality_score must be an integer in 1..5, got {quality_score}")

    # Read original contents for rollback/fail-closed semantics
    original_content = b""
    if reviews_path.exists():
        original_content = reviews_path.read_bytes()

    # 1. Verify blind_id exists in mapping
    valid_blind_ids = set()
    with open(mapping_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                valid_blind_ids.add(json.loads(line).get("blind_id"))

    if blind_id not in valid_blind_ids:
        raise ValueError(f"Unknown blind ID: {blind_id}")

    # 2. Check for duplicate scoring in reviews_path
    existing_scores = set()
    if reviews_path.exists():
        with open(reviews_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    existing_scores.add(json.loads(line).get("blind_id"))

    if blind_id in existing_scores:
        raise ValueError(f"Duplicate review score for blind_id: {blind_id}")

    # 3. Append review result with atomic write and rollback on error
    score_record = {
        "blind_id": blind_id,
        "api_correct": api_correct,
        "hallucinated_api": hallucinated_api,
        "requirement_score": requirement_score,
        "quality_score": quality_score,
    }
    
    new_line = (json.dumps(score_record, sort_keys=True) + "\n").encode("utf-8")

    try:
        with open(reviews_path, "ab") as f:
            f.write(new_line)
    except Exception as exc:
        # Rollback/restore original file content on write failure
        if original_content:
            reviews_path.write_bytes(original_content)
        elif reviews_path.exists():
            reviews_path.unlink()
        raise RuntimeError(f"Failed to record review score, rolled back: {exc}") from exc


def evaluate_reviewed_results(
    raw_jsonl_path: Path,
    reviews_path: Path,
    mapping_path: Path,
) -> list[dict]:
    raw_jsonl_path = Path(raw_jsonl_path)
    reviews_path = Path(reviews_path)
    mapping_path = Path(mapping_path)

    check_symlinks_and_escapes(raw_jsonl_path, raw_jsonl_path.parent)
    check_symlinks_and_escapes(mapping_path, mapping_path.parent)
    if reviews_path.exists():
        check_symlinks_and_escapes(reviews_path, reviews_path.parent)

    # Read mapping
    mapping = {}
    with open(mapping_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                mapping[data["blind_id"]] = data["run_id"]

    # Read reviews
    reviews = {}
    if reviews_path.exists():
        with open(reviews_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    reviews[data["blind_id"]] = data

    # Read raw JSONL and join in memory
    joined_results = []
    with open(raw_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                run_id = r.get("run_id")
                
                # Find matching blind_id
                blind_id = next((b_id for b_id, r_id in mapping.items() if r_id == run_id), None)
                if blind_id and blind_id in reviews:
                    rev = reviews[blind_id]
                    joined = dict(r)
                    joined.update({
                        "api_correct": rev["api_correct"],
                        "hallucinated_api": rev["hallucinated_api"],
                        "requirement_score": rev["requirement_score"],
                        "quality_score": rev["quality_score"],
                    })
                    joined_results.append(joined)
                else:
                    joined_results.append(dict(r))

    return joined_results

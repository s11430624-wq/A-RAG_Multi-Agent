from __future__ import annotations

import json
import hashlib
from pathlib import Path
import pytest
from jsonschema import validate

def test_frozen_smoke_artifacts():
    # 1. Paths
    repo_root = Path(__file__).resolve().parents[2]
    smoke_id = "m7d_smoke_20260611T123000Z"
    
    report_path = repo_root / "results" / "raw" / "gates" / f"{smoke_id}.json"
    jsonl_path = repo_root / "results" / "raw" / f"{smoke_id}.jsonl"
    artifacts_dir = repo_root / "results" / "raw" / "artifacts" / smoke_id
    retrieval_dir = repo_root / "results" / "raw" / "retrieval" / smoke_id
    schema_path = repo_root / "contracts" / "result.schema.json"
    
    assert report_path.is_file(), f"Report file not found: {report_path}"
    assert jsonl_path.is_file(), f"JSONL file not found: {jsonl_path}"
    assert schema_path.is_file(), f"Schema file not found: {schema_path}"
    
    # 2. Verify report file hash is exactly as required
    report_bytes = report_path.read_bytes()
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    expected_report_sha = "a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a"
    assert report_sha == expected_report_sha, f"Report SHA mismatch: got {report_sha}, expected {expected_report_sha}"
    
    # Load report data
    report_data = json.loads(report_bytes.decode("utf-8"))
    assert report_data["smoke_experiment_id"] == smoke_id
    
    # 3. Verify raw JSONL hash matches the report
    jsonl_bytes = jsonl_path.read_bytes()
    jsonl_sha = hashlib.sha256(jsonl_bytes).hexdigest()
    assert jsonl_sha == report_data["source_jsonl_sha256"], "JSONL SHA mismatch with report"
    
    # 4. Verify 3 records are schema-valid and check strategies/tool_calls
    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)
        
    records = []
    for line in jsonl_bytes.decode("utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
            
    assert len(records) == 3, f"Expected exactly 3 records, found {len(records)}"
    
    strategies_seen = set()
    for idx, rec in enumerate(records):
        # Validate schema
        validate(instance=rec, schema=schema)
        
        # Verify fields
        strategy = rec["strategy"]
        strategies_seen.add(strategy)
        assert rec["task_id"] == "T01"
        assert rec["repetition"] == 1
        assert rec["seed"] == 42
        assert rec["model"] == "google/gemini-3.5-flash"
        assert rec["valid_run"] is True
        assert rec["infra_error"] is False
        
        # Verify tool calls
        tool_calls = rec.get("tool_calls", 0)
        if strategy in ("A", "C"):
            assert tool_calls == 0, f"Strategy {strategy} must have 0 tool calls"
        elif strategy == "E":
            assert tool_calls > 0, "Strategy E must have more than 0 tool calls"
            assert tool_calls == 3, f"Strategy E tool_calls must be 3, got {tool_calls}"
            
    assert strategies_seen == {"A", "C", "E"}
    
    # 5. Recalculate artifact manifest set hash
    manifest_items = []
    assert artifacts_dir.is_dir(), f"Artifacts dir not found: {artifacts_dir}"
    
    # Locate all manifest.json files physically
    for run_dir in sorted(artifacts_dir.iterdir()):
        if run_dir.is_dir():
            manifest_file = run_dir / "manifest.json"
            assert manifest_file.is_file(), f"manifest.json missing in {run_dir}"
            
            # Read and verify manifest content
            m_bytes = manifest_file.read_bytes()
            m_data = json.loads(m_bytes.decode("utf-8"))
            
            # Assert correct provider_id, model, seed
            assert m_data["provider_id"] == "hermes_vertex_gateway"
            assert m_data["model"] == "google/gemini-3.5-flash"
            assert m_data["seed"] == 42
            assert m_data["usage_complete"] is True
            
            m_sha = hashlib.sha256(m_bytes).hexdigest()
            rel_path = manifest_file.relative_to(repo_root).as_posix()
            manifest_items.append({"path": rel_path, "sha256": m_sha})
            
    assert len(manifest_items) == 3, f"Expected 3 manifests, found {len(manifest_items)}"
    
    manifest_items.sort(key=lambda x: x["path"])
    manifest_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in manifest_items]
    manifest_set_bytes = "\n".join(manifest_lines).encode("utf-8")
    recalculated_manifest_set_sha = hashlib.sha256(manifest_set_bytes).hexdigest()
    
    assert recalculated_manifest_set_sha == report_data["artifact_manifest_set_sha256"], "Manifest set SHA mismatch"
    
    # 6. Recalculate retrieval log set hash
    assert retrieval_dir.is_dir(), f"Retrieval dir not found: {retrieval_dir}"
    
    retrieval_items = []
    for log_file in sorted(retrieval_dir.iterdir()):
        if log_file.is_file() and log_file.name.endswith(".jsonl"):
            log_bytes = log_file.read_bytes()
            log_sha = hashlib.sha256(log_bytes).hexdigest()
            rel_path = log_file.relative_to(repo_root).as_posix()
            retrieval_items.append({"path": rel_path, "sha256": log_sha})
            
    assert len(retrieval_items) == 1, f"Expected 1 retrieval log file, found {len(retrieval_items)}"
    
    retrieval_items.sort(key=lambda x: x["path"])
    retrieval_lines = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in retrieval_items]
    retrieval_set_bytes = "\n".join(retrieval_lines).encode("utf-8")
    recalculated_retrieval_set_sha = hashlib.sha256(retrieval_set_bytes).hexdigest()
    
    assert recalculated_retrieval_set_sha == report_data["retrieval_log_set_sha256"], "Retrieval log set SHA mismatch"
    
    # 7. Verify cost_unknown is in risk_flags and does not fail automated_gate_passed
    assert report_data["cost_known"] is False
    assert "unknown_cost" in report_data["risk_flags"]
    assert report_data["automated_gate_passed"] is True

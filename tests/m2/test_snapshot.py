import os
import json
import hashlib

def test_snapshot_verification():
    snapshot_path = os.path.abspath("student_system/SNAPSHOT.json")
    assert os.path.exists(snapshot_path), "SNAPSHOT.json does not exist"
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    assert "snapshot_id" in snapshot
    assert "created_at" in snapshot
    assert "files" in snapshot
    
    paths_seen = set()
    for entry in snapshot["files"]:
        path = entry["path"]
        expected_sha = entry["sha256"]
        
        # Uniqueness check
        assert path not in paths_seen, f"Path '{path}' is duplicated in SNAPSHOT.json"
        paths_seen.add(path)
        
        # Self-inclusion check
        assert "SNAPSHOT.json" not in path, "SNAPSHOT.json must not be included in itself"
        
        # Real file validation
        file_abspath = os.path.abspath(path)
        assert os.path.exists(file_abspath), f"File in snapshot '{path}' does not exist on disk"
        
        with open(file_abspath, "rb") as f:
            real_sha = hashlib.sha256(f.read()).hexdigest()
            
        assert real_sha == expected_sha, f"Hash mismatch for '{path}': expected {expected_sha}, got {real_sha}"
        
    # Check that we have exactly the files specified in snapshot
    expected_count = 13
    assert len(snapshot["files"]) == expected_count, f"SNAPSHOT should have exactly {expected_count} files, got {len(snapshot['files'])}"

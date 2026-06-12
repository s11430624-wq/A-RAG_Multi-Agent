import os
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from experiments.runtime.workspace import WorkspaceManager, WorkspaceError, CleanupError

@pytest.fixture
def temp_project_dir(tmp_path):
    # Create a mock project structure under tmp_path
    student_sys = tmp_path / "student_system"
    student_sys.mkdir()
    (student_sys / "src").mkdir()
    (student_sys / "tests" / "public").mkdir(parents=True)
    
    # Write some dummy source files
    files = {
        "student_system/README.md": "readme content",
        "student_system/src/student.py": "def foo(): pass",
        "student_system/tests/public/test_t01.py": "def test_foo(): assert True"
    }
    
    snapshot_files = []
    import hashlib
    for rel_path, content in files.items():
        full_path = tmp_path / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        snapshot_files.append({"path": rel_path, "sha256": h})
        
    snapshot_data = {
        "snapshot_id": "snap_mock",
        "created_at": "2026-06-11T12:00:00Z",
        "files": snapshot_files
    }
    
    snapshot_path = student_sys / "SNAPSHOT.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2)
        
    return tmp_path

def test_workspace_located_in_temp(temp_project_dir):
    # Verify sandbox is built inside TEMP
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
        resolved_workspace = workspace_path.resolve()
        assert resolved_workspace.is_relative_to(temp_root)
    finally:
        manager.cleanup()

def test_snapshot_verification_before_creation(temp_project_dir):
    # Corrupt a file in the temp project source directory before building workspace
    corrupted_file = temp_project_dir / "student_system" / "src" / "student.py"
    with open(corrupted_file, "w", encoding="utf-8") as f:
        f.write("corrupted content")
        
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    
    # Should fail hash check before copy
    with pytest.raises(WorkspaceError):
        manager.create()

def test_snapshot_only_copies_listed_files(temp_project_dir):
    # Put an unlisted file in the source directory
    unlisted_file = temp_project_dir / "student_system" / "unlisted.py"
    with open(unlisted_file, "w", encoding="utf-8") as f:
        f.write("unlisted content")
        
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    try:
        # The unlisted file should not exist in the sandbox
        dest_unlisted = workspace_path / "student_system" / "unlisted.py"
        assert not dest_unlisted.exists()
    finally:
        manager.cleanup()

def test_post_patch_integrity_unauthorized_add(temp_project_dir):
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    try:
        # Simulate unauthorized addition of a file
        new_file = workspace_path / "student_system" / "src" / "extra.py"
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("extra content")
            
        with pytest.raises(WorkspaceError):
            manager.verify_post_patch_integrity(["student_system/src/student.py"])
    finally:
        manager.cleanup()

def test_post_patch_integrity_unauthorized_delete(temp_project_dir):
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    try:
        # Simulate deletion of a required file
        target = workspace_path / "student_system" / "src" / "student.py"
        os.remove(target)
        
        with pytest.raises(WorkspaceError):
            manager.verify_post_patch_integrity(["student_system/src/student.py"])
    finally:
        manager.cleanup()

def test_post_patch_integrity_unauthorized_modify(temp_project_dir):
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    try:
        # Modify a file not in files_to_modify list
        target = workspace_path / "student_system" / "README.md"
        with open(target, "w", encoding="utf-8") as f:
            f.write("modified readme")
            
        with pytest.raises(WorkspaceError):
            manager.verify_post_patch_integrity(["student_system/src/student.py"])
            
        # Should pass if it is inside files_to_modify
        target_student = workspace_path / "student_system" / "src" / "student.py"
        with open(target_student, "w", encoding="utf-8") as f:
            f.write("modified student")
            
        # Should now pass for student.py, but fail because README.md is still modified
        with pytest.raises(WorkspaceError):
            manager.verify_post_patch_integrity(["student_system/src/student.py"])
            
        # Revert README.md
        with open(target, "w", encoding="utf-8") as f:
            f.write("readme content")
            
        # Should now succeed since only student.py is modified and it is allowed
        assert manager.verify_post_patch_integrity(["student_system/src/student.py"])
    finally:
        manager.cleanup()

def test_cleanup_raises_cleanup_error(temp_project_dir):
    snapshot_path = temp_project_dir / "student_system" / "SNAPSHOT.json"
    manager = WorkspaceManager("run_mock", "T01", str(snapshot_path))
    workspace_path = manager.create()
    
    # Mock self._temp_dir.cleanup to raise an exception
    class BadTempDir:
        def cleanup(self):
            raise OSError("Access denied")
            
    manager._temp_dir = BadTempDir()
    with pytest.raises(CleanupError) as exc_info:
        manager.cleanup()
        
    assert str(workspace_path) in str(exc_info.value)
    assert manager.workspace_path == workspace_path

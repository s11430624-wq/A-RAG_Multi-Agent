import os
import json
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import List
from experiments.runtime.guards import SecurityGuards

class WorkspaceError(Exception):
    pass

class CleanupError(WorkspaceError):
    pass

def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

class WorkspaceManager:
    """
    Manages physical sandbox workspace lifecycles, performing three-stage integrity verification.
    """
    def __init__(self, run_id: str, task_id: str, snapshot_path: str = "student_system/SNAPSHOT.json"):
        self.run_id = run_id
        self.task_id = task_id
        self.snapshot_path = Path(snapshot_path).resolve()
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self.workspace_path: Path | None = None
        
    def create(self) -> Path:
        """
        1. Validate original snapshot hashes.
        2. Create temp sandbox directory.
        3. Copy only snapshot files.
        4. Validate copied files' hashes.
        5. Return workspace path.
        """
        if not self.snapshot_path.exists():
            raise WorkspaceError(f"SNAPSHOT.json not found at {self.snapshot_path}")
            
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)
            files = snapshot_data["files"]
        except Exception as e:
            raise WorkspaceError(f"Failed to read SNAPSHOT.json: {e}")
            
        # Parent of the student_system folder is the project root directory
        source_root = self.snapshot_path.parent.parent
        
        # Phase A: Validate hashes of source files before copying
        for f_info in files:
            rel_path = f_info["path"]
            expected_hash = f_info["sha256"]
            src_file = source_root / rel_path
            
            if not src_file.exists():
                raise WorkspaceError(f"Required source file not found: {rel_path}")
                
            actual_hash = calculate_sha256(src_file)
            if actual_hash != expected_hash:
                raise WorkspaceError(f"Source file integrity mismatch for {rel_path}")
                
        # Phase B: Create temp sandbox workspace directory
        try:
            self._temp_dir = tempfile.TemporaryDirectory()
            self.workspace_path = Path(self._temp_dir.name).resolve()
        except Exception as e:
            raise WorkspaceError(f"Failed to create temporary directory: {e}")
            
        # Copy only the listed snapshot files, creating missing directories
        for f_info in files:
            rel_path = f_info["path"]
            src_file = source_root / rel_path
            dest_file = self.workspace_path / rel_path
            
            try:
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
            except Exception as e:
                self.cleanup()
                raise WorkspaceError(f"Failed to copy file {rel_path} to sandbox: {e}")
                
        # Phase C: Validate sandbox copy integrity after copy
        for f_info in files:
            rel_path = f_info["path"]
            expected_hash = f_info["sha256"]
            dest_file = self.workspace_path / rel_path
            
            if not dest_file.exists():
                self.cleanup()
                raise WorkspaceError(f"Copied sandbox file not found: {rel_path}")
                
            actual_hash = calculate_sha256(dest_file)
            if actual_hash != expected_hash:
                self.cleanup()
                raise WorkspaceError(f"Sandbox copy integrity mismatch for {rel_path}")
                
        return self.workspace_path
        
    def verify_post_patch_integrity(self, files_to_modify: List[str]) -> bool:
        """
        Validates post-patch workspace state:
        - Only files in files_to_modify can be changed.
        - No snapshot files deleted.
        - No unauthorized files added (ignoring __pycache__, .pytest_cache, *.pyc).
        """
        if not self.workspace_path:
            raise WorkspaceError("Workspace not created yet.")
            
        normalized_files_to_modify = {Path(f).as_posix() for f in files_to_modify}
        
        # Load snapshot files
        try:
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                snapshot_data = json.load(f)
            snapshot_files = {f["path"]: f["sha256"] for f in snapshot_data["files"]}
        except Exception as e:
            raise WorkspaceError(f"Failed to read SNAPSHOT.json: {e}")
            
        # Traverse workspace files
        current_files = {}
        for root, dirs, filenames in os.walk(self.workspace_path):
            # Prune cache folders
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache")]
            for filename in filenames:
                if filename.endswith(".pyc") or filename.endswith(".pyo"):
                    continue
                full_path = Path(root) / filename
                rel_path = full_path.relative_to(self.workspace_path).as_posix()
                current_files[rel_path] = full_path
                
        # 1. Check for deletions
        for snap_rel_path in snapshot_files:
            if snap_rel_path not in current_files:
                raise WorkspaceError(f"Snapshot file was deleted: {snap_rel_path}")
                
        # 2. Check for unauthorized additions
        for cur_rel_path in current_files:
            if cur_rel_path not in snapshot_files:
                raise WorkspaceError(f"Unauthorized new file added: {cur_rel_path}")
                
        # 3. Check for unauthorized modifications
        for snap_rel_path, expected_hash in snapshot_files.items():
            cur_file_path = current_files[snap_rel_path]
            actual_hash = calculate_sha256(cur_file_path)
            
            if actual_hash != expected_hash:
                if snap_rel_path not in normalized_files_to_modify:
                    raise WorkspaceError(f"Unauthorized modification to file: {snap_rel_path}")
                    
        return True
        
    def cleanup(self) -> None:
        """
        Destroys the temporary workspace sandbox. Throws CleanupError on failure.
        On failure, preserves workspace_path for audit/retry.
        """
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
                self._temp_dir = None
                self.workspace_path = None
            except Exception as e:
                raise CleanupError(f"Failed to destroy workspace at {self.workspace_path}: {e}")

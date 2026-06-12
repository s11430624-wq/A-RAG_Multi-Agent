import os
import re
import json
import tempfile
from pathlib import Path
from typing import List, Dict
from experiments.runtime.guards import SecurityGuards

class PatchError(Exception):
    pass

class InvalidPatchError(PatchError):
    pass

class PatchApplyError(PatchError):
    pass

# Hunk header regex: @@ -start_line,num_lines +start_line,num_lines @@
# Ensure there is either EOL or a space and optional heading after the closing @@ to reject trailing garbage.
HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(?:$| ([^\s].*(?<!\s))$)")

def parse_patch(patch_content: str, files_to_modify: List[str]) -> Dict[str, List[dict]]:
    if not patch_content or not patch_content.strip():
        raise InvalidPatchError("Patch content is empty or contains only whitespace")
        
    lines = patch_content.splitlines()
    i = 0
    sections = {}
    normalized_files_to_modify = {Path(f).as_posix() for f in files_to_modify}
    found_any_section = False
    
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
            
        if not line.startswith("--- "):
            if line.startswith("+++ "):
                raise InvalidPatchError("+++ found without matching --- header")
            if line.startswith("Binary files"):
                raise InvalidPatchError("Binary diff not allowed")
            if line.startswith("@@ "):
                raise InvalidPatchError("Hunk header found before any file section")
            raise InvalidPatchError(f"Unexpected text before file header: {line}")
            
        found_any_section = True
        src_line = line
        if i + 1 >= len(lines) or not lines[i+1].startswith("+++ "):
            raise InvalidPatchError("--- header without matching +++ header")
        dest_line = lines[i+1]
        
        src_path_raw = src_line[4:].strip()
        dest_path_raw = dest_line[4:].strip()
        
        # Clean paths (remove timestamp or tabs)
        src_path_clean = src_path_raw.split('\t')[0].strip()
        dest_path_clean = dest_path_raw.split('\t')[0].strip()
        
        # Strip potential prefixes a/ or b/
        def strip_prefix(p: str) -> str:
            for prefix in ("a/", "b/"):
                if p.startswith(prefix):
                    return p[len(prefix):]
            return p
            
        src_rel = strip_prefix(src_path_clean)
        dest_rel = strip_prefix(dest_path_clean)
        
        # 1. dev/null check (creation/deletion not allowed)
        if "/dev/null" in (src_rel, dest_rel) or "dev/null" in (src_rel, dest_rel):
            raise InvalidPatchError("File creation or deletion is not allowed (/dev/null detected)")
            
        # 2. Path safety validations
        for path_str in (src_rel, dest_rel):
            if path_str.startswith("/") or path_str.startswith("\\") or Path(path_str).is_absolute():
                raise InvalidPatchError(f"Absolute path not allowed in patch: {path_str}")
            if ".." in Path(path_str).parts:
                raise InvalidPatchError(f"Path traversal not allowed in patch: {path_str}")
                
        # 3. Rename check
        if src_rel != dest_rel:
            raise InvalidPatchError(f"File renaming not allowed: {src_rel} != {dest_rel}")
            
        # 4. Allowlist check
        posix_rel = Path(src_rel).as_posix()
        if posix_rel not in normalized_files_to_modify:
            raise InvalidPatchError(f"File not in allowlist: {posix_rel}")
            
        # 5. Duplicate section check
        if posix_rel in sections:
            raise InvalidPatchError(f"Duplicate file section in patch: {posix_rel}")
            
        sections[posix_rel] = []
        
        i += 2
        found_hunk_for_section = False
        while i < len(lines) and not lines[i].startswith("--- "):
            hunk_line = lines[i]
            if not hunk_line.strip():
                raise InvalidPatchError("Empty line not allowed inside file section")
                
            if not hunk_line.startswith("@@ "):
                if hunk_line.startswith("Binary files") or hunk_line.startswith("+++ "):
                    raise InvalidPatchError("Malformed unified diff structure")
                raise InvalidPatchError(f"Unexpected non-hunk line in file section: {hunk_line}")
                
            found_hunk_for_section = True
            # Parse hunk header
            m = HUNK_HEADER_RE.match(hunk_line)
            if not m:
                raise InvalidPatchError(f"Malformed hunk header: {hunk_line}")
                
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1
            
            # Check ordering and overlap
            if sections[posix_rel]:
                prev_hunk = sections[posix_rel][-1]
                prev_end = prev_hunk["old_start"] + prev_hunk["old_count"]
                if old_start < prev_end:
                    raise InvalidPatchError(
                        f"Hunks for {posix_rel} overlap or are out of order. "
                        f"Previous ends at {prev_end}, current starts at {old_start}."
                    )
            
            hunk = {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": []
            }
            
            i += 1
            old_num = 0
            new_num = 0
            while i < len(lines) and (old_num < old_count or new_num < new_count):
                if i >= len(lines):
                    raise InvalidPatchError("Unexpected end of patch inside hunk")
                l = lines[i]
                if l.startswith(" "):
                    hunk["lines"].append(l)
                    old_num += 1
                    new_num += 1
                elif l.startswith("-"):
                    hunk["lines"].append(l)
                    old_num += 1
                elif l.startswith("+"):
                    hunk["lines"].append(l)
                    new_num += 1
                elif l.startswith(r"\ No newline"):
                    hunk["lines"].append(l)
                else:
                    raise InvalidPatchError(f"Malformed line in hunk: {l}")
                i += 1
                
            if old_num != old_count or new_num != new_count:
                raise InvalidPatchError(
                    f"Hunk line count mismatch for {posix_rel}. "
                    f"Expected old: {old_count}, new: {new_count}. "
                    f"Actual old: {old_num}, new: {new_num}."
                )
                
            # 1. 處理可選的合法的 \ No newline marker (當 count 滿時，下一行可能是 \ No newline)
            if i < len(lines) and lines[i].startswith(r"\ No newline"):
                hunk["lines"].append(lines[i])
                i += 1

            sections[posix_rel].append(hunk)
            
        if not found_hunk_for_section:
            raise InvalidPatchError(f"File section for {posix_rel} contains no hunks")
            
    if not found_any_section:
        raise InvalidPatchError("No unified diff file sections found in patch")
        
    return sections

def apply_hunks(file_content: str, hunks: List[dict]) -> str:
    file_lines = file_content.split('\n')
    offset = 0
    has_no_newline = False
    
    for hunk in hunks:
        target_idx = hunk["old_start"] - 1 + offset
        if target_idx < 0 or target_idx > len(file_lines):
            raise PatchApplyError(f"Hunk old_start {hunk['old_start']} is out of bounds")
            
        base_idx = target_idx
        new_file_lines = []
        
        hunk_lines = hunk["lines"]
        for hl in hunk_lines:
            if hl.startswith(" ") or hl.startswith("-"):
                expected_line = hl[1:]
                if base_idx >= len(file_lines):
                    raise PatchApplyError(f"Hunk expects line at {base_idx + 1} but file ended")
                actual_line = file_lines[base_idx]
                if actual_line != expected_line:
                    raise PatchApplyError(
                        f"Context mismatch at line {base_idx + 1}. Expected: '{expected_line}', Got: '{actual_line}'"
                    )
                if hl.startswith(" "):
                    new_file_lines.append(actual_line)
                base_idx += 1
            elif hl.startswith("+"):
                new_file_lines.append(hl[1:])
            elif hl.startswith(r"\ No newline"):
                pass
                
        # Replaced line range: target_idx to base_idx
        old_lines_count = base_idx - target_idx
        file_lines[target_idx:base_idx] = new_file_lines
        offset += len(new_file_lines) - old_lines_count
        
        if hunk_lines and hunk_lines[-1].startswith(r"\ No newline"):
            if len(hunk_lines) >= 2 and hunk_lines[-2].startswith("+"):
                has_no_newline = True
                
    result = '\n'.join(file_lines)
    if has_no_newline and result.endswith('\n'):
        result = result[:-1]
    return result

class PatchEngine:
    @staticmethod
    def validate_patch(patch_content: str, files_to_modify: List[str]) -> None:
        """
        Validates unified diff patch formatting and constraint compliance.
        Throws InvalidPatchError on failure.
        """
        parse_patch(patch_content, files_to_modify)
        
    @staticmethod
    def apply_patch(workspace_path: Path | str, patch_content: str, files_to_modify: List[str] | None = None) -> None:
        """
        Applies a unified diff patch to target files inside workspace_path.
        If files_to_modify is None, it defaults to files registered in the snapshot.
        Atomically writes updates only if all hunks across all files apply successfully in memory.
        """
        workspace_path = Path(workspace_path)
        
        # Extract files list from SNAPSHOT if none is provided
        if files_to_modify is None:
            snapshot_file = workspace_path / "student_system/SNAPSHOT.json"
            if snapshot_file.exists():
                try:
                    with open(snapshot_file, "r", encoding="utf-8") as f:
                        snap_data = json.load(f)
                    files_to_modify = [f["path"] for f in snap_data["files"]]
                except Exception:
                    files_to_modify = []
            else:
                files_to_modify = []
                
        # 1. Parse and validate diff
        sections = parse_patch(patch_content, files_to_modify)
        
        # 2. Stage changes in memory
        staged_changes = {}
        for rel_path, hunks in sections.items():
            full_path = workspace_path / rel_path
            SecurityGuards.assert_safe_path(full_path, workspace_path)
            
            if not full_path.exists():
                raise PatchApplyError(f"Target patch file does not exist: {rel_path}")
                
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            patched_content = apply_hunks(content, hunks)
            staged_changes[full_path] = patched_content
            
        # 3. Transactional Writeback
        # We write staged changes to temp files in the same directory, flush, sync, backup original, and swap.
        # If anything fails, rollback already-swapped files and clean up.
        temp_files = [] # list of (original_path, temp_path, backup_path, fd)
        committed_files = [] # list of (original_path, backup_path, has_backup)
        try:
            for full_path, new_content in staged_changes.items():
                parent_dir = full_path.parent
                fd, temp_path_str = tempfile.mkstemp(dir=parent_dir, prefix=".patch_tmp_", suffix=".tmp")
                temp_path = Path(temp_path_str)
                backup_path = parent_dir / f".patch_bak_{full_path.name}.bak"
                
                temp_files.append((full_path, temp_path, backup_path, fd))
                
                # Write new content, flush and fsync
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                    f.write(new_content)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        # Some platforms/filesystems might not support fsync (e.g. mock filesystems),
                        # but we try it.
                        pass
            
            # Atomic swap
            for full_path, temp_path, backup_path, _ in temp_files:
                has_backup = False
                if full_path.exists():
                    os.rename(full_path, backup_path)
                    has_backup = True
                
                try:
                    os.rename(temp_path, full_path)
                    committed_files.append((full_path, backup_path, has_backup))
                except Exception as swap_ex:
                    # Restore backup immediately for this failed file
                    if has_backup:
                        try:
                            os.rename(backup_path, full_path)
                        except Exception:
                            pass
                    raise swap_ex
                    
        except Exception as commit_err:
            # Transaction Rollback
            # Restore previously committed files
            for full_path, backup_path, has_backup in committed_files:
                if full_path.exists():
                    try:
                        os.remove(full_path)
                    except Exception:
                        pass
                if has_backup and backup_path.exists():
                    try:
                        os.rename(backup_path, full_path)
                    except Exception:
                        pass
            
            # Clean up temp and backup files
            for _, temp_path, backup_path, _ in temp_files:
                if temp_path.exists():
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                if backup_path.exists():
                    try:
                        os.remove(backup_path)
                    except Exception:
                        pass
            raise PatchApplyError(f"Atomic transaction commit failed: {commit_err}")
            
        # Success cleanup: remove backups
        for _, temp_path, backup_path, _ in temp_files:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            if backup_path.exists():
                try:
                    os.remove(backup_path)
                except Exception:
                    pass

import pytest
from pathlib import Path
from experiments.runtime.patching import PatchEngine, InvalidPatchError, PatchApplyError

@pytest.fixture
def workspace_with_files(tmp_path):
    student_py = tmp_path / "student_system" / "src" / "student.py"
    student_py.parent.mkdir(parents=True, exist_ok=True)
    with open(student_py, "w", encoding="utf-8") as f:
        f.write("line 1\nline 2\nline 3\n")
        
    utils_py = tmp_path / "student_system" / "src" / "utils.py"
    with open(utils_py, "w", encoding="utf-8") as f:
        f.write("util 1\nutil 2\n")
        
    return tmp_path

def test_legitimate_patch_success(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    
    PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])
    
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert content == "line 1\nline 2 modified\nline 3\n"

def test_patch_allowlist_violation(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    
    # Allowed list does not contain student.py
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/utils.py"])

def test_patch_absolute_path_rejected(workspace_with_files):
    patch = (
        "--- /etc/passwd\n"
        "+++ /etc/passwd\n"
        "@@ -1,1 +1,1 @@\n"
        "-root\n"
        "+hack\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["/etc/passwd"])

def test_patch_traversal_path_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/../src/student.py\n"
        "+++ student_system/src/../src/student.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-line 1\n"
        "+hack\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_dev_null_rejected(workspace_with_files):
    patch = (
        "--- /dev/null\n"
        "+++ student_system/src/student.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+new line\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_rename_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/grade.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-line 1\n"
        "+line 1\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_binary_diff_rejected(workspace_with_files):
    patch = (
        "Binary files student_system/src/student.py and student_system/src/student.py differ\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_duplicate_sections_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,2 +1,2 @@\n"
        " line 1\n"
        " line 2\n"
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -2,2 +2,2 @@\n"
        " line 2\n"
        " line 3\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_malformed_hunk_header_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 and some garbage @@\n"
        " line 1\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_incorrect_line_count_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        " line 2\n"
        # Missing line 3 context but header says count is 3
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_context_mismatch_transactional(workspace_with_files):
    # This patch contains two files.
    # The first file patch matches context.
    # The second file patch does NOT match context.
    # We assert that because the second one fails, neither file is modified.
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
        "--- student_system/src/utils.py\n"
        "+++ student_system/src/utils.py\n"
        "@@ -1,2 +1,2 @@\n"
        " wrong line 1\n"
        "-util 2\n"
        "+util 2 modified\n"
    )
    
    with pytest.raises(PatchApplyError):
        PatchEngine.apply_patch(
            workspace_with_files, 
            patch, 
            ["student_system/src/student.py", "student_system/src/utils.py"]
        )
        
    # Check that student.py is NOT modified
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        student_content = f.read()
    assert student_content == "line 1\nline 2\nline 3\n"


def test_patch_small_hunk_offset_applies_when_context_is_unique(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -3,1 +3,2 @@\n"
        " line 2\n"
        "+inserted\n"
    )

    PatchEngine.apply_patch(
        workspace_with_files,
        patch,
        ["student_system/src/student.py"],
    )

    assert (
        workspace_with_files / "student_system" / "src" / "student.py"
    ).read_text(encoding="utf-8") == "line 1\nline 2\ninserted\nline 3\n"


def test_patch_small_hunk_offset_rejects_ambiguous_context(workspace_with_files):
    target = workspace_with_files / "student_system" / "src" / "student.py"
    target.write_text("same\nmiddle\nsame\n", encoding="utf-8", newline="")
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -2,1 +2,2 @@\n"
        " same\n"
        "+inserted\n"
    )

    with pytest.raises(PatchApplyError, match="ambiguous"):
        PatchEngine.apply_patch(
            workspace_with_files,
            patch,
            ["student_system/src/student.py"],
        )


def test_patch_empty_or_whitespace_rejected(workspace_with_files):
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, "", ["student_system/src/student.py"])
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, "   \n  \n", ["student_system/src/student.py"])

def test_patch_arbitrary_non_diff_rejected(workspace_with_files):
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, "random text", ["student_system/src/student.py"])

def test_patch_no_hunks_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_hunk_header_garbage_rejected(workspace_with_files):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@garbage_text\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_hunks_out_of_order_rejected(workspace_with_files):
    # Second hunk starts at line 1, which is before first hunk's end
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -2,2 +2,2 @@\n"
        " line 2\n"
        " line 3\n"
        "@@ -1,2 +1,2 @@\n"
        " line 1\n"
        " line 2\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_hunks_overlap_rejected(workspace_with_files):
    # Hunks overlap: first hunk ends at line 3 (starts 1, count 2 -> covers lines 1, 2)
    # Second hunk starts at line 2 (covers lines 2, 3), which is before line 3.
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,2 +1,2 @@\n"
        " line 1\n"
        " line 2\n"
        "@@ -2,2 +2,2 @@\n"
        " line 2\n"
        " line 3\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])

def test_patch_write_failure_rollback(workspace_with_files, monkeypatch):
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
        "--- student_system/src/utils.py\n"
        "+++ student_system/src/utils.py\n"
        "@@ -1,2 +1,2 @@\n"
        " util 1\n"
        "-util 2\n"
        "+util 2 modified\n"
    )
    
    # Mock os.rename to raise exception on committing utils.py
    import os
    original_rename = os.rename
    def mock_rename(src, dst):
        if "utils.py" in str(dst) and not str(src).endswith(".bak"):
            raise IOError("Disk write error")
        return original_rename(src, dst)
        
    monkeypatch.setattr(os, "rename", mock_rename)
    
    with pytest.raises(PatchApplyError):
        PatchEngine.apply_patch(
            workspace_with_files, 
            patch, 
            ["student_system/src/student.py", "student_system/src/utils.py"]
        )
        
    # Check that student.py is NOT modified due to rollback
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        student_content = f.read()
    assert student_content == "line 1\nline 2\nline 3\n"

def test_hunk_count_extra_plus_line_rejected(workspace_with_files):
    # hunk count is 3 (old 3, new 3), but there is an extra "+" line right after it.
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
        "+extra line\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])
    # Ensure file is NOT modified
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        assert f.read() == "line 1\nline 2\nline 3\n"

def test_hunk_count_extra_minus_line_rejected(workspace_with_files):
    # hunk count is 3 (old 3, new 3), but there is an extra "-" line right after it.
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
        "-extra line\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        assert f.read() == "line 1\nline 2\nline 3\n"

def test_hunk_count_extra_context_line_rejected(workspace_with_files):
    # hunk count is 3 (old 3, new 3), but there is an extra context line right after it.
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
        " extra line\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        assert f.read() == "line 1\nline 2\nline 3\n"

def test_patch_hunk_header_garbage_with_spaces_rejected(workspace_with_files):
    # Garbage with spaces: @@ ... @@  garbage_text (multiple spaces) or trailing spaces
    patch1 = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@  garbage\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch1, ["student_system/src/student.py"])
        
    patch2 = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@ garbage \n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    with pytest.raises(InvalidPatchError):
        PatchEngine.apply_patch(workspace_with_files, patch2, ["student_system/src/student.py"])
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        assert f.read() == "line 1\nline 2\nline 3\n"

def test_patch_hunk_header_legal_optional_heading(workspace_with_files):
    # Legal: @@ ... @@ def calculate_pass_rate(course_id: str) -> float: (exactly one space before heading)
    patch = (
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1,3 +1,3 @@ def calculate_pass_rate(course_id: str) -> float:\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )
    # This must be allowed and applied successfully
    PatchEngine.apply_patch(workspace_with_files, patch, ["student_system/src/student.py"])
    with open(workspace_with_files / "student_system" / "src" / "student.py", "r", encoding="utf-8") as f:
        assert f.read() == "line 1\nline 2 modified\nline 3\n"

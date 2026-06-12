import os
import sys
import stat
import shutil
import tempfile
import subprocess
import pytest

def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def parse_and_apply_diff(diff_path, target_root):
    with open(diff_path, "r", encoding="utf-8") as f:
        diff_lines = f.readlines()
        
    files_patches = {}
    current_file = None
    current_hunk_old = []
    current_hunk_new = []
    in_hunk = False
    
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        if line.startswith("--- "):
            pass
        elif line.startswith("+++ "):
            if in_hunk and current_file:
                files_patches.setdefault(current_file, []).append((current_hunk_old, current_hunk_new))
                current_hunk_old = []
                current_hunk_new = []
                in_hunk = False
            
            dest_path = line[4:].strip()
            if dest_path.startswith("b/"):
                dest_path = dest_path[2:]
            current_file = os.path.normpath(dest_path)
            i += 1
            continue
        elif line.startswith("@@ "):
            if in_hunk and current_file:
                files_patches.setdefault(current_file, []).append((current_hunk_old, current_hunk_new))
                current_hunk_old = []
                current_hunk_new = []
            in_hunk = True
            i += 1
            continue
        elif in_hunk:
            if line.startswith("-"):
                current_hunk_old.append(line[1:])
            elif line.startswith("+"):
                current_hunk_new.append(line[1:])
            elif line.startswith(" "):
                current_hunk_old.append(line[1:])
                current_hunk_new.append(line[1:])
            else:
                in_hunk = False
                if current_file:
                    files_patches.setdefault(current_file, []).append((current_hunk_old, current_hunk_new))
                    current_hunk_old = []
                    current_hunk_new = []
        i += 1
        
    if in_hunk and current_file:
        files_patches.setdefault(current_file, []).append((current_hunk_old, current_hunk_new))
        
    # Apply patches
    for rel_path, hunks in files_patches.items():
        target_path = os.path.join(target_root, rel_path)
        assert os.path.exists(target_path), f"File to patch does not exist: {target_path}"
        
        with open(target_path, "r", encoding="utf-8") as f_in:
            content = f_in.read()
            
        for old_lines, new_lines in hunks:
            content_lf = content.replace("\r\n", "\n")
            old_block = "".join(old_lines).replace("\r\n", "\n")
            new_block = "".join(new_lines).replace("\r\n", "\n")
            
            assert old_block in content_lf, f"Old block not found in {rel_path}!\nExpected:\n{old_block}"
            content_lf = content_lf.replace(old_block, new_block, 1)
            content = content_lf
            
        with open(target_path, "w", encoding="utf-8", newline="\n") as f_out:
            f_out.write(content)

def ignore_patterns(path, names):
    ignored = []
    for name in names:
        if name in ("__pycache__", ".pytest_cache") or name.endswith(".pyc"):
            ignored.append(name)
    return ignored

@pytest.mark.parametrize("task_id", ["T01", "T02", "T03", "T04", "T05"])
def test_task_reference_patch_passes(task_id):
    # Use standard python tempfile.TemporaryDirectory to create sandbox in OS temp folder
    with tempfile.TemporaryDirectory(prefix=f"arag_m2_sandbox_{task_id}_") as temp_dir:
        sandbox_dir = os.path.abspath(temp_dir)
        
        # 1. Copy student_system and evaluation into sandbox, excluding caches and compiled pyc files
        shutil.copytree("student_system", os.path.join(sandbox_dir, "student_system"), ignore=ignore_patterns)
        shutil.copytree("evaluation", os.path.join(sandbox_dir, "evaluation"), ignore=ignore_patterns)
        shutil.copy("pyproject.toml", os.path.join(sandbox_dir, "pyproject.toml"))
        
        # 2. Apply the reference patch
        diff_path = os.path.abspath(f"evaluation/reference_patches/{task_id}.diff")
        assert os.path.exists(diff_path), f"Reference patch {diff_path} does not exist"
        
        parse_and_apply_diff(diff_path, sandbox_dir)
        
        # 3. Invoke pytest in sandbox with --import-mode=importlib and PYTHONDONTWRITEBYTECODE=1
        public_test_file = f"student_system/tests/public/test_{task_id.lower()}.py"
        hidden_test_file = f"evaluation/hidden_tests/test_{task_id.lower()}.py"
        
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        
        cmd = [sys.executable, "-m", "pytest", public_test_file, hidden_test_file, "--import-mode=importlib", "-v"]
        result = subprocess.run(cmd, cwd=sandbox_dir, capture_output=True, text=True, env=env)
        
        # Verify exit code
        assert result.returncode == 0, f"Tests failed for {task_id} after patching!\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

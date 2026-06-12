import os
import sys
import time
import shutil
import tempfile
import subprocess
import pytest
from pathlib import Path
from experiments.runtime.guards import SecurityGuards, PathEscapeError
from experiments.runtime.test_runner import SecureTestRunner, PublicTestResult, HiddenTestSummary

def test_sibling_prefix_escape_detection():
    # Setup base folder and sibling folder
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir).resolve()
        base_dir = temp_path / "base"
        base_dir.mkdir()
        sibling_dir = temp_path / "base2"
        sibling_dir.mkdir()
        
        target_file = sibling_dir / "file.txt"
        with open(target_file, "w") as f:
            f.write("test")
            
        with pytest.raises(PathEscapeError):
            SecurityGuards.assert_safe_path(target_file, base_dir)

def test_symlink_escape_checks_and_windows_skip():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir).resolve()
        base_dir = temp_path / "base"
        base_dir.mkdir()
        
        outside_file = temp_path / "outside.txt"
        with open(outside_file, "w") as f:
            f.write("outside")
            
        link_path = base_dir / "outside_link.txt"
        try:
            os.symlink(outside_file, link_path)
        except (OSError, PermissionError):
            pytest.skip("Windows non-admin symlink not supported")
            
        with pytest.raises(PathEscapeError):
            SecurityGuards.assert_safe_path(link_path, base_dir)

def test_imported_module_file_must_be_in_workspace(tmp_path):
    # Verify subprocess imports from sandbox workspace only
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "student_system" / "src").mkdir(parents=True)
    
    # Create mock module
    with open(workspace / "student_system" / "src" / "student.py", "w") as f:
        f.write("def foo(): return 'sandbox'")
        
    test_file = workspace / "student_system" / "tests" / "test_import.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    with open(test_file, "w") as f:
        f.write(
            "import os\n"
            "from pathlib import Path\n"
            "from student_system.src import student\n"
            "def test_file_loc():\n"
            "    # Assert imported student.py path is relative to CWD using Path.is_relative_to\n"
            "    assert Path(student.__file__).resolve().is_relative_to(Path(os.getcwd()).resolve())\n"
        )
        
    runner = SecureTestRunner(workspace, approved_hidden_root=tmp_path / "hidden", timeout_seconds=10.0)
    result = runner.run_public_tests(["student_system/tests/test_import.py"])
    
    assert result.passed
    assert not result.timeout_occurred

def test_sanitize_feedback():
    res = PublicTestResult(
        passed=False,
        passed_tests=["test_a"],
        failed_tests=["test_b"],
        stdout="my stdout content",
        stderr="my stderr content",
        traceback="detailed traceback",
        duration_seconds=1.2,
        timeout_occurred=False
    )
    
    policy_all = {
        "include_stdout": True,
        "include_stderr": True,
        "include_traceback": True,
        "max_chars": 1000
    }
    
    feedback = SecureTestRunner.sanitize_feedback(res, policy_all)
    assert "stdout" in feedback
    assert "stderr" in feedback
    assert "traceback" in feedback
    
    # Test max_chars = 0 returns empty string
    policy_zero = {
        "include_stdout": True,
        "max_chars": 0
    }
    assert SecureTestRunner.sanitize_feedback(res, policy_zero) == ""
    
    # Test invalid negative max_chars raises ValueError
    policy_invalid = {
        "max_chars": -5
    }
    with pytest.raises(ValueError):
        SecureTestRunner.sanitize_feedback(res, policy_invalid)
        
    # Test truncation message included in max_chars exactly
    policy_short = {
        "include_stdout": True,
        "include_stderr": False,
        "include_traceback": False,
        "max_chars": 30
    }
    feedback_short = SecureTestRunner.sanitize_feedback(res, policy_short)
    assert len(feedback_short) <= 30
    assert feedback_short.endswith("\n... (truncated)")

def test_hidden_test_summary_does_not_leak():
    summary = HiddenTestSummary(
        passed_count=2,
        total_count=3,
        duration_seconds=0.5,
        timeout_occurred=False
    )
    
    assert hasattr(summary, "passed_count")
    assert hasattr(summary, "total_count")
    assert hasattr(summary, "duration_seconds")
    assert hasattr(summary, "timeout_occurred")
    assert not hasattr(summary, "stdout")
    assert not hasattr(summary, "stderr")
    assert not hasattr(summary, "traceback")

def test_junit_xml_cleaned_up(tmp_path, monkeypatch):
    # Track the exact directories created during this runner call to confirm removal
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    created_dirs = []
    original_tempdir = tempfile.TemporaryDirectory
    
    def spy_tempdir(*args, **kwargs):
        td = original_tempdir(*args, **kwargs)
        created_dirs.append(Path(td.name).resolve())
        return td
        
    monkeypatch.setattr(tempfile, "TemporaryDirectory", spy_tempdir)
    
    runner = SecureTestRunner(workspace, approved_hidden_root=tmp_path / "hidden", timeout_seconds=5.0)
    runner.run_public_tests(["nonexistent_test.py"])
    
    assert len(created_dirs) > 0
    for d in created_dirs:
        # Verify that the exact temp directory created was cleaned up
        assert not d.exists()

def test_timeout_kills_only_target_process_tree(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    test_file = workspace / "test_sleep.py"
    with open(test_file, "w") as f:
        f.write(
            "import time\n"
            "def test_sleep():\n"
            "    time.sleep(100)\n"
        )
        
    runner = SecureTestRunner(workspace, approved_hidden_root=tmp_path / "hidden", timeout_seconds=1.0)
    
    start_time = time.time()
    result = runner.run_public_tests(["test_sleep.py"])
    end_time = time.time()
    
    assert result.timeout_occurred
    assert end_time - start_time < 5.0

def test_runner_path_guards_violations(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    approved_hidden = tmp_path / "hidden"
    approved_hidden.mkdir()
    
    runner = SecureTestRunner(workspace, approved_hidden_root=approved_hidden, timeout_seconds=5.0)
    
    # 1. run_public_tests rejects escaping paths
    res = runner.run_public_tests(["../outside_test.py"])
    assert "PathEscapeError" in res.traceback
    
    # 2. run_hidden_tests rejects relative paths
    with pytest.raises(ValueError) as ex:
        runner.run_hidden_tests(["relative_hidden_test.py"])
    assert "must be absolute" in str(ex.value)
    
    # 3. run_hidden_tests rejects paths inside workspace
    runner_parent_root = SecureTestRunner(workspace, approved_hidden_root=tmp_path, timeout_seconds=5.0)
    workspace_test = workspace / "student_system/tests/public/test_t01.py"
    workspace_test.parent.mkdir(parents=True, exist_ok=True)
    with open(workspace_test, "w") as f:
        f.write("def test_dummy(): pass")
        
    with pytest.raises(ValueError) as ex:
        runner_parent_root.run_hidden_tests([str(workspace_test.resolve())])
    assert "must be outside workspace" in str(ex.value)
    
    # 4. run_hidden_tests rejects paths outside approved_hidden_root
    unapproved_test = tmp_path / "unapproved_test.py"
    with open(unapproved_test, "w") as f:
        f.write("def test_dummy(): pass")
        
    with pytest.raises(ValueError) as ex:
        runner.run_hidden_tests([str(unapproved_test.resolve())])
    assert "Path escape detected" in str(ex.value)


def test_runner_nonexistent_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    approved_hidden = tmp_path / "hidden"
    approved_hidden.mkdir()
    
    runner = SecureTestRunner(workspace, approved_hidden_root=approved_hidden, timeout_seconds=5.0)
    
    # public test path does not exist
    res = runner.run_public_tests(["nonexistent_test.py"])
    assert res.runner_error
    assert "exit code" in res.collection_error or "XML missing" in res.collection_error
    assert not res.passed
    assert res.total_count == 0

    # hidden test path does not exist (in approved hidden root)
    hidden_path = approved_hidden / "nonexistent_hidden_test.py"
    res_hidden = runner.run_hidden_tests([str(hidden_path)])
    assert res_hidden.runner_error
    assert res_hidden.total_count == 0
    assert res_hidden.passed_count == 0


def test_runner_suite_all_skipped(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    approved_hidden = tmp_path / "hidden"
    approved_hidden.mkdir()
    
    # public test with skipped
    public_skipped = workspace / "test_public_skipped.py"
    with open(public_skipped, "w") as f:
        f.write(
            "import pytest\n"
            "@pytest.mark.skip(reason='testing skip')\n"
            "def test_skip(): pass\n"
        )
        
    runner = SecureTestRunner(workspace, approved_hidden_root=approved_hidden, timeout_seconds=5.0)
    res = runner.run_public_tests(["test_public_skipped.py"])
    assert not res.passed  # skipped > 0 means passed must be False
    assert res.skipped_count == 1
    assert res.total_count == 1
    assert not res.runner_error
    
    # hidden test with skipped
    hidden_skipped = approved_hidden / "test_hidden_skipped.py"
    with open(hidden_skipped, "w") as f:
        f.write(
            "import pytest\n"
            "@pytest.mark.skip(reason='testing hidden skip')\n"
            "def test_hidden_skip(): pass\n"
        )
        
    res_hidden = runner.run_hidden_tests([str(hidden_skipped)])
    assert not res_hidden.runner_error
    assert res_hidden.total_count == 1
    assert res_hidden.passed_count == 0


def test_runner_collection_syntax_error(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    approved_hidden = tmp_path / "hidden"
    approved_hidden.mkdir()
    
    # public test with syntax error
    public_syntax_error = workspace / "test_public_syntax.py"
    with open(public_syntax_error, "w") as f:
        f.write("def test_syntax(:\n    pass\n") # Syntax error!
        
    runner = SecureTestRunner(workspace, approved_hidden_root=approved_hidden, timeout_seconds=5.0)
    res = runner.run_public_tests(["test_public_syntax.py"])
    assert not res.passed
    assert res.runner_error
    assert "exit code" in res.collection_error or "XML missing" in res.collection_error


def test_runner_malformed_empty_xml(tmp_path):
    from experiments.runtime.test_runner import parse_junit_xml
    
    # Test parse_junit_xml directly with malformed and empty files
    empty_xml = tmp_path / "empty.xml"
    with open(empty_xml, "w") as f:
        f.write("")
    assert parse_junit_xml(empty_xml) is None
    
    malformed_xml = tmp_path / "malformed.xml"
    with open(malformed_xml, "w") as f:
        f.write("<testsuite><testcase></testsuite>") # unmatched tag
    assert parse_junit_xml(malformed_xml) is None


def test_runner_count_accuracy(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    approved_hidden = tmp_path / "hidden"
    approved_hidden.mkdir()
    
    public_test = workspace / "test_public.py"
    with open(public_test, "w") as f:
        f.write(
            "def test_pass_1(): assert True\n"
            "def test_pass_2(): assert True\n"
            "def test_fail_1(): assert False\n"
        )
        
    runner = SecureTestRunner(workspace, approved_hidden_root=approved_hidden, timeout_seconds=5.0)
    res = runner.run_public_tests(["test_public.py"])
    assert not res.passed
    assert res.total_count == 3
    assert len(res.passed_tests) == 2
    assert len(res.failed_tests) == 1
    assert "test_pass_1" in res.passed_tests[0] or "test_pass_1" in res.passed_tests[1]
    assert "test_fail_1" in res.failed_tests[0]


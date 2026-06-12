import os
import sys
import xml.etree.ElementTree as ET
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from experiments.runtime.guards import SecurityGuards, PathEscapeError

class PublicTestResult:
    """
    Detailed results of public unit tests.
    """
    def __init__(self, passed: bool, passed_tests: List[str], failed_tests: List[str],
                 stdout: str, stderr: str, traceback: str, duration_seconds: float, timeout_occurred: bool,
                 total_count: int = 0, skipped_count: int = 0, collection_error: str = "", runner_error: bool = False):
        self.passed = passed
        self.passed_tests = passed_tests
        self.failed_tests = failed_tests
        self.stdout = stdout
        self.stderr = stderr
        self.traceback = traceback
        self.duration_seconds = duration_seconds
        self.timeout_occurred = timeout_occurred
        self.total_count = total_count
        self.skipped_count = skipped_count
        self.collection_error = collection_error
        self.runner_error = runner_error

class HiddenTestSummary:
    """
    Highly sanitized summary of hidden tests. Leaves no trace of failures.
    """
    def __init__(self, passed_count: int, total_count: int, duration_seconds: float, timeout_occurred: bool, runner_error: bool = False):
        self.passed_count = passed_count
        self.total_count = total_count
        self.duration_seconds = duration_seconds
        self.timeout_occurred = timeout_occurred
        self.runner_error = runner_error

def parse_junit_xml(xml_path: Path) -> dict | None:
    if not xml_path.exists() or xml_path.stat().st_size == 0:
        return None
        
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return None

    # Parse counts from attributes
    tests = 0
    failures = 0
    errors = 0
    skipped = 0
    duration_seconds = 0.0

    if root.tag == "testsuite":
        tests = int(root.get("tests") or 0)
        failures = int(root.get("failures") or 0)
        errors = int(root.get("errors") or 0)
        skipped = int(root.get("skipped") or 0)
        duration_seconds = float(root.get("time") or 0.0)
    elif root.tag == "testsuites":
        if root.get("tests") is not None:
            tests = int(root.get("tests") or 0)
            failures = int(root.get("failures") or 0)
            errors = int(root.get("errors") or 0)
            skipped = int(root.get("skipped") or 0)
            duration_seconds = float(root.get("time") or 0.0)
        else:
            testsuites = root.findall(".//testsuite")
            for ts in testsuites:
                tests += int(ts.get("tests") or 0)
                failures += int(ts.get("failures") or 0)
                errors += int(ts.get("errors") or 0)
                skipped += int(ts.get("skipped") or 0)
                duration_seconds += float(ts.get("time") or 0.0)
    else:
        # Fallback to scanning testsuite children in custom root formats
        testsuites = root.findall(".//testsuite")
        if testsuites:
            for ts in testsuites:
                tests += int(ts.get("tests") or 0)
                failures += int(ts.get("failures") or 0)
                errors += int(ts.get("errors") or 0)
                skipped += int(ts.get("skipped") or 0)
                duration_seconds += float(ts.get("time") or 0.0)
        else:
            return None

    passed_tests = []
    failed_tests = []
    stdout_parts = []
    stderr_parts = []
    traceback_parts = []

    # Parse individual test cases
    testcases = root.findall(".//testcase")
    for tc in testcases:
        name = tc.get("name") or "unknown_test"
        classname = tc.get("classname") or ""
        full_name = f"{classname}.{name}" if classname else name
        
        failure_el = tc.find("failure")
        error_el = tc.find("error")
        skipped_el = tc.find("skipped")
        
        if skipped_el is not None:
            # skipped, not in passed or failed
            pass
        elif failure_el is not None or error_el is not None:
            failed_tests.append(full_name)
            if failure_el is not None:
                msg = failure_el.get("message") or ""
                tb = failure_el.text or ""
                traceback_parts.append(f"FAIL: {full_name}\nMessage: {msg}\n{tb}\n")
            if error_el is not None:
                msg = error_el.get("message") or ""
                tb = error_el.text or ""
                traceback_parts.append(f"ERROR: {full_name}\nMessage: {msg}\n{tb}\n")
        else:
            passed_tests.append(full_name)
            
        sys_out = tc.find("system-out")
        if sys_out is not None and sys_out.text:
            stdout_parts.append(sys_out.text)
            
        sys_err = tc.find("system-err")
        if sys_err is not None and sys_err.text:
            stderr_parts.append(sys_err.text)

    # Capture global system-out/err in testsuites/testsuite
    for ts in root.findall(".//testsuite"):
        sys_out = ts.find("system-out")
        if sys_out is not None and sys_out.text and sys_out.text not in stdout_parts:
            stdout_parts.append(sys_out.text)
        sys_err = ts.find("system-err")
        if sys_err is not None and sys_err.text and sys_err.text not in stderr_parts:
            stderr_parts.append(sys_err.text)

    return {
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "stdout": "\n".join(stdout_parts),
        "stderr": "\n".join(stderr_parts),
        "traceback": "\n".join(traceback_parts),
        "duration_seconds": duration_seconds
    }

def kill_process_tree(pid: int) -> None:
    """
    Kills a process tree starting at target PID. Prevents orphaned subprocesses.
    """
    try:
        # On Windows, taskkill /F /T terminates process and all descendants
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
    except Exception:
        try:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

class SecureTestRunner:
    """
    Subprocess test runner that enforces isolation, timeouts, and feedback sanitization.
    """
    def __init__(self, workspace_path: Path | str, approved_hidden_root: Path | str, timeout_seconds: float = 30.0):
        self.workspace_path = Path(workspace_path).resolve()
        self.approved_hidden_root = Path(approved_hidden_root).resolve()
        self.timeout_seconds = timeout_seconds
        
    def run_public_tests(self, test_paths: List[str]) -> PublicTestResult:
        # Validate path safety
        for tp in test_paths:
            full_tp = self.workspace_path / tp
            try:
                SecurityGuards.assert_safe_path(full_tp, self.workspace_path)
            except PathEscapeError as e:
                return PublicTestResult(
                    passed=False,
                    passed_tests=[],
                    failed_tests=[],
                    stdout="",
                    stderr=str(e),
                    traceback="PathEscapeError",
                    duration_seconds=0.0,
                    timeout_occurred=False,
                    total_count=0,
                    skipped_count=0,
                    collection_error="PathEscapeError",
                    runner_error=True
                )
                
        # Run public tests inside workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_path = Path(temp_dir) / "junit.xml"
            
            # Prepare clean environment
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                *test_paths,
                f"--junitxml={xml_path}",
                f"--rootdir={self.workspace_path}"
            ]
            
            proc = None
            timeout_occurred = False
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=self.workspace_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                timeout_occurred = True
                if proc:
                    kill_process_tree(proc.pid)
                    try:
                        stdout, stderr = proc.communicate(timeout=2.0)
                    except Exception:
                        stdout, stderr = "", ""
                else:
                    stdout, stderr = "", ""
            except Exception as e:
                return PublicTestResult(
                    passed=False,
                    passed_tests=[],
                    failed_tests=[],
                    stdout="",
                    stderr=str(e),
                    traceback="Runner internal failure",
                    duration_seconds=0.0,
                    timeout_occurred=False,
                    total_count=0,
                    skipped_count=0,
                    collection_error=f"Process launch error: {e}",
                    runner_error=True
                )
                
            if timeout_occurred:
                return PublicTestResult(
                    passed=False,
                    passed_tests=[],
                    failed_tests=[],
                    stdout=stdout or "",
                    stderr=stderr or "",
                    traceback="TimeoutExpired",
                    duration_seconds=self.timeout_seconds,
                    timeout_occurred=True,
                    total_count=0,
                    skipped_count=0,
                    collection_error="TimeoutExpired",
                    runner_error=True
                )
                
            xml_data = parse_junit_xml(xml_path)
            
            # Determine exit code
            exit_code = proc.returncode if proc else -1
            
            if xml_data is None:
                # Missing or malformed XML
                return PublicTestResult(
                    passed=False,
                    passed_tests=[],
                    failed_tests=[],
                    stdout=stdout or "",
                    stderr=stderr or "",
                    traceback=f"Test runner execution failed. Exit code: {exit_code}",
                    duration_seconds=0.0,
                    timeout_occurred=False,
                    total_count=0,
                    skipped_count=0,
                    collection_error=f"XML missing or malformed (Exit code: {exit_code})",
                    runner_error=True
                )
                
            tests_val = xml_data["tests"]
            failures_val = xml_data["failures"]
            errors_val = xml_data["errors"]
            skipped_val = xml_data["skipped"]
            passed_count = tests_val - failures_val - errors_val - skipped_val
            
            # Collection error detection
            has_collection_error = False
            collection_err_msg = ""
            if exit_code in (4, 5):
                has_collection_error = True
                collection_err_msg = f"pytest exit code {exit_code}"
            elif tests_val == 0:
                has_collection_error = True
                collection_err_msg = "No tests collected (tests=0)"
            else:
                for ft in xml_data["failed_tests"]:
                    if "collection failure" in ft.lower() or "session failure" in ft.lower():
                        has_collection_error = True
                        collection_err_msg = f"Collection failure in: {ft}"
                        break
                if not has_collection_error:
                    # check stdout/stderr for CollectionError or similar
                    for line in (stdout or "").splitlines() + (stderr or "").splitlines():
                        if "CollectionError" in line or "errors during collection" in line:
                            has_collection_error = True
                            collection_err_msg = line
                            break
                            
            is_runner_err = False
            if has_collection_error:
                is_runner_err = True
            elif exit_code not in (0, 1):
                is_runner_err = True
                collection_err_msg = f"pytest non-zero exit code: {exit_code}"

            # Passed condition:
            # - subprocess exit code == 0
            # - total_count > 0
            # - failures == 0
            # - errors == 0
            # - skipped == 0
            # - passed_count == total_count
            passed_val = False
            if (exit_code == 0 
                and tests_val > 0 
                and failures_val == 0 
                and errors_val == 0 
                and skipped_val == 0 
                and passed_count == tests_val 
                and not is_runner_err):
                passed_val = True
                
            return PublicTestResult(
                passed=passed_val,
                passed_tests=xml_data["passed_tests"],
                failed_tests=xml_data["failed_tests"],
                stdout=xml_data["stdout"] or stdout or "",
                stderr=xml_data["stderr"] or stderr or "",
                traceback=xml_data["traceback"],
                duration_seconds=xml_data["duration_seconds"],
                timeout_occurred=False,
                total_count=tests_val,
                skipped_count=skipped_val,
                collection_error=collection_err_msg,
                runner_error=is_runner_err
            )
            
    def run_hidden_tests(self, hidden_test_absolute_paths: List[str]) -> HiddenTestSummary:
        # Validate hidden paths
        for tp in hidden_test_absolute_paths:
            p_tp = Path(tp)
            if not p_tp.is_absolute():
                raise ValueError(f"Hidden test path must be absolute: {tp}")
                
            # Must reside inside approved_hidden_root
            try:
                SecurityGuards.assert_safe_path(p_tp, self.approved_hidden_root)
            except PathEscapeError as e:
                raise ValueError(f"Hidden test path escape: {e}")
                
            # Must reside outside workspace
            resolved_tp = p_tp.resolve()
            resolved_workspace = self.workspace_path.resolve()
            is_inside = False
            try:
                if resolved_tp.is_relative_to(resolved_workspace):
                    is_inside = True
            except ValueError:
                pass
            if is_inside:
                raise ValueError(f"Hidden test path must be outside workspace: {tp}")

                
        # Run hidden tests using external absolute paths
        with tempfile.TemporaryDirectory() as temp_dir:
            xml_path = Path(temp_dir) / "junit.xml"
            
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                *hidden_test_absolute_paths,
                f"--junitxml={xml_path}",
                f"--rootdir={self.workspace_path}"
            ]
            
            proc = None
            timeout_occurred = False
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=self.workspace_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                timeout_occurred = True
                if proc:
                    kill_process_tree(proc.pid)
                    try:
                        proc.communicate(timeout=2.0)
                    except Exception:
                        pass
            except Exception:
                return HiddenTestSummary(
                    passed_count=0,
                    total_count=0,
                    duration_seconds=0.0,
                    timeout_occurred=False,
                    runner_error=True
                )
                
            if timeout_occurred:
                return HiddenTestSummary(
                    passed_count=0,
                    total_count=0,
                    duration_seconds=self.timeout_seconds,
                    timeout_occurred=True,
                    runner_error=True
                )
                
            xml_data = parse_junit_xml(xml_path)
            
            exit_code = proc.returncode if proc else -1
            
            if xml_data is None:
                return HiddenTestSummary(
                    passed_count=0,
                    total_count=0,
                    duration_seconds=0.0,
                    timeout_occurred=False,
                    runner_error=True
                )
                
            tests_val = xml_data["tests"]
            failures_val = xml_data["failures"]
            errors_val = xml_data["errors"]
            skipped_val = xml_data["skipped"]
            passed_count = tests_val - failures_val - errors_val - skipped_val
            
            # Collection error detection
            has_collection_error = False
            if exit_code in (4, 5):
                has_collection_error = True
            elif tests_val == 0:
                has_collection_error = True
            else:
                for ft in xml_data["failed_tests"]:
                    if "collection failure" in ft.lower() or "session failure" in ft.lower():
                        has_collection_error = True
                        break
                if not has_collection_error:
                    for line in (stdout or "").splitlines() + (stderr or "").splitlines():
                        if "CollectionError" in line or "errors during collection" in line:
                            has_collection_error = True
                            break
                            
            is_runner_err = False
            if has_collection_error:
                is_runner_err = True
            elif exit_code not in (0, 1):
                is_runner_err = True
                
            return HiddenTestSummary(
                passed_count=passed_count if not is_runner_err else 0,
                total_count=tests_val,
                duration_seconds=xml_data["duration_seconds"],
                timeout_occurred=False,
                runner_error=is_runner_err
            )
            
    @staticmethod
    def sanitize_feedback(public_result: PublicTestResult, policy_mapping: Dict[str, Any]) -> str:
        """
        Sanitizes raw test execution outputs according to task policy bounds.
        """
        max_chars = policy_mapping.get("max_chars", 2048)
        if not isinstance(max_chars, int) or max_chars < 0:
            raise ValueError(f"max_chars must be a non-negative integer, got {max_chars}")
            
        if max_chars == 0:
            return ""
            
        parts = []
        if policy_mapping.get("include_stdout", True) and public_result.stdout:
            parts.append("--- STDOUT ---")
            parts.append(public_result.stdout)
        if policy_mapping.get("include_stderr", True) and public_result.stderr:
            parts.append("--- STDERR ---")
            parts.append(public_result.stderr)
        if policy_mapping.get("include_traceback", True) and public_result.traceback:
            parts.append("--- TRACEBACK ---")
            parts.append(public_result.traceback)
            
        feedback = "\n".join(parts)
        
        if len(feedback) > max_chars:
            trunc_msg = "\n... (truncated)"
            if max_chars <= len(trunc_msg):
                feedback = feedback[:max_chars]
            else:
                feedback = feedback[:max_chars - len(trunc_msg)] + trunc_msg
                
        return feedback

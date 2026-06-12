import os
import json
import pytest
import time
from pathlib import Path
from jsonschema import Draft202012Validator

from experiments.evaluation.evaluator import Evaluator, evaluate_task_with_deterministic_patches
from experiments.evaluation.metrics import (
    MetricsCollector,
    EmptyResponseError,
    TestTimeoutError,
    RunnerError,
)
from experiments.runtime.workspace import WorkspaceManager, WorkspaceError, CleanupError
from experiments.runtime.patching import InvalidPatchError, PatchApplyError
from experiments.runtime.test_runner import SecureTestRunner

@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent.parent

@pytest.fixture
def evaluator(project_root):
    task_config_path = project_root / "experiments" / "tasks.json"
    return Evaluator(task_config_path)

def test_load_and_validate_tasks(evaluator):
    """Verify that tasks are successfully loaded and validated against the schema."""
    assert len(evaluator.tasks) > 0
    assert "T01" in evaluator.tasks
    assert "T02" in evaluator.tasks

@pytest.mark.parametrize("task_id", ["T01", "T02", "T03", "T04", "T05"])
def test_all_reference_patches_success(evaluator, project_root, task_id):
    """Test that T01-T05 reference patches apply cleanly under strict mode and pass both public/hidden tests."""
    ref_patch_path = project_root / "evaluation" / "reference_patches" / f"{task_id}.diff"
    with open(ref_patch_path, "r", encoding="utf-8") as f:
        initial_patch = f.read()

    result = evaluator.evaluate_task(task_id, initial_patch, repair_patches=[], max_repair_rounds=2)

    assert result["valid_run"] is True
    assert result["infra_error"] is False
    assert result["error_type"] == "none"
    assert result["stop_reason"] == "public_pass"
    assert result["pass1_public"] is True
    assert result["pass1_hidden"] is True
    assert result["final_public"] is True
    assert result["final_hidden"] is True
    assert result["repair_rounds"] == 0
    assert result["patch_apply_failures"] == 0
    assert result["public_tests_passed"] == result["public_tests_total"]
    assert result["hidden_tests_passed"] == result["hidden_tests_total"]
    assert result["public_tests_total"] > 0
    assert result["hidden_tests_total"] > 0

def test_empty_initial_patch(evaluator):
    """Test that empty or whitespaced initial patch raises/reports empty_response."""
    result = evaluator.evaluate_task("T01", "   ", repair_patches=[], max_repair_rounds=2)
    assert result["valid_run"] is True
    assert result["infra_error"] is False
    assert result["error_type"] == "empty_response"
    assert result["stop_reason"] == "repair_limit"
    assert result["pass1_public"] is False
    assert result["pass1_hidden"] is False

def test_strict_hunk_location_check(evaluator):
    """Test that a patch with incorrect line location fails (Line 99 hunk cannot search and modify Line 3)."""
    # Context corresponds to S002 line at the top of student.py (line 3), but header specifies line 99
    bad_location_patch = """--- a/student_system/src/student.py
+++ b/student_system/src/student.py
@@ -99,2 +99,2 @@
     "S002": {"student_id": "S002", "name": "Bob"}
 }
"""
    result = evaluator.evaluate_task("T02", bad_location_patch, repair_patches=[], max_repair_rounds=2)
    assert result["valid_run"] is True
    assert result["infra_error"] is False
    # Under strict mode, incorrect start line causes context mismatch during apply, mapping to patch_apply_error
    assert result["error_type"] == "patch_apply_error"
    assert result["stop_reason"] == "repair_limit"
    assert result["patch_apply_failures"] == 1

def test_strict_hunk_line_count_mismatch(evaluator):
    """Test that strict hunk line count mismatch is rejected during parsing as invalid_patch."""
    # Header says 2 old lines, but hunk only has 1 context line
    mismatched_patch = """--- a/student_system/src/student.py
+++ b/student_system/src/student.py
@@ -1,2 +1,2 @@
 _STUDENTS = {
"""
    result = evaluator.evaluate_task("T02", mismatched_patch, repair_patches=[], max_repair_rounds=2)
    assert result["valid_run"] is True
    assert result["infra_error"] is False
    assert result["error_type"] == "invalid_patch"
    assert result["stop_reason"] == "repair_limit"
    assert result["patch_apply_failures"] == 1

def test_no_clean_pre_run_and_call_counts(evaluator, project_root, monkeypatch):
    """Test that evaluator does not run tests on clean workspace, and call counts are exact."""
    ref_patch_path = project_root / "evaluation" / "reference_patches" / "T01.diff"
    with open(ref_patch_path, "r", encoding="utf-8") as f:
        initial_patch = f.read()

    public_calls = 0
    hidden_calls = 0
    
    orig_run_public = SecureTestRunner.run_public_tests
    orig_run_hidden = SecureTestRunner.run_hidden_tests
    
    def mock_run_public(self, test_paths):
        nonlocal public_calls
        public_calls += 1
        return orig_run_public(self, test_paths)
        
    def mock_run_hidden(self, hidden_paths):
        nonlocal hidden_calls
        hidden_calls += 1
        return orig_run_hidden(self, hidden_paths)
        
    monkeypatch.setattr(SecureTestRunner, "run_public_tests", mock_run_public)
    monkeypatch.setattr(SecureTestRunner, "run_hidden_tests", mock_run_hidden)
    
    result = evaluator.evaluate_task("T01", initial_patch, repair_patches=[], max_repair_rounds=2)
    
    assert result["valid_run"] is True
    # Exactly 1 public call and 1 hidden call for Pass 1 (no pre-runs)
    assert public_calls == 1
    assert hidden_calls == 1

def test_feedback_sanitization_and_no_hidden_leak(evaluator, project_root):
    """Test that feedback is sanitized per task policy and contains no hidden details."""
    initial_patch = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -11,2 +11,5 @@
 def get_grades_by_course(course_id: str) -> list[dict]:
     return [g.copy() for g in _GRADES if g["course_id"] == course_id]
+
+def calculate_pass_rate(course_id: str) -> float:
+    return 0.0
"""
    repair_patch = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -14,2 +14,8 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 0.0
+    from student_system.src import course
+    course.get_course_by_id(course_id)
+    grades = get_grades_by_course(course_id)
+    if not grades:
+        return 0.0
+    pass_count = sum(1 for g in grades if g["score"] >= 60)
+    return round(pass_count / len(grades), 4)
"""
    result = evaluator.evaluate_task(
        "T01", 
        initial_patch, 
        repair_patches=[repair_patch], 
        max_repair_rounds=1
    )
    
    assert result["valid_run"] is True
    assert len(evaluator.public_feedback_history) == 2  # round 0 (initial) and round 1 (repair)
    
    for record in evaluator.public_feedback_history:
        # Check that sanitized feedback conforms to policy (e.g. traceback excluded)
        assert "traceback" not in record.sanitized_public_feedback.lower()
        # Strictly check that no hidden tests info (such as the word "hidden", or names of hidden tests) leak into feedback
        assert "hidden" not in record.sanitized_public_feedback.lower()
        
        # Verify PublicFeedbackRecord fields exist and are populated
        assert isinstance(record.round_index, int)
        assert isinstance(record.public_passed, bool)
        assert isinstance(record.public_passed_count, int)
        assert isinstance(record.public_total, int)
        # Ensure that no hidden round metrics exist on PublicFeedbackRecord
        assert not hasattr(record, "hidden_passed_count")
        assert not hasattr(record, "hidden_total")

def test_caller_cannot_exceed_limits(evaluator, project_root):
    """Test that requested max_repair_rounds cannot override task limit, and invalid limits are rejected."""
    # Invalid max_repair_rounds input must raise ValueError
    for invalid_val in [-1, 1.5, "2", True, False]:
        with pytest.raises(ValueError):
            evaluator.evaluate_task("T01", "some patch", max_repair_rounds=invalid_val)
            
    # T01 has a task limit of 2 max_repair_rounds.
    # If caller requests 5, but we only supply 3 repair patches, only 2 should be executed.
    initial_patch = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -11,2 +11,5 @@
 def get_grades_by_course(course_id: str) -> list[dict]:
     return [g.copy() for g in _GRADES if g["course_id"] == course_id]
+
+def calculate_pass_rate(course_id: str) -> float:
+    return 0.0
"""
    # 3 repair patches, all keeping code failing/invalid to run all rounds
    repair_1 = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -14,2 +14,2 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 0.0
+    return 1.0
"""
    repair_2 = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -14,2 +14,2 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 1.0
+    return 2.0
"""
    repair_3 = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -14,2 +14,2 @@
 def calculate_pass_rate(course_id: str) -> float:
-    return 2.0
+    return 3.0
"""
    result = evaluator.evaluate_task(
        "T01",
        initial_patch,
        repair_patches=[repair_1, repair_2, repair_3],
        max_repair_rounds=5
    )
    
    assert result["valid_run"] is True
    # Should stop at 2 rounds due to T01 limit of 2 max_repair_rounds
    assert result["repair_rounds"] == 2
    assert len(evaluator.public_feedback_history) == 3 # round 0, 1, 2

def test_cleanup_failure_overrides_prior_error(evaluator, monkeypatch):
    """Test that a cleanup failure always overrides any prior error status to runner_error/infra_error."""
    # Trigger an InvalidPatchError first
    bad_patch = "invalid patch format"
    
    def mock_cleanup(self):
        raise CleanupError("cleanup failed")
        
    monkeypatch.setattr(WorkspaceManager, "cleanup", mock_cleanup)
    
    result = evaluator.evaluate_task("T01", bad_patch, repair_patches=[], max_repair_rounds=2)
    
    assert result["valid_run"] is False
    assert result["infra_error"] is True
    assert result["error_type"] == "runner_error"
    assert result["stop_reason"] == "infra_error"

def test_manual_review_status_scores_validation(evaluator, project_root):
    """Test that reviewed/disputed manual status requires explicit non-null score arguments."""
    ref_patch_path = project_root / "evaluation" / "reference_patches" / "T01.diff"
    with open(ref_patch_path, "r", encoding="utf-8") as f:
        initial_patch = f.read()

    #reviewed status missing scores raises ValueError
    with pytest.raises(ValueError) as exc_info:
        evaluator.evaluate_task("T01", initial_patch, manual_review_status="reviewed")
    assert "manual review scores" in str(exc_info.value)
    
    # reviewed status with non-null scores succeeds
    result = evaluator.evaluate_task(
        "T01",
        initial_patch,
        manual_review_status="reviewed",
        api_correct=1,
        hallucinated_api=0,
        requirement_score=2,
        quality_score=4
    )
    assert result["valid_run"] is True
    assert result["manual_review_status"] == "reviewed"
    assert result["api_correct"] == 1
    assert result["hallucinated_api"] == 0
    assert result["requirement_score"] == 2
    assert result["quality_score"] == 4

def test_estimated_cost_defaults_to_none(evaluator, project_root):
    """Test that estimated_cost defaults to None."""
    ref_patch_path = project_root / "evaluation" / "reference_patches" / "T01.diff"
    with open(ref_patch_path, "r", encoding="utf-8") as f:
        initial_patch = f.read()

    result = evaluator.evaluate_task("T01", initial_patch)
    assert result["estimated_cost"] is None
    assert result["model"] == "deterministic-fixture"

def test_patch_apply_error_context_mismatch(evaluator):
    """Test that patch apply error (context mismatch) reports patch_apply_error."""
    bad_patch = """--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -11,2 +11,5 @@
 def get_grades_by_course(non_existent_context: str) -> list[dict]:
     return []
+
+def calculate_pass_rate(course_id: str) -> float:
+    return 0.5
"""
    result = evaluator.evaluate_task("T01", bad_patch, repair_patches=[], max_repair_rounds=2)
    assert result["valid_run"] is True
    assert result["infra_error"] is False
    assert result["error_type"] == "patch_apply_error"
    assert result["stop_reason"] == "repair_limit"
    assert result["patch_apply_failures"] == 1

# Manual Run Record

## Metadata

- experiment_id: manual_hermes_eval
- task_id: T01
- strategy: A
- repetition: rep01
- model: Hermes / GPT-5.4 manual run
- operator: user
- date_time: 2026-06-12
- session_links:

## Strategy Setting

- agent_setup: A_SoloCoder
- tool_access: chat/file output only; public/hidden tests executed by Codex operator
- rag_enabled: false
- allowed_corpus: None
- forbidden_sources: hidden tests, reference patches, previous runs, results, workspaces, repo-external files
- max_repair_rounds: 2
- workspace_policy_confirmed: true

## Files In This Package

- task_packet.md
- run_record.md
- output_patch.diff
- no rag_corpus/ for this strategy

## Interaction Log

### Round 0

#### Agent Responses

```text
Agent produced an initial calculate_pass_rate patch. Initial validation failed because the patch hunk header/count caused the final return line not to apply in the clean workspace.
```

#### Patch

```diff
Initial patch omitted the effective final return after application due to malformed diff hunk count.
```

#### Public Test Result

```text
FAILED: 1 failed, 1 passed
Failure: test_calculate_pass_rate_normal expected 0.5 but got None.
```

### Round 1

#### Feedback Given

```text
Public test failed. calculate_pass_rate("C001") returned None. Repair by returning round(pass_count / total, 4). Do not run tests or use tools; only output corrected unified diff.
```

#### Agent Responses

```text
Corrected patch includes return round(pass_count / total, 4).
```

#### Patch

```diff
--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -27,3 +27,16 @@ def add_grade(student_id: str, course_id: str, score: int | float) -> None:
     # Hardcoded check to be removed in T05 refactoring
     if score < 0 or score > 100:
         raise ValueError("Invalid Score")
+
+def calculate_pass_rate(course_id: str) -> float:
+    from student_system.src.course import get_course_by_id
+    # Verify course exists
+    get_course_by_id(course_id)
+    
+    grades = get_grades_by_course(course_id)
+    if not grades:
+        return 0.0
+    
+    pass_count = sum(1 for g in grades if g["score"] >= 60)
+    total = len(grades)
+    return round(pass_count / total, 4)
```

#### Public Test Result

```text
2 passed in 0.03s
```

### Round 2

#### Feedback Given

```text
Not used. Public tests passed after repair round 1.
```

#### Agent Responses

```text
Not used.
```

#### Patch

```diff
Not used.
```

#### Public Test Result

```text
Not used.
```

## RAG Log

```text
RAG not allowed; no RAG used.
```

## Final Output

- changed_files: student_system/src/grade.py
- final_public_passed: true
- public_passed_count: 2
- public_total_count: 2
- stop_reason: public_passed_after_repair_1

### Final Patch

```diff
--- a/student_system/src/grade.py
+++ b/student_system/src/grade.py
@@ -27,3 +27,16 @@ def add_grade(student_id: str, course_id: str, score: int | float) -> None:
     # Hardcoded check to be removed in T05 refactoring
     if score < 0 or score > 100:
         raise ValueError("Invalid Score")
+
+def calculate_pass_rate(course_id: str) -> float:
+    from student_system.src.course import get_course_by_id
+    # Verify course exists
+    get_course_by_id(course_id)
+    
+    grades = get_grades_by_course(course_id)
+    if not grades:
+        return 0.0
+    
+    pass_count = sum(1 for g in grades if g["score"] >= 60)
+    total = len(grades)
+    return round(pass_count / total, 4)
```

## Evaluator Result

- hidden_passed_count: 3
- hidden_total_count: 3
- valid_run: true
- infra_error: false
- error_type: none
- stop_reason: public_passed_after_repair_1

## Manual Notes

- operator_notes: Patch was verified in a clean temporary git clone from HEAD, not against the dirty working tree.
- unexpected_behavior: Earlier pilot attempts used tool/search behavior; final validation is based on the corrected patch saved in output_patch.diff.
- rule_violations: none recorded for final corrected patch validation
- forbidden_path_requests:
- out_of_scope_file_modifications: none

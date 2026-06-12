# Task Packet T03: Fix score_to_gpa mapping

這份題目包可以直接提供給 Hermes agent。

## 使用規則

- 不可以使用 hidden tests。
- 不可以使用 reference patches。
- 不可以看其他 strategy 或其他 repetition 的結果。
- 只能修改 files_to_modify 列出的檔案。
- public test source 不直接提供；由操作員執行 public test 後回饋結果。
- 如果是 Strategy A 或 C，不可以使用 RAG。
- 如果是 Strategy E，只能使用本題對應的 manual_rag_corpus 資料夾。

## Workspace Policy

Repository root:

```text
C:/上課檔案/報告/A-RAG_Multi-Agent
```

This task may only modify:

- student_system/src/grade.py

Forbidden paths:

```text
evaluation/hidden_tests/
evaluation/reference_patches/
results/
workspaces/
.git/
__pycache__/
.pytest_cache/
```

Strategy A and C must not read manual_rag_corpus/.
Strategy E may read only manual_rag_corpus/T03/.

## Task Metadata

- task_id: T03
- title: Fix score_to_gpa mapping
- task_type: bug_fix
- difficulty: easy
- tags: mapping, bounds

## Task Description

```text
Fix the logic in score_to_gpa(score) inside grade.py. Correct the mapping so that 85-89 maps to GPA 3.5 (currently missing) and 70-74 maps to GPA 2.0 (currently 1.5). Add ValueError validation for scores outside the [0, 100] interval.
```

## Files To Modify

- student_system/src/grade.py

## Starter Files Included Below

- student_system/src/grade.py

## Public Test Command

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest student_system/tests/public/test_t03.py -q
```

## Expected Behavior

- Correctly converts 85 to GPA 3.5.
- Correctly converts 72 to GPA 2.0.
- Raises ValueError for out of bounds scores or invalid types.

## Forbidden Behaviors


## Grading Hints From Public Task Metadata

### Required API Symbols
- score_to_gpa

### Forbidden API Symbols
- None

### Requirement Checks
- Correctly maps score 85-89 to GPA 3.5
- Correctly maps score 70-74 to GPA 2.0
- Raises ValueError for scores outside [0, 100]

## Strategy E RAG Corpus

Use only this folder for Strategy E: manual_rag_corpus/T03/

Allowed source paths represented in that folder:
- student_system/API_SPEC.md
- student_system/STYLE_GUIDE.md
- student_system/ISSUES.md

## Starter Code

### student_system/src/grade.py

```python
_GRADES = [
    {"student_id": "S001", "course_id": "C001", "score": 85, "gpa": 3.0},
    {"student_id": "S001", "course_id": "C002", "score": 90, "gpa": 4.0},
    {"student_id": "S002", "course_id": "C001", "score": 55, "gpa": 0.0},
    {"student_id": "S002", "course_id": "C002", "score": 72, "gpa": 1.5}
]

def get_grades_by_student(student_id: str) -> list[dict]:
    return [g.copy() for g in _GRADES if g["student_id"] == student_id]

def get_grades_by_course(course_id: str) -> list[dict]:
    return [g.copy() for g in _GRADES if g["course_id"] == course_id]

def score_to_gpa(score: int | float) -> float:
    # Deliberate starter bugs (Issue #1 in ISSUES.md)
    if score >= 90:
        return 4.0
    if score >= 80:
        return 3.0
    if score >= 70:
        return 1.5
    if score >= 60:
        return 1.0
    return 0.0

def add_grade(student_id: str, course_id: str, score: int | float) -> None:
    # Hardcoded check to be removed in T05 refactoring
    if score < 0 or score > 100:
        raise ValueError("Invalid Score")
```


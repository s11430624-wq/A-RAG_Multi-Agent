# Task Packet T01: Calculate Pass Rate

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
Strategy E may read only manual_rag_corpus/T01/.

## Task Metadata

- task_id: T01
- title: Calculate Pass Rate
- task_type: code_generation
- difficulty: easy
- tags: statistics, grades

## Task Description

```text
Create a function calculate_pass_rate(course_id: str) -> float in grade.py that calculates the ratio of passed students (score >= 60). Returns round(pass_count / total, 4) for normal courses, 0.0 for courses that exist but have no enrolled students, and raises ValueError for non-existent courses.
```

## Files To Modify

- student_system/src/grade.py

## Starter Files Included Below

- student_system/src/grade.py
- student_system/src/course.py

## Public Test Command

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest student_system/tests/public/test_t01.py -q
```

## Expected Behavior

- Returns pass count ratio rounded to 4 decimal places.
- Returns 0.0 if course exists but has no grades.
- Raises ValueError if course does not exist.

## Forbidden Behaviors

- Do not hardcode return values.

## Grading Hints From Public Task Metadata

### Required API Symbols
- get_grades_by_course
- course.get_course_by_id

### Forbidden API Symbols
- None

### Requirement Checks
- Returns round(pass_rate, 4)
- Returns 0.0 for empty courses
- Raises ValueError for non-existent courses

## Strategy E RAG Corpus

Use only this folder for Strategy E: manual_rag_corpus/T01/

Allowed source paths represented in that folder:
- student_system/API_SPEC.md
- student_system/STYLE_GUIDE.md

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

### student_system/src/course.py

```python
_COURSES = {
    "C001": {"course_id": "C001", "title": "Mathematics", "credits": 3},
    "C002": {"course_id": "C002", "title": "Physics", "credits": 4},
    "C003": {"course_id": "C003", "title": "Empty Course", "credits": 2}
}

_ENROLLMENT = {
    "C001": ["S001", "S002"],
    "C002": ["S001", "S002"],
    "C003": []
}

def get_course_by_id(course_id: str) -> dict:
    if course_id not in _COURSES:
        raise ValueError("Course not found")
    return _COURSES[course_id].copy()

def get_students_by_course(course_id: str) -> list[dict]:
    from student_system.src.student import get_student_by_id
    if course_id not in _COURSES:
        raise ValueError("Course not found")
    return [get_student_by_id(sid) for sid in _ENROLLMENT[course_id]]
```


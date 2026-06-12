# Student System API Specification

本文件為 A-RAG 唯一核准的 API 真實依據，所有 Agent 與模型必須依此規格調用系統 API。

## 1. Student Module (`student_system/src/student.py`)

### `get_student_by_id(student_id: str) -> dict`
- **輸入**：`student_id` (字串，格式為 `S[0-9]{3}`)
- **輸出**：`{"student_id": str, "name": str}` 字典
- **例外**：若此學生 ID 不存在，拋出 `ValueError("Student not found")`。

### `get_all_students() -> list[dict]`
- **輸出**：包含全體學生資料的字典列表。

---

## 2. Course Module (`student_system/src/course.py`)

### `get_course_by_id(course_id: str) -> dict`
- **輸入**：`course_id` (字串，格式為 `C[0-9]{3}`)
- **輸出**：`{"course_id": str, "title": str, "credits": int}` 字典
- **例外**：若此課程 ID 不存在，拋出 `ValueError("Course not found")`。

### `get_students_by_course(course_id: str) -> list[dict]`
- **輸入**：`course_id` (字串)
- **輸出**：修讀該課程的所有學生字典（`{"student_id": str, "name": str}`）列表。
- **例外**：若無此課程，拋出 `ValueError("Course not found")`。若該課程存在但無學生修讀，回傳空列表 `[]`。

---

## 3. Grade Module (`student_system/src/grade.py`)

### `get_grades_by_student(student_id: str) -> list[dict]`
- **輸入**：`student_id` (字串)
- **輸出**：修讀成績記錄字典列表：
  `[{"student_id": str, "course_id": str, "score": int, "gpa": float}]`
- **例外**：無，若該學生無任何成績記錄則回傳空列表 `[]`。

### `get_grades_by_course(course_id: str) -> list[dict]`
- **輸入**：`course_id` (字串)
- **輸出**：該課程所有成績記錄字典列表。
- **例外**：無，若無任何記錄回傳空列表 `[]`。

### `score_to_gpa(score: int | float) -> float`
- **輸入**：`score` 數值（0-100）
- **輸出**：對應 GPA。
  - 90-100 -> 4.0
  - 85-89  -> 3.5
  - 80-84  -> 3.0
  - 75-79  -> 2.5
  - 70-74  -> 2.0
  - 60-69  -> 1.0
  - < 60   -> 0.0
- **例外**：超出 0-100 區間或輸入型別不符時拋出 `ValueError`。

---

## 4. Utils Module (`student_system/src/utils.py`)

### `is_valid_score(score: object) -> bool`
- **輸入**：任意物件 `score`
- **輸出**：若為 `int` 或 `float`（排除 `bool` 型別）且在 `[0, 100]` 區間內則為 `True`，其餘一律為 `False`。

### `validate_score(score: object) -> None`
- **輸入**：任意物件 `score`
- **輸出**：無（靜默通過）。
- **例外**：若不合法（非數值、布林值或超出 [0, 100] 區間），拋出 `ValueError("Invalid score")`。

# Milestone 2 計畫：Student System 與任務集設計

本計畫詳細規劃 Milestone 2 (M2) 「Student System 與任務集」的技術架構、程式庫起始狀態（Starter Snapshot）、刻意缺陷、五題任務（T01–T05）細部規格，以及對應的公開測試、隱藏測試與參考修正檔（Reference Patches）設計。

---

## 一、 專案目錄結構與統一路徑規範

為了確保實驗數據可重現，以及 A-RAG 檢索組件的定位精確，所有配置在 `experiments/tasks.json` 與 `student_system/SNAPSHOT.json` 中的路徑，**一律統一採用相對於專案根目錄（Repo-root-relative）的格式**。

### 1.1 預定建立之目錄骨架
```text
student_system/
  README.md
  API_SPEC.md
  STYLE_GUIDE.md
  ISSUES.md
  SNAPSHOT.json
  src/
    student.py
    course.py
    grade.py
    utils.py
  tests/
    public/
      test_t01.py
      test_t02.py
      test_t03.py
      test_t04.py
      test_t05.py

evaluation/
  hidden_tests/
    test_t01.py
    test_t02.py
    test_t03.py
    test_t04.py
    test_t05.py
  reference_patches/
    T01.diff
    T02.diff
    T03.diff
    T04.diff
    T05.diff

experiments/
  tasks.json
```

---

## 二、 學生系統（student_system）文件與 API 規格

所有 API 統一採用 **模組層級函式（Module-level functions）**，徹底不使用同名的靜態類別方法，避免模型在理解、檢索與調用時產生歧義。

### 2.1 `student_system/API_SPEC.md` 規格設計
本文件為 A-RAG 唯一核准的 API 真實依據，內容明確列出各模組的函式：

- **`student_system/src/student.py`**
  - `get_student_by_id(student_id: str) -> dict`
    - *輸入*：`student_id` (格式 `S[0-9]{3}`)
    - *輸出*：`{"student_id": str, "name": str}` 字典
    - *例外*：無此學生時拋出 `ValueError`。
  - `get_all_students() -> list[dict]`
    - *輸出*：全體學生字典列表。

- **`student_system/src/course.py`**
  - `get_course_by_id(course_id: str) -> dict`
    - *輸入*：`course_id` (格式 `C[0-9]{3}`)
    - *輸出*：`{"course_id": str, "title": str, "credits": int}` 字典
    - *例外*：無此課程時拋出 `ValueError`。
  - `get_students_by_course(course_id: str) -> list[dict]`
    - *輸入*：`course_id`
    - *輸出*：修讀該課程的所有學生字典列表。
    - *例外*：無此課程時拋出 `ValueError`；存在但無學生的課程回傳空列表 `[]`。

- **`student_system/src/grade.py`**
  - `get_grades_by_student(student_id: str) -> list[dict]`
    - *輸入*：`student_id`
    - *輸出*：`[{"student_id": str, "course_id": str, "score": int, "gpa": float}]` 列表。
  - `get_grades_by_course(course_id: str) -> list[dict]`
    - *輸入*：`course_id`
    - *輸出*：該課程所有學生成績列表。
  - `score_to_gpa(score: int | float) -> float`
    - *輸入*：`score` 數值（0-100）
    - *輸出*：對應 GPA。
    - *例外*：超出 0-100 時拋出 `ValueError`。

- **`student_system/src/utils.py`**
  - `is_valid_score(score: object) -> bool`
    - *輸入*：任意物件
    - *輸出*：若為 `int` 或 `float`（排除 `bool` 型別）且在 `[0, 100]` 區間則為 `True`，其餘一律為 `False`。
  - `validate_score(score: object) -> None` (T05 新增)
    - *例外*：若型別不符或超出 0-100 區間，拋出 `ValueError("Invalid score")`，其餘靜默通過。

### 2.2 `student_system/STYLE_GUIDE.md` 規格設計
- **命名規範**：變數與函式統一為 `snake_case`，變數型別採用 PEP 484 Type Hints。
- **異常處理**：嚴禁使用寬泛的 `except Exception:`。必須捕獲特定型別，無效輸入應拋出含有明確描述的 `ValueError`。
- **數值規範**：及格比例（pass rate）為 `0.0` 至 `1.0` 之間的 `float`；所有統計回傳之 `float` 一律使用 `round(val, 4)` 四捨五入至第四位。

### 2.3 `student_system/ISSUES.md` 規格設計
- **Issue #1**：`grade.score_to_gpa` 映射區間有嚴重邏輯漏洞（80-89 分轉為 3.0，使 85-89 的 3.5 級分消失；且 70-74 誤映射為 1.5）。
- **Issue #2**：`utils.is_valid_score` 實作有瑕疵，未處理 `0` 與 `100` 分的邊界，且未過濾非數值與布林值。
- **Issue #3**：分數合法性驗證分散於 `student.py` 與 `grade.py`，未遵循 DRY 原則抽取統一驗證。

---

## 三、 五題任務 T01–T05 細部設計規格

五題任務彼此完全獨立。每題測試在套用其專屬 Reference Patch 後，皆從乾淨 Starter 狀態中套用，不得要求其他題目的修正先存在。

### [ ] 3.1 T01: calculate_pass_rate (Code Generation)
- **精確路徑**：`student_system/src/grade.py`
- **新增 API Signature**：
  ```python
  def calculate_pass_rate(course_id: str) -> float:
      """
      計算指定課程的及格率 (分數 >= 60 為及格)。
      - 正常課程：回傳 round(pass_count / total, 4)
      - 存在但無學生的課程：回傳 0.0
      - 不存在的 course_id：拋出 ValueError (必須先調用 course.get_course_by_id 驗證)
      """
  ```
- **Starter 行為**：該函式完全不存在（調用時會引發 `AttributeError`）。
- **Public Test (`student_system/tests/public/test_t01.py`)**：
  - 斷言：及格率正常計算。例如修課學生分數為 `[80, 55, 90]`，則及格率應為 `round(2/3, 4)`，即 `0.6667`。
- **Hidden Test (`evaluation/hidden_tests/test_t01.py`)**：
  - 斷言：輸入存在但無學生的 `course_id`（如 `"C003"`），必須回傳 `0.0`。
  - 斷言：輸入不存在的 `course_id`（如 `"C999"`），必須拋出 `ValueError`。
- **Reference Patch (`evaluation/reference_patches/T01.diff`)**：
  ```diff
  +from student_system.src import course
  +def calculate_pass_rate(course_id: str) -> float:
  +    course.get_course_by_id(course_id)
  +    grades = get_grades_by_course(course_id)
  +    if not grades:
  +        return 0.0
  +    pass_count = sum(1 for g in grades if g["score"] >= 60)
  +    return round(pass_count / len(grades), 4)
  ```
- **tasks.json 配置欄位**：
  - `task_id`: `"T01"`
  - `task_type`: `"code_generation"`
  - `starter_files`: `["student_system/src/grade.py", "student_system/src/course.py"]`
  - `files_to_modify`: `["student_system/src/grade.py"]`
  - `allowed_corpus`: `["student_system/API_SPEC.md", "student_system/STYLE_GUIDE.md"]`
  - `required_evidence`: `["student_system/API_SPEC.md"]`
  - `grading`: { `required_api_symbols`: `["get_grades_by_course", "course.get_course_by_id"]`, `forbidden_api_symbols`: `[]`, `requirement_checks`: `["Returns round(pass_rate, 4)", "Returns 0.0 for empty courses", "Raises ValueError for non-existent courses"]` }

---

### [ ] 3.2 T02: Student Course Summary (API Usage)
- **精確路徑**：`student_system/src/student.py`
- **新增 API Signature**：
  ```python
  def get_student_course_summary(student_id: str) -> dict:
      """
      取得指定學生的修課成績摘要。
      - 必須調用 grade.get_grades_by_student(student_id) 取得成績列表。
      - 對每筆成績，必須調用 course.get_course_by_id(course_id) 取得 credits 與 title。
      - 若 student_id 不存在或無此學生，應拋出 ValueError。
      - 嚴禁直接讀取 grade 模組的內部 raw_data 或全域 mock 字典。
      - 回傳結構：
        {
          "student_id": "S001",
          "courses": [
            {"course_id": "C001", "title": "Math", "credits": 3, "score": 85, "gpa": 3.5}
          ]
        }
      """
  ```
- **Starter 行為**：函式完全不存在（調用時引發 `AttributeError`）。
- **Public Test (`student_system/tests/public/test_t02.py`)**：
  - 斷言：正常獲取修課摘要，回傳的結構中包含 `student_id` 與修讀課程的 `title` 欄位。
- **Hidden Test (`evaluation/hidden_tests/test_t02.py`)**：
  - 斷言：傳入不存在學生 `"S999"` 拋出 `ValueError`。
  - 斷言：靜態分析代碼中不包含 `raw_grades` 或 `grades_db` 等虛構/私有全域字典，必須經由規定的 `get_grades_by_student` 取得。
- **Reference Patch (`evaluation/reference_patches/T02.diff`)**：
  ```diff
  +from student_system.src import grade, course
  +def get_student_course_summary(student_id: str) -> dict:
  +    get_student_by_id(student_id)
  +    grades = grade.get_grades_by_student(student_id)
  +    summary = {"student_id": student_id, "courses": []}
  +    for g in grades:
  +        c_info = course.get_course_by_id(g["course_id"])
  +        summary["courses"].append({
  +            "course_id": g["course_id"],
  +            "title": c_info["title"],
  +            "credits": c_info["credits"],
  +            "score": g["score"],
  +            "gpa": g["gpa"]
  +        })
  +    return summary
  ```
- **tasks.json 配置欄位**：
  - `task_id`: `"T02"`
  - `task_type`: `"api_usage"`
  - `starter_files`: `["student_system/src/student.py", "student_system/src/grade.py", "student_system/src/course.py"]`
  - `files_to_modify`: `["student_system/src/student.py"]`
  - `allowed_corpus`: `["student_system/API_SPEC.md", "student_system/src/course.py", "student_system/src/grade.py"]`
  - `required_evidence`: `["student_system/API_SPEC.md"]`
  - `grading`: { `required_api_symbols`: `["grade.get_grades_by_student", "course.get_course_by_id", "get_student_by_id"]`, `forbidden_api_symbols`: `["raw_grades", "grades_db"]`, `requirement_checks`: `["Retrieves list of student grade dicts", "Retrieves metadata for each course", "Raises ValueError for non-existent students"]` }

---

### [ ] 3.3 T03: GPA Calculation Bug (Bug Fix)
- **精確路徑**：`student_system/src/grade.py`
- **要修正的 API Signature**：
  ```python
  def score_to_gpa(score: int | float) -> float:
      """
      依據 ISSUES.md 規定轉換 GPA。
      - 90-100 -> 4.0
      - 85-89  -> 3.5
      - 80-84  -> 3.0
      - 75-79  -> 2.5
      - 70-74  -> 2.0
      - 60-69  -> 1.0
      - < 60   -> 0.0
      - 若分數超出 0-100，拋出 ValueError。
      """
  ```
- **Starter 刻意 bug 實作**：
  - 原始實作中，將 `80-89` 統一回傳 `3.0`（遺失了 `3.5` 的對應），且將 `70-74` 回傳為 `1.5`。此外，超出範圍的分數（如 `-5`, `105`）未進行攔截。
- **Public Test (`student_system/tests/public/test_t03.py`)**：
  - 斷言：正常分數與 GPA 轉換。測試 `90` 轉換為 `4.0`；特別包含測試 `85` 轉換為 `3.5`（此點 Starter 會 FAILED，因為 Starter 誤回傳 `3.0`）。
- **Hidden Test (`evaluation/hidden_tests/test_t03.py`)**：
  - 斷言：臨界分數 `85` 必須回傳 `3.5`（Starter 誤回傳 `3.0`）。
  - 斷言：臨界分數 `72` 必須回傳 `2.0`（Starter 誤回傳 `1.5`）。
  - 斷言：輸入 `-1` 或 `101` 必須拋出 `ValueError`。
- **Reference Patch (`evaluation/reference_patches/T03.diff`)**：
  ```diff
  def score_to_gpa(score: int | float) -> float:
+     if not isinstance(score, (int, float)) or isinstance(score, bool):
+         raise ValueError("Invalid score type")
+     if score < 0 or score > 100:
+         raise ValueError("Score out of bounds")
-     if score >= 90: return 4.0
-     if score >= 80: return 3.0
-     if score >= 70: return 1.5
+     if score >= 90: return 4.0
+     if score >= 85: return 3.5
+     if score >= 80: return 3.0
+     if score >= 75: return 2.5
+     if score >= 70: return 2.0
+     if score >= 60: return 1.0
+     return 0.0
  ```
- **tasks.json 配置欄位**：
  - `task_id`: `"T03"`
  - `task_type`: `"bug_fix"`
  - `starter_files`: `["student_system/src/grade.py"]`
  - `files_to_modify`: `["student_system/src/grade.py"]`
  - `allowed_corpus`: `["student_system/API_SPEC.md", "student_system/STYLE_GUIDE.md", "student_system/ISSUES.md"]`
  - `required_evidence`: `["student_system/ISSUES.md"]`
  - `grading`: { `required_api_symbols`: `["score_to_gpa"]`, `forbidden_api_symbols`: `[]`, `requirement_checks`: `["Correctly maps score 85-89 to GPA 3.5", "Correctly maps score 70-74 to GPA 2.0", "Raises ValueError for scores outside [0, 100]"]` }

---

### [ ] 3.4 T04: Score Boundary Type Checking (Bug Fix)
- **精確路徑**：`student_system/src/utils.py`
- **要修正的 API Signature**：
  ```python
  def is_valid_score(score: object) -> bool:
      """
      驗證分數是否為合法數值且在 [0, 100] 內。
      - 必須排除 bool 型別（因為 isinstance(True, int) 為 True）。
      - 非 int 或 float 一律回傳 False。
      """
  ```
- **Starter 刻意 bug 實作**：
  - 原始實作誤寫為：`if score > 0 and score < 100: return True`（排除 `0` 與 `100` 分的邊界，且未過濾非數值。傳入 `"90"` 字串將直接在比較時引發 `TypeError` 崩潰）。
- **Public Test (`student_system/tests/public/test_t04.py`)**：
  - 斷言：驗證邊界值 `0` 與 `100` 必須回傳 `True`（此點 Starter 會 FAILED，因為 Starter 排除 `0` 與 `100`），並驗證一般值 `85` 回傳 `True`。
- **Hidden Test (`evaluation/hidden_tests/test_t04.py`)**：
  - 斷言：邊界值 `0` 與 `100` 必須回傳 `True`。
  - 斷言：傳入 `"80"` (字串)、`[50]` (陣列)、`None`，一律回傳 `False` 且不拋出任何異常。
  - 斷言：傳入 `True` 或 `False`（布林值），一律回傳 `False`。
- **Reference Patch (`evaluation/reference_patches/T04.diff`)**：
  ```diff
  def is_valid_score(score: object) -> bool:
-     if score > 0 and score < 100:
-         return True
-     return False
+     if isinstance(score, bool):
+         return False
+     if not isinstance(score, (int, float)):
+         return False
+     return 0 <= score <= 100
  ```
- **tasks.json 配置欄位**：
  - `task_id`: `"T04"`
  - `task_type`: `"bug_fix"`
  - `starter_files`: `["student_system/src/utils.py"]`
  - `files_to_modify`: `["student_system/src/utils.py"]`
  - `allowed_corpus`: `["student_system/API_SPEC.md", "student_system/STYLE_GUIDE.md", "student_system/ISSUES.md"]`
  - `required_evidence`: `["student_system/ISSUES.md"]`
  - `grading`: { `required_api_symbols`: `["is_valid_score"]`, `forbidden_api_symbols`: `[]`, `requirement_checks`: `["Returns True for 0 and 100", "Returns False for strings, arrays or None without crashing", "Returns False for boolean values True/False"]` }

---

### [ ] 3.5 T05: Score Validation Refactoring (Refactoring)
- **精確路徑**：`student_system/src/utils.py`、`student_system/src/student.py`、`student_system/src/grade.py`
- **重構設計與 API Signature**：
  1. 在 `student_system/src/utils.py` 中，定義全新且完全獨立的驗證函式（不得呼叫 `is_valid_score`）：
     ```python
     def validate_score(score: object) -> None:
         """
         驗證分數是否合法。
         - 若為布林值或非 int/float 類型，拋出 ValueError("Invalid score")。
         - 若數值超出 [0, 100] 區間，拋出 ValueError("Invalid score")。
         - 合規則靜默通過。
         """
         if isinstance(score, bool) or not isinstance(score, (int, float)):
             raise ValueError("Invalid score")
         if score < 0 or score > 100:
             raise ValueError("Invalid score")
     ```
  2. 刪除 `student.py` 與 `grade.py` 中所有硬編碼的分數比較式（如 `score < 0 or score > 100`），改為統一導入並呼叫 `validate_score(score)`。
- **Starter 狀態與陰性設計**：
  - 原始 Starter 狀態下，`utils.py` 中**完全不定義 `validate_score`**，且 `student.py`/`grade.py` 仍保留散落的比較句。
  - **T05 Public Test 設計**：測試中會驗證 `validate_score` 的合法與非法輸入（測試 50 靜默通過，測試 105 拋出 `ValueError`）。**因為 Starter 中此函式不存在，此測試在 Starter 狀態下執行時會百分之百失敗（ImportError/AttributeError）**，保證陰性不變量。
- **Public Test (`student_system/tests/public/test_t05.py`)**：
  - 斷言：呼叫 `utils.validate_score(105)` 必須拋出 `ValueError`。
  - 斷言：呼叫 `utils.validate_score(50)` 靜默通過。
- **Hidden Test (`evaluation/hidden_tests/test_t05.py`)**：
  - 斷言：使用 Python `ast` 模組，載入 `student.py` 與 `grade.py` 的抽象語法樹。
  - 斷言：AST 節點遍歷：確認在 `student.py` 與 `grade.py` 含有分數操作的方法內，**存在調用 `validate_score` 的 Call 節點**（容許 `import utils` 或 `from utils import validate_score` 的等價形式）。
  - 斷言：AST 遍歷：確認 `student.py` 與 `grade.py` 中，**已經徹底不存在對分數進行小於、大於硬編碼比較的 Compare 節點**（例如無 `score < 0` 比較），以確保 DRY 被徹底執行。
- **Reference Patch (`evaluation/reference_patches/T05.diff`)**：
  *包含 `utils.py`、`student.py` 與 `grade.py` 三個檔案的完整修改*：
  ```diff
  *** Begin Patch
  *** Update File: student_system/src/utils.py
  @@ ... @@
  +def validate_score(score: object) -> None:
  +    if isinstance(score, bool) or not isinstance(score, (int, float)):
  +        raise ValueError("Invalid score")
  +    if score < 0 or score > 100:
  +        raise ValueError("Invalid score")
  *** Update File: student_system/src/grade.py
  @@ ... @@
  +from student_system.src.utils import validate_score
   def add_grade(student_id, course_id, score):
  -    if score < 0 or score > 100:
  -        raise ValueError("Invalid Score")
  +    validate_score(score)
  *** Update File: student_system/src/student.py
  @@ ... @@
  +from student_system.src.utils import validate_score
   def update_student_score(student_id, score):
  -    if score < 0 or score > 100:
  -        raise ValueError("Invalid Score")
  +    validate_score(score)
  *** End Patch
  ```
- **tasks.json 配置欄位**：
  - `task_id`: `"T05"`
  - `task_type`: `"refactoring"`
  - `starter_files`: `["student_system/src/utils.py", "student_system/src/student.py", "student_system/src/grade.py"]`
  - `files_to_modify`: `["student_system/src/utils.py", "student_system/src/student.py", "student_system/src/grade.py"]`
  - `allowed_corpus`: `["student_system/STYLE_GUIDE.md", "student_system/src/utils.py", "student_system/src/student.py", "student_system/src/grade.py"]`
  - `required_evidence`: `["student_system/STYLE_GUIDE.md"]`
  - `grading`: { `required_api_symbols`: `["validate_score"]`, `forbidden_api_symbols`: `[]`, `requirement_checks`: `["Extracts utils.validate_score to enforce DRY", "Integrates validation across student and grade modules", "Eliminates duplicate boundary comparisons"]` }

---

## 四、 測試套件執行與獨立隔離性驗證計畫

為防止任務之間互相依賴干擾，M2 的驗收測試必須使用嚴格的「隔離沙盒沙盤推演」。

### 4.1 每題獨立執行之不變量 (Independence Invariant)
1. 驗收時，將先建立一個乾淨 Workspace。
2. 逐題（例如對於 T01）拷貝乾淨的 Starter Snapshot 到 Workspace。
3. 此時，若對其執行 T01 公開測試套件：
   ```bash
   python -m pytest student_system/tests/public/test_t01.py -v
   ```
   **預期必須：FAILED**（因 Starter 狀態尚未修正該題）。
4. 接續套用對應的 Reference Patch：
   ```bash
   patch -p1 < evaluation/reference_patches/T01.diff
   ```
5. 再次執行該題的 Public 與 Hidden 測試：
   ```bash
   python -m pytest student_system/tests/public/test_t01.py evaluation/hidden_tests/test_t01.py -v
   ```
   **預期必須：PASSED**（證明單獨修正此題，即可使其完全通過，不需要任何其他題目的修正）。
6. 清除 Workspace，重複以上流程驗證下一題，確保 100% 的任務獨立性。

---

## 五、 `student_system/SNAPSHOT.json` 範圍收斂設計

為了徹底防範測試洩露（No Leakage），`SNAPSHOT.json` 僅能包含 Starter 原始碼與公開文件，嚴禁包含 Hidden Tests、Reference Patches、`tasks.json` 或結果日誌。

### 5.1 Snapshot 規格
- **`path` 格式**：一律使用相對於專案根目錄的 Repo-root-relative 路徑。
- **`sha256` 格式**：64 位十六進位小寫字串。
- **配置清單**：
  ```json
  {
    "snapshot_id": "snap_v1_starter_20260611",
    "created_at": "2026-06-11T12:00:00Z",
    "files": [
      { "path": "student_system/README.md", "sha256": "[sha256-hex]" },
      { "path": "student_system/API_SPEC.md", "sha256": "[sha256-hex]" },
      { "path": "student_system/STYLE_GUIDE.md", "sha256": "[sha256-hex]" },
      { "path": "student_system/ISSUES.md", "sha256": "[sha256-hex]" },
      { "path": "student_system/src/student.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/src/course.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/src/grade.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/src/utils.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/tests/public/test_t01.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/tests/public/test_t02.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/tests/public/test_t03.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/tests/public/test_t04.py", "sha256": "[sha256-hex]" },
      { "path": "student_system/tests/public/test_t05.py", "sha256": "[sha256-hex]" }
    ]
  }
  ```

---

## 六、 實作步驟 Checkbox 計畫 (紅-綠-黃 TDD 順序)

### [ ] Phase 1: 基礎文件與骨架初始化 (Setup)
- [ ] 1. 建立 `student_system/` 目錄與對應之 `.gitkeep` 保留檔。
- [ ] 2. 撰寫 `student_system/README.md`、`student_system/API_SPEC.md`。
- [ ] 3. 撰寫 `student_system/STYLE_GUIDE.md`、`student_system/ISSUES.md`。
- [ ] 4. 撰寫 Starter 原始碼（刻意漏洞狀態）：
  - 建立 `student_system/src/student.py` (Mock 數據加載)。
  - 建立 `student_system/src/course.py` (Mock 數據加載)。
  - 建立 `student_system/src/grade.py` (包含 GPA Bug, 無 calculate_pass_rate)。
  - 建立 `student_system/src/utils.py` (包含 `is_valid_score` 缺陷, 無 `validate_score`)。
- [ ] 5. *執行命令*：`python -c "import student_system.src.utils as u; print(hasattr(u, 'validate_score'))"`
- [ ] *預期結果*：`False` (確認起始狀態合規)。

### [ ] Phase 2: 陰性與不變量測試建立 (Red)
- [ ] 1. 撰寫 5 個公開測試套件：
  - `student_system/tests/public/test_t01.py` 至 `test_t05.py`。
- [ ] 2. 撰寫 5 個隱藏測試套件（嚴格杜絕洩露）：
  - `evaluation/hidden_tests/test_t01.py` 至 `test_t05.py`。
- [ ] 3. *逐題執行公開測試，驗證陰性失敗*：
  - *命令1*：`python -m pytest student_system/tests/public/test_t01.py -v` -> *預期*：**FAILED**
  - *命令2*：`python -m pytest student_system/tests/public/test_t02.py -v` -> *預期*：**FAILED**
  - *命令3*：`python -m pytest student_system/tests/public/test_t03.py -v` -> *預期*：**FAILED** (測試 85分等臨界 GPA)
  - *命令4*：`python -m pytest student_system/tests/public/test_t04.py -v` -> *預期*：**FAILED** (測試邊界)
  - *命令5*：`python -m pytest student_system/tests/public/test_t05.py -v` -> *預期*：**FAILED** (測試 validate_score 是否存在)

### [ ] Phase 3: 參考修正與不變量通過驗證 (Green)
- [ ] 1. 在 `evaluation/reference_patches/` 下撰寫 `T01.diff` 至 `T05.diff`。
- [ ] 2. *逐題套用 Reference Patch，驗證通過*：
  - [ ] 套用 T01.diff -> 執行 `pytest student_system/tests/public/test_t01.py evaluation/hidden_tests/test_t01.py` -> *預期*：**PASSED** -> 復原 T01
  - [ ] 套用 T02.diff -> 執行 `pytest student_system/tests/public/test_t02.py evaluation/hidden_tests/test_t02.py` -> *預期*：**PASSED** -> 復原 T02
  - [ ] 套用 T03.diff -> 執行 `pytest student_system/tests/public/test_t03.py evaluation/hidden_tests/test_t03.py` -> *預期*：**PASSED** -> 復原 T03
  - [ ] 套用 T04.diff -> 執行 `pytest student_system/tests/public/test_t04.py evaluation/hidden_tests/test_t04.py` -> *預期*：**PASSED** -> 復原 T04
  - [ ] 套用 T05.diff -> 執行 `pytest student_system/tests/public/test_t05.py evaluation/hidden_tests/test_t05.py` -> *預期*：**PASSED** -> 復原 T05

### [ ] Phase 4: 配置與快照鎖定 (Yellow)
- [ ] 1. 撰寫符合 M1 標準 Draft 2020-12 規範的 `experiments/tasks.json`。
- [ ] 2. 執行校驗：確認 `required_evidence` 是 `allowed_corpus` 的子集，且路徑皆為 repo-root-relative。
- [ ] 3. 執行檢索安全校驗：確認 `tasks.json` 與 `student_system/SNAPSHOT.json` 中，**絕對不含有** `evaluation/hidden_tests` 與 `evaluation/reference_patches` 的任何路徑字眼。
- [ ] 4. 計算 `student_system` 下所有文件、原始碼與公開測試的 SHA-256，寫入 `student_system/SNAPSHOT.json`。
- [ ] 5. *執行驗證器檢查*：確認所有 JSON Schema 均使用標準之 `Draft202012Validator.check_schema(...)` 驗證。
- [ ] *預期結果*：順利完成 M2 驗收，系統回歸乾淨 Starter 狀態。

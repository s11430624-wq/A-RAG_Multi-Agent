# Open Issues & Defect Logs

本文件詳細記錄當前系統中已知的刻意缺陷（Defects）與漏洞，作為 Bug Fix 與 Refactoring 任務之需求來源。

## Issue #1: GPA 映射缺陷 (Affects: `student_system/src/grade.py`)
- **描述**：`score_to_gpa` 邏輯中有嚴重缺陷：
  - 85-89 分轉為 GPA 時，被錯誤對照成了 `3.0`（根據 API 規格應為 `3.5`）。
  - 70-74 分轉為 GPA 時，被錯誤對照成了 `1.5`（根據 API 規格應為 `2.0`）。
  - 超出 [0, 100] 範圍的異常輸入（負數或大於 100），系統未做例外處理。

## Issue #2: 分數合法性驗證與邊界缺陷 (Affects: `student_system/src/utils.py`)
- **描述**：`is_valid_score` 實作有瑕疵：
  - 誤排除 `0` 與 `100` 分的合法臨界值（若為 0 或 100 分則會返回 `False`）。
  - 當傳入 `"90"` (字串)、`[50]` (陣列)、`None` 或布林值 `True/False` 時，由於未進行過濾，會直接引發 `TypeError` 崩潰，應對不合規型別回傳 `False`。

## Issue #3: 重複的檢驗與重複程式碼 (DRY Principle Violation)
- **描述**：`student.py` 與 `grade.py` 在寫入或更新成績時，均各自硬編碼了 `if score < 0 or score > 100: raise ValueError("Invalid Score")`。
- **重構要求**：在 `utils.py` 中抽取定義獨立的 `validate_score(score: object) -> None`，並在兩模組中導入呼叫，清除重複邏輯。

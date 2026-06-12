# Student Information Management System (student_system)

本系統是一個精簡的小型學生資訊管理系統，用作 A-RAG × Multi-Agent 整合實驗的測試對象。

## 系統模組架構

- `student_system/src/student.py`：管理學生基本資料。
- `student_system/src/course.py`：管理課程基本資料。
- `student_system/src/grade.py`：管理學生成績與 GPA 計算。
- `student_system/src/utils.py`：通用數值與格式驗證工具。

## 測試執行

本系統使用 `pytest` 執行公開測試：
```bash
python -m pytest student_system/tests/public -v
```
所有修改必須遵循 `STYLE_GUIDE.md` 規範，且僅能在規定的題目範圍內，以 `unified diff` 形式進行修改。

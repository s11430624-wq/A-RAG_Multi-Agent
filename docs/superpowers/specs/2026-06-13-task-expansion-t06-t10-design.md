# T06-T10 Task Expansion Design

日期: 2026-06-13

## 目標

在現有 `student_system` 題庫 `T01` 到 `T05` 之外，新增 5 題更高難度但仍可穩定評測的任務，作為後續人工或代理實驗的進階題組。

本批新增題目採用混合型高難度設計，不追求刁鑽，而是追求以下三點：

1. 更高的跨模組整合需求
2. 更明確的 hidden 邊界與排序/驗證陷阱
3. 更能拉開 `A / C / E` 三種策略的實際差異

## 設計原則

### 1. 保持同一個小系統

所有題目都限定在既有的 `student_system` 內完成，不新增外部依賴，不引入資料庫、不引入新框架。

### 2. 难度提升方向

本批 5 題的難度提升主要來自：

- 同時整合 `student.py`、`course.py`、`grade.py`、`utils.py`
- 排序穩定性
- 空資料與不存在資料的區分
- 嚴格 API 邊界
- 受限重構而非自由改寫

### 3. Hidden 測試要有資訊價值

Public tests 應提供足夠方向，避免題目不透明；hidden tests 則用來檢查：

- 是否使用核准 API，而非偷讀內部資料結構
- 排序 tie-break 是否正確
- rounding 是否依 `round(x, 4)`
- 型別與布林值等邊界處理是否穩定
- 是否誤把「存在但空資料」與「不存在」混成同一情況

### 4. 與既有 schema 相容

所有新題仍需符合 `contracts/task.schema.json`：

- `task_id`: `T06` 到 `T10`
- `difficulty`: 採 `hard`
- `task_type`: 僅使用既有 enum
- `limits.max_repair_rounds`: 維持 `2`

## 題型配置

本批 5 題按類型分配如下：

- 2 題跨模組整合
- 2 題規格陷阱 / hidden 易錯
- 1 題受限重構

---

## T06: Student Transcript Summary

### 定位

跨模組整合題。

### 題目目標

在 `student.py` 中新增 `get_student_transcript_summary(student_id: str) -> dict`，回傳某學生的完整修課摘要。

### 建議輸出結構

```python
{
    "student_id": "S001",
    "name": "Alice",
    "total_courses": 2,
    "total_credits": 7,
    "passed_courses": 2,
    "pass_rate": 1.0,
    "average_gpa": 3.5,
    "courses": [
        {
            "course_id": "C001",
            "title": "Mathematics",
            "credits": 3,
            "score": 85,
            "gpa": 3.5,
            "passed": True,
        },
        ...
    ],
}
```

### 應修改檔案

- `student_system/src/student.py`

### 可讀證據

- `student_system/API_SPEC.md`
- `student_system/src/grade.py`
- `student_system/src/course.py`

### 難點

- 需要整合學生、成績、課程資料
- `courses` 需要穩定排序，建議以 `course_id` 升冪
- `average_gpa` 與 `pass_rate` 都要 `round(..., 4)`
- 對不存在學生應拋出 `ValueError`
- 對存在但沒有成績的學生，應回傳空 `courses` 與 `0.0` 統計值，而不是拋錯

### Hidden 重點

- 是否直接偷讀 `_STUDENTS`、`_COURSES`、`_GRADES`
- 是否錯把無成績視為不存在
- 是否在 GPA 平均時使用 grade record 內既有 `gpa`，而非用 `score_to_gpa` 重算；兩者哪個作為唯一正解，需在任務文案中明確規範

### 推薦規範

明確要求以 `score_to_gpa(score)` 作為 GPA 真值來源，避免舊資料欄位與 API 規格產生衝突。

---

## T07: Course Leaderboard

### 定位

規格陷阱題。

### 題目目標

在 `course.py` 中新增 `get_course_leaderboard(course_id: str) -> list[dict]`，回傳某課程學生排行榜。

### 建議輸出結構

每個元素包含：

```python
{
    "rank": 1,
    "student_id": "S001",
    "name": "Alice",
    "score": 90,
    "gpa": 4.0,
}
```

### 應修改檔案

- `student_system/src/course.py`

### 可讀證據

- `student_system/API_SPEC.md`
- `student_system/src/student.py`
- `student_system/src/grade.py`

### 排序契約

先按 `score` 降冪，再按 `student_id` 升冪。

`rank` 採 1-based 連續排名，不做同分跳號。

### 難點

- 不存在課程應拋出 `ValueError`
- 存在但無成績的課程應回傳空列表
- GPA 值應根據 `score_to_gpa(score)` 產生
- hidden 很適合放 tie-break 與空課程案例

### Hidden 重點

- 是否使用 `get_course_by_id` 做存在性驗證
- 是否誤用 `get_students_by_course` 導致排序資料不足
- 是否在同分學生的排序上不穩定

---

## T08: Honor Roll Students

### 定位

跨模組整合題。

### 題目目標

在 `student.py` 中新增 `get_honor_roll_students(min_average_gpa: float = 3.0) -> list[dict]`，回傳符合榮譽資格的學生名單。

### 建議資格規則

學生必須同時符合：

1. 至少修過 1 門課
2. 所有已修課程皆及格
3. 平均 GPA 大於等於 `min_average_gpa`

### 建議輸出結構

```python
{
    "student_id": "S001",
    "name": "Alice",
    "average_gpa": 3.75,
    "total_courses": 2,
}
```

### 應修改檔案

- `student_system/src/student.py`

### 可讀證據

- `student_system/API_SPEC.md`
- `student_system/src/grade.py`

### 排序契約

先按 `average_gpa` 降冪，再按 `student_id` 升冪。

### 難點

- 需對所有學生做聚合
- 需明確區分「沒修課」與「修課但不及格」
- `min_average_gpa` 可能本身不合法，是否要驗證需在題目中明訂

### Hidden 重點

- 浮點 rounding 是否在比較前後一致
- 是否直接用 grade record 的舊 `gpa` 欄位，而不是依 API 規格重算
- 是否將部分及格學生錯誤納入 honor roll

### 推薦規範

要求 `min_average_gpa` 若不在 `[0.0, 4.0]` 區間則拋出 `ValueError`，可提升題目邊界價值。

---

## T09: Bulk Score Update Preview

### 定位

規格陷阱題。

### 題目目標

在 `grade.py` 中新增 `preview_bulk_score_update(updates: list[dict]) -> dict`，對一批分數更新請求做驗證與預覽，但不實際寫入。

### 建議輸入格式

```python
[
    {"student_id": "S001", "course_id": "C001", "score": 88},
    ...
]
```

### 建議輸出結構

```python
{
    "valid_updates": [...],
    "invalid_updates": [...],
    "summary": {
        "total": 3,
        "valid": 2,
        "invalid": 1,
    },
}
```

### 驗證規則

每筆更新需驗證：

- `student_id` 存在
- `course_id` 存在
- `score` 合法

### 應修改檔案

- `student_system/src/grade.py`

### 可讀證據

- `student_system/API_SPEC.md`
- `student_system/src/student.py`
- `student_system/src/course.py`
- `student_system/src/utils.py`

### 難點

- 題目不是單純丟錯，而是要回傳結構化驗證結果
- 對 `bool`、`None`、字串數字等輸入要穩定處理
- 可在 hidden 中加入重複更新紀錄，測是否保留順序或做重複判定

### Hidden 重點

- 是否使用 `validate_score`
- 是否因某一筆錯誤就中斷整批，而不是逐筆收集結果
- 是否改動了全域資料，違反 preview 契約

### 推薦規範

明定此函式不得修改任何現有資料，且回傳順序需與輸入順序一致。

---

## T10: Validation and Aggregation Refactor

### 定位

受限重構題。

### 題目目標

重構 `student_system` 中與成績摘要有關的重複邏輯，新增一個共享 helper，但不得改壞既有公開 API 的簽名與行為。

### 推薦方向

在 `utils.py` 新增：

```python
def summarize_grade_records(records: list[dict]) -> dict:
    ...
```

回傳：

- `total_courses`
- `passed_courses`
- `pass_rate`
- `average_gpa`

然後要求 `T06`、`T08` 等後續功能使用此 helper，或在題目中限定只需重構既有新函式共用邏輯。

### 應修改檔案

- `student_system/src/utils.py`
- `student_system/src/student.py`

### 可讀證據

- `student_system/STYLE_GUIDE.md`
- `student_system/API_SPEC.md`
- `student_system/src/grade.py`

### 難點

- 這不是自由重寫，而是受限抽取
- 不可破壞既有函式輸出
- helper 本身要處理空列表與 rounding
- hidden 可測 helper 是否偷偷依賴外部模組狀態

### Hidden 重點

- 是否讓 helper 變得過度耦合
- 是否改壞既有 T06/T08 輸出格式
- 是否在重構後漏掉空資料 case

---

## 題目間的相依建議

為避免新題彼此形成過強依賴，建議：

- `T06`、`T07`、`T08` 都可以獨立完成
- `T09` 獨立存在，不依賴 `T06-T08`
- `T10` 可作為最後一題，明確宣告是受限重構題

這樣的好處是：

1. 不會因前一題做壞而讓後續題目全部污染
2. 人工或代理跑單題時更容易隔離問題
3. A / C / E 的差異可以在更多維度上被觀察，而不是被題目鏈式依賴綁死

## 對 A / C / E 差異的預期

### A

較可能在：

- 排序規格細節
- hidden 邊界
- 跨模組 API 選擇

上失分。

### C

理論上在整合題會比 A 更穩，但如果 Planner/Reviewer 的格式控制不佳，仍可能在規格陷阱題浪費回合。

### E

若檢索策略正常，應最有機會在：

- 證據核對
- API 邊界遵守
- hidden 契約保持

上表現最好；但前提是 retrieval 成本不能反過來壓垮修復空間。

## 推薦下一步

下一步不要直接一次做完全部，而是分兩段：

1. 先把 `T06-T10` 寫入 `experiments/tasks.json`
2. 再補 `student_system/tests/public/test_t06.py` 到 `test_t10.py`

建議實作順序：

1. `T07`
2. `T06`
3. `T08`
4. `T09`
5. `T10`

原因是 `T07` 最單純，最適合先驗證高難度排序題的測試語氣；`T10` 則最適合最後做，因為它會回頭吃掉前面題目的共用邏輯。

## 明確不做的事

本設計階段不做以下事情：

- 不修改 `experiments/tasks.json`
- 不新增 public tests
- 不新增 hidden tests
- 不改動 `student_system/src/*`
- 不碰現有 M7 實驗輸出與里程碑資料

## 設計結論

本批 `T06-T10` 應採「混合型高難度」方案，核心不是增加語句複雜度，而是增加：

- API 邊界遵守成本
- 跨模組整合密度
- hidden 邊界的資訊價值

若後續要落地，我們可以在不改變整體框架的前提下，把這 5 題直接接到現有 `tasks.json + public tests` 工作流中。

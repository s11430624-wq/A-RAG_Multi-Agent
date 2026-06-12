# Code Style Guide

本系統遵循以下 Python 撰寫標準，在人工評分與 Reviewer 盲審時將嚴格依此計分。

## 1. 命名規範
- 變數與函式名稱統一採用 `snake_case`（例如：`calculate_pass_rate`）。
- 類別名稱採用 `PascalCase`（本系統 M2 全數改為模組函式，但若涉及類別則須遵循此項）。

## 2. 類型標註 (Type Hints)
- 所有新增或重構的函式，其 Signature 必須標明明確的型別（Type Hints）。
- 嚴禁使用 built-in `any` 當作型別（`any` 是內建函式），如果需要表示任意型別，必須使用 `object`。
- 數值分數的型別標註統一使用 `int | float`。

## 3. 例外與錯誤處理
- 嚴禁使用寬泛的 `except Exception:` 抓取所有錯誤。
- 拋出例外時，必須採用 Python 標準內建例外：
  - 引數不合規、無效或超出預期區間時，必須拋出 **`ValueError`**。
  - 型別不符時，可選擇拋出 **`ValueError`** 或 **`TypeError`**。

## 4. 數值與精度規範
- 及格比例、平均 GPA 等統計回傳之 `float` 值，必須一律使用 `round(val, 4)` 四捨五入保留至小數點後第四位。

# Milestone 7-C.1: Reasoning Token Accounting Decision Plan

**Milestone:** 7-C.1 (Reasoning Token Accounting Decision Plan)  
**Status:** Planning Completed (Ready for Implementation Phase)  
**Date:** 2026-06-11  

---

## 1. 背景與問題陳述

在 Milestone 7-C 的單次 Live Probe 中，`google/gemini-3.5-flash` 經由本機 Local Vertex Proxy 回傳的 `usage` 物件如下：

```json
{
  "prompt_tokens": 8,
  "completion_tokens": 1,
  "total_tokens": 102,
  "completion_tokens_details": {
    "reasoning_tokens": 93
  }
}
```

這導致了計數不一致：
$$\text{prompt\_tokens} (8) + \text{completion\_tokens} (1) = 9 \neq \text{total\_tokens} (102)$$

### 原因分析：
Google Vertex AI 的相容介面將 **93 個推理標記 (Reasoning Tokens)** 歸類在 `completion_tokens_details.reasoning_tokens` 下，並計入 `total_tokens`，但**並未**累加至外層的 `completion_tokens`（其外層僅代表可見的輸出文字 token 數，即 1）。  
這導致 A-RAG 系統既有的 `Usage` 不變量約束斷言失敗（`total_tokens must equal input_tokens + output_tokens`），系統正確地觸發 **Fail-Closed** 安全阻斷，使得 M7-D Smoke Runs 無法執行。

---

## 2. 方案比較 (Options Analysis)

### 方案 A：Strict OpenAI Usage Only
* **運作機制：** 保持現有不變量 `input_tokens + output_tokens == total_tokens`。若發現任何 reasoning token 導致的計數 mismatch，一律不予寬限，直接拋出例外 fail closed。
* **優點：** 
  - 邏輯最保守、最安全。
  - 結果欄位語意最純粹、乾淨，不需做任何轉換。
* **缺點：** 
  - `google/gemini-3.5-flash` 模型將永遠無法在 A-RAG 系統中運行 Smoke 或 Full Run 實驗。
* **評價：** 無法解決多模型相容評估的商業目標。

### 方案 B：Provider-Specific Usage Normalization (推薦方案)
* **運作機制：** 
  - 接受 `completion_tokens_details.reasoning_tokens`。
  - 將 `output_tokens` 進行正規化投影，定義為「可計費/運算輸出標記數」：
    $$\text{normalized\_output\_tokens} = \text{completion\_tokens} + \text{reasoning\_tokens}$$
  - 將投影結果映射至現有的 `Usage` 合約中：
    - `input_tokens = prompt_tokens`
    - `output_tokens = normalized_output_tokens`
    - `total_tokens = total_tokens`
    - `source = "provider_normalized"`
  - **保留完整審計追蹤 (Raw Audit Metadata)：**  
    在不變更既有 `Usage` 類別定義的情況下，將原始資料（如 `raw_completion_tokens`、`reasoning_tokens`、`normalization_rule`）以鍵值對形式存入 `ModelResponse.sanitized_metadata` 中，並隨著結果寫入 `raw_results.jsonl` 以供後續核帳與稽核。
* **優點：** 
  - **完全不需變更資料庫/結果 JSON Schema**，相容 M1-M6 既有管線與下游 `derived.py` 的 CSV 轉換邏輯。
  - 保留了 `input + output == total` 的核心不變量約束。
  - 能夠真實、準確地反映該模型的 token 消耗成本（Reasoning Tokens 是收費與耗能的實體）。
* **缺點：** 
  - `output_tokens` 在此模式下不僅代表「可見文字」，而是「實質運算輸出 token 數」，容易造成字面語意混淆，因此必須加強命名規範與 metadata 審計追蹤。
* **評價：** **最優平衡方案**，兼顧了管線不變量、下游相容性，且能順利將 Gemini / o1 等推理模型納入評估。

### 方案 C：Schema Extension
* **運作機制：** 直接修改底層 Result Schema 與資料合約，增加 `reasoning_tokens` 與 `raw_completion_tokens` 等專屬欄位。
* **優點：** 
  - 語意最完整，不需做任何投影或正規化。
* **缺點：** 
  - 影響層面極大。需要重構所有 M1-M6 既有的資料庫合約、`derived.py` 報表轉換、自動評估、手動評分（Manual Review）、測試套件，極易引發 Regression 風險，不符合現有 Milestone 收斂規則。
* **評價：** 風險過高，在 M7 實驗階段應避免進行破壞性 Schema 變查。

---

## 3. 推薦方案 B 詳細設計與決策細節 (M7-C.1 Decision)

本決策完全採納 **方案 B (Provider-Specific Usage Normalization)**，具體規範如下：

### (1) Normalized Usage Contract (正規化不變量合約)
當 Provider 啟動正規化時，回傳的 `Usage` 物件必須嚴格遵守以下物理約束：
- `Usage.input_tokens` 必須等於 `prompt_tokens`。
- `Usage.output_tokens` 必須等於 `completion_tokens` (可見) + `reasoning_tokens` (思考)。
- `Usage.total_tokens` 必須等於 `input_tokens + output_tokens`。
- `Usage.source` 必須標記為 `"provider_normalized"`。

### (2) Raw Usage Audit Fields 存放位置
為了確保可稽核性，原始（Raw）數據將被捕獲並保存在：
- 保存於 `ArtifactManifest` 的 `call_records` 中，其對應的 `ModelCallRecord` 新增 `audit_metadata: tuple[tuple[str, str], ...]` 欄位：
  - `("raw_completion_tokens", "1")`
  - `("reasoning_tokens", "93")`
  - `("normalization_rule", "google_vertex_reasoning_accumulation")`
  - `("usage_source", "provider_normalized")`
  - `("normalized_output_tokens", "94")`
- 絕不更改 `result.schema.json` 也不在 `raw_results.jsonl` 中新增 root-level 欄位，維持極高安全性。

### (3) Result Schema 修改需求：**不需要**
- 因方案 B 完美將正規化 token 投影至現有 `output_tokens`，且將審計資訊塞入 `ArtifactManifest` 中，故 **100% 不需要修改底層的 Result Schema 或資料庫 Schema**。

### (4) Provider Parser 修改範圍
- 僅限於 `experiments/providers/openai_compatible.py` 中的 `_parse_usage` 輔助函數。
- 當解析 `usage` 字典時，若偵測到 `completion_tokens_details.reasoning_tokens` 存在且大於 0：
  - 應讀取該值。
  - 將其累加至 `output_tokens`。
  - 將原始資訊（`raw_completion_tokens`、`reasoning_tokens`、`rule`）整理後寫入 metadata。
- 絕不更動此檔案以外的任何 Runner、Orchestrator 或 DB 邏輯。

### (5) Probe Contract 升級細節
- `experiments/live/probe.py` 中的 `GatewayProbe` 依然維持 `prompt_tokens + completion_tokens == total_tokens` 的校驗（此時其拿到的 `completion_tokens` 是已經過 Provider 累加正規化後的輸出）。
- 同時，探針必須斷言：當 `source == "provider_normalized"` 時，其 `sanitized_metadata` 內必須存在合法的原始審計紀錄，藉此達成「雙重校驗」。

### (6) Smoke Gate 的 Usage 完整性判定
- `SmokeGateReport` 判定 `usage_complete` 的條件為：
  - 所有 3 次實驗運行的 `usage` 皆非空。
  - 每個運行的 `total_tokens` 與 `input_tokens + output_tokens` 嚴格相等。
  - 若 `source == "provider_normalized"`，必須審計該運行是否正確追蹤並記錄了原始 token metadata。

### (7) Derived CSV token 欄位保存
- 下游轉換工具 `experiments/runner/derived.py` 在產出 CSV 時，依然讀取主 `input_tokens` 與 `output_tokens`，不需新增特殊欄位，無痛相容。
- 由於累積後的 `output_tokens` 同時包含了推理費用，因此其計算的「重複運行累計 cost」與「token 預算線」將會 100% 準確，不會漏計推理成本。

### (8) 未知 Provider 與缺失 Reasoning Token 的 Fail-Closed 規則
- 若未知 Provider 發生 token 計數不一致，且其回應中**完全沒有** `completion_tokens_details.reasoning_tokens` 字段：
  - 系統拒絕做任何通融或猜測，立即拋出 `ProviderUsageUnavailableError` 並 **Fail-Closed 阻斷**。
- 若 `completion_tokens_details` 存在但其 `reasoning_tokens` 的值非整數或為負數：
  - 拒絕正規化，拋出 `ProviderMalformedResponseError`，**Fail-Closed 阻斷**。

### (9) 驗證絕對不會使用 Tokenizer 猜測 Token 的測試策略
- A-RAG 系統內建的 `openai_compatible.py` 在解析時：
  - 若 `usage` 物件為 `None`，必須嚴格遵循 M5 契約拋出 `ProviderUsageUnavailableError`，**禁止導入任何 tiktoken、sentencepiece 或任何 local tokenizer 庫進行估算**。
- 必須在單元測試中，模擬 `usage` 缺失的 HTTP 200 響應，並斷言其必定會拋出 `ProviderUsageUnavailableError`，且未加載任何 tokenizer 模組。

### (10) 避免不同 Provider 混用 Normalization Rule
- 每一條正規化規則都必須與 `ProviderConfig.provider_id` 綁定。
- 目前僅允許 `"hermes_vertex_gateway"`（且模型為支援 reasoning 的 `google/gemini-3.5-flash`）套用 `google_vertex_reasoning_accumulation` 規則。
- 其他 provider (例如標準 openai、anthropic 等) 若無顯式配置與對應的 provider 標記，一律禁止套用此正規化累加。

---

## 4. 下一步規劃

1. 本輪**嚴禁執行任何程式碼修改與實作**。
2. 後續待 M7-C.1 決策計畫核准後，將在 M7-C.2 的 TDD 任務中：
   - 實作 `openai_compatible.py` 的 `_parse_usage` 修正。
   - 新增詳細的對齊與安全測試，徹底解除 M7-D 的 Blocker，方可准入 Smoke Runs。

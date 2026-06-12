# Milestone 7-C Live Probe Report

**Milestone:** 7-C (Single Live Probe Verification)  
**Status:** M7-C Diagnostic Completed, Smoke Approval Denied (Fail-Closed Verified)  
**Date:** 2026-06-11  

---

## 1. Readiness Check Results

1. **`configs/models.yaml` 靜態檢驗:**  
   - `default_model` 確實配置為 `"google/gemini-3.5-flash"`。  
   - `hermes_vertex_gateway.api_base` 確實配置為 `"http://127.0.0.1:8787/v1"`。  
   - [OK] 檢查符合 M7-B 核准之本機安全契約。  

2. **OS 埠口聆聽狀態 (Port Check):**  
   - 經使用 OS socket connection 檢測，本機 `127.0.0.1:8787` 正處於 **LISTENING** 狀態，可成功建立連線。  
   - [OK] 服務端已就緒，且此檢查未讀取任何 `.json` 憑證或 `share-session.json` 分享檔案。  

3. **M7-B 傳輸層加固狀態 (M7-B Transport Gating):**  
   - 經 LiveProviderFactory 實體化 `google/gemini-3.5-flash` 之 provider。  
   - 驗證 `no_auth_loopback` 模式處於 **`True`** 狀態。  
   - 驗證 Client 傳輸層在建立請求時完全不傳送 `Authorization` 標頭，且禁止 Caller 手動注入。  
   - [OK] 傳輸層邊界安全無漏失。  

---

## 2. Single Live Probe 執行與回應分析

在確認 Readiness 安全就緒後，發起一次最小化單體 Live Probe 到 `POST http://127.0.0.1:8787/v1/chat/completions`。

### 實際回應指標 (Response Metrics)

- **HTTP Status:** `200 OK` (OK)
- **Response Model (回應模型識別碼):** `google/gemini-3.5-flash` (與預期模型一致，OK)  
- **Finish Reason:** `"stop"` (完美符合完成原因 stop 字樣, OK)  
- **Provider Request ID:** `fV8qauqHLY6R9tMPg-uF4QY` (存在且由 Google 正常產出, OK)  
- **實際 Usage 欄位內容:**  
  ```json
  {
    "completion_tokens": 1,
    "completion_tokens_details": {
      "reasoning_tokens": 93
    },
    "extra_properties": {
      "google": {
        "traffic_type": "ON_DEMAND"
      }
    },
    "prompt_tokens": 8,
    "total_tokens": 102
  }
  ```

---

### 3. 關鍵漏洞阻擋事件：Token 計數不一致阻斷器 (Critical Capability Mismatch Blocker)

- **漏洞檢測結果:** **FAIL CLOSED** (安全阻斷，阻擋後續 smoke/full run，不寫入任何 smoke result、不產生 raw JSONL、不建立/污染任何 workspace 檔案)  
- **阻擋原因 (Blocker Detail):**  
  在對 Usage 物件實施 A-RAG 契約校驗時，觸發了嚴格的計數不合理阻斷：  
  $$\text{prompt\_tokens} (8) + \text{completion\_tokens} (1) = 9 \neq \text{total\_tokens} (102)$$  
- **不一致明細 (Usage Mismatch Detail):**
  - `prompt_tokens` = 8
  - `completion_tokens` = 1
  - `reasoning_tokens` = 93
  - `total_tokens` = 102
- **根本原因 (Root Cause):**  
  Google Vertex AI 平台對 Gemini 3.5 Flash 進行 OpenAI-compatible 轉換時，將 **93 個推理思考標記 (Reasoning Tokens)** 歸類在 `completion_tokens_details.reasoning_tokens` 下，並加總進 `total_tokens`。  
  然而，Google 並未將這些思考標記累加至外層的主 `completion_tokens` 中，導致：  
  $$\text{completion\_tokens} = 1$$  
  這使得 `prompt_tokens (8) + completion_tokens (1) = 9` 與 `total_tokens (102)` 產生巨大的計數矛盾，直接觸發 `Usage` 類別內置的 `ValueError("total_tokens must equal input_tokens + output_tokens")`，進而 Fail-Closed 阻斷。

---

## 4. 決策與建議 (Resolution & Next Steps)

1. **嚴禁修改 M5 Provider / Production 程式碼:**  
   遵循 M7-C 指示「請不要硬改 production，先回報 capability mismatch blocker」。我們已安全地將系統導向 Fail-Closed 狀態，有效阻止了任何未校準的 Smoke 與批次實驗。
2. **另開 M7-C.1 Compatibility Decision:**  
   下一步**絕對不是進入 M7-D**。我們已在 [M7-C.1 決策文件](<C:/上課檔案/報告/A-RAG_Multi-Agent/docs/superpowers/plans/2026-06-11-m7c1-reasoning-token-accounting.md>) 與 [M7-C.1 驗收計畫](<C:/上課檔案/報告/A-RAG_Multi-Agent/docs/milestones/M7C1_acceptance.md>) 中完成「方案 B：Provider-Specific Usage Normalization」的合約不變量設計：
   - **不變量合約：** $\text{output\_tokens} = \text{completion\_tokens} + \text{reasoning\_tokens}$，以此確保 $input\_tokens + output\_tokens == total\_tokens$。
   - **審計 metadata 追蹤：** 原始數據保存於 `ArtifactManifest` 的 `call_records` 中，絕不更動資料庫 Schema 或 `raw_results.jsonl` 的 root record 欄位，從而完整保存了高精度的審計路徑。
   - **目前狀態：** 決策與 TDD 實作已全數完成。在 M7-C.2 的探針單體呼叫修正（M7-C.2 Single-Call Probe Correction）中，我們重構並消除了 redundant 探針請求，成功達成「僅呼叫一次 `provider.generate`」與「僅呼叫一次 `transport.send`」的 Single Call 契約。
- **M7-D 狀態：** 目前 M7-D (Smoke Runs) 依舊維持 **Blocked / Planned**，直到執行一次全新的真實本機 opt-in single live probe（即 M7-C.3 live re-probe confirmation），證明在真實 Gateway 上其正規化與審計 metadata 寫入完全通過，方可准入 Smoke 階段。

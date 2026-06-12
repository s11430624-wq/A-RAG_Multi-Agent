# Milestone 7-C.3 Single Live Re-Probe Confirmation Report

**Milestone:** 7-C.3 (Single Live Re-Probe Confirmation)  
**Status:** M7-C.3 Live Re-Probe Passed, Normalization Confirmed Against Real Gateway. M7-D Ready for Smoke Planning.  
**Date:** 2026-06-11  

---

## 1. Readiness Check (前置檢查)

在啟動實體網路探針前，已完成以下本機環境安全性與一致性靜態檢查：

1. **`configs/models.yaml` 配置查核：**  
   - `default_model` 配置為 `"GPT5.4"`。  
   - `openai_compatible_gateway.api_base` 配置為 `"http://127.0.0.1:8787/v1"`。  
   - 確無包含任何 API Key、金鑰或 OAuth 憑證路徑。  
   - 符合 M7-B 要求的本機安全性約定。

2. **本機 Socket 埠口聆聽狀態：**  
   - 使用作業系統級別 socket connection 測試，驗證本機 `127.0.0.1:8787` 的 Local OpenAI-Compatible Proxy 正在進行 **LISTENING**，連線可成功建立。  
   - 本檢查完全自主，並未讀取任何 `.json` 金鑰檔、Service Account 或 `share-session.json`。

3. **M7-B 傳輸層加固狀態 (Transport Gating)：**  
   - `LiveProviderFactory` 實例化的 `GPT5.4` provider，其底層 `no_auth_loopback` 模式為 **`True`**。  
   - 請求發送過程中完全不攜帶 `Authorization` 標頭，且禁止 Caller 手動注入，若發現則 Fail-Closed 拒絕，安全性完美。

---

## 2. 實體探針執行指令 (Exact Executed Command)

在確認 Readiness 安全無虞後，使用以下指令執行實體 Live Re-Probe。此指令啟動了實體網路傳輸：

```bash
PYTHONPATH=. ARAG_RUN_LIVE_GATEWAY=1 ARAG_ALLOW_SINGLE_PROBE=1 python experiments/cli.py live-probe --repo-root .
```

---

## 3. 探針執行輸出與物理單次呼叫證明 (Single-Call Invariant Verification)

### CLI 實體輸出 (Console Output Log)
```text
=== M7-C Local OpenAI-Compatible Proxy Live Probe ===
Step 1: Readiness check...
  [OK] models.yaml configuration is correct.
  [OK] Local OpenAI-Compatible Proxy is listening on 127.0.0.1:8787.
  [OK] M7-B loopback transport validated (No Auth, no Authorization header, origin restricted).
Step 2: Sending single live probe request...
  [OK] HTTP request succeeded.

--- Probe Response Analysis ---
Response Model: GPT5.4
Finish Reason: stop
Content: 'hi'
Provider Request ID: _HAqaob5MMGQ9tMPxfn14AI
Usage Object (Normalized): input_tokens=8, output_tokens=94, total_tokens=102, source=provider_normalized
  [Audit Metadata] normalization_rule: openai_reasoning_accumulation
  [Audit Metadata] raw_completion_tokens: 1
  [Audit Metadata] reasoning_tokens: 93
  [Audit Metadata] normalized_output_tokens: 94
  [Audit Metadata] usage_source: provider_normalized
Seed support: Checked (applied seed=42 in request).

[SUCCESS] Single live probe passed all checks!
```

### 物理單次呼叫證明 (Single-Call Audit Evidence)
- **`provider.generate` 呼叫次數：** **1次**。經 TDD 單元測試 `test_run_live_probe_cli_calls_provider_generate_exactly_once` 以 `MagicMock(wraps=...)` 監測，驗證其在整個 CLI 生命周期中僅發生 exactly one 呼叫，不為校驗發起額外請求。
- **`transport.send` 呼叫次數：** **1次**。經 TDD 單元測試 `test_run_live_probe_cli_calls_transport_send_exactly_once` 驗證，僅發生 exactly one 實體網路 HTTP 傳輸，未發生任何 redundant 探針請求。

---

## 4. 探針成功條件比對 (Probe Criteria Checklist)

| 檢驗指標 | 系統實際表現 | 驗收狀態 |
| :--- | :--- | :---: |
| **Exit Code** | `0` (正常完成) | **PASSED** |
| **HTTP status** | `200 OK` | **PASSED** |
| **Model ID** | `GPT5.4` | **PASSED** |
| **Finish Reason** | `stop` | **PASSED** |
| **Provider Request ID** | `_HAqaob5MMGQ9tMPxfn14AI` (存在) | **PASSED** |
| **Usage Source** | `provider_normalized` | **PASSED** |
| **Token 計數守恆** | $8 \text{ (input)} + 94 \text{ (output)} == 102 \text{ (total)}$ | **PASSED** |
| **Audit Metadata 完整性** | 完整包含：`normalization_rule`, `raw_completion_tokens`, `reasoning_tokens`, `normalized_output_tokens`, `usage_source` | **PASSED** |
| **正規化計數守恆** | $94 \text{ (normalized\_output)} == 1 \text{ (raw\_completion)} + 93 \text{ (reasoning)}$ | **PASSED** |

---

## 5. 無副作用安全性驗收 (No Side-Effects Invariant)

- **是否有任何 `results/raw` JSONL 檔案寫入？**  
  **否**。整場實施未寫入任何 `results/raw_results.jsonl` 評估數據，確保測試與批次評估系統解耦。
- **是否有建立臨時 `workspace` 資料夾？**  
  **否**。沒有在 `workspaces/` 下建立或污染任何虛擬 workspace 檔案。
- **是否有任何 `smoke` 或 `strategy` 被執行？**  
  **否**。沒有呼叫任何 `execute_run`，完全未啟動 M1-M6 當中的任何 Agent Strategy (如 A/C/E 等)。

---

## 6. 指標與下一階段計畫 (M7-D Status)

- **M7-C.3 重新探針驗收結論：**  
  實體探針已在真實 Local OpenAI-Compatible Proxy 埠口 `8787` 上**成功通過所有物理不變量、安全性與正規化驗證**。
- **M7-D (Smoke Runs) 狀態：**  
  由 `Blocked / Planned` 變更為 **`Ready for Smoke Planning / Pending explicit approval`** (已完成 Smoke 前置所有必備安全防禦、正規化、與單體單次呼叫測試)。
- **安全宣告：**  
  本輪執行完全遵照規範：**無修改任何 Production Code、無修改 Schema、無進行任何 Smoke Runs、無進行任何 Full Runs、無執行任何 Strategy Live Runs、無讀取任何 credentials 金鑰。**

---

## 7. 驗證指令輸出

```powershell
# 全 Regression 432 個測試 100% 綠燈！
export PYTHONDONTWRITEBYTECODE='1' && python -B -m pytest -q
# 結果：432 passed, 2 skipped in 142.82s
```

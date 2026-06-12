# Milestone 7-E.22: Final Rerun Preflight after Coder Evidence Inheritance

## 1. 策略契約實體確認 (Physical Contract Auditing)

我們已在 `experiments/strategies/arag_multi_agent.py` 中，針對 **Option D+** 方案完成完整之代碼實施。在本次預檢中，我們再次以唯讀形式實體確認以下策略契約：

*   **預算規格 (Budget Limits)：**
    *   **Planner/initial budget = 5**
    *   **Coder/initial budget = 3**（由 2 提升至 3，為 Coder 在角色隔離限制下提供必要的檢索裕度）
    *   **Reviewer/initial budget = 1**
    *   **repair budget = 2**
*   **Coder 證據繼承規則 (Evidence Inheritance)：**
    *   Coder 在 `initial` 階段僅能單向、唯讀繼承當前 run 且同 task 的 `Planner/initial` 證據項目雜湊 ID（`planner_evidence_ids`）。
    *   繼承之 `EvidenceItem` 屬性保持完全不變（`role` 仍保持 `Planner`，`phase` 仍保持 `initial`），不進行任何拷貝或屬性篡改。
*   **授權不繼承原則 (No Authorization Inheritance)：**
    *   Coder **不繼承** Planner 的 `SearchAuthorization` 項目。
    *   Coder 企圖讀取（`chunk_read`）任何 Planner 的證據時，若 Coder 自己未先對該檔案進行合法搜尋，將被系統 Fail-Closed 阻斷並拋出特化例外：`StrategyResponseError("chunk_read is not authorized for this scope")`（此錯誤特化自 `ValueError`）。
*   **跨角色快取隔離 (Cache Scope Scoped)：**
    *   系統快取嚴格隔離角色的 `role` 與 `phase`，快取絕不跨角色重用。Coder 提出與 Planner 相同的檢索，仍會實體呼叫 backend、寫入 Coder 檢索 log、並扣減 Coder 的預算。
*   **Reviewer / Repair 盲審繼承：**
    *   Reviewer 與修復階段（Repair Rounds）仍嚴格僅能繼承 Coder 的證據 `self._coder_evidence_ids`，**絕不傳入或隱式繼承任何 Planner 證據**。Reviewer 引用 Planner 證據會觸發 `StrategyResponseError` Fail-Closed 阻斷。

---

## 2. 實驗 ID 衝突檢查 (ID Collision Check)

預留之全新 Experiment ID 如下：
*   **Experiment ID:** `m7e_full_20260612T040000Z`

經實體路徑掃描，與此新 ID 相關之所有產物、暫存或工作區路徑**完全不存在**，碰撞檢查 **100% 通過 (Zero Collisions)**：

*   `results/raw/m7e_full_20260612T040000Z.jsonl` ➔ **不存在 🟢**
*   `results/raw/artifacts/m7e_full_20260612T040000Z` ➔ **不存在 🟢**
*   `results/raw/retrieval/m7e_full_20260612T040000Z` ➔ **不存在 🟢**
*   `results/raw/diagnostics/m7e_full_20260612T040000Z` ➔ **不存在 🟢**
*   `results/derived/m7e_full_20260612T040000Z.csv` ➔ **不存在 🟢**
*   `results/derived/m7e_full_20260612T040000Z_summary.md` ➔ **不存在 🟢**
*   `workspaces/m7e_full_20260612T040000Z` ➔ **不存在 🟢**

---

## 3. Frozen Hash Revalidation (不變性校驗)

我們已使用實體 SHA-256 雜湊演算法，在預檢階段對以下 7 份關鍵歷史凍結產物進行雜湊校驗。校驗結果與預期雜湊值 100% 匹配，無任何不一致：

| 項目名稱 (Item) | 實體檔案路徑 (File Path) | SHA-256 雜湊值 (Calculated Hash) | 狀態 |
| :--- | :--- | :--- | :---: |
| **m7d smoke report** | `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | 一致 🟢 |
| **m7d smoke JSONL** | `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | 一致 🟢 |
| **m7e 210000Z** | `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | 一致 🟢 |
| **m7e 230000Z** | `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` | 一致 🟢 |
| **m7e 010000Z** | `results/raw/m7e_full_20260612T010000Z.jsonl` | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` | 一致 🟢 |
| **m7e 020000Z** | `results/raw/m7e_full_20260612T020000Z.jsonl` | `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456` | 一致 🟢 |
| **m7e 030000Z** | `results/raw/m7e_full_20260612T030000Z.jsonl` | `548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664` | 一致 🟢 |

---

## 4. 模型與 API 配置核對 (Model & Adapter Auditing)

根據 `configs/models.yaml` 與 `configs/experiment.yaml` 設定，我們完成以下唯讀檢查：

*   **Provider ID:** `hermes_vertex_gateway` ➔ **核對一致 🟢**
*   **Model Name:** `google/gemini-3.5-flash` ➔ **核對一致 🟢**
*   **API Base Endpoint:** `http://127.0.0.1:8787/v1` ➔ **核對一致 🟢**
*   **不讀取 Credentials 🟢：** 預檢程序未讀取任何環境變數或配置中的 API 密鑰/Credentials。
*   **不發送 HTTP 請求 🟢：** 預檢程序全程離線，絕不發起任何對 Gateway 埠口（`8787`）或網際網路的實體 HTTP 連線。

---

## 5. 純離線測試通過結果 (Offline Tests Sweeping)

我們在隔離之 OS 沙盒內完成了以下三個測試集的完全離線校驗，結果均為綠色通過（GREEN）：

1.  **測試集 1 - 所有策略邏輯與 TDD 隔離單元測試：**
    ```bash
    PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/strategies -q
    95 passed in 1.11s
    ```
2.  **測試集 2 - 全局 full-run gate、煙霧校驗、與中斷診斷測試：**
    ```bash
    PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q
    40 passed in 5.09s
    ```
3.  **測試集 3 - 全庫回歸單元與整合測試 (排除 live-evaluator)：**
    ```bash
    PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
    568 passed, 2 skipped in 73.80s (0:01:13)
    ```

---

## 6. PowerShell 實體 Rerun 執行命令草稿 (草稿 ➔ 禁止執行 🚫)

此處僅提供未來 M7-E.23 獲得明確批准時的 PowerShell 執行命令草稿。**此命令在當前預檢階段嚴格禁止執行**：

```powershell
# ==============================================================================
# 警告：此指令為預備草稿，在未獲得操作員明確批准之前，嚴禁執行！
# ==============================================================================

# 1. 設置一次性 live 執行閘門；明確移除 fake provider
$env:PYTHONDONTWRITEBYTECODE='1'
$env:ARAG_RUN_LIVE_GATEWAY='1'
$env:ARAG_EXECUTE_FULL_RUN_ONCE='1'
Remove-Item Env:ARAG_USE_FAKE_FULL_RUN_PROVIDER -ErrorAction SilentlyContinue

# 2. 啟動 A-RAG 實體重跑（新 Experiment ID）
python -B -m experiments.cli live-run `
  --repo-root . `
  --approved-smoke-report "results/raw/gates/m7d_smoke_20260611T123000Z.json" `
  --approved-smoke-sha256 "a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a" `
  --full-experiment-id "m7e_full_20260612T040000Z" `
  --human-approval FULL_RUN `
  --approved-input-token-budget 1000000 `
  --approved-output-token-budget 500000 `
  --approved-wall-clock-seconds 3600 `
  --allow-unknown-cost
```

---

## 7. Residue Scan (無殘留校驗)

我們已在預檢前執行了完整的快取與暫存檔案深度清理，實體掃描確認目前整個工作目錄的編譯與臨時殘留均為 **0**：

*   `__pycache__` 目錄數量：**0 🟢**
*   `.pytest_cache` 目錄數量：**0 🟢**
*   `*.pyc` 檔案數量：**0 🟢**
*   `*.pyo` 檔案數量：**0 🟢**
*   `sandbox_temp` / `temp_sandbox` 臨時沙盒數量：**0 🟢**

---

## 8. 最後明確 Stop Point 🔒

**預檢程序到此完全結束。系統已完全上鎖。**

> ⚠️ **CRITICAL STOP POINT**
>
> 系統在此強行阻斷。Milestone 7-E.23（實體大重跑）**嚴格必須**等待操作員手動進行安全審查，並在當前視窗中明確回覆：
>
> **「批准執行 M7-E.23，使用 experiment id m7e_full_20260612T040000Z」**
>
> 未獲得此 exact 批准語句前，嚴禁操作任何執行指令、嚴禁連線 Gateway。

---

## 9. M7-E.23 Execution Result

The operator subsequently supplied the exact approval sentence. M7-E.23 was executed once and ended in a controlled abort:

```text
Experiment ID: m7e_full_20260612T040000Z
Completed records: 15/45
Failed active run: T02 / E / rep01
Abort reason: ProviderTransportError: HTTP Error 429: Too Many Requests
```

See `docs/milestones/M7E23_abort_audit.md`. No resume or automatic rerun was performed.

# Milestone 7-E.21 Acceptance Criteria Document (Option D+ Revised Implementation)

## 1. Deliverables & Execution Status
- **Status:** **Controlled Abort / Partial Results Preserved / Final Dataset Not Complete** (TDD Implementation Completed & Verified Offline)
- **Active Task:** Milestone 7-E.21: Coder Evidence Inheritance + Retrieval Budget TDD Implementation.
- **Artifact Created:** `docs/milestones/M7E21_acceptance.md`
- **Modified Production Files:**
  - `experiments/strategies/arag_multi_agent.py`
- **Modified Test Files:**
  - `tests/strategies/test_arag_multi_agent.py`
- **Modified Documentation Files:**
  - `docs/superpowers/plans/2026-06-12-m7e20-coder-retrieval-policy.md` (Fixed ValueError to StrategyResponseError & Added Section 6 Frozen Hash Revalidation)
  - `docs/milestones/M7E20_acceptance.md` (Fixed Section reference to Section 6)
  - `docs/milestones/M7_acceptance.md` (Updated status for M7-E.21)

---

## 2. Option D+ Structural Rules & Compliance Verification

### 2.1 最終 Budget Map
系統之所有角色與階段預算嚴格設定如下，並已於實體程式碼 `_BUDGETS` 與 TDD 測試中完全驗證：
- **Planner/initial:** 5 次 (未變更)
- **Coder/initial:** 3 次 (原為 2 次，Option D+ 調升至 3 次)
- **Reviewer/initial:** 1 次 (未變更)
- **Repair Round (repair):** 2 次 (未變更)

```python
_BUDGETS = {("Planner", "initial"): 5, ("Coder", "initial"): 3, ("Reviewer", "initial"): 1}
```

### 2.2 Planner Evidence 收集與 Coder 繼承規則 (planner_evidence_ids)
- **收集規則：** 在 Planner 完成其 initial 階段後，系統立即在 `generate_initial_patch` 中掃描整個 `evidence_ledger`，精確收集屬於當前 `run_id`、`task_id`，且為 `role="Planner"`、`phase="initial"` 的所有 `evidence_id`。
- **傳遞：** 將收集到的 `planner_evidence_ids` 作為唯讀的 `inherited_evidence_ids` 傳入 Coder 階段的 `_role_turn()` 中。
- **不修改/不複製 EvidenceItem：** 系統維持 EvidenceItem 的 `role`、`phase` 與 `provenance` 完全不變，Coder 僅能在其 Prompt 中唯讀檢視。

```python
planner_evidence_ids = tuple(
    item.evidence_id
    for item in self.evidence_ledger.items
    if (
        item.run_id == self.run_id
        and item.task_id == self.task.task_id
        and item.role == "Planner"
        and item.phase == "initial"
    )
)
```

### 2.3 Cache Scope & Isolation
- **Role/Phase Scoped:** 系統快取（Cache Key）嚴格隔離角色的 `role` 與 `phase`，即使 Coder 發起與 Planner 完全相同的 query，亦**無法跨角色命中的快取**，必須作為獨立的 retrieval 請求呼叫後端、扣減 Coder 的預算、並寫入 Coder 的檢索日誌中。
- 只有當前階段（例如 Coder/initial）發起 100% 相同的查詢時，才會命中快取不扣預算。

### 2.4 Authorization Scope
- **No Shared Authorization Pool:** Coder 唯讀繼承 Planner 的證據內容，但 **不繼承** 任何 `SearchAuthorization`（搜尋授權項目）。
- Coder 若要讀取某個 chunk（執行 `chunk_read`），**必須自己先完成合法的搜尋**（Keyword 或 Semantic 搜尋），以在 `EvidenceLedger` 中為自己角色（`role="Coder", phase="initial"`）建立專屬的授權項目。
- 若 Coder 企圖直接 `chunk_read` 未經 Coder 自己搜尋授權的 chunk，系統將 fail-closed 阻斷並拋出 `StrategyResponseError("chunk_read is not authorized for this scope")`（此錯誤繼承自 `ValueError`）。

### 2.5 Reviewer Provenance 契約
- **純淨隔離 (Purity Guard):** `self._coder_evidence_ids` 仍嚴格限制僅收集 `role == "Coder"` 且 `phase == "initial"` 的證據。
- **Reviewer 僅能繼承 Coder 證據：** Reviewer 的 `allowed_evidence_ids` 與 `inherited_evidence_ids` 僅能使用 `self._coder_evidence_ids`。
- **Cite Restriction:** Reviewer 絕對不得引用 Planner 的 Evidence ID，若引用則 parser 會立即 fail-closed 拋出 `StrategyResponseError`。

### 2.6 Repair Evidence Scope
- 修復階段（Repair Rounds）維持獨立的修復鏈，僅繼承 `self._coder_evidence_ids`，**不隱式或自動繼承** Planner 的 evidence，確保審計溯源的單一指向性。

---

## 3. TDD RED/GREEN 過程實錄 (RED/GREEN TDD Run)

為實現最嚴格的 TDD 開發，我們在此完整記錄從測試失敗到代碼綠色通關的完整軌跡。

### 3.1 RED 測試名稱與失敗摘要
當在 production 代碼修改前（此時 Coder/initial 預算仍為 2，且未傳入 `planner_evidence_ids`），執行 32 個 offline 測試時，精確出現以下 **4 個預期中的失敗**：

1. **`test_a_c_strategies_remain_zero_retrieval`**
   - **失敗原因:** `AssertionError: {('Coder', 'initial'): 2} != {('Coder', 'initial'): 3}`
   - **歸屬:** 屬於 **Budget=2** 引起之不一致。

2. **`test_coder_inherits_visible_planner_evidence`**
   - **失敗原因:** `AssertionError: assert 'E000001' in 'You are the Coder role...\n<EVIDENCE_DATA>[]</EVIDENCE_DATA>\n'`
   - **歸屬:** 屬於 **Coder 尚未取得 planner_evidence_ids** 引起之失敗（Coder 無法在 Prompt 中檢視 Planner 收集的 `E000001` 證據）。

3. **`test_coder_three_distinct_searches_allowed`**
   - **失敗原因:** `RetrievalBudgetExceededError: Coder/initial retrieval budget exhausted`
   - **歸屬:** 屬於 **Budget=2** 限制了第 3 次相異檢索之成功。

4. **`test_coder_fourth_distinct_search_fails_before_backend`**
   - **失敗原因:** `AssertionError: assert 4 == 5`
   - **歸屬:** 屬於 **Budget=2** 使得系統在第 3 次查詢時就已提前阻斷（導致 provider 總 request 數為 4 而非預期的 5）。

其餘所有 28 個測試（包括跨角色快取隔離、不繼承授權、不繼承 Planner 證據進行 chunk_read、Reviewer 盲審阻斷等精密 TDD 測試）皆在 RED 階段預先綠色通過，證明了 Option D+ 的結構安全隔離防禦力。

---

### 3.2 GREEN 測試結果 (100% 通關)
在修改 `experiments/strategies/arag_multi_agent.py` 注入 Option D+ 代碼後，執行所有測試集全部 100% 通關：

1. **`test_arag_multi_agent.py` 測試結果:**
   ```bash
   $env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
   ................................                                         [100%]
   32 passed in 0.88s
   ```

2. **所有策略離線測試結果:**
   ```bash
   $env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies -q
   ........................................................................ [ 75%]
   .......................                                                  [100%]
   95 passed in 1.29s
   ```

3. **所有 live-run/smoke 離線門禁測試結果:**
   ```bash
   $env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q
   ........................................                                 [100%]
   40 passed in 6.42s
   ```

4. **全局回歸與非整合測試結果 (568 個測試全數通關):**
   ```bash
   $env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
   ........................................................................ [ 12%]
   ........................................................................ [ 25%]
   ..................s........................................s............ [ 37%]
   ........................................................................ [ 50%]
   ........................................................................ [ 63%]
   ........................................................................ [ 75%]
   ........................................................................ [ 88%]
   ..................................................................       [100%]
   568 passed, 2 skipped in 74.14s (0:01:14)
   ```

---

## 4. Frozen Hash Revalidation (不變性校驗)
我們再次列出並比對了系統中關鍵歷史凍結產物的雜湊值，確保其 100% 保持未被修改之凍結狀態：

- **m7d smoke report:** `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` (Unchanged)
- **m7d smoke JSONL:** `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` (Unchanged)
- **m7e 210000Z:** `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` (Unchanged)
- **m7e 230000Z (Raw JSONL):** `results/raw/m7e_full_20260611T230000Z.jsonl` / `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` (Unchanged)
- **m7e 010000Z:** `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` (Unchanged)
- **m7e 020000Z:** `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456` (Unchanged)
- **m7e 030000Z:** `548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664` (Unchanged)

---

## 5. Residue Scan (無殘留校驗)
- **掃描結果:** `__pycache__`、`.pytest_cache`、`*.pyc`、`*.pyo`、workspace 暫存檔案與未登錄局部輸出均為 0。
- 整個測試流程完全在隔離之 OS pytest `tmp_path` 內安全進行，保障主工作區乾淨無污染。

---

## 6. Security and Process Declarations
- **無 Rerun / 無 Resume:** 本輪執行嚴格遵循安全指令，**未執行任何實體 Rerun、未執行 live-run、未執行 smoke-run、且未執行任何 Resume 操作**。
- **無 Gateway / 無模型呼叫:** 所有 TDD 測試與驗證皆使用 Mock Provider/Store 離線進行，**未連線本地或遠端 Gateway，亦未發生任何真實模型 API 呼叫**。
- **無修改歷史產物:** 沒有修改或刪除任何 raw JSONL, artifacts, retrieval logs 或 smoke outputs。

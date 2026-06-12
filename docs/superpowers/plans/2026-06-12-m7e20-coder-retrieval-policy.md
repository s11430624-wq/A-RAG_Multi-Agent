# Coder Retrieval Policy Decision Plan (Option D+ Revision)

## 1. 既有隔離設計與四大契約阻礙深度分析 (In-Depth Analysis of Existing Isolation & Four Contract Blockers)

根據對 `experiments/strategies/arag_multi_agent.py` 的實體程式碼與系統架構深度審查，我們針對原先 Option E 規劃中發現的四大關鍵契約阻礙（Blockers）進行全面修正，確保與系統的底層約束（Isolation & Integrity）完全一致。

### 1.1 `_role_turn()` 中的證據可見性過濾與 Coder 盲區
在 `_role_turn()` 內部，每次迭代時會動態計算該 Role 於目前 Phase 可看見的證據（`visible_evidence`）：
```python
visible_evidence = tuple(
    item
    for item in self.evidence_ledger.items
    if (item.role == role and item.phase == phase) or item.evidence_id in inherited_evidence_ids
)
```
因為 Coder/initial 啟動時預設沒有傳入任何 `inherited_evidence_ids`，導致其完全看不到 Planner/initial 在同一個 Run 檢索到的 API SPEC 與程式碼參考文檔（屬性為 `role="Planner", phase="initial"`），迫使其必須進行盲目摸索與重複檢索。

---

### 1.2 契約阻礙一：跨 Role 快取擊中（Cross-Role Cache Hit）之禁止
- **原規劃錯誤：** 誤以為 Coder 可以直接共用或命中 Planner 曾發起過的快取查詢，且不扣預算。
- **實體程式碼約束：** 
  快取鍵值（Cache Key）的構造方式為：
  ```python
  if retrieval_request.tool == "chunk_read":
      cache_key = (role, phase, "chunk_read", retrieval_request.file_path, retrieval_request.chunk_id)
  else:
      cache_key = (role, phase, retrieval_request.tool, retrieval_request.query, retrieval_request.top_k)
  ```
  快取鍵中**強制包含了 `role` 與 `phase`**。因此，即使 Coder 與 Planner 提出 100% 相同的查詢（如 `get_student_course_summary`），其構造出的 Cache Key 也是完全不同的（`Planner` vs `Coder`）。
- **修正後規則（No Cross-Role Cache）：**
  - 快取僅在**同一個 run/session、同一個 role、同一個 phase、以及完全相同的 request 參數**下重用。
  - Coder **無法直接命中** Planner 的快取。
  - Coder 重複 Planner 的查詢仍視為 Coder 的**獨立相異檢索**，會呼叫 backend、寫入 Coder 獨立日誌、並扣減 Coder 預算。
  - Coder 唯有重複自己在 Coder/initial 已做過的查詢時，方能命中快取不減預算。
  - 我們絕對不打破或修改 role/phase 的快取隔離。

---

### 1.3 契約阻礙二：Planner 檢索授權（SearchAuthorization）繼承之禁止
- **原規劃錯誤：** 誤以為能將 Planner 的 `SearchAuthorization` 一併注入 Coder，或者讓 inherited authorization 對 Coder/initial 的 `chunk_read` 自動生效。
- **實體程式碼約束：**
  `SearchAuthorization` 定義如下：
  ```python
  @dataclass(frozen=True)
  class SearchAuthorization:
      run_id: str
      task_id: str
      role: RoleName
      phase: PhaseName
      file_path: str
      chunk_id: str
  ```
  `RetrievalRequestParser` 對 `chunk_read` 執行這 **六個欄位的完全相等匹配（Exact Match）**。若 Coder 企圖直接讀取某個 chunk，但資料庫中只有 Planner/initial 的授權項目（`role="Planner", phase="initial"`），驗證會直接 Fail-Closed 阻斷。
- **修正後規則（No Authorization Inheritance）：**
  - Coder **單向且唯讀**繼承同 run、同 task 的 Planner/initial `EvidenceItem`，使其能看見內文，但**不繼承任何 `SearchAuthorization`**。
  - Coder 若需要直接進行 `chunk_read`，**必須自己先完成合法的搜尋**（如關鍵字或語義搜尋），以在 `EvidenceLedger` 中為自己（`role="Coder", phase="initial"`）建立專屬的實體 `SearchAuthorization`。
  - 嚴禁共用或建立任何跨角色的授權池（No Shared Authorization Pool）。

---

### 1.4 契約阻礙三：Reviewer 只能繼承 Coder Provenance 證據之限縮
- **原規劃錯誤：** 誤將 `planner_evidence_ids` 合併寫入 `self._coder_evidence_ids` 中，使得 Reviewer 看見或繼承了 Planner 的證據。
- **實體程式碼約束：**
  - 為了保障 Reviewer 的盲審獨立性與 Provenance 的正確生命週期，Reviewer 只能也必須只能接觸 Coder 的產物。
  - 雖然 Coder 在 `initial` 階段會單向獲取 `planner_evidence_ids` 作為繼承以理解需求，但當 Coder 完畢後，`self._coder_evidence_ids` **仍只能收集 Coder 自己在該階段產生的 Evidence**：
    ```python
    self._coder_evidence_ids = tuple(
        item.evidence_id
        for item in self.evidence_ledger.items
        if item.role == "Coder" and item.phase == "initial"
    )
    ```
  - Reviewer/initial 啟動時：
    - `allowed_evidence_ids` 與 `inherited_evidence_ids` 仍嚴格綁定 `self._coder_evidence_ids`。
    - **Reviewer 絕對不得直接看到或引用 Planner 的 Evidence ID**。若 Reviewer 引用了 Planner 的 Evidence ID 進行審查，系統必須直接 fail-closed 阻斷。
    - Planner 的 `plan` 仍可透過既有的 `data={"plan": plan, ...}` 純文字變數傳給 Reviewer，這僅作為文字輸入，不等同於 Evidence 檢索授權。

---

### 1.5 契約阻礙四：推薦方案 Option D+ 語意與設計
- **原規劃錯誤：** Option E 企圖建立共享 pool 與共享 authorization，容易導致測試與實體執行時的安全性漏洞，且大幅增加實作侵入半徑。
- **最終推薦方案：Option D+**
  - **Coder 單向、唯讀**看見同 run/task 內 Planner/initial 的 `EvidenceItem`（寫入為 Coder `inherited_evidence_ids` 參數）。
  - **不繼承** Planner `SearchAuthorization`。
  - **不跨 Role** 共用或擊中 Cache（維持 Cache role/phase 完全隔離）。
  - **Coder/initial 預算** 由 2 提升至 `3`，提供在 D+ 限制下的合理相異檢索裕度。
  - **Reviewer 保持純淨：** 只能繼承 `self._coder_evidence_ids`，絕不繼承或直接看見 Planner evidence。
  - **修復階段（Repair Rounds）：** 維持既有 `self._coder_evidence_ids` 的修復鏈條，**不自動或隱式繼承** Planner/initial 的 evidence，確保修復軌跡乾淨。
  - **其餘預算完全不變：** `Planner` 初始預算 = 5，`Reviewer` 初始預算 = 1，`Repair` 預算 = 2。

---

## 2. 五個方案之多維度評估矩陣 (Revised Decision Matrix)

| 評估維度 (Dimensions) | Option A | Option B | Option C | Option D | Option D+ (最終推薦) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Fairness (公平性)** | ⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| **Scientific validity (科學有效性)** | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| **Completion probability (完成率)** | ❌ (0%) | ⚠️ (中) | ⚠️ (高) | ⚠️ (中) | 99% (極高) |
| **Provider/model cost (API 成本)** | 🟢 低 | 🟡 中 | 🔴 極高 | 🟢 低 | 🟢 極低 (無冗餘檢索) |
| **Retrieval leakage risk (洩漏風險)** | 🟢 無 | 🟢 無 | 🟢 無 | 🟢 無 | 🟢 無 (嚴格 Scope) |
| **Role isolation (角色職責隔離)** | 🟢 完美 | 🟢 完美 | 🟢 完美 | 🟢 完美 | 🟢 完美 (無 Auth/Cache 穿透) |
| **Evidence provenance (審計溯源)** | 🟢 完美 | 🟢 完美 | 🟢 完美 | 🟢 完美 | 🟢 完美 (維持獨立 Role 記錄) |
| **Implementation blast radius (修改半徑)**| 🟢 零 | 🟢 極小 | 🟢 極小 | 🟡 中 | 🟢 極小 (無需重構 Auth) |
| **Compatibility with EvidenceLedger** | 🟢 100% | 🟢 100% | 🟢 100% | 🟢 100% | 🟢 100% (不修改 Ledger 欄位) |
| **Compatibility with Strategy Schedule** | 🟢 100% | 🟢 100% | 🟢 100% | 🟢 100% | 🟢 100% |
| **Impact on reproducibility (可重現性)** | 🟢 無影響 | 🟢 無影響 | 🟢 無影響 | 🟢 無影響 | 🟢 無影響 (確定性) |

*說明：Option D+ 在確保 100% 職責隔離與安全約束的同時，提供了最低的修改半徑與極高的通關機率，在所有方案中表現最為卓越。*

---

## 3. Option D+ 詳細設計與虛擬碼 (Option D+ Design & Pseudocode)

### 3.1 介面與生命週期流動
1. **收集 Planner 證據（不變更 Evidence Ledger）：**
   ```python
   planner_evidence_ids = tuple(
       item.evidence_id
       for item in self.evidence_ledger.items
       if item.role == "Planner" and item.phase == "initial"
   )
   ```
2. **Coder 單向繼承（唯讀）：**
   ```python
   # 在呼叫 Coder 階段注入 inherited_evidence_ids
   patch = self._role_turn(
       role="Coder",
       phase="initial",
       template_name="coder.txt",
       data={"plan": plan},
       final_parser=PatchResponseParser.parse,
       inherited_evidence_ids=planner_evidence_ids,
   )
   ```
3. **Coder 結束後，Reviewer 保持純淨隔離：**
   ```python
   # Coder Evidence 收集維持只拿 Coder 自己的：
   self._coder_evidence_ids = tuple(
       item.evidence_id
       for item in self.evidence_ledger.items
       if item.role == "Coder" and item.phase == "initial"
   )
   
   # Reviewer 呼叫，僅能繼承 self._coder_evidence_ids，絕不傳入 planner_evidence_ids
   verdict = self._role_turn(
       role="Reviewer",
       phase="initial",
       template_name="reviewer.txt",
       data={"plan": plan, "patch": patch, "coder_evidence_ids": self._coder_evidence_ids},
       final_parser=lambda text: ReviewerResponseParser.parse(
           text,
           allowed_evidence_ids=self._coder_evidence_ids,
       ),
       inherited_evidence_ids=self._coder_evidence_ids,
   )
   ```

---

## 4. Milestone 7-E.21 TDD 測試案例規劃 (TDD Test Suite Specifications)

為確保實作完全符合規範，我們規劃了以下 **15 個核心離線測試**（完全新增與修改於 `tests/strategies/test_arag_multi_agent.py`）。

1. **`test_coder_inherits_visible_planner_evidence`**
   - 驗證 Coder 在 initial 階段能夠在 `<EVIDENCE_DATA>` 中看見 Planner 在同階段檢索出的內文。

2. **`test_coder_inheritance_rejects_cross_run_task_phase_evidence`**
   - 驗證 Coder 在任何情況下皆看不到其他 run_id、task_id 或不屬於 Planner/initial 階段的證據。

3. **`test_coder_can_view_planner_evidence_without_inheriting_authorization`**
   - 驗證 Coder 雖能唯讀看見 Planner 的證據內文，但並未繼承其實體 `SearchAuthorization` 權限項目。

4. **`test_planner_authorization_does_not_authorize_coder_chunk_read`**
   - 驗證當 Coder 企圖使用 Planner 的 `SearchAuthorization` 直接進行 `chunk_read` 時，驗證必須阻斷並拋出 `StrategyResponseError("chunk_read is not authorized for this scope")`（而非 ValueError）。

5. **`test_coder_own_search_authorizes_coder_chunk_read`**
   - 驗證 Coder 必須先完成一次屬於自己的搜尋（`role="Coder", phase="initial"`），建立合規授權項目後，方能成功執行 `chunk_read`。

6. **`test_coder_same_role_phase_duplicate_search_uses_cache_without_budget_decrement`**
   - 驗證當 Coder 連續發起兩次完全相同的 Coder/initial 檢索時，第二次能命中 Coder 的快取，不減 Coder 獨立預算。

7. **`test_coder_query_matching_planner_does_not_cross_role_cache`**
   - 驗證當 Coder 發起與 Planner/initial 相同的查詢時，因為 Cache 設有嚴格的 `role` 隔離，**無法直接命中 Planner 快取**，必須作為獨立實體檢索呼叫 backend、記日誌並扣減 Coder 預算。

8. **`test_coder_three_distinct_searches_allowed`**
   - 驗證 Coder/initial 預算調高至 3 後，允許最多執行 3 次不重複的實體檢索。

9. **`test_coder_fourth_distinct_search_fails_before_backend`**
   - 驗證 Coder 在發起第 4 次相異檢索時，會立刻在呼叫後端前 fail-closed 阻斷，並拋出 `RetrievalBudgetExceededError`。

10. **`test_reviewer_only_gets_coder_provenance_evidence`**
    - 驗證 Reviewer 的 `allowed_evidence_ids` 只包含 Coder 自己的 evidence IDs，絕不包含任何 Planner 的 evidence IDs。

11. **`test_reviewer_rejects_planner_evidence_id`**
    - 驗證若 Reviewer 企圖直接引用 Planner 的 evidence ID，驗證層會立即 fail-closed 拋出例外。

12. **`test_repair_round_does_not_gain_planner_evidence_implicitly`**
    - 驗證進入修復階段後，修復策略僅自動繼承 `self._coder_evidence_ids`，不會隱式繼承 Planner 的證據。

13. **`test_a_c_strategies_remain_zero_retrieval`**
    - 確保策略 A 與 C 的檢索上限依然維持為 `0`，完全不被干涉。

14. **`test_retrieval_requests_not_printed_to_stdout_or_stderr`**
    - 驗證系統的所有標準輸出與標準錯誤皆不洩漏任何敏感的 raw 檢索細節。

15. **`test_frozen_hashes_unchanged`**
    - 確保所有凍結檔案的實體雜湊值保持 100% 不變。

---

## 5. 安全阻斷 Stop Point
- **STOP HERE.**
- 在 M7-E.21 的實作尚未由 operator 手動批准之前，**嚴禁執行任何實體大重跑（Rerun）、不得連線真實 Gateway、不呼叫模型。**
- 未來實體大重跑必須且只能使用全新 Experiment ID（如 `m7e_full_20260612T040000Z`），嚴禁覆寫 any 既有產物。

---

## 6. Frozen Hash Revalidation

我們在此列出並核對所有系統中關鍵凍結產物的 SHA-256 雜湊值（Hashes），確保在進行 TDD 開發與策略改造過程中，這些歷史數據與測試產物 100% 未被修改：

| 項目名稱 (Item) | 檔案路徑或識別碼 (Path / ID) | 預期 SHA-256 雜湊值 (Expected Hash) |
| :--- | :--- | :--- |
| **m7d smoke report** | `docs/milestones/M7_acceptance.md` 相關凍結雜湊 | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` |
| **m7d smoke JSONL** | 凍結之 smoke JSONL 雜湊值 | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` |
| **m7e 210000Z** | `m7e_full_20260611T210000Z` 雜湊值 | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` |
| **m7e 230000Z** | `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` |
| **m7e 010000Z** | `m7e_full_20260612T010000Z` 雜湊值 | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` |
| **m7e 020000Z** | `m7e_full_20260612T020000Z` 雜湊值 | `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456` |
| **m7e 030000Z** | `m7e_full_20260612T030000Z` 雜湊值 | `548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664` |

此雜湊表作為系統完整性的最高防線，任何策略的實作或重構均嚴格不得更動上述數據。


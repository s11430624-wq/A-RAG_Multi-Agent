# Milestone 7-E.9 Acceptance: Retrieval Budget Policy TDD Implementation

**Status:** Completed

---

## 1. Background
In the previous experiment `m7e_full_20260611T230000Z` (Strategy E, rep02), the run triggered a `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted` during the 3rd retrieval request, leading to a Controlled Abort. Following the M7-E.8 Decision Plan, the recommended policy is Option B: relax the Planner initial retrieval budget from 2 to 3.

This Milestone (M7-E.9) implements this policy change using strict Test-Driven Development (TDD) while keeping all existing experimental runs, outputs, and constraints completely frozen.

---

## 2. TDD Implementation Details

### RED Phase
Two new tests were added to `tests/strategies/test_arag_multi_agent.py` before modifying the production budget settings:
1. `test_strategy_e_planner_initial_third_retrieval_allowed_under_new_budget`
2. `test_strategy_e_planner_initial_fourth_retrieval_fail_closed`

#### RED Test Names & Failure Reasons:
- **`test_strategy_e_planner_initial_third_retrieval_allowed_under_new_budget`**
  - **Failure reason:** Raised `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted` during the 3rd retrieval because the production budget limit was still hardcoded to 2.
- **`test_strategy_e_planner_initial_fourth_retrieval_fail_closed`**
  - **Failure reason:** Failed with `AssertionError: assert 3 == 4` because budget enforcement stopped the run at the 3rd retrieval, resulting in only 3 provider requests instead of the expected 4.

---

### GREEN Phase
The production code was modified to update the retrieval budget dictionary `_BUDGETS`.

#### Modified Files, Line Numbers & Diff:
- **File:** `experiments/strategies/arag_multi_agent.py`
- **Line:** 38
- **`_BUDGETS` Comparison:**
  - **Before:**
    ```python
    _BUDGETS = {("Planner", "initial"): 2, ("Coder", "initial"): 2, ("Reviewer", "initial"): 1}
    ```
  - **After (Option B):**
    ```python
    _BUDGETS = {("Planner", "initial"): 3, ("Coder", "initial"): 2, ("Reviewer", "initial"): 1}
    ```

#### GREEN Test Summary:
Following the budget update, the entire test suite was run and passed:
- `test_strategy_e_planner_initial_third_retrieval_allowed_under_new_budget` **PASSED** (successfully completed the 3rd retrieval, executed Coder and Reviewer, and returned the patch).
- `test_strategy_e_planner_initial_fourth_retrieval_fail_closed` **PASSED** (successfully executed 3 retrievals, then blocked the 4th with `RetrievalBudgetExceededError`).
- `test_retrieval_budget_exhaustion_stops_without_fourth_tool_or_provider_call` (updated old test) **PASSED** (ensuring budget of 3 stops correctly on the 4th request).

---

## 3. Security, Permissions & Constraints Verification

- **A/C Strategy Retrieval Isolation:** Strategy A and C have absolutely zero retrieval capability. Verified by existing `test_strategy_a_and_c_fail_closed_at_guard_boundary` and `test_strategy_a_and_c_fail_closed_at_build_and_create` checks which raise `RetrievalPermissionError` for non-E strategies.
- **Retrieval Log Directory Protection:** Strategy E retrieval logs are strictly constrained to write only to the approved retrieval log root directory. Path escapes, symlinks, or directory traversals are completely blocked (verified by `test_log_writer_rejects_escape_suffix_and_sibling_prefix` and `test_log_writer_rejects_symlink_escape`).
- **Preflight and ID Guards:** Resuming of the aborted `m7e_full_20260611T230000Z` run is strictly forbidden and rejected. Any future full-run execution requires a brand-new experiment ID.

---

## 4. Frozen Hash Validation

The SHA-256 hashes of all frozen experimental inputs, outputs, and smoke gates have been verified and remain 100% unchanged:

| File Path | SHA-256 Hash | Status |
| :--- | :--- | :--- |
| `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | Unchanged |
| `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | Unchanged |
| `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | Unchanged |
| `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` | Unchanged |

---

## 5. Absolute Execution Boundaries Compliance

- **No Resume / Rerun:** No resume was executed. No full-runs, smoke-runs, or strategy live runs were executed or re-evaluated.
- **No Gateway Calls:** No connections were made to `127.0.0.1:8787` or any external API.
- **No LLM Calls:** No model calls were triggered or simulated.
- **No Leftover Residue:** No temporary results, mock artifacts, diagnostics folders, or temporary cache files were left in the workspace.
- **No Phase Creep:** No entry into M7-E.10 or any final experiment reruns.

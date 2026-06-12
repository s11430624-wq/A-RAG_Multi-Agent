# Milestone 7-E.13 Retrieval Loop Hardening TDD Implementation Acceptance Report

**Status:** Completed with TDD Verification  
**Date:** 2026-06-12  

---

## 1. Executive Summary

Milestone 7-E.13 successfully implements both prompt-level query discipline and runtime-level duplicate retrieval interception. This prevents model-driven agents (e.g. Planner, Coder, Reviewer) from issuing repetitive queries in the same role and phase, saving budget and eliminating redundant logging without affecting accuracy or system stability.

This hardening has been executed with strict compliance with all constraints:
- **No live-run, smoke-run, or full-run has been performed.**
- **No connection to Vertex Gateway or model calling has been made.**
- **No resume or rerun of the experiment has been executed.**
- **No modification of raw results, artifacts, retrieval logs, diagnostics, or other frozen outputs.**

---

## 2. TDD Verification & Phase Summary

### 2.1 RED Phase Tests & Failures
Prior to implementation, the newly created tests in `tests/strategies/test_arag_multi_agent.py` failed as expected (TDD RED):
1. `test_strategy_e_duplicate_keyword_search_reuses_cached_empty_result_without_budget_decrement`:
   - *Failure Reason:* The duplicate empty queries were executed, decremented the budget, and caused budget exhaustion.
2. `test_strategy_e_duplicate_keyword_search_does_not_write_duplicate_retrieval_log`:
   - *Failure Reason:* The duplicate empty queries were written twice to `retrieval.jsonl`.
3. `test_strategy_e_after_duplicate_empty_result_can_use_new_query_with_remaining_budget`:
   - *Failure Reason:* The duplicate empty queries exhausted the budget, blocking subsequent distinct queries.
4. `test_strategy_e_duplicate_semantic_search_uses_cache_same_as_keyword`:
   - *Failure Reason:* Duplicate semantic search queries were executed twice.
5. `test_strategy_e_retrieval_request_is_not_printed_to_stdout_or_stderr`:
   - *Failure Reason:* Raw retrieval request text could be emitted through stdout, violating the no-raw-model-output leakage boundary.

### 2.2 GREEN Phase Tests & Success
After the minimal implementation and stdout leakage guard, all 15 tests in `tests/strategies/test_arag_multi_agent.py`, 78 tests in `tests/strategies`, 40 tests in `tests/live/` (including smoke freeze and gates), and the non-hidden regression suite passed 100% successfully.

---

## 3. Implementation Details

### 3.1 Cache Key Design
A per-strategy-session cache dictionary `self.retrieval_cache` was added to `ARAGMultiAgentStrategySession`.  
The cache key is a tuple scoped to the active run, agent role, phase, and request parameters:
- **For `RetrievalSearchRequest`:**
  `cache_key = (role, phase, retrieval_request.tool, retrieval_request.query, retrieval_request.top_k)`
- **For `RetrievalChunkReadRequest`:**
  `cache_key = (role, phase, "chunk_read", retrieval_request.file_path, retrieval_request.chunk_id)`

This ensures isolation:
- Cache does not cross different roles (e.g. Planner and Coder have independent caches).
- Cache does not cross different phases (e.g. `initial` and `repair_1` have independent caches).
- Cache does not cross different session instances/runs.
- Different parameters (like query, tool, top_k, chunk/file) generate different cache keys.

### 3.2 Interception Logic
Inside `_role_turn` in `experiments/strategies/arag_multi_agent.py`, the duplicate request is checked before budget check, backend invocation, log writing, and evidence appending:
1. Parse retrieval request.
2. Generate cache key.
3. If `cache_key` exists in `self.retrieval_cache`:
   - Call `_record_accepted_response()` to record turn progress.
   - Re-use the existing result (the evidence is already loaded in the ledger from the first query).
   - **Do not decrement budget** (no `retrieval_count += 1`).
   - **Do not write duplicate log line**.
   - **Do not invoke retrieval backend**.
   - Continue model conversation loop.
4. If `cache_key` is not in cache:
    - Check budget limits.
    - Execute retrieval backend.
    - Store in `self.retrieval_cache[cache_key]`.
    - Log the retrieval and increment `retrieval_count`.

### 3.3 Stdout/Stderr Leakage Guard
Raw retrieval requests are never printed to stdout or stderr. A regression test asserts that even sensitive query text embedded in a retrieval request is not emitted through terminal output.

### 3.4 Prompt-Level Discipline (Planner Prompt Template)
The template `experiments/prompts/planner.txt` has been updated with clear instructions to prevent duplicate queries:
- Never repeat the exact same retrieval query in the same role/phase.
- If a keyword search returns no results, try alternative terms or `semantic_search`.
- Consolidate related evidence needs when possible.

---

## 4. Modified Files and Line Numbers

1. `experiments/prompts/planner.txt` (Line 10-14):
   - Added guidelines for query discipline.
2. `experiments/strategies/arag_multi_agent.py` (Line 63, Line 215-230):
   - Initialized `self.retrieval_cache` inside `__init__`.
   - Added cache lookup, interception, and caching logic in `_role_turn`.
3. `tests/strategies/test_arag_multi_agent.py` (Line 153-305):
   - Added TDD test coverage for duplicate keyword search, duplicate logging, semantic cache, budget recovery, stdout/stderr leakage prevention, cache scoping, and Strategy A/C regression.
   - Refactored previous budget tests to use distinct queries.
4. `tests/strategies/test_repair_boundary.py` (Line 61-71):
   - Adjusted maximum schedule test to use distinct queries.
5. `tests/live/test_smoke_executor.py` (Line 399-401):
   - Updated smoke executor test assertions to reflect that production runs with identical queries correctly cache them (reducing executed tool calls and retrieval log lines from 9 to 5).
6. `docs/milestones/M7_acceptance.md` (Line 3, Line 35):
   - Updated Milestone 7 Status to reflect that M7-E.13 has been completed.

---

## 5. Verification & Budget Audit

### 5.1 Retrieval Budgets Unchanged (`_BUDGETS`)
The initial retrieval budgets are strictly preserved and untouched:
- **Planner (initial):** 3
- **Coder (initial):** 2
- **Reviewer (initial):** 1

### 5.2 Frozen Artifact Hash Integrity
All frozen test artifacts and raw outputs have been verified. Their SHA-256 hashes remain exactly identical to their frozen states:

| File | SHA-256 Hash | Integrity |
| :--- | :--- | :--- |
| `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | UNCHANGED |
| `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | UNCHANGED |
| `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | UNCHANGED |
| `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` | UNCHANGED |
| `results/raw/m7e_full_20260612T010000Z.jsonl` | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` | UNCHANGED |

### 5.3 Residue Scan
A complete workspace scan confirms zero residue:
- **No new `results/raw/*.jsonl`** files.
- **No new `artifacts/`** folders or files.
- **No new `retrieval/` logs** generated.
- **No `diagnostics/`** generated.
- **No derived outputs** present.
- **No workspace/cache/temp residue** found.

---

## 6. Declarations & Safe Guard confirmations

We explicitly confirm that during this milestone:
1. **NO live-run** was executed.
2. **NO Vertex Gateway or external model call** was made.
3. **NO resume or rerun** was triggered.
4. **NO transition to M7-E.14** was attempted.

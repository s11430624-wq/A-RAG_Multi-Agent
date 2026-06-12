# Milestone 7-E.12 Plan: A-RAG Retrieval Budget & Strategy Redesign Decision

**Status:** Decision Plan Completed (No Implementation, Pure Planning & Analysis)

---

## 1. Context & Executive Summary

During the execution of Milestone 7-E.11 (the real final full 45-run rerun), the experiment aborted on Task T02 under Strategy E (Run ID: `m7e_full_20260612T010000Z__T02__E__rep01__seed42`). 

The abort was triggered by a `RetrievalBudgetExceededError` because the Planner attempted a 4th initial retrieval query, which exceeded the Option B budget limit of 3 established in Milestone 7-E.9. 

This document provides a systematic review of the aborted run's retrieval log, identifies the root cause of the budget exhaustion, compares six structural design options, and makes a concrete, non-implemented architectural recommendation for future research phases.

---

## 2. Aborted Run Retrieval Log Audit Analysis

### Captured Retrieval Logs (`results/raw/retrieval/m7e_full_20260612T010000Z/m7e_full_20260612T010000Z__T02__E__rep01__seed42.jsonl`):

```json
{"agent_role":"Planner","content_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","excerpt":"","query":"calculate_pass_rate","returned_chunk_ids":[],"returned_files":[],"run_id":"m7e_full_20260612T010000Z__T02__E__rep01__seed42","strategy":"E","task_id":"T02","timestamp":"2026-06-11T16:20:35Z","token_count":0,"tool_name":"keyword_search"}
{"agent_role":"Planner","content_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","excerpt":"","query":"calculate_pass_rate","returned_chunk_ids":[],"returned_files":[],"run_id":"m7e_full_20260612T010000Z__T02__E__rep01__seed42","strategy":"E","task_id":"T02","timestamp":"2026-06-11T16:20:38Z","token_count":0,"tool_name":"keyword_search"}
{"agent_role":"Planner","content_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","excerpt":"","query":"calculate_pass_rate","returned_chunk_ids":[],"returned_files":[],"run_id":"m7e_full_20260612T010000Z__T02__E__rep01__seed42","strategy":"E","task_id":"T02","timestamp":"2026-06-11T16:20:40Z","token_count":0,"tool_name":"keyword_search"}
```

### Key Analytical Findings:

1. **Exact Query Redundancy:**
   - The Planner executed **three identical `keyword_search` queries** for `"calculate_pass_rate"`.
   - All three queries returned zero hits (`returned_chunk_ids: []`, `token_count: 0`).
   
2. **Behavioral Loop (No Error-Handling Fallback):**
   - After the first query returned empty, the Planner failed to diversify its search terms (e.g., trying `"grade"`, `"pass"`, or `"rate"`) and did not switch from `keyword_search` to `semantic_search` which might have tolerated the phrase.
   - The Planner repeatedly emitted the exact same query string, burning its entire budget of 3 on redundant, unproductive search calls.

3. **Subsequent Budgets Depletion:**
   - Once the budget of 3 was exhausted by these 3 identical attempts, the Planner finally attempted to issue a different query (`"get_student_course_summary"`).
   - Because the budget threshold had already been reached (`3 >= 3`), the budget controller immediately intercepted the 4th request and triggered the `RetrievalBudgetExceededError` to abort the run.

4. **Underlying Issues Identified:**
   - **Hyper-granular/Static Prompts:** The Planner lacks prompt-level instructions on how to handle empty search results, leading to cognitive looping.
   - **Static Tool Choice:** The Planner doesn't fallback to semantic search when keyword search yields zero results.
   - **No State-level Loop Detection:** The strategy runner lacks a mechanism to detect and block identical repeated queries from consuming the budget.

---

## 3. Comparative Evaluation of 6 Design Options

To resolve this issue, we compare six different design strategies below:

### Option A: Maintain Planner initial=3, Accept Abort
- **Fairness:** **High**. Maintains the strict baseline comparison across strategies without altering any parameters post-hoc.
- **Cost:** **Low**. Restricts unnecessary token usage by early abort.
- **Leakage Risk:** **Zero**. No additional search queries are permitted.
- **Implementation Blast Radius:** **None**. Code remains untouched.
- **Scientific Validity:** **High**. Keeps the scientific baseline strictly frozen and avoids parameter-tuning on the test dataset.
- **Probability of Completing T01-T05:** **Low**. Strategy E will consistently fail on tasks that trigger cognitive loops (T02).

### Option B: Increase Planner initial from 3 to 4
- **Fairness:** **Moderate**. Strategy E gets slightly more budget, which deviates from the initial plan but allows room for discovery.
- **Cost:** **Slightly Higher**. Consumes more tokens due to extra retrieval loops.
- **Leakage Risk:** **Slightly Higher**. More queries increase the chances of hit-matching on code chunks.
- **Implementation Blast Radius:** **Trivial**. Change a single budget setting in `arag_multi_agent.py`.
- **Scientific Validity:** **Moderate**. Post-hoc budget expansion can be seen as "tuning to the test set" to force completion.
- **Probability of Completing T01-T05:** **Moderate**. May allow Task T02 to proceed if the 4th query completes the loop, but other tasks might still abort if they loop on different queries.

### Option C: Increase Planner initial from 3 to 5
- **Fairness:** **Low**. Strategy E is given significantly more budget compared to Strategy C, altering the execution constraints.
- **Cost:** **High**. Heavy token consumption since Planner can spin up to 5 times.
- **Leakage Risk:** **Moderate**.
- **Implementation Blast Radius:** **Trivial**. Single-line modification.
- **Scientific Validity:** **Low**. Post-hoc expansion of limits weakens the baseline rigor.
- **Probability of Completing T01-T05:** **High**. Extra headroom allows the Planner to survive typical loops and complete.

### Option D: Unified Role-Agnostic Retrieval Pool (e.g., Planner + Coder Total = 5)
- **Fairness:** **Moderate**. Redistributes the existing budget among agents dynamically rather than giving unlimited expansion.
- **Cost:** **Moderate**. Capped at a total of 5.
- **Leakage Risk:** **Moderate**.
- **Implementation Blast Radius:** **Medium**. Requires rewrite of `_role_turn` and `ARAGMultiAgentStrategySession` budget enforcement to track a shared transaction log rather than role-phase scoped limits.
- **Scientific Validity:** **High**. Structurally sound concept where the multi-agent system allocates its finite retrieval capability based on need.
- **Probability of Completing T01-T05:** **High**. Allows Planner to use more queries if needed, while Coder uses fewer (or vice-versa).

### Option E: Prompt-Level Query Consolidation (Instructed Multi-Query)
- **Fairness:** **High**. Does not change the budget number; instead, improves agent capabilities.
- **Cost:** **Low**. Actually reduces costs by consolidating multiple distinct queries into a single multi-search call.
- **Leakage Risk:** **Low**.
- **Implementation Blast Radius:** **Medium**. Requires editing the Planner agent prompt (`planner.txt` template) to explicitly mandate multi-query syntax and prohibit exact repetitions, plus adding parsing support for batch queries.
- **Scientific Validity:** **Very High**. Enhances the prompt engineering and reasoning quality without altering budget constraints.
- **Probability of Completing T01-T05:** **High**. Directly stops loops and encourages the Planner to fetch everything in its first try.

### Option F: State-Level Evidence Reuse & Loop Interception
- **Fairness:** **High**. Strict budget limits of 3 remain, but redundant calls do not decrement budget or are blocked.
- **Cost:** **Very Low**. De-duplicates identical queries, saving token overhead.
- **Leakage Risk:** **Low**.
- **Implementation Blast Radius:** **Medium**. Modify `_role_turn` or `RetrievalSession` to track prior queries in the transaction history and return cached results or block duplicate calls from consuming the budget.
- **Scientific Validity:** **Very High**. Improves systemic robustness against LLM repetition defects.
- **Probability of Completing T01-T05:** **High**. Planner is forced to diversify or is saved from wasting its budget on duplicate misses.

---

## 4. Evaluation Summary Matrix

| Metric | Option A | Option B | Option C | Option D | Option E (Recommended) | Option F |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fairness** | **High** | Moderate | Low | Moderate | **High** | **High** |
| **Cost Efficiency** | **High** | Moderate | Low | Moderate | **Very High** | **Very High** |
| **Leakage Safety** | **High** | Moderate | Low | Moderate | **High** | **High** |
| **Implementation Radius** | **None** | Trivial | Trivial | Medium | Medium | Medium |
| **Scientific Validity** | **High** | Moderate | Low | High | **Very High** | **Very High** |
| **Completion Probability**| Low | Moderate | High | High | **High** | **High** |

---

## 5. Architectural Recommendations (Future Work)

For future development cycles beyond Milestone 7, the following combined approach is highly recommended:

1. **Implement Option E (Prompt-Level Query Consolidation):**
   - Redesign the Planner's instructions in `planner.txt` to require query consolidation.
   - Instruct the Planner to provide up to 3 distinct search terms in a single turn as a batch request, and explicitly guide it to select alternative keywords (fallbacks) if initial terms fail.
   
2. **Implement Option F (Loop Interception & Cache Reuse):**
   - Introduce a deduplication interceptor in `experiments/strategies/arag_multi_agent.py` to cache query results.
   - If an agent sends an identical query in the same phase, the controller should immediately return the cached result (even if empty) without deducting from the retrieval budget.

---

## 6. Rerun Traceability Requirements

- **Strict New ID Rule:** If a future execution run is authorized, it **MUST** use a brand-new Experiment ID (e.g., `m7e_full_20260612T020000Z` or similar), and **MUST NOT** resume or overwrite `m7e_full_20260612T010000Z`.
- **Durable Audit Trail:** All past aborted JSONL files and partial retrieval logs remain completely frozen and preserved for audit traceability.

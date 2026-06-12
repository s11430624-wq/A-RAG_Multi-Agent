# Milestone 7-E.8 Plan: Retrieval Budget Policy Decision Plan

This document defines the **Retrieval Budget Policy Decision Plan** under **Milestone 7-E.8 (M7-E.8)**. 
Following the Controlled Abort of the final rerun `m7e_full_20260611T230000Z` due to `RetrievalBudgetExceededError` in Strategy E (rep02), this plan evaluates and compares retrieval budget policies to guide future full-scale experiment executions.

---

## 1. Context & The Core Problem

During the execution of `m7e_full_20260611T230000Z`, run `m7e_full_20260611T230000Z__T01__E__rep02__seed42` triggered a **Controlled Abort** because the Planner agent of Strategy E requested its 3rd retrieval during the initial phase. 
*   **Enforced Limit:** The current system enforces `_BUDGETS = {("Planner", "initial"): 2, ("Coder", "initial"): 2, ("Reviewer", "initial"): 1}`.
*   **Observed Behavior:** The Planner performed 2 successful retrieval queries (logged with 34 retrieved tokens total), and then attempted a 3rd query, triggering `retrieval_count >= budget` (`2 >= 2` holds true), which correctly raised `RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted` to prevent runaway costs.
*   **The Conflict:** Strategy E is designed as an Active Retrieval-Augmented Generation (A-RAG) strategy. However, some tasks require more than 2 initial search queries to find style guides, APIs, and relevant files. A rigid limit of 2 calls halts execution under strict fail-closed safety guards, while a loose budget risks runaway token costs and API spending.

---

## 2. Policy Options Comparison

We analyze and compare 5 distinct policy options across 6 critical evaluation axes:

### Summary Matrix

| Option | Description | Fairness | Cost | Leakage Risk | A/C/E Comparability | Scientific Validity | Blast Radius |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A: Preserve Current Budget** | Keep budget = 2, accept abort evidence as final. | **High** (uniform baseline) | **Zero** (no new calls) | **Zero** | **None** (incomplete dataset) | **Low** (incomplete dataset) | **Zero** (no changes) |
| **B: Initial Budget 2 ➔ 3** | Incremental increase to 3 queries for Planner initial. | **High** | **Low-Medium** (+1 call/run) | **Zero** | **High** (all Strategy E runs use same limit) | **High** (allows completion) | **Low** (minor change in Python dictionary) |
| **C: Initial Budget 2 ➔ 4** | Generous increase to 4 queries for Planner initial. | **High** | **Medium** (+2 calls/run) | **Zero** | **High** | **High** (fully completed runs) | **Low** (minor change in Python dictionary) |
| **D: Prompt-Level Discipline** | Reinforce prompt to self-limit queries to ≤2; budget = 2. | **Low** (model might hallucinate / fail) | **Low** (no budget increase) | **Zero** | **Low** (unstable model behavior) | **Low** (non-deterministic results) | **Medium** (requires prompt adjustments) |
| **E: Adaptive / Shared Budget** | Shared budget pool (e.g. max 5) or difficulty-based scaling. | **Medium** (dynamic pools make comparison harder) | **High** (dynamic bounds) | **Low** | **Medium** (non-uniform run budgets) | **Medium** (variable environments) | **High** (complex schema and logic changes) |

---

### In-Depth Option Analysis

#### Option A: Preserve current budget, accept abort evidence (Halt & Preserve)
*   **Fairness:** High. No dynamic or ad-hoc rule adjustments are introduced mid-experiment.
*   **Cost:** Zero. No further API spending, Gateway usage, or model token calls.
*   **Leakage Risk:** Zero. All inputs/outputs are completely frozen.
*   **A/C/E Comparability:** None. Because the 45-run experiment is permanently aborted at 7/45 runs, we do not have a complete dataset to compare Strategy E against Strategy A and C.
*   **Scientific Validity:** Low for comparative analysis, but High as proof of budget/safety mechanism correctness. The data serves as live evidence that the system fails closed as designed.
*   **Implementation Blast Radius:** Zero. No codebase, configuration, or test modifications.

#### Option B: Planner initial budget 2 ➔ 3 (Incremental Headroom)
*   **Fairness:** High. A uniform, static budget is applied to all Strategy E runs equally.
*   **Cost:** Low to Medium. Strategy E runs are allowed at most 1 additional initial model request and retrieval execution. The cost impact is minimal and fits well within the absolute project limits.
*   **Leakage Risk:** Zero. The retrieval tool operates under the same strict path-denylist constraints.
*   **A/C/E Comparability:** High. Strategy E is allowed slight headroom to showcase its retrieval capability fairly without breaking comparability against zero-retrieval strategies (A and C).
*   **Scientific Validity:** High. Allows Strategy E runs to successfully bypass rigid thresholds and complete the experiment, producing a complete 45-run comparative dataset.
*   **Implementation Blast Radius:** Low. Only requires modifying one integer value in `_BUDGETS` within `experiments/strategies/arag_multi_agent.py` (`("Planner", "initial"): 3`).

#### Option C: Planner initial budget 2 ➔ 4 (Generous Headroom)
*   **Fairness:** High. Uniform static budget applied to all runs.
*   **Cost:** Medium. Allows up to 4 initial queries, which can double the retrieval cost for simple tasks where 2 queries would have sufficed if the model is talkative.
*   **Leakage Risk:** Zero. Path-denylist constraints are fully preserved.
*   **A/C/E Comparability:** High. Provides an excellent evaluation of how a "fully-informed" retrieval strategy compares to zero-retrieval.
*   **Scientific Validity:** High. Guarantees successful completion of all Strategy E tasks by eliminating narrow retrieval bottlenecks.
*   **Implementation Blast Radius:** Low. Only requires modifying one integer value in `_BUDGETS` within `experiments/strategies/arag_multi_agent.py` (`("Planner", "initial"): 4`).

#### Option D: Prompt-level retrieval discipline, budget unchanged
*   **Fairness:** Low. It penalizes the agent's capability by forcing it to operate under strict token/reasoning constraints while attempting to count its own tool-use calls. State-of-the-art models are notoriously bad at precise tool-call self-counting.
*   **Cost:** Low. No changes to budget bounds, but higher prompt token overhead (adding limiting instructions).
*   **Leakage Risk:** Zero.
*   **A/C/E Comparability:** Low. The retrieval capability becomes bottlenecked by prompt compliance, making Strategy E's comparison unrepresentative of actual A-RAG potential.
*   **Scientific Validity:** Low. Results will carry a high degree of non-determinism and model-compliance variance rather than strategy-effectiveness variance.
*   **Implementation Blast Radius:** Medium. Requires editing prompt templates and re-evaluating prompt engineering for all Strategy E files.

#### Option E: Evidence-sharing / adaptive retrieval budget
*   **Fairness:** Medium. Allowing different runs or tasks to have different budget ceilings based on dynamic pools reduces the uniformity of the scientific baseline.
*   **Cost:** High. Code complexity is high, and dynamic pooling can lead to unchecked runaway retrievals in outlier tasks.
*   **Leakage Risk:** Low.
*   **A/C/E Comparability:** Medium. Comparing Strategy E (which would have variable budgets per task) to Strategy A and C becomes much harder to analyze.
*   **Scientific Validity:** Medium. Breaks the "controlled variable" principle of experimental design.
*   **Implementation Blast Radius:** High. Requires rewriting the budget tracking classes, strategy execution loops, and updating schemas/tests to support dynamic budget allocations.

---

## 3. Recommended Policy Decision

**We strongly recommend Option B (Planner initial budget 2 ➔ 3) as the primary policy decision.**

### Justification
1.  **Statistical Balance:** Strategy E's failure occurred exactly on the 3rd requested call under `rep02`. Giving the Planner exactly **3** calls of headroom is the minimal necessary modification (the "Principle of Least Privilege/Headroom") to allow task completion while maintaining strict budget safety.
2.  **Comparative Fairness:** Incremental increase preserves the core comparison parameters between Strategy A (0), Strategy C (0), and Strategy E (A-RAG), showing the marginal benefit of retrieval with tight limits.
3.  **Minimal Development Impact:** It requires modifying a single line in a Python strategy module without altering JSON schemas, config contracts, or rewriting budget trackers.

---

## 4. Rerun Protocol & Frozen Abort Guard

To guarantee scientific auditability and protect historical evidence:

1.  **State Protection:**
    The aborted dataset `m7e_full_20260611T230000Z` is **completely frozen**. No resume operations, partial record additions, or metadata rewrites are permitted on this ID.
2.  **Mandatory New ID Rule:**
    If a rerun is performed in the future (under Option B or C), **it MUST be executed under a brand new, unique Experiment ID** (e.g., `m7e_full_20260611T233000Z` or `m7e_rerun_...`). 
3.  **No Resume Guard:**
    Any script command attempting to resume `m7e_full_20260611T230000Z` must fail-closed. This ensures that unhardened, hardened, and budget-adjusted execution records are never mixed within the same dataset file.

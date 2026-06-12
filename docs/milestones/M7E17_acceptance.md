# Milestone 7-E.17 Retrieval Budget Option F TDD Implementation Acceptance

**Status:** Completed (TDD Implementation, Offline Only)

**Date:** 2026-06-12

---

## 1. Scope

M7-E.17 implements the M7-E.16 Option F decision by increasing only the Strategy E `Planner/initial` retrieval budget from `3` to `5`.

This milestone does **not** execute any live rerun, smoke run, Gateway request, model call, retrieval over production results, or resume of old experiment IDs.

## 2. Files Modified

| File | Change |
| :--- | :--- |
| `experiments/strategies/arag_multi_agent.py` | Changed `ARAGMultiAgentStrategySession._BUDGETS[("Planner", "initial")]` from `3` to `5`. |
| `tests/strategies/test_arag_multi_agent.py` | Added and updated TDD tests for 5 distinct Planner retrievals allowed, 6th distinct retrieval fail-closed, duplicate cache preservation, and A/C zero-retrieval regression. |
| `docs/milestones/M7_acceptance.md` | Updated M7 status and deliverables to include M7-E.17 implementation completion. |
| `docs/milestones/M7E17_acceptance.md` | Added this acceptance record. |

## 3. Final Budget Policy

```python
ARAGMultiAgentStrategySession._BUDGETS = {
    ("Planner", "initial"): 5,
    ("Coder", "initial"): 2,
    ("Reviewer", "initial"): 1,
}
```

Repair phases remain governed by the existing code path:

```python
budget = 2 if phase.startswith("repair_") else self._BUDGETS[(role, phase)]
```

## 4. TDD Evidence

### RED

New test:

```text
tests/strategies/test_arag_multi_agent.py::test_strategy_e_planner_initial_five_distinct_retrievals_allowed
```

Observed RED before production change:

```text
FAILED with RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted
```

This proved the test was exercising the previous `Planner/initial=3` budget boundary.

### GREEN

After the minimal production change:

```text
tests/strategies/test_arag_multi_agent.py
18 passed
```

Then the full strategy suite passed:

```text
tests/strategies
81 passed
```

## 5. Acceptance Matrix

| ID | Requirement | Verification | Status |
| :--- | :--- | :--- | :--- |
| M7E17-001 | RED test proves 5 distinct Planner retrievals failed under previous budget | Single test failed with `RetrievalBudgetExceededError` before code change | Completed |
| M7E17-002 | Planner initial budget is now 5 | `ARAGMultiAgentStrategySession._BUDGETS[("Planner", "initial")] == 5` | Completed |
| M7E17-003 | Coder and Reviewer budgets unchanged | Coder initial remains `2`, Reviewer initial remains `1` | Completed |
| M7E17-004 | Repair budget unchanged | Existing repair branch remains `2` | Completed |
| M7E17-005 | Five distinct Planner retrievals are allowed | `test_strategy_e_planner_initial_five_distinct_retrievals_allowed` passes | Completed |
| M7E17-006 | Sixth distinct Planner retrieval fails closed | `test_strategy_e_planner_initial_sixth_distinct_retrieval_fails_closed` passes | Completed |
| M7E17-007 | Duplicate retrievals still do not consume budget or duplicate logs | duplicate/cache tests pass | Completed |
| M7E17-008 | A/C strategies remain retrieval-free | Strategy regression test confirms A/C unaffected | Completed |
| M7E17-009 | Live gate remains closed | Live gate tests are part of required verification before preflight | Completed |
| M7E17-010 | No live execution performed | No live command, Gateway request, model call, or rerun was executed | Completed |

## 6. Required Next State

M7-E.17 completes the offline code change only. The next safe step is a separate **M7-E.18 Final Rerun Preflight** with a new canonical experiment ID.

The next preflight must:

1. Confirm no collision for the new raw JSONL, artifact, retrieval, diagnostics, derived, and workspace paths.
2. Recheck all frozen hashes.
3. Confirm the final `_BUDGETS` policy is `Planner=5`, `Coder=2`, `Reviewer=1`.
4. Draft the exact live-run command.
5. Stop for explicit operator approval before any Gateway/model call.

## 7. Boundary Declaration

During M7-E.17:

- No live-run was executed.
- No smoke-run was executed.
- No Gateway connection was made.
- No model was called.
- No old experiment ID was resumed.
- No raw JSONL, artifact, retrieval log, diagnostic, derived output, or workspace was generated.
- Frozen M7-D, M7-E.3, M7-E.7, M7-E.11, and M7-E.15 outputs remain historical audit artifacts.


# Milestone 7-E.16 Retrieval Budget Option F Decision Acceptance

**Status:** Completed (Decision / Plan Only)

**Date:** 2026-06-12

---

## 1. Scope

This milestone records the post-M7-E.15 decision that Strategy E needs a larger bounded Planner initial retrieval budget for medium-complexity integration tasks.

This milestone is **not** an implementation milestone. It does not modify production code, tests, schemas, configs, raw results, artifacts, retrieval logs, diagnostics, derived outputs, or workspaces.

## 2. Evidence Used

Latest controlled abort:

```text
Experiment ID: m7e_full_20260612T020000Z
Failed run: m7e_full_20260612T020000Z__T02__E__rep01__seed42
Abort reason: RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted
Completed records: 15/45
Raw JSONL SHA-256: 327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456
```

Key finding:

```text
The failed T02 Strategy E Planner made three distinct successful retrievals:
1. get_student_course_summary
2. get_grades_by_student
3. get_student_by_id

The fourth attempted distinct retrieval was blocked by Planner/initial budget=3.
```

Interpretation:

```text
This is not a duplicate-query loop. M7-E.13 loop hardening remains valid.
The remaining issue is bounded evidence headroom for Strategy E on cross-module tasks.
```

## 3. Decision

Recommended next implementation:

```python
ARAGMultiAgentStrategySession._BUDGETS = {
    ("Planner", "initial"): 5,
    ("Coder", "initial"): 2,
    ("Reviewer", "initial"): 1,
}
```

The repair budget remains:

```python
budget = 2 if phase.startswith("repair_") else self._BUDGETS[(role, phase)]
```

The implementation must preserve:

1. Duplicate retrieval cache before budget decrement.
2. Role/phase/tool/query/top_k scoped cache keys.
3. A/C zero retrieval.
4. No derived outputs on controlled abort.
5. New experiment ID for any future live rerun.
6. Frozen historical files unchanged.

## 4. Acceptance Matrix

| ID | Requirement | Verification | Status |
| :--- | :--- | :--- | :--- |
| M7E16-001 | M7-E.16 plan exists | `docs/superpowers/plans/2026-06-12-m7e16-retrieval-budget-option-f.md` exists | Completed |
| M7E16-002 | Plan cites M7-E.15 abort evidence | Plan includes `m7e_full_20260612T020000Z__T02__E__rep01__seed42` and the three distinct retrieval queries | Completed |
| M7E16-003 | Decision recommends bounded budget expansion | Plan recommends Planner initial `3 -> 5` only | Completed |
| M7E16-004 | Coder/Reviewer/repair budgets remain unchanged | Plan explicitly keeps Coder initial `2`, Reviewer initial `1`, repair `2` | Completed |
| M7E16-005 | Duplicate-query hardening remains required | Plan requires keeping cache-before-budget behavior | Completed |
| M7E16-006 | Old partial experiment IDs must not be resumed | Plan rejects resume of `m7e_full_20260612T020000Z` and earlier partial IDs | Completed |
| M7E16-007 | Future live rerun requires new preflight | Plan requires a new canonical full-run ID and explicit operator approval | Completed |
| M7E16-008 | No production code modified in this milestone | File changes are limited to docs | Completed |
| M7E16-009 | No live call or Gateway connection performed | This milestone performs no live command | Completed |
| M7E16-010 | M7 acceptance status updated | `docs/milestones/M7_acceptance.md` references M7-E.16 | Completed |

## 5. Frozen Hashes That Must Remain Unchanged

```text
results/raw/gates/m7d_smoke_20260611T123000Z.json
a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a

results/raw/m7d_smoke_20260611T123000Z.jsonl
74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c

results/raw/m7e_full_20260611T210000Z.jsonl
c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638

results/raw/m7e_full_20260611T230000Z.jsonl
d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7

results/raw/m7e_full_20260612T010000Z.jsonl
67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a

results/raw/m7e_full_20260612T020000Z.jsonl
327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456
```

## 6. Boundary Declaration

During M7-E.16:

- No live-run was executed.
- No smoke-run was executed.
- No Gateway connection was made.
- No model was called.
- No retrieval session was executed.
- No raw JSONL, artifact, retrieval log, diagnostic, derived output, or workspace was created.
- No schema, config, task definition, or student system file was modified.


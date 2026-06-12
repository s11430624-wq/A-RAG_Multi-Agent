# Milestone 7-E.18 Final Rerun Preflight Acceptance

**Status:** Completed (Preflight Only / Awaiting Explicit Approval)

**Date:** 2026-06-12

---

## 1. Scope

M7-E.18 performs the offline preflight for the next real 45-run full rerun after M7-E.17 raised Strategy E `Planner/initial` retrieval budget to `5`.

No live execution occurs in this milestone.

## 2. Proposed Experiment ID

```text
m7e_full_20260612T030000Z
```

## 3. Acceptance Matrix

| ID | Requirement | Evidence | Status |
| :--- | :--- | :--- | :--- |
| M7E18-001 | Preflight document exists | `docs/milestones/M7E18_preflight.md` | Completed |
| M7E18-002 | New canonical experiment ID selected | `m7e_full_20260612T030000Z` | Completed |
| M7E18-003 | Raw JSONL output path collision-free | `results/raw/m7e_full_20260612T030000Z.jsonl` does not exist | Completed |
| M7E18-004 | Artifact root collision-free | `results/raw/artifacts/m7e_full_20260612T030000Z` does not exist | Completed |
| M7E18-005 | Retrieval log root collision-free | `results/raw/retrieval/m7e_full_20260612T030000Z` does not exist | Completed |
| M7E18-006 | Diagnostics root collision-free | `results/raw/diagnostics/m7e_full_20260612T030000Z` does not exist | Completed |
| M7E18-007 | Derived outputs collision-free | `results/derived/m7e_full_20260612T030000Z.csv` and summary path do not exist | Completed |
| M7E18-008 | Workspace path collision-free | `workspaces/m7e_full_20260612T030000Z` does not exist | Completed |
| M7E18-009 | Strategy E budget confirmed | Planner `5`, Coder `2`, Reviewer `1` | Completed |
| M7E18-010 | Frozen hashes rechecked | M7-D smoke and all partial full-run JSONL hashes match expected values | Completed |
| M7E18-011 | Exact live command drafted | Command included in `M7E18_preflight.md` | Completed |
| M7E18-012 | Stop point preserved | Document requires explicit operator approval before execution | Completed |
| M7E18-013 | No live execution performed | No Gateway/model command executed in this milestone | Completed |

## 4. Required Approval Before Next Step

M7-E.19 must not start until the operator explicitly approves:

```text
批准執行 M7-E.19，使用 experiment id m7e_full_20260612T030000Z
```

## 5. Boundary Declaration

During M7-E.18:

- No live-run was executed.
- No smoke-run was executed.
- No Gateway connection was made.
- No model was called.
- No old experiment ID was resumed.
- No raw JSONL, artifact, retrieval log, diagnostic, derived output, or workspace was generated.


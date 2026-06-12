# Milestone 7-E.18 Final Rerun Preflight After Option F Budget Implementation

**Status:** Completed (Preflight Only / Stop Point)

**Date:** 2026-06-12

---

## 1. Purpose

This document performs the final offline preflight for a new real 45-run full experiment after M7-E.17 implemented Option F:

```text
Planner/initial retrieval budget: 5
Coder/initial retrieval budget: 2
Reviewer/initial retrieval budget: 1
Repair retrieval budget: 2
```

This preflight does **not** execute a live run, connect to the Gateway, call a model, resume an old experiment ID, or modify frozen outputs.

## 2. Proposed New Experiment ID

```text
m7e_full_20260612T030000Z
```

Rationale:

1. It is a new canonical full-run ID.
2. It does not collide with previous partial IDs:
   - `m7e_full_20260611T210000Z`
   - `m7e_full_20260611T230000Z`
   - `m7e_full_20260612T010000Z`
   - `m7e_full_20260612T020000Z`
3. It must not be resumed from any previous output.

## 3. Output Collision Check

All target paths were checked and do not exist:

| Path | Exists | Result |
| :--- | :---: | :--- |
| `results/raw/m7e_full_20260612T030000Z.jsonl` | false | Clean |
| `results/raw/artifacts/m7e_full_20260612T030000Z` | false | Clean |
| `results/raw/retrieval/m7e_full_20260612T030000Z` | false | Clean |
| `results/raw/diagnostics/m7e_full_20260612T030000Z` | false | Clean |
| `results/derived/m7e_full_20260612T030000Z.csv` | false | Clean |
| `results/derived/m7e_full_20260612T030000Z_summary.md` | false | Clean |
| `workspaces/m7e_full_20260612T030000Z` | false | Clean |

Conclusion: the proposed ID is collision-free.

## 4. Strategy E Budget Confirmation

Current implementation in `experiments/strategies/arag_multi_agent.py`:

```python
ARAGMultiAgentStrategySession._BUDGETS = {
    ("Planner", "initial"): 5,
    ("Coder", "initial"): 2,
    ("Reviewer", "initial"): 1,
}
```

Repair budget remains:

```python
budget = 2 if phase.startswith("repair_") else self._BUDGETS[(role, phase)]
```

Interpretation:

- M7-E.15 failed because T02 Strategy E needed a fourth distinct Planner retrieval after three successful distinct queries.
- M7-E.17 now permits up to five distinct Planner initial retrievals.
- The sixth distinct Planner retrieval still fails closed.
- Duplicate retrievals still reuse cache and do not decrement budget or write duplicate logs.

## 5. Frozen Historical Hashes

The following frozen files were rehashed and remain unchanged:

| File | SHA-256 |
| :--- | :--- |
| `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` |
| `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` |
| `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` |
| `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` |
| `results/raw/m7e_full_20260612T010000Z.jsonl` | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` |
| `results/raw/m7e_full_20260612T020000Z.jsonl` | `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456` |

## 6. Frozen Live-Run Command Draft

This command is a draft only. It must not be executed without explicit operator approval.

```powershell
$env:ARAG_RUN_LIVE_GATEWAY='1'
$env:ARAG_EXECUTE_FULL_RUN_ONCE='1'
Remove-Item Env:ARAG_USE_FAKE_FULL_RUN_PROVIDER -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'

python -B -m experiments.cli live-run `
  --repo-root . `
  --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json `
  --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a `
  --full-experiment-id m7e_full_20260612T030000Z `
  --human-approval FULL_RUN `
  --approved-input-token-budget 1000000 `
  --approved-output-token-budget 500000 `
  --approved-wall-clock-seconds 3600 `
  --allow-unknown-cost
```

## 7. Expected Safety Behavior

If approved and executed later:

1. The command must run exactly once for this ID.
2. It must not set `ARAG_USE_FAKE_FULL_RUN_PROVIDER`.
3. It must not resume any previous partial ID.
4. It must stop immediately on controlled abort.
5. It must write only completed, schema-valid records.
6. It must not generate derived outputs unless all 45 runs complete.
7. It must preserve all historical frozen files listed above.

## 8. Offline Verification Performed

The following checks were performed during this preflight:

```text
Output collision check: passed
Budget source check: Planner=5, Coder=2, Reviewer=1
Frozen hash recheck: passed
```

No live command was executed.

## 9. Stop Point

**STOP HERE.**

Do not execute M7-E.19 live rerun unless the operator explicitly approves the exact command above.

Approval phrase recommended:

```text
批准執行 M7-E.19，使用 experiment id m7e_full_20260612T030000Z
```

## 10. Boundary Confirmation

- No live-run was executed.
- No Gateway connection was made.
- No model was called.
- No old experiment ID was resumed.
- No raw JSONL, artifact, retrieval log, diagnostic, derived output, or workspace was created.
- Frozen smoke and partial full-run outputs remain unchanged.


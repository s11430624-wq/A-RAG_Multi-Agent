# Milestone 7-E.26: Final Rerun Preflight after Gateway 429 Recovery

**Status:** Completed (Offline Preflight Only / Live Execution Blocked)

**Date:** 2026-06-12

**Proposed experiment ID:** `m7e_full_20260612T050000Z`

## 1. Scope

M7-E.26 verifies that the M7-E.25 rate-limit recovery implementation is ready
for a newly approved full run. This milestone is read-only with respect to
production results.

This milestone does not:

- execute `live-run`, `live-smoke`, or `live-probe`;
- connect to `127.0.0.1:8787`;
- call a model;
- read a credential;
- resume an existing experiment ID;
- create raw JSONL, artifacts, retrieval logs, diagnostics, derived outputs, or
  workspaces.

## 2. Production Contract Audit

The following values were read from the current production code:

| Contract | Verified value |
| :--- | :--- |
| Provider | `openai_compatible_gateway` |
| Model | `GPT5.4` |
| API base | `http://127.0.0.1:8787/v1` |
| Seed | `42` |
| Strategies | `A`, `C`, `E` |
| Repetitions | `3` |
| Planned runs | `45` |
| Physical provider-attempt ceiling | `660` |
| Input-token ceiling | `1,000,000` |
| Output-token ceiling | `500,000` |
| Wall-clock ceiling | `5,400` seconds |
| Minimum interval between physical attempts | `1` second |
| Inter-run cooldown | `10` seconds |
| Retry-After clamp | `1..120` seconds |
| Missing/malformed 429 Retry-After fallback | `30`, then `60` seconds |
| Consecutive infrastructure failure threshold | `2` |
| Gateway final-failure threshold | `2` |

Strategy E remains:

```text
Planner/initial=5
Coder/initial=3
Reviewer/initial=1
repair=2
```

The Coder receives Planner evidence as read-only evidence only. Search
authorization and retrieval cache remain role/phase scoped.

## 3. Output Collision Check

All paths reserved for `m7e_full_20260612T050000Z` were physically checked and
do not exist:

| Path | Exists |
| :--- | :---: |
| `results/raw/m7e_full_20260612T050000Z.jsonl` | No |
| `results/raw/artifacts/m7e_full_20260612T050000Z` | No |
| `results/raw/retrieval/m7e_full_20260612T050000Z` | No |
| `results/raw/diagnostics/m7e_full_20260612T050000Z` | No |
| `results/derived/m7e_full_20260612T050000Z.csv` | No |
| `results/derived/m7e_full_20260612T050000Z_summary.md` | No |
| `workspaces/m7e_full_20260612T050000Z` | No |

This ID must not be used before the M7-E.27 approval sentence is supplied.

## 4. Frozen Hash Revalidation

The following physical SHA-256 values were recalculated during this preflight:

| Frozen file | SHA-256 |
| :--- | :--- |
| `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` |
| `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` |
| `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` |
| `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` |
| `results/raw/m7e_full_20260612T010000Z.jsonl` | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` |
| `results/raw/m7e_full_20260612T020000Z.jsonl` | `327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456` |
| `results/raw/m7e_full_20260612T030000Z.jsonl` | `548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664` |
| `results/raw/m7e_full_20260612T040000Z.jsonl` | `fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d` |

No historical experiment ID may be resumed or appended.

## 5. Frozen M7-E.27 Command Draft

The following PowerShell command is a draft only. M7-E.26 does not authorize
its execution.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:ARAG_RUN_LIVE_GATEWAY='1'
$env:ARAG_EXECUTE_FULL_RUN_ONCE='1'
Remove-Item Env:ARAG_USE_FAKE_FULL_RUN_PROVIDER -ErrorAction SilentlyContinue

python -B -m experiments.cli live-run `
  --repo-root . `
  --approved-smoke-report "results/raw/gates/m7d_smoke_20260611T123000Z.json" `
  --approved-smoke-sha256 "a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a" `
  --full-experiment-id "m7e_full_20260612T050000Z" `
  --human-approval FULL_RUN `
  --approved-input-token-budget 1000000 `
  --approved-output-token-budget 500000 `
  --approved-wall-clock-seconds 5400 `
  --allow-unknown-cost
```

The CLI binds the physical provider-attempt ceiling to `660`; it is not a
user-adjustable command-line argument.

## 6. Offline Verification

Preflight gate and recovery tests:

```text
python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py tests/live/test_rate_limit_and_recovery.py -q
66 passed
```

The M7-E.26 non-hidden regression result was:

```text
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
594 passed, 2 skipped in 69.63s
```

## 7. Risk and Abort Policy

- Cost remains unknown and requires `--allow-unknown-cost`.
- A final 429 after bounded retries remains fail-closed.
- Attempt `661` must be rejected before transport send.
- Wall-clock exhaustion must be detected before and after every pacing wait.
- Only completed records may enter the raw JSONL.
- A failed active run must not produce a completed result record.
- Provider failure diagnostics must be sanitized and exclusive-create.
- Derived outputs must be generated only after all 45 records complete.

## 8. Critical Stop Point

M7-E.27 remains blocked. Execution requires this exact operator approval:

```text
批准執行 M7-E.27，使用 experiment id m7e_full_20260612T050000Z，批准 physical attempts 660 與 wall clock 5400 秒
```

Without that exact approval, do not set the execution environment variables and
do not run the frozen command.

## 9. Subsequent M7-E.27 Result

The operator later supplied the exact approval sentence. M7-E.27 was executed
once and ended in a controlled abort:

```text
Experiment ID: m7e_full_20260612T050000Z
Completed records: 15/45
Failed active run: T02 / E / rep01
Abort reason: BudgetExceededError: Input token budget exceeded
```

See `docs/milestones/M7E27_execution_audit.md`. No resume or automatic rerun
was performed.

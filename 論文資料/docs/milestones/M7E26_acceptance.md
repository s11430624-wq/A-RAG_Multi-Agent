# Milestone 7-E.26 Acceptance: Final Rerun Preflight

**Status:** Completed (Offline Preflight Only / M7-E.27 Blocked)

## Acceptance Matrix

| ID | Requirement | Status |
| :--- | :--- | :---: |
| M7E26-001 | M7-E.26 preflight document exists | Completed |
| M7E26-002 | New canonical ID is `m7e_full_20260612T050000Z` | Completed |
| M7E26-003 | Raw JSONL path is collision-free | Completed |
| M7E26-004 | Artifact root is collision-free | Completed |
| M7E26-005 | Retrieval log root is collision-free | Completed |
| M7E26-006 | Diagnostics root is collision-free | Completed |
| M7E26-007 | Derived output paths are collision-free | Completed |
| M7E26-008 | Workspace path is collision-free | Completed |
| M7E26-009 | Provider/model/API-base/seed configuration matches the approved live profile | Completed |
| M7E26-010 | Physical attempt ceiling is exactly `660` | Completed |
| M7E26-011 | Input/output token ceilings remain `1,000,000` / `500,000` | Completed |
| M7E26-012 | Wall-clock ceiling is exactly `5,400` seconds | Completed |
| M7E26-013 | Shared pacing policy is `1` second per attempt and `10` seconds per completed run | Completed |
| M7E26-014 | Retry-After is bounded to `1..120` seconds with `30/60` fallback | Completed |
| M7E26-015 | All eight frozen file hashes were recalculated and matched | Completed |
| M7E26-016 | Frozen PowerShell command uses the new ID and amended wall-clock budget | Completed |
| M7E26-017 | Gate/revalidation/recovery suite passes offline | Completed |
| M7E26-018 | No live-run, Gateway connection, model call, credential read, or new execution output occurred | Completed |
| M7E26-019 | Old experiment IDs remain non-resumable and immutable | Completed |
| M7E26-020 | M7-E.27 remains blocked pending the exact operator approval sentence | Completed |

## Required Approval

M7-E.27 must not execute until the operator supplies:

```text
批准執行 M7-E.27，使用 experiment id m7e_full_20260612T050000Z，批准 physical attempts 660 與 wall clock 5400 秒
```

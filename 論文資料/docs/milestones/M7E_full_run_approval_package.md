# Milestone 7-E: Full-Run Approval Package

> [!IMPORTANT]
> **Status:** M7-E.0 Approval Gate, M7-E.1 Plan, and M7-E.2 Dry Activation Completed. Actual live full-run execution (M7-E.3) was executed and has entered a Controlled Abort state with 7/45 runs successfully completed and preserved. Resume decision pending. Please refer to [M7-E.3 Abort Audit](M7E3_abort_audit.md) for full details.

## Smoke Run Reference
- **Approved Smoke Report Path**: `results/raw/gates/m7d_smoke_20260611T123000Z.json`
- **Approved Smoke SHA-256**: `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a`
- **Smoke Experiment ID**: `m7d_smoke_20260611T123000Z`

## Proposed Full-Run Parameters
- **Proposed Full Experiment ID Format**: `m7e_full_[0-9]{8}T[0-9]{6}Z`
- **Proposed Run Count**: `45`
- **Strategies**: `A`, `C`, `E` (15 runs per strategy)
- **Tasks**: `T01`, `T02`, `T03`, `T04`, `T05` (5 tasks)
- **Repetitions**: `3`
- **Model**: `GPT5.4`
- **Provider**: `openai_compatible_gateway`
- **Seed Policy**: Shared seed `42` for all runs

## Proposed Budget Limits
- **Approved Token Budget (Input)**: `1,000,000` tokens (suggested maximum)
- **Approved Token Budget (Output)**: `500,000` tokens (suggested maximum)
- **Approved Wall-Clock Seconds**: `3,600.0` seconds (1 hour, suggested maximum)
- **Allow Unknown Cost**: `false` (default)

## Safety & Revalidation Checklist
- Prior to starting the full run, the CLI must verify the raw JSONL matches `source_jsonl_sha256`.
- The CLI must recalculate and match both the artifact manifest set hash (`artifact_manifest_set_sha256`) and the retrieval log set hash (`retrieval_log_set_sha256`).
- **Warning**: The `unknown_cost` risk flag must be explicitly accepted before M7-E execution can start.

## Approval Protocol
- **Required Human Approval Token for Future Stage**: `FULL_RUN`
- **Execution Mode**: Offline composition check -> Operator approval confirmation -> Sequential execution

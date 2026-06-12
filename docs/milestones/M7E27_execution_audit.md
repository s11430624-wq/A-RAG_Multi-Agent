# Milestone 7-E.27 Real Full Rerun Execution Audit

**Status:** Controlled Abort / Partial Results Preserved / Final Dataset Not Complete

**Experiment ID:** `m7e_full_20260612T050000Z`

**Execution date:** 2026-06-12

## 1. Approval and One-Shot Boundary

The operator explicitly approved:

```text
批准執行 M7-E.27，使用 experiment id m7e_full_20260612T050000Z，批准 physical attempts 660 與 wall clock 5400 秒
```

The approved command was executed exactly once with:

- the real `hermes_vertex_gateway`;
- model `google/gemini-3.5-flash`;
- API base `http://127.0.0.1:8787/v1`;
- fake full-run provider disabled;
- physical provider-attempt ceiling `660`;
- input-token ceiling `1,000,000`;
- output-token ceiling `500,000`;
- wall-clock ceiling `5,400` seconds.

No automatic retry of the experiment and no resume were performed after the
process ended.

## 2. Execution Result

```text
Exit code: 1
Elapsed wall time: 1683.449 seconds
Final state: Controlled Abort
Completed records: 15/45
Failed active run: m7e_full_20260612T050000Z__T02__E__rep01__seed42
Abort reason: BudgetExceededError: Input token budget exceeded
```

The failed active run was rejected and was not appended as a completed result.

## 3. Raw JSONL Audit

```text
Path: results/raw/m7e_full_20260612T050000Z.jsonl
SHA-256: 5e7522eddd74f5ef631f02ae483ebf2351eded11f0f6b0f666f6bac93addd52f
Record count: 15
Unique completed run IDs: 15
Schema error lines: 0
valid_run: 15
infra_error: 0
```

Distribution:

```text
Strategies: A=6, C=6, E=3
Tasks: T01=9, T02=6, T03=0, T04=0, T05=0
Stop reasons: public_pass=2, repair_limit=13
```

Completed pass records:

```text
m7e_full_20260612T050000Z__T01__A__rep01__seed42
m7e_full_20260612T050000Z__T02__A__rep02__seed42
```

Completed-record totals:

```text
input_tokens=112868
output_tokens=103045
tool_calls=3
retrieved_tokens=51
```

## 4. Artifact Audit

```text
Manifest count: 15
Finalized provider_attempt_count sum: 62
Finalized call_records sum: 62
Verified artifact files: 165
Artifact hash errors: 0
Manifest input-token sum: 112868
Manifest output-token sum: 103045
```

The failed active run did not finalize an artifact manifest.

## 5. Retrieval Audit

```text
Retrieval log files: 4
Retrieval log lines: 6
Retrieval log token_count sum: 168
Logged role set: Planner
A/C retrieval logs: 0
```

Completed Strategy E logs:

```text
T01 E rep01: 1 line
T01 E rep02: 1 line
T01 E rep03: 1 line
```

Partial failed-run audit log:

```text
T02 E rep01: 3 lines / 117 tokens
```

The partial log is audit evidence only and has no corresponding completed raw
record.

## 6. Controlled Abort Root Cause

M7-E.25 successfully changed the prior Gateway 429 behavior:

- no terminal HTTP 429 occurred in this run;
- shared pacing and bounded retry logic remained active;
- the run progressed for approximately 28 minutes.

The new terminal condition was the global input-token budget:

```text
BudgetExceededError: Input token budget exceeded
```

The budget tracker checks a proposed token update before committing it. The 15
finalized runs account for `112,868` input tokens. The failed active run had
already consumed additional non-finalized calls, and its next response would
have raised the cumulative input total above `1,000,000`.

The exact failed-run attempt and token totals are **unknown** because:

- the failed run did not finalize a manifest;
- its staged call records were rolled back;
- the provider failure diagnostic records the outer `LiveExecutionAbort`, not
  the active run's non-finalized usage.

No token count is inferred or fabricated for the failed run.

## 7. Failure Diagnostic

One diagnostic was written:

```text
results/raw/diagnostics/m7e_full_20260612T050000Z/
  m7e_full_20260612T050000Z__T02__E__rep01__seed42/
  provider_failure.json
```

Its sanitized contents report:

```text
error_class=LiveExecutionAbort
sanitized_error_code=infrastructure_failure
final_http_status=null
attempt_count=0
elapsed_seconds=1682.219
```

This diagnostic contains no credential, raw response body, hidden-test path, or
reference-patch path. It also demonstrates the current audit limitation for a
budget abort: failed active-run usage is not durable.

## 8. Derived Outputs and Cleanup

```text
Derived CSV count: 0
Derived summary count: 0
Workspace for this experiment ID: absent
temp_sandbox_*: 0
.patch_tmp_*: 0
.patch_bak_*: 0
```

Derived outputs were correctly withheld because the 45-run dataset is
incomplete.

## 9. Frozen Historical Integrity

All eight pre-existing frozen files retain their expected SHA-256 values,
including:

```text
M7-D smoke report:
a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a

M7-D smoke JSONL:
74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c

M7-E.23 partial JSONL:
fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d
```

The full eight-file revalidation result was `ALL_MATCH=True`.

## 10. Final Execution Decision

M7-E.27 is the final authorized model execution in this milestone sequence.

- Do not resume `m7e_full_20260612T050000Z`.
- Do not allocate another experiment ID automatically.
- Do not increase the input-token budget and rerun without a separate research
  protocol amendment.
- Preserve this partial dataset as controlled-abort evidence.

The next stage, if requested, is M7-E.28 final read-only reporting and analysis.
It must not call a model or Gateway.

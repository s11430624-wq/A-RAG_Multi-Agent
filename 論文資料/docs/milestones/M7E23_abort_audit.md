# Milestone 7-E.23 Real Full Rerun Controlled Abort Audit

**Status:** Controlled Abort / Partial Results Preserved / Final Dataset Not Complete

**Experiment ID:** `m7e_full_20260612T040000Z`

**Date:** 2026-06-12

## 1. Execution Lifecycle

The operator explicitly approved:

```text
批准執行 M7-E.23，使用 experiment id m7e_full_20260612T040000Z
```

The command was executed exactly once with:

- real `openai_compatible_gateway`
- model `GPT5.4`
- API base `http://127.0.0.1:8787/v1`
- `ARAG_USE_FAKE_FULL_RUN_PROVIDER` removed
- no resume of an older experiment ID

Execution result:

```text
Exit code: 1
Elapsed wall time: 1007.3 seconds
Final state: Controlled Abort
Completed records: 15/45
Failed active run: m7e_full_20260612T040000Z__T02__E__rep01__seed42
Abort reason: ProviderTransportError: HTTP Error 429: Too Many Requests
```

The failed active run was rejected and was not appended to the completed raw JSONL.

## 2. Raw JSONL Audit

```text
Path: results/raw/m7e_full_20260612T040000Z.jsonl
SHA-256: fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d
Record count: 15
Schema-valid records: 15
Schema errors: 0
```

Distribution and completed-record totals:

```text
Strategies: A=6, C=6, E=3
Tasks: T01=9, T02=6, T03=0, T04=0, T05=0
valid_run=15
infra_error=0
input_tokens=115265
output_tokens=109379
retrieved_tokens=68
tool_calls=4
patch_apply_failures=13
```

Stop reasons:

```text
repair_limit=13
public_pass=2
```

Complete public and hidden pass records:

```text
m7e_full_20260612T040000Z__T02__A__rep01__seed42
m7e_full_20260612T040000Z__T02__A__rep02__seed42
```

## 3. Artifact Manifest Audit

```text
Artifact root: results/raw/artifacts/m7e_full_20260612T040000Z
Manifest count: 15
Verified artifact files: 167
Artifact hash errors: 0
Finalized provider_attempt_count sum: 63
Finalized call_records sum: 63
```

The failed active run did not finalize a manifest. Its failed provider attempt count is therefore not included in the finalized totals.

## 4. Retrieval Log Audit

```text
Retrieval root: results/raw/retrieval/m7e_full_20260612T040000Z
Retrieval log count: 4
A/C retrieval logs: 0
```

Completed E logs:

```text
T01 E rep01: 1 line
T01 E rep02: 2 lines
T01 E rep03: 1 line
```

Partial failed-run audit log:

```text
T02 E rep01: 3 lines
```

The partial log is audit evidence only. It has no corresponding completed raw record.

## 5. Root Cause

M7-E.21 successfully removed the prior Coder evidence-visibility and retrieval-budget blocker. The M7-E.23 active run progressed to `T02 / E / rep01`, but the Gateway eventually returned:

```text
HTTP 429: Too Many Requests
```

This is a provider/Gateway rate-limit failure, not a retrieval-budget or evidence-inheritance failure. The runner correctly stopped immediately and did not write a fabricated fallback record.

## 6. Diagnostics, Derived Outputs, and Residue

```text
Diagnostics files for this ID: 0
Derived CSV: absent
Derived summary: absent
Workspace folder after cleanup: absent
__pycache__=0
.pytest_cache=0
*.pyc=0
*.pyo=0
temp_sandbox_*=0
.patch_tmp_*=0
.patch_bak_*=0
```

## 7. Frozen Historical Hashes

All seven prior frozen artifacts remain unchanged:

```text
m7d smoke report: a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a
m7d smoke JSONL: 74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c
m7e 210000Z: c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638
m7e 230000Z: d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7
m7e 010000Z: 67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a
m7e 020000Z: 327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456
m7e 030000Z: 548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664
```

## 8. Verification

Offline gate verification after the abort:

```text
python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q
40 passed
```

## 9. Decision

Do not resume or immediately rerun `m7e_full_20260612T040000Z`.

The next safe milestone is:

```text
M7-E.24 Gateway 429 Rate-Limit and Batch Throttling Decision Plan
```

That plan must evaluate provider retry/backoff behavior, inter-run pacing, durable failed-attempt audit, fairness across A/C/E, and a new experiment ID policy before any further live execution.

## 10. Compliance Confirmation

- M7-E.23 was executed exactly once.
- No old experiment ID was resumed.
- No fake provider was used.
- The failed active run was not written as completed data.
- No derived output was generated from the partial dataset.
- No automatic rerun occurred.


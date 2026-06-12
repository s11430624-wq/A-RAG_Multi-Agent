# Milestone 7-E.19 Real Full Rerun Controlled Abort Audit

**Status:** Controlled Abort / Partial Results Preserved / Final Dataset Not Complete

**Experiment ID:** `m7e_full_20260612T030000Z`

**Date:** 2026-06-12

---

## 1. Execution Lifecycle

The operator explicitly approved the real live full-run command:

```text
批准執行 M7-E.19，使用 experiment id m7e_full_20260612T030000Z
```

The run was executed exactly once with the real local loopback Gateway path. `ARAG_USE_FAKE_FULL_RUN_PROVIDER` was explicitly removed before execution.

Execution result:

```text
Exit code: 1
Final state: Controlled Abort
Completed records: 15/45
Failed active run: m7e_full_20260612T030000Z__T02__E__rep01__seed42
Abort reason: RetrievalBudgetExceededError: Coder/initial retrieval budget exhausted
```

The failed active run was rejected and was not written as a completed raw JSONL record.

## 2. Raw JSONL Audit

```text
Path: results/raw/m7e_full_20260612T030000Z.jsonl
SHA-256: 548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664
Record count: 15
Schema errors: 0
```

Distribution:

```text
Strategies: A=6, C=6, E=3
Tasks: T01=9, T02=6, T03=0, T04=0, T05=0
valid_run=15
infra_error=0
```

Token and tool totals from completed records:

```text
input_tokens=122756
output_tokens=110227
retrieved_tokens=102
tool_calls=6
```

Stop reasons:

```text
repair_limit=13
public_pass=2
```

Complete public+hidden pass records:

```text
m7e_full_20260612T030000Z__T02__A__rep01__seed42
m7e_full_20260612T030000Z__T02__A__rep02__seed42
```

## 3. Completed Record Listing

```text
T01__A__rep01__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__A__rep02__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__A__rep03__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__C__rep01__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__C__rep02__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__C__rep03__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T01__E__rep01__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=2 retrieved=34
T01__E__rep02__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=2 retrieved=34
T01__E__rep03__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=2 retrieved=34
T02__A__rep01__seed42 stop=public_pass public=2/2 hidden=2/2 tool_calls=0 retrieved=0
T02__A__rep02__seed42 stop=public_pass public=2/2 hidden=2/2 tool_calls=0 retrieved=0
T02__A__rep03__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T02__C__rep01__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T02__C__rep02__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
T02__C__rep03__seed42 stop=repair_limit public=0/0 hidden=0/0 tool_calls=0 retrieved=0
```

## 4. Artifact Manifest Audit

```text
Artifact root: results/raw/artifacts/m7e_full_20260612T030000Z
Manifest count: 15
Provider IDs: openai_compatible_gateway
All usage_complete: true
Finalized provider_attempt_count sum: 67
Finalized call_records sum: 67
```

The failed active run did not finalize a manifest and is not included in the finalized manifest totals.

## 5. Retrieval Log Audit

```text
Retrieval root: results/raw/retrieval/m7e_full_20260612T030000Z
Retrieval log count: 4
A/C retrieval logs: 0
```

Completed E logs:

```text
m7e_full_20260612T030000Z__T01__E__rep01__seed42.jsonl lines=2
m7e_full_20260612T030000Z__T01__E__rep02__seed42.jsonl lines=2
m7e_full_20260612T030000Z__T01__E__rep03__seed42.jsonl lines=2
```

Partial failed-run audit log:

```text
m7e_full_20260612T030000Z__T02__E__rep01__seed42.jsonl lines=4
```

Partial log contents:

```text
1 Planner keyword_search calculate_pass_rate 17
2 Coder keyword_search calculate_pass_rate 17
3 Planner keyword_search get_student_course_summary 52
4 Coder keyword_search get_grades_by_student 28
```

Interpretation:

- Planner initial budget `5` successfully prevented the previous Planner/initial abort.
- The next active failure moved to Coder initial retrieval budget.
- Coder initial budget remains `2`, so after Coder completed two distinct retrievals, any third Coder retrieval attempt correctly failed closed.

## 6. Diagnostics, Derived Outputs, and Residue

```text
Diagnostics folder for this ID: absent
Derived outputs for this ID: absent
Workspace folder for this ID: absent after cleanup
```

Residue scan after execution:

```text
__pycache__=0
*.pyc=0
*.pyo=0
.pytest_cache=0
temp_sandbox_*=0
.patch_tmp_*=0
.patch_bak_*=0
```

## 7. Frozen Historical Hashes

Frozen historical files remain unchanged:

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

## 8. Root Cause

M7-E.17 successfully fixed the previous Planner/initial evidence headroom issue by raising Planner initial budget to `5`.

The M7-E.19 controlled abort occurred later in the same failed active run because the Coder attempted to exceed its unchanged `Coder/initial=2` retrieval budget.

This means the system advanced beyond the previous Planner bottleneck and exposed the next bounded evidence bottleneck:

```text
Coder/initial retrieval budget exhausted
```

## 9. Recommendation

Do not resume `m7e_full_20260612T030000Z`.

Recommended next safe step:

```text
M7-E.20 Coder Initial Retrieval Budget Decision Plan
```

That plan should decide whether to raise `Coder/initial` from `2` to `3` or redesign Coder evidence inheritance, while preserving:

1. Planner initial budget `5`.
2. Duplicate retrieval cache.
3. A/C zero retrieval.
4. New experiment ID for any future full rerun.
5. No derived outputs until 45/45 complete.

## 10. Compliance Confirmation

- The approved M7-E.19 command was executed exactly once.
- No old experiment ID was resumed.
- No previous result file was overwritten.
- The failed active run was not written as a completed raw JSONL record.
- No derived CSV or summary was generated.
- Historical smoke and partial full-run hashes remain frozen.


# Milestone 7-E.16 Retrieval Budget Option F Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the next safe retrieval-budget policy after M7-E.15 proved that Strategy E still aborts on T02 after three distinct Planner retrievals.

**Architecture:** Keep the existing retrieval loop hardening from M7-E.13 intact, preserve role/phase scoped caching, and make the smallest auditable policy change needed for medium-complexity integration tasks. The recommended implementation path is Option F: raise only `Planner/initial` from `3` to `5`, keep Coder/Reviewer/repair budgets unchanged, and require a new full-run experiment ID for any future live rerun.

**Tech Stack:** Python 3.11, pytest, existing `experiments/strategies/arag_multi_agent.py`, existing `tests/strategies/test_arag_multi_agent.py`, M7 live gate tests.

---

## 1. Context

M7-E.15 executed real live full-run experiment `m7e_full_20260612T020000Z` and preserved 15 complete records before a controlled abort at:

```text
m7e_full_20260612T020000Z__T02__E__rep01__seed42
```

The abort reason was:

```text
RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted
```

The failed partial E run performed three distinct Planner retrievals:

```text
keyword_search("get_student_course_summary")
keyword_search("get_grades_by_student")
keyword_search("get_student_by_id")
```

Unlike the earlier M7-E.11 failure, this was not an identical-query loop. M7-E.13 duplicate-query cache and prompt discipline worked. The remaining problem is that Task T02 needs more distinct evidence than `Planner/initial=3` allows.

## 2. Decision

Recommended decision: **Option F - bounded Planner initial evidence expansion**.

Policy:

```python
ARAGMultiAgentStrategySession._BUDGETS = {
    ("Planner", "initial"): 5,
    ("Coder", "initial"): 2,
    ("Reviewer", "initial"): 1,
}
```

Rules:

1. Keep duplicate retrieval cache active before budget decrement.
2. Keep cache scoped by `(role, phase, tool, query, top_k)` or chunk parameters.
3. Keep repair budget unchanged at `2`.
4. Keep A/C retrieval impossible.
5. Do not resume any previous partial experiment IDs.
6. Any future live rerun must use a new canonical ID such as `m7e_full_YYYYMMDDTHHMMSSZ`.
7. Do not generate derived CSV/summary unless all 45 records complete.

Rejected alternatives:

| Option | Decision | Reason |
| :--- | :--- | :--- |
| Keep budget 3 | Rejected | E.15 showed T02 needs at least a fourth distinct Planner retrieval. |
| Set Planner initial to 4 | Rejected for now | It may pass T02 but leaves no safety margin for T03-T05 integration tasks. |
| Shared role budget pool | Deferred | More principled but larger implementation blast radius. |
| Unlimited or adaptive budget | Rejected | Weakens fairness, cost predictability, and leakage discipline. |
| Resume `m7e_full_20260612T020000Z` | Rejected | Would mix old budget policy with new budget policy in one JSONL. |

## 3. File Structure

Files expected for the next implementation milestone:

```text
experiments/strategies/arag_multi_agent.py
tests/strategies/test_arag_multi_agent.py
tests/live/test_full_run_gate.py
docs/milestones/M7E17_acceptance.md
docs/milestones/M7_acceptance.md
```

Responsibilities:

- `experiments/strategies/arag_multi_agent.py`: source of truth for Strategy E role/phase retrieval budgets.
- `tests/strategies/test_arag_multi_agent.py`: focused TDD tests proving `Planner/initial=5`, sixth distinct retrieval fail-closed, duplicate cache behavior still saves budget, and A/C remain retrieval-free.
- `tests/live/test_full_run_gate.py`: regression guard that live-run still requires explicit approval and new output paths.
- `docs/milestones/M7E17_acceptance.md`: implementation evidence for the future code change.
- `docs/milestones/M7_acceptance.md`: high-level status update after implementation.

## 4. Implementation Tasks

### Task 1: Add RED tests for Planner initial budget 5

**Files:**
- Modify: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Replace the current fourth-retrieval fail-closed expectation with a fifth-retrieval success case**

Add this test near the existing Planner budget tests:

```python
def test_strategy_e_planner_initial_five_distinct_retrievals_allowed(tmp_path, project_root):
    queries = tuple(
        f'{{"action":"retrieve","query":"query{i}","tool":"keyword_search","top_k":1}}'
        for i in range(1, 6)
    )
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (*queries, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.metrics.tool_calls == 5
    assert len(provider.requests) == 8
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py::test_strategy_e_planner_initial_five_distinct_retrievals_allowed -q
```

Expected result before implementation:

```text
FAILED with RetrievalBudgetExceededError: Planner/initial retrieval budget exhausted
```

### Task 2: Add RED test for sixth distinct retrieval fail-closed

**Files:**
- Modify: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Add sixth-retrieval rejection test**

```python
def test_strategy_e_planner_initial_sixth_distinct_retrieval_fails_closed(tmp_path, project_root):
    queries = tuple(
        f'{{"action":"retrieve","query":"query{i}","tool":"keyword_search","top_k":1}}'
        for i in range(1, 7)
    )
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (*queries, PLAN),
    )

    with pytest.raises(RetrievalBudgetExceededError):
        session.generate_initial_patch()

    assert len(provider.requests) == 6
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5
```

- [ ] **Step 2: Run the test before implementation**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py::test_strategy_e_planner_initial_sixth_distinct_retrieval_fails_closed -q
```

Expected result before implementation:

```text
PASSED
```

This test may already pass under budget `3`; keep it as a future GREEN invariant after raising the budget to `5`.

### Task 3: Update the Strategy E budget source of truth

**Files:**
- Modify: `experiments/strategies/arag_multi_agent.py`

- [ ] **Step 1: Make the minimal code change**

Replace:

```python
_BUDGETS = {("Planner", "initial"): 3, ("Coder", "initial"): 2, ("Reviewer", "initial"): 1}
```

With:

```python
_BUDGETS = {("Planner", "initial"): 5, ("Coder", "initial"): 2, ("Reviewer", "initial"): 1}
```

- [ ] **Step 2: Run focused budget tests**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
```

Expected result:

```text
all tests pass
```

If existing tests still assert budget `3`, update their names and assertions so they match the new policy:

```python
assert ARAGMultiAgentStrategySession._BUDGETS == {
    ("Planner", "initial"): 5,
    ("Coder", "initial"): 2,
    ("Reviewer", "initial"): 1,
}
```

### Task 4: Preserve duplicate-cache and leakage guards

**Files:**
- Modify: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Add a regression test that duplicates still do not consume budget**

```python
def test_strategy_e_duplicate_queries_still_do_not_consume_budget_after_budget_5(tmp_path, project_root):
    q1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    q2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    q3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    q4 = '{"action":"retrieve","query":"query4","tool":"keyword_search","top_k":1}'
    q5 = '{"action":"retrieve","query":"query5","tool":"keyword_search","top_k":1}'
    session, _provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (q1, q1, q1, q2, q3, q4, q5, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.metrics.tool_calls == 5
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5
```

- [ ] **Step 2: Run duplicate-cache regression tests**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py -k "duplicate or cache" -q
```

Expected result:

```text
all selected tests pass
```

### Task 5: Update dry-run/live gate expectations without executing live

**Files:**
- Modify: `tests/live/test_full_run_gate.py`
- Modify: `docs/milestones/M7E17_acceptance.md`

- [ ] **Step 1: Verify live-run still requires explicit approval**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/live/test_full_run_gate.py -q
```

Expected result:

```text
all tests pass
```

- [ ] **Step 2: Ensure tests do not require Gateway**

Confirm that the command above does not require:

```text
ARAG_RUN_LIVE_GATEWAY=1
ARAG_EXECUTE_FULL_RUN_ONCE=1
```

The implementation milestone must not run a live experiment. It should only prove that the gate stays closed until a separate preflight and explicit operator approval.

### Task 6: Verify frozen results and residue

**Files:**
- No code changes.

- [ ] **Step 1: Recheck frozen hashes**

Run:

```powershell
$files = @(
  'results/raw/gates/m7d_smoke_20260611T123000Z.json',
  'results/raw/m7d_smoke_20260611T123000Z.jsonl',
  'results/raw/m7e_full_20260611T210000Z.jsonl',
  'results/raw/m7e_full_20260611T230000Z.jsonl',
  'results/raw/m7e_full_20260612T010000Z.jsonl',
  'results/raw/m7e_full_20260612T020000Z.jsonl'
)
foreach ($f in $files) {
  Get-FileHash -LiteralPath $f -Algorithm SHA256
}
```

Expected hashes:

```text
a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a
74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c
c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638
d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7
67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a
327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456
```

- [ ] **Step 2: Run residue scan**

Run:

```powershell
$patterns = @('__pycache__','*.pyc','*.pyo','.pytest_cache','temp_sandbox_*','.patch_tmp_*','.patch_bak_*')
foreach ($pat in $patterns) {
  $items = @(Get-ChildItem -Path . -Recurse -Force -Filter $pat -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\.git\\' })
  "$pat=$($items.Count)"
}
```

Expected result after cleanup:

```text
__pycache__=0
*.pyc=0
*.pyo=0
.pytest_cache=0
temp_sandbox_*=0
.patch_tmp_*=0
.patch_bak_*=0
```

## 5. Required Verification Commands

Run in this order:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest tests/strategies tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```

The hidden evaluator integration suite is not required for this budget-policy code change unless the operator explicitly approves running hidden-test integration.

## 6. Future Live Rerun Gate

Do not start a live rerun during this implementation milestone.

After implementation and offline verification, create a separate preflight document for a new ID such as:

```text
m7e_full_20260612T030000Z
```

That preflight must:

1. Confirm no output collision.
2. Recheck all frozen hashes.
3. Confirm `_BUDGETS[("Planner", "initial")] == 5`.
4. Draft the exact command.
5. Stop for explicit operator approval.

## 7. Self-Review Checklist

- Spec coverage: Covers the E.15 abort, Option F decision, exact code location, tests, gate checks, frozen hashes, and future live-run boundary.
- Deferred-detail scan: No deferred implementation text is used.
- Type consistency: Uses existing `ARAGMultiAgentStrategySession`, `RetrievalBudgetExceededError`, `_build`, `PLAN`, `DIFF`, and `REVIEW` names from current tests.
- Boundary check: This plan does not authorize any Gateway call, live-run, smoke-run, resume, or old-ID mutation.

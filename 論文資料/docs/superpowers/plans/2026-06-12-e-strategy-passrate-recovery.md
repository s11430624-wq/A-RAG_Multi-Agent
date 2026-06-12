# E Strategy Pass-Rate Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Strategy E so it stops forcing unnecessary retrieval, breaks cache-hit loops cleanly, and starts producing non-zero real pass results without regressing A or C.

**Architecture:** The fix is centered on Strategy E state handling, not on provider or budget infrastructure. We will introduce an explicit retrieval-satisfaction signal derived from visible evidence, propagate cache-hit progress state into prompt rendering, and strengthen Coder/repair prompt behavior so the session transitions from evidence gathering into patch generation instead of looping. All work stays inside the strategy and prompt-rendering layer, with live verification deferred until offline tests are green.

**Tech Stack:** Python, pytest, existing `FakeProvider`, `PromptLoader`, `ARAGMultiAgentStrategySession`

---

## File Map

- Modify: `experiments/strategies/prompt_loader.py`
  - Add an explicit retrieval-state input so prompt wording is not controlled only by `retrieved_queries`.
- Modify: `experiments/strategies/arag_multi_agent.py`
  - Derive retrieval satisfaction from visible evidence.
  - Record cache-hit progress state for the next prompt.
  - Bias Coder toward patching when evidence is already visible.
- Test: `tests/strategies/test_prompt_loader.py`
  - Add prompt-rendering red tests for visible-evidence satisfaction and cache-hit guidance.
- Test: `tests/strategies/test_arag_multi_agent.py`
  - Add session-level red tests that prove Coder can move forward without forced retrieval and that cache-hit loops emit a forward-progress signal.

---

### Task 1: Add Prompt-Level Retrieval State

**Files:**
- Modify: `experiments/strategies/prompt_loader.py`
- Test: `tests/strategies/test_prompt_loader.py`

- [ ] **Step 1: Write the failing prompt-rendering tests**

Add these tests near the existing retrieval prompt tests in `tests/strategies/test_prompt_loader.py`:

```python
def test_coder_with_visible_evidence_is_not_forced_to_retrieve_again():
    loader = PromptLoader()
    task = _task()
    rendered = loader.render(
        "coder.txt",
        task=task,
        capability=CapabilityContext(True),
        data={"plan": {"implementation_steps": ["change"]}},
        evidence=(
            {
                "evidence_id": "E000001",
                "role": "Planner",
                "phase": "initial",
                "tool_name": "keyword_search",
                "file_path": "student_system/API_SPEC.md",
                "chunk_id": "chunk-1",
                "content_hash": "h",
                "text": "API evidence",
                "token_count": 12,
                "run_id": "run-e",
                "task_id": "T01",
            },
        ),
        retrieved_queries=(),
        retrieval_required=False,
    )

    assert "You MUST perform retrieval using this format at least once" not in rendered.user_prompt
    assert "You have already performed retrieval. If you have sufficient information" in rendered.user_prompt


def test_cache_hit_progress_note_is_rendered_when_present():
    loader = PromptLoader()
    task = _task()
    rendered = loader.render(
        "coder.txt",
        task=task,
        capability=CapabilityContext(True),
        evidence=(),
        retrieved_queries=(),
        retrieval_required=False,
        retrieval_progress_note="The requested retrieval is already satisfied by visible evidence. Do not repeat it.",
    )

    assert "already satisfied by visible evidence" in rendered.user_prompt
```

- [ ] **Step 2: Run the prompt tests to verify they fail**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_prompt_loader.py -q
```

Expected:

- FAIL because `PromptLoader.render()` does not yet accept `retrieval_required`
- FAIL because `PromptLoader.render()` does not yet accept `retrieval_progress_note`

- [ ] **Step 3: Implement the minimal prompt-loader changes**

Update `PromptLoader.render()` in `experiments/strategies/prompt_loader.py` so it accepts the new explicit state:

```python
def render(
    self,
    name: str,
    *,
    task: ModelVisibleTask,
    capability: CapabilityContext,
    data: Mapping[str, Any] | None = None,
    evidence: tuple[Any, ...] | None = None,
    retrieved_queries: tuple[Any, ...] | None = None,
    retrieval_required: bool | None = None,
    retrieval_progress_note: str | None = None,
) -> RenderedPrompt:
```

Change the retrieval capability block selection so that:

```python
effective_retrieval_required = True if retrieval_required is None else retrieval_required

if capability.retrieval_enabled:
    if name in ("planner.txt", "coder.txt"):
        if not effective_retrieval_required:
            capability_text = (
                "<CAPABILITY>Retrieval is available only through exact JSON action=retrieve requests. "
                "You have already performed retrieval. If you have sufficient information, "
                "you may now provide your final output.</CAPABILITY>"
            )
        else:
            capability_text = (
                "<CAPABILITY>Retrieval is available only through exact JSON action=retrieve requests. "
                "You MUST perform retrieval using this format at least once before submitting your final output.</CAPABILITY>"
            )
```

Append the progress note after the evidence block when present:

```python
if retrieval_progress_note:
    evidence_text += f"<RETRIEVAL_PROGRESS>{canonical_prompt_json({'note': retrieval_progress_note})}</RETRIEVAL_PROGRESS>"
```

- [ ] **Step 4: Re-run the prompt tests to verify they pass**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_prompt_loader.py -q
```

Expected:

- PASS for the new tests
- existing prompt-loader tests remain green

- [ ] **Step 5: Commit**

```powershell
git add experiments/strategies/prompt_loader.py tests/strategies/test_prompt_loader.py
git commit -m "test: add explicit retrieval state to prompt rendering"
```

---

### Task 2: Make Strategy E Derive Retrieval Satisfaction from Visible Evidence

**Files:**
- Modify: `experiments/strategies/arag_multi_agent.py`
- Test: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Write the failing strategy tests**

Add focused tests to `tests/strategies/test_arag_multi_agent.py`:

```python
def test_coder_prompt_relaxes_when_inherited_planner_evidence_is_visible(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    coder_prompt = provider.requests[2].user_prompt
    assert "You MUST perform retrieval using this format at least once" not in coder_prompt
    assert "You have already performed retrieval. If you have sufficient information" in coder_prompt


def test_cache_hit_loop_adds_forward_progress_note_to_next_turn(tmp_path, project_root):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    assert "already satisfied by visible evidence" in provider.requests[1].user_prompt
```

- [ ] **Step 2: Run the focused strategy tests to verify they fail**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
```

Expected:

- FAIL because the current session loop still decides mandatory retrieval from `retrieved_queries` behavior only
- FAIL because no forward-progress note is injected after cache hits

- [ ] **Step 3: Implement visible-evidence retrieval satisfaction**

Inside `_role_turn()` in `experiments/strategies/arag_multi_agent.py`, derive retrieval state before prompt rendering:

```python
visible_evidence = tuple(
    item
    for item in self.evidence_ledger.items
    if (item.role == role and item.phase == phase) or item.evidence_id in inherited_evidence_ids
)

has_visible_retrieval_evidence = any(
    item.tool_name in ("keyword_search", "semantic_search", "chunk_read")
    for item in visible_evidence
)

retrieval_required = role in ("Planner", "Coder") and not has_visible_retrieval_evidence
```

Pass that state into the renderer:

```python
rendered = self.prompt_loader.render(
    template_name,
    task=self.task,
    capability=CapabilityContext(True),
    data=data,
    evidence=visible_evidence,
    retrieved_queries=tuple(retrieved_queries),
    retrieval_required=retrieval_required,
    retrieval_progress_note=retrieval_progress_note,
)
```

Initialize the note at the start of the turn:

```python
retrieval_progress_note: str | None = None
```

- [ ] **Step 4: Re-run the focused strategy tests to verify the first behavior passes**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
```

Expected:

- the inherited-evidence prompt test passes
- the cache-hit progress-note test may still fail until Task 3

- [ ] **Step 5: Commit**

```powershell
git add experiments/strategies/arag_multi_agent.py tests/strategies/test_arag_multi_agent.py
git commit -m "feat: derive retrieval satisfaction from visible evidence"
```

---

### Task 3: Break Cache-Hit Loops with an Explicit Progress Signal

**Files:**
- Modify: `experiments/strategies/arag_multi_agent.py`
- Test: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Write the failing cache-hit progression test**

If the previous cache-hit note test was added in Task 2, keep it and confirm it is still the red case. Add one more stronger assertion if needed:

```python
def test_cached_retrieval_hit_does_not_leave_next_turn_without_guidance(tmp_path, project_root):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    assert "<RETRIEVAL_PROGRESS>" in provider.requests[1].user_prompt
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
```

Expected:

- FAIL because no progress note is being injected on cache hit yet

- [ ] **Step 3: Implement the cache-hit forward-progress note**

In `_role_turn()` when a cached retrieval request is detected, set the next-turn note before continuing:

```python
if cache_key is not None and cache_key in self.retrieval_cache:
    if cache_hit_count >= self._MAX_CACHE_HITS_PER_ROLE_PHASE:
        raise RetrievalBudgetExceededError(
            f"{role}/{phase} cached retrieval repetition limit exceeded"
        )
    cache_hit_count += 1
    retrieval_progress_note = (
        "The requested retrieval is already satisfied by visible evidence. "
        "Do not repeat the same retrieval. Proceed using the current evidence."
    )
    self._record_accepted_response(response, rendered, role, phase, template_name)
    continue
```

Also clear the note after a distinct successful retrieval so stale guidance is not carried forever:

```python
retrieval_progress_note = None
```

- [ ] **Step 4: Re-run the strategy tests to verify they pass**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_arag_multi_agent.py -q
```

Expected:

- PASS for the cache-hit guidance tests
- existing cache limit tests remain green

- [ ] **Step 5: Commit**

```powershell
git add experiments/strategies/arag_multi_agent.py tests/strategies/test_arag_multi_agent.py
git commit -m "feat: add forward-progress guidance after cached retrieval hits"
```

---

### Task 4: Bias Coder and Repair Toward Patch Convergence, Then Verify

**Files:**
- Modify: `experiments/strategies/prompt_loader.py`
- Modify: `experiments/strategies/arag_multi_agent.py`
- Test: `tests/strategies/test_prompt_loader.py`
- Test: `tests/strategies/test_arag_multi_agent.py`

- [ ] **Step 1: Write the failing convergence-oriented tests**

Add one prompt test and one strategy test:

```python
def test_coder_prompt_with_visible_evidence_prefers_patch_generation():
    loader = PromptLoader()
    rendered = loader.render(
        "coder.txt",
        task=_task(),
        capability=CapabilityContext(True),
        data={"plan": {"implementation_steps": ["change"]}},
        evidence=(
            {
                "evidence_id": "E000001",
                "role": "Planner",
                "phase": "initial",
                "tool_name": "keyword_search",
                "file_path": "student_system/API_SPEC.md",
                "chunk_id": "chunk-1",
                "content_hash": "h",
                "text": "API evidence",
                "token_count": 12,
                "run_id": "run-e",
                "task_id": "T01",
            },
        ),
        retrieval_required=False,
    )

    assert "generate the smallest valid patch" in rendered.user_prompt


def test_repair_round_still_sees_only_coder_evidence_after_prompt_changes(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_search, DIFF, REVIEW, DIFF),
    )
    session.generate_initial_patch()
    feedback = SanitizedPublicFeedback(1, "fail", "hash")
    session.generate_repair_patch(feedback, DIFF)

    repair_prompt = provider.requests[-1].user_prompt
    assert "E000001" not in repair_prompt
    assert "E000002" in repair_prompt
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_prompt_loader.py tests/strategies/test_arag_multi_agent.py -q
```

Expected:

- FAIL because the coder prompt does not yet explicitly prefer patch generation from visible evidence

- [ ] **Step 3: Implement the minimal convergence wording**

Add a Coder-specific instruction branch in `PromptLoader.render()` when:

- `name == "coder.txt"`
- retrieval is enabled
- `retrieval_required` is `False`

Append an explicit sentence to the capability text:

```python
"Use the visible evidence and plan to generate the smallest valid patch. "
"Do not repeat retrieval unless specific required information is still missing."
```

Do not apply this extra wording to Planner or Reviewer.

Keep repair provenance unchanged in `ARAGMultiAgentStrategySession`; this step is mostly a regression lock to ensure no accidental widening occurs while prompt behavior changes.

- [ ] **Step 4: Run the full focused verification set**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/strategies/test_prompt_loader.py tests/strategies/test_arag_multi_agent.py -q
python -B -m pytest tests/strategies -q
python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py tests/live/test_abort_diagnostics.py -q
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```

Expected:

- all focused strategy and prompt tests pass
- A/C zero-retrieval protections remain green
- non-hidden regression remains green

- [ ] **Step 5: Commit**

```powershell
git add experiments/strategies/prompt_loader.py experiments/strategies/arag_multi_agent.py tests/strategies/test_prompt_loader.py tests/strategies/test_arag_multi_agent.py
git commit -m "feat: steer strategy e from repeated retrieval into patch convergence"
```

---

### Task 5: Controlled Live Verification for Non-Zero E Results

**Files:**
- No required code changes before running
- Verify against existing output/report paths only after offline green

- [ ] **Step 1: Reconfirm frozen artifacts are unchanged before any live verification**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/live/test_smoke_freeze_revalidation.py -q
```

Expected:

- PASS

- [ ] **Step 2: Execute the smallest approved live verification batch for known E failure cases**

Use the repo’s current approved live workflow rather than inventing a new one. The batch should target the known Strategy E failure pattern first, not jump directly to a full rerun.

Example verification target:

```text
Run the smallest real batch that includes Strategy E cases which previously aborted on repeated retrieval behavior, using a fresh experiment id and preserving all frozen artifacts.
```

- [ ] **Step 3: Inspect live results for the actual success condition**

Check:

- Strategy E no longer aborts on already-satisfied retrieval loops
- Strategy E produces at least one real passing record
- A/C remain stable if included in the batch

- [ ] **Step 4: Record the outcome in milestone docs**

Update or create the relevant milestone note only after the live verification actually finishes.

- [ ] **Step 5: Commit documentation updates**

```powershell
git add docs/milestones/*.md docs/superpowers/plans/*.md
git commit -m "docs: record strategy e pass-rate recovery verification"
```

---

## Self-Review

### Spec coverage

- Retrieval-satisfaction state: covered by Tasks 1-2
- Cache-hit forward progress: covered by Task 3
- Coder patch-first behavior: covered by Task 4
- Reviewer/repair strictness preservation: covered by Tasks 2 and 4 regression locks
- Non-zero real pass verification: covered by Task 5

### Placeholder scan

- No `TODO`, `TBD`, or "similar to above" placeholders remain
- Each task includes explicit files, tests, commands, and code snippets

### Type consistency

- `PromptLoader.render()` new fields use `retrieval_required` and `retrieval_progress_note` consistently across plan steps
- Strategy tests refer to existing helpers `_build`, `_task`, `SanitizedPublicFeedback`, `CapabilityContext`

---

Plan complete and saved to `docs/superpowers/plans/2026-06-12-e-strategy-passrate-recovery.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

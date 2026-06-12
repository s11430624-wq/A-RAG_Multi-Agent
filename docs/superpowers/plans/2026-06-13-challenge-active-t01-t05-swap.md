# Challenge Active T01-T05 Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active `T01-T05` task set with a harder challenge set that still fits the current 45-run pipeline, while preserving a reversible backup of the baseline task/test/reference artifacts.

**Architecture:** Keep the scheduler, evaluator, and run-count math unchanged by reusing task IDs `T01-T05`. Replace the active task definitions, public tests, hidden tests, and reference patches as one consistent bundle so the existing 45-run machinery can execute without code-path changes.

**Tech Stack:** Python, pytest, JSON task configs, unified diff reference patches

---

### Task 1: Snapshot the current active task bundle

**Files:**
- Create: `experiments/task_sets/baseline_active_t01_t05/README.md`
- Create: `experiments/task_sets/baseline_active_t01_t05/tasks.json`
- Create: `experiments/task_sets/baseline_active_t01_t05/public/test_t01.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/public/test_t02.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/public/test_t03.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/public/test_t04.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/public/test_t05.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/hidden/test_t01.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/hidden/test_t02.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/hidden/test_t03.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/hidden/test_t04.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/hidden/test_t05.py`
- Create: `experiments/task_sets/baseline_active_t01_t05/reference_patches/T01.diff`
- Create: `experiments/task_sets/baseline_active_t01_t05/reference_patches/T02.diff`
- Create: `experiments/task_sets/baseline_active_t01_t05/reference_patches/T03.diff`
- Create: `experiments/task_sets/baseline_active_t01_t05/reference_patches/T04.diff`
- Create: `experiments/task_sets/baseline_active_t01_t05/reference_patches/T05.diff`

- [ ] Copy the current active task definition and all active public/hidden/reference artifacts into the baseline backup folder.
- [ ] Add a short README explaining that this folder is the restoration source for the original easy/medium `T01-T05`.

### Task 2: Replace active tasks with the challenge bundle

**Files:**
- Modify: `experiments/tasks.json`
- Modify: `student_system/tests/public/test_t01.py`
- Modify: `student_system/tests/public/test_t02.py`
- Modify: `student_system/tests/public/test_t03.py`
- Modify: `student_system/tests/public/test_t04.py`
- Modify: `student_system/tests/public/test_t05.py`
- Modify: `evaluation/hidden_tests/test_t01.py`
- Modify: `evaluation/hidden_tests/test_t02.py`
- Modify: `evaluation/hidden_tests/test_t03.py`
- Modify: `evaluation/hidden_tests/test_t04.py`
- Modify: `evaluation/hidden_tests/test_t05.py`
- Modify: `evaluation/reference_patches/T01.diff`
- Modify: `evaluation/reference_patches/T02.diff`
- Modify: `evaluation/reference_patches/T03.diff`
- Modify: `evaluation/reference_patches/T04.diff`
- Modify: `evaluation/reference_patches/T05.diff`

- [ ] Overwrite the active task records so `T01-T05` become the new challenge tasks.
- [ ] Ensure every task is independent from snapshot state and does not rely on another task having run before it.
- [ ] Keep task IDs unchanged so the 45-run planner still yields exactly `5 tasks x 3 strategies x 3 repetitions = 45 runs`.

### Task 3: Verify offline integrity before any live execution

**Files:**
- Test: `tests/m2/test_tasks_dataset.py`
- Test: `tests/m2/test_reference_patches.py`
- Test: `tests/runtime/test_evaluator_integration.py`
- Test: `student_system/tests/public/test_t01.py`
- Test: `student_system/tests/public/test_t02.py`
- Test: `student_system/tests/public/test_t03.py`
- Test: `student_system/tests/public/test_t04.py`
- Test: `student_system/tests/public/test_t05.py`

- [ ] Run task-dataset validation.
- [ ] Run reference-patch validation for `T01-T05`.
- [ ] Run evaluator integration on `T01-T05`.
- [ ] Run the five public test files directly.
- [ ] Run a scheduler sanity check to confirm the plan still contains 45 runs.

### Task 4: Execute the 45-run pipeline only after green verification

**Files:**
- Runtime: existing `live-run` pipeline only

- [ ] If offline verification is green, run the existing 45-run pipeline against the swapped-in challenge task bundle.
- [ ] Collect exact run counts, pass counts, and residue state.
- [ ] If execution fails, stop and report the exact blocker without attempting destructive cleanup.

### Task 5: Keep restoration path explicit

**Files:**
- Modify: `docs/superpowers/specs/2026-06-13-task-expansion-t06-t10-design.md`

- [ ] Append a note that the live experiment used a temporary active-ID swap strategy.
- [ ] Record that the baseline bundle is restorable from `experiments/task_sets/baseline_active_t01_t05/`.

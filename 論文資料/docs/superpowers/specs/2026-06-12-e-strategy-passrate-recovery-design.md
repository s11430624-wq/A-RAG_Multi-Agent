# E Strategy Pass-Rate Recovery Design

## Goal

Recover Strategy E from its current failure mode so that it can produce non-zero real pass results, not merely reduce abort frequency.

This design targets the current A-RAG multi-agent pipeline in `experiments/strategies/arag_multi_agent.py` and related prompt rendering in `experiments/strategies/prompt_loader.py`.

The intended outcome is:

1. Strategy E no longer aborts simply because retrieval was already satisfied but the role is still forced to retrieve again.
2. Strategy E no longer spins on repeated cached retrieval requests without meaningful forward progress.
3. Strategy E moves more reliably from retrieval into patch generation and review, producing real successful runs instead of all-zero outcomes.
4. Strategy A and Strategy C remain behaviorally unchanged.

---

## Current Problem

The current Strategy E implementation already includes:

- Planner initial retrieval budget = 5
- Coder initial retrieval budget = 3
- Reviewer initial retrieval budget = 1
- Coder inheritance of Planner evidence ids
- Cache-hit repetition guard

Even with those protections, Strategy E still underperforms because the system uses the wrong signal for deciding whether a role still must retrieve.

Today, prompt rendering for `planner.txt` and `coder.txt` switches on `retrieved_queries`, which effectively means:

- if this role has not yet issued its own retrieval request, the prompt still says retrieval is mandatory
- even when the role already has visible inherited evidence, the prompt can still force another retrieval step

That creates a bad loop:

1. Planner retrieves valid evidence.
2. Coder can see inherited evidence.
3. Coder prompt still says it must retrieve at least once.
4. Coder repeats retrieval instead of patching.
5. Repetition hits cache or budget guards.
6. Strategy E aborts or wastes turns before coding converges.

This is not only a retrieval-budget issue. It is a retrieval-satisfaction-state issue.

---

## Root-Cause Statement

The root cause is that Strategy E currently treats retrieval completion as "this role has already issued retrieval queries" instead of "this role now has sufficient visible retrieval evidence to proceed."

That makes inherited evidence operationally visible but strategically underutilized.

The result is a mismatch between:

- evidence visibility
- prompt obligations
- retrieval repetition handling

The system is therefore giving the model the wrong next-step instruction after evidence is already available.

---

## Design Principles

### 1. Visible evidence is what matters

Retrieval should be considered satisfied when the active role already has usable visible evidence in its prompt context, whether that evidence originated from the same role or from approved inheritance.

### 2. Retrieval loops must be actively broken

A cache hit must not behave like a silent no-op that leaves the model to rediscover the same behavior. The next turn must contain an explicit forward-progress signal.

### 3. Coding must become the default next action once evidence exists

For Coder, once sufficient evidence is visible, the prompt should bias toward producing the smallest valid patch rather than re-entering retrieval exploration.

### 4. Reviewer and repair provenance stays strict

Reviewer and repair rounds must preserve the existing evidence-boundary rules. This work must not widen reviewer visibility or leak Planner evidence into later stages that are intended to remain constrained.

### 5. A and C are protected

Any implementation must leave Strategy A and Strategy C unchanged in retrieval behavior, outputs, and test expectations.

---

## Recommended Approach

Implement a four-part repair:

1. Replace role-local retrieval completion checks with visible-evidence-based retrieval satisfaction checks.
2. Add explicit cache-hit progress feedback into the next rendered prompt state.
3. Tighten Coder prompt behavior so that visible evidence drives patching, not repeated exploration.
4. Improve Reviewer or repair-stage feedback shaping so failed patches produce concrete, repairable guidance instead of low-information loops.

This is intentionally broader than another budget-only adjustment. Budget changes alone have already proven insufficient.

---

## Detailed Design

### A. Retrieval-Satisfaction State

Introduce a derived decision inside Strategy E turn execution:

- `retrieval_required = True` only when the active role has no sufficient visible retrieval evidence for the current phase
- `retrieval_required = False` when the role already has usable visible evidence in prompt scope

For Planner initial:

- retrieval usually starts required

For Coder initial:

- if inherited Planner evidence is already visible, retrieval is not automatically required
- Coder may still choose retrieval when it needs more information, but it is no longer forced to retrieve once before final output

For Reviewer initial:

- retrieval remains effectively unavailable as a completion requirement

Implementation note:

The prompt renderer should stop using only `retrieved_queries` as the decision input for mandatory retrieval language. It should accept an explicit retrieval-state input derived from visible evidence.

### B. Cache-Hit Forward Progress Signal

On cached repeated retrieval requests, do not only record the accepted response and continue.

Also record a prompt-state signal for the next turn that tells the model:

- the requested retrieval has already been satisfied by existing evidence
- it should not repeat the same retrieval
- it should proceed to planning, patch generation, or review

This signal should be rendered in structured prompt text, not hidden in logs only.

The intent is to change the next-turn model behavior, not merely enforce a later failure.

### C. Coder Patch-First Mode After Evidence

When the Coder phase has visible evidence:

- the capability block should no longer require at least one retrieval before final output
- the role instruction should explicitly prefer generating a minimal valid patch using visible evidence and the Planner plan

This is a behavior shift from:

- "retrieve first, then maybe patch"

to:

- "patch from current evidence unless missing information is specific and necessary"

This keeps retrieval available, but removes it as the default reflex.

### D. Reviewer and Repair Feedback Quality

Once Strategy E gets deeper into coding instead of dying in retrieval, poor repair feedback can become the next bottleneck.

Therefore:

- reviewer outputs must remain strict in structure
- repair prompts must receive concrete, bounded feedback
- feedback should emphasize actionable code/test deltas rather than abstract critique

This work does not propose weakening parser safety. It proposes improving the usefulness of compliant failure feedback so repair rounds converge more often.

---

## Scope of Code Changes

Expected primary touchpoints:

- `experiments/strategies/arag_multi_agent.py`
- `experiments/strategies/prompt_loader.py`
- prompt templates only if required by the final rendered-instruction shape
- Strategy E tests in `tests/strategies/test_arag_multi_agent.py`
- prompt rendering tests in `tests/strategies/test_prompt_loader.py`

Possible secondary touchpoints:

- reviewer/repair parser-adjacent tests if prompt behavior changes require stronger validation of compliant repair feedback

Out of scope:

- provider transport changes
- budget tracker redesign
- smoke/full-run CLI contract changes
- schema changes to results JSONL
- any widening of Reviewer evidence scope

---

## Testing Strategy

Implementation must follow TDD.

### Red tests to add first

1. Coder with inherited visible Planner evidence is not forced by prompt text to retrieve at least once before final output.
2. A cache-hit repeated retrieval request produces a next-turn prompt state that explicitly tells the model retrieval is already satisfied.
3. Coder can proceed directly to a final patch output when inherited evidence is sufficient.
4. Repeated cached retrieval requests no longer rely only on silent `continue` behavior for progress.
5. Reviewer still cannot see Planner-only evidence ids.
6. Repair rounds still do not gain implicit Planner evidence.
7. Strategy A and C retrieval behavior remains zero and unchanged.

### Verification after green

1. Focused strategy tests
2. Prompt rendering tests
3. Non-hidden regression suites already used in this repo for M7 strategy verification
4. Small live verification only after offline green

---

## Live Verification Plan

Do not jump directly back to full 45-run execution.

Use a staged verification path:

1. Offline strategy and prompt tests all green
2. Small live verification centered on Strategy E failure cases
3. Confirm Strategy E no longer aborts on the known retrieval-loop pattern
4. Confirm Strategy E produces real successful runs, not only completed failures
5. Only then decide whether a larger pilot or full rerun is justified

The live success condition is not "fewer aborts."  
The live success condition is "Strategy E begins producing non-zero pass results."

---

## Success Criteria

This design is complete only when all of the following are true:

1. Strategy E no longer aborts due to the already-satisfied-yet-still-mandatory retrieval pattern.
2. Prompt behavior correctly distinguishes between missing evidence and already-visible evidence.
3. Cached repeated retrieval does not create an unchanged or effectively unchanged decision loop.
4. At least one small live verification batch shows real Strategy E passes rather than all-zero results.
5. Strategy A and Strategy C remain stable.

---

## Risks

### Risk 1: Over-relaxing retrieval discipline

If retrieval is declared satisfied too early, the model may patch from insufficient context.

Mitigation:

- tie satisfaction to visible evidence presence, not a loose heuristic
- keep retrieval available when the role genuinely needs more evidence

### Risk 2: Regressing reviewer isolation

If inheritance and prompt-state changes are implemented carelessly, Planner evidence could leak into Reviewer scope.

Mitigation:

- preserve existing reviewer allowed-evidence constraints
- add explicit tests for reviewer rejection of Planner-only evidence ids

### Risk 3: Solving aborts without improving pass rate

It is possible to make E survive longer while still producing bad patches.

Mitigation:

- treat non-zero real pass results as part of the acceptance criteria
- include repair-feedback quality in scope

---

## Stop Conditions

If offline changes make Strategy A or C regress, stop and repair that regression before any live verification.

If Strategy E stops aborting but still remains all-zero in small live verification, do not declare success. That outcome means the control-flow problem was reduced, but patch-quality convergence still remains unresolved and needs a second targeted design pass.

---

## Summary

The next repair should not be framed as another retrieval-budget tweak.

It should be framed as a Strategy E state-machine correction:

- retrieval satisfaction should be determined by visible usable evidence
- cache-hit loops must inject forward-progress signals
- Coder must shift into patch-first behavior once evidence exists
- Reviewer and repair must remain strict but more actionable

That is the smallest design that aims at the user-visible outcome that matters: Strategy E producing real passing results instead of all-zero performance.

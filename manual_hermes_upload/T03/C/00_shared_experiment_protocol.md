# Shared Experiment Protocol

## Purpose

The manual experiment evaluates practical AI coding workflows under controlled tool access:

- Strategy A: one solo Hermes coding agent.
- Strategy C: Hermes Planner, Coder, and Reviewer without RAG.
- Strategy E: Hermes Planner, Coder, and Reviewer with controlled RAG for Planner and Coder.

The study must be reported as a workflow-level comparison, not a perfectly seed-controlled model benchmark.

## User Profile For All Agents

The operator is a time-constrained student/researcher finishing an A-RAG multi-agent experiment report. The operator needs concise, reproducible, auditable outputs. The operator is not asking for open-ended teaching; the operator needs patches that can be tested.

All agents should assume the operator values:

- stable behavior over creative exploration;
- direct patch output over long explanation;
- strict compliance with allowed evidence;
- no hidden-test leakage;
- no invented APIs;
- no uncontrolled refactoring.

## Global Task Input Given To Agents

For each run, the operator should provide:

- `task_id`
- task description
- starter file contents or relevant excerpts
- files allowed to modify
- public test command and public feedback
- max repair rounds
- for E only: allowed RAG corpus list

All agents must also follow [Workspace Policy](workspace_policy.md). The workspace policy defines the repository root, readable files, writable files, forbidden paths, and strategy-specific file access limits.

## Hidden Information Policy

Agents must never receive:

- hidden test source;
- hidden test output before final evaluation;
- reference patches;
- previous runs from other strategies;
- previous repetitions of the same task;
- final strategy comparison statistics.

Agents must never request files outside the allowed task packet, allowed starter code, or, for Strategy E only, the same-task RAG corpus.

## Repair Loop

Each run should use:

1. Initial attempt.
2. Public test execution by operator.
3. Repair round 1 if public tests fail.
4. Public test execution by operator.
5. Repair round 2 if public tests fail.
6. Final patch is evaluated once with public and hidden tests by the operator/evaluator.

Hidden results are collected only after the final patch and must not be pasted back into any agent.

## Output Requirements

Every coding agent must output a unified diff patch or clearly separated file replacements. Prefer unified diff.

Every non-coding agent must output structured text matching its role:

- Planner: plan and constraints only.
- Reviewer: verdict and issues only.
- RAG-enabled roles: RAG queries and evidence IDs/excerpts.

## Fairness Rules

- Each repetition starts from a fresh session.
- Do not paste successful patches from one strategy into another.
- Do not tell an agent that another strategy succeeded or failed.
- Keep max repair rounds identical across A, C, and E.
- Keep public feedback format consistent.

## Stop Conditions

Stop a run when:

- public tests pass;
- max repair rounds are exhausted;
- the agent refuses or cannot produce a patch;
- the agent uses forbidden information;
- the agent repeatedly outputs invalid non-patch content.

Record the stop reason exactly in the run record.

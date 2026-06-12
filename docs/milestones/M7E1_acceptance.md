# Milestone 7-E.1 Acceptance: Full-Run Execution Plan Only

**Status:** Completed and Verified

This document defines the acceptance status and verification results for Milestone 7-E.1 (M7-E.1).
M7-E.1 establishes the full-run execution plan, approval-to-execution contract, budget limits, abort/resume policies, leakage controls, and a complete TDD verification plan without performing any model or Gateway calls.

---

## 1. Acceptance Checklist

| ID | Area | Requirement | Verification Method / Artifact | Status |
| :--- | :--- | :--- | :--- | :--- |
| M7E1-001 | Plan Document | Plan document exists under plans directory | `docs/superpowers/plans/2026-06-11-m7e-full-run-execution-plan.md` | Completed |
| M7E1-002 | Scope Definition | Defines exact 45-run scope (T01-T05, A/C/E, 3 reps, gemini-3.5-flash, hermes_vertex_gateway, seed 42) | Section 1 of E.1 Plan | Completed |
| M7E1-003 | Prerequisites | Defines approval gate binding (M7-E.0 gate pass, smoke report path + sha256, --human-approval, budgets, --allow-unknown-cost) | Section 2 of E.1 Plan | Completed |
| M7E1-004 | Architecture | Compares Executor options and recommends Generalization (Option B) | Section 3 of E.1 Plan | Completed |
| M7E1-005 | Budget Policy | Defines max provider attempts (330) and token budgets (1M input, 500k output, 3600s wall clock) | Section 4 of E.1 Plan | Completed |
| M7E1-006 | Abort Policy | Defines immediate halt on any failure, keeping valid written records, no partial writes, exit codes (3-6) | Section 5 of E.1 Plan | Completed |
| M7E1-007 | Resume Policy | Defines skip completed run_ids, re-verify smoke hashes, snap consistency, reject malformed JSONL, no leakage | Section 6 of E.1 Plan | Completed |
| M7E1-008 | Output Contract | Defines target directories and exclusive-create / append-only writes | Section 7 of E.1 Plan | Completed |
| M7E1-009 | Leakage Controls | Restricts strategy-level context, retrieval isolation, and test environment isolation | Section 8 of E.1 Plan | Completed |
| M7E1-010 | TDD Tasks | Defines 10 specific TDD test cases to be written before execution | Section 9 of E.1 Plan | Completed |
| M7E1-011 | Verification | Explicitly confirms NO model or Gateway calls are executed in this phase | Section 10 of E.1 Plan & Final Report | Completed |

---

## 2. Executor Architecture Comparison Summary

* **Option A: Separate Executor (`FullRunExecutor`)**
  * *Pros:* Complete isolation from smoke runner; zero risk of mutating frozen smoke code.
  * *Cons:* Substantial duplicate logic for state initialization, budget monitoring, and recovery.
* **Option B: Generalized Executor (`LiveExperimentExecutor`) [RECOMMENDED]**
  * *Pros:* Single robust execution pathway for all live tasks. Maximizes code reuse, guarantees consistent budget application, and reduces debugging overhead.
  * *Cons:* Requires rigorous directory and path parameterization to avoid overlapping smoke/full files.
* **Recommendation:** **Option B (Generalization)** is recommended. Strong path validation, output path collision checks, and clean workspace separation mitigates the risk of modifying frozen smoke data.

---

## 3. Scope and Budgets At-A-Glance

* **Total Run Count:** 45 (5 Tasks $\times$ 3 Strategies $\times$ 3 Repetitions)
* **Model & Provider:** `google/gemini-3.5-flash` via `hermes_vertex_gateway`
* **Deterministic Seeds:** Shared seed `42`
* **Max Provider API Attempts:** Exactly `330` attempts (worst-case scenario: Strategy A [3 calls] $\times$ 15 runs + Strategy C [5 calls] $\times$ 15 runs + Strategy E [14 calls] $\times$ 15 runs = 330) with no extra headroom.
* **Token Budgets:** `1,000,000` (input) and `500,000` (output) tokens.
* **Wall-Clock Seconds:** `3,600.0` seconds (1 hour).

---

## 4. No Execution Confirmation
* **Model Calls Made:** 0
* **Gateway Connections:** None
* **Smoke Run Mutations:** None. All smoke files under `results/raw/` and `results/raw/gates/` are unmodified.

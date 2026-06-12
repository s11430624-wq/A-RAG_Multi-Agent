# Milestone 7-E.14: Final Rerun Preflight after Retrieval Loop Hardening

**Status:** Completed & Blocked on Stop Point  
**Date:** 2026-06-12  
**Target Experiment ID:** `m7e_full_20260612T020000Z`

---

## 1. Executive Summary

This document establishes the preflight audit, collision analysis, and frozen state verification for the final rerun attempt under the target experiment ID `m7e_full_20260612T020000Z`.

Following the implementation of Retrieval Loop Hardening (M7-E.13), this preflight verifies that the runtime-level interception, prompt-level disciplines, and execution configurations are correct.

**Strict Safe Guard Confirmation:**  
- No live-run execution has been started.  
- No connection to Vertex Gateway or external model calling has been performed.  
- No resume/rerun of past runs has been initiated.  
- No transition to M7-E.15 is allowed without explicit approval.

---

## 2. Preflight Checklist

### 2.1 Model & Provider Configuration
Verified from `configs/models.yaml`:
- **Default Provider:** `hermes_vertex_gateway`
- **Default Model:** `google/gemini-3.5-flash`
- **API Base:** `http://127.0.0.1:8787/v1`
- **Temperature:** `0.0`
- **Max Output Tokens:** `4096`
- **Top P:** `0.95`

### 2.2 Retrieval Budgets (`_BUDGETS`)
Verified from `experiments/strategies/arag_multi_agent.py`:
- **Planner (initial):** 3
- **Coder (initial):** 2
- **Reviewer (initial):** 1

### 2.3 Retrieval Loop Hardening Presence (M7-E.13)
Verified from `experiments/strategies/arag_multi_agent.py`:
- **Per-Session Cache:** `self.retrieval_cache` is initialized in `__init__`.
- **Cache Key Scoping:** Key is a tuple containing `(role, phase, tool, query, top_k)` or `(role, phase, "chunk_read", file_path, chunk_id)`.
- **Interception Safety:**
  - Cache hits bypass the backend call.
  - Cache hits **do not decrement retrieval budget**.
  - Cache hits **do not write duplicate retrieval log lines**.
  - Cache hits reuse existing evidence without side effects.

### 2.4 Prompt-Level Query Discipline
Verified from `experiments/prompts/planner.txt`:
- Explicit rule preventing identical retrieval query emission.
- Explicit directive to switch to alternative terms or `semantic_search` on empty results.
- Explicit instruction to consolidate related evidence needs.

---

## 3. Collision Check

We have programmatically verified that no outputs or workspace folders exist for the target experiment ID `m7e_full_20260612T020000Z`:

| Path | Status | Verification |
| :--- | :--- | :--- |
| `results/raw/m7e_full_20260612T020000Z.jsonl` | **ABSENT** | PASS |
| `results/raw/artifacts/m7e_full_20260612T020000Z` | **ABSENT** | PASS |
| `results/raw/retrieval/m7e_full_20260612T020000Z` | **ABSENT** | PASS |
| `results/raw/diagnostics/m7e_full_20260612T020000Z` | **ABSENT** | PASS |
| `results/derived/m7e_full_20260612T020000Z.csv` | **ABSENT** | PASS |
| `results/derived/m7e_full_20260612T020000Z_summary.md` | **ABSENT** | PASS |
| `workspaces/m7e_full_20260612T020000Z` | **ABSENT** | PASS |

*No file collision risk detected. The target namespace is 100% clean and ready for clean-slate execution.*

---

## 4. Frozen Hash Integrity

All frozen and partial historical experiment outputs have been recalculated and verified. Their SHA-256 integrity hashes are confirmed as follows:

| Milestone ID / Artifact | Target Path | SHA-256 Hash | Status |
| :--- | :--- | :--- | :--- |
| **M7-D Smoke Report** | `results/raw/gates/m7d_smoke_20260611T123000Z.json` | `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` | **MATCH** |
| **M7-D Smoke Raw** | `results/raw/m7d_smoke_20260611T123000Z.jsonl` | `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` | **MATCH** |
| **M7-E.3 Partial** | `results/raw/m7e_full_20260611T210000Z.jsonl` | `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` | **MATCH** |
| **M7-E.7 Partial** | `results/raw/m7e_full_20260611T230000Z.jsonl` | `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` | **MATCH** |
| **M7-E.11 Partial** | `results/raw/m7e_full_20260612T010000Z.jsonl` | `67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a` | **MATCH** |

---

## 5. Frozen Command Draft (PowerShell / Bash)

Below is the designed execution command. **This is a draft for reference only. It must NOT be executed during this preflight turn.**

### 5.1 Environment Variable Rules
- `ARAG_RUN_LIVE_GATEWAY=1` (Opt-in to use the live Local Vertex Proxy gateway).
- `ARAG_EXECUTE_FULL_RUN_ONCE=1` (Permits full-run 45-run execution bypass).
- **CRITICAL:** Do NOT set `ARAG_USE_FAKE_FULL_RUN_PROVIDER` (ensures live, production model integration is utilized).

### 5.2 PowerShell Draft
```powershell
$env:ARAG_RUN_LIVE_GATEWAY="1"
$env:ARAG_EXECUTE_FULL_RUN_ONCE="1"
Remove-Item Env:\ARAG_USE_FAKE_FULL_RUN_PROVIDER -ErrorAction SilentlyContinue

python -B -m experiments.cli live-run `
  --repo-root . `
  --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json `
  --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a `
  --full-experiment-id m7e_full_20260612T020000Z `
  --human-approval FULL_RUN `
  --approved-input-token-budget 1000000 `
  --approved-output-token-budget 500000 `
  --approved-wall-clock-seconds 3600 `
  --allow-unknown-cost `
```

### 5.3 Bash/MSYS Draft
```bash
export ARAG_RUN_LIVE_GATEWAY="1"
export ARAG_EXECUTE_FULL_RUN_ONCE="1"
unset ARAG_USE_FAKE_FULL_RUN_PROVIDER

python -B -m experiments.cli live-run \
  --repo-root . \
  --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json \
  --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a \
  --full-experiment-id m7e_full_20260612T020000Z \
  --human-approval FULL_RUN \
  --approved-input-token-budget 1000000 \
  --approved-output-token-budget 500000 \
  --approved-wall-clock-seconds 3600 \
  --allow-unknown-cost \
```

---

## 6. Stop Point Statement

### 🛑 STOP POINT: Waiting for Explicit Approval 🛑

**This preflight turn is now COMPLETE and 100% GREEN.**

**WE HAVE HALTED AT THIS BOUNDARY. UNDER NO CIRCUMSTANCES SHALL THE AGENT EXECUTE THE FINAL LIVE RUN COMMAND OR PROCEED TO MILESTONE M7-E.15 WITHOUT EXPLICIT WRITTEN USER APPROVAL.**

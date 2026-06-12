# Milestone 7-E.10 Preflight: Final Rerun Preflight with New Experiment ID

**Status:** Completed (Preflight Validated - Execution Paused)

---

## 1. Background & Context
Following the successful Test-Driven Development (TDD) implementation of Milestone 7-E.9 (where Strategy E's Planner initial retrieval budget was increased from 2 to 3), we are preparing for the final full rerun of the 45-run experiment. 

To maintain scientific integrity:
- Resuming `m7e_full_20260611T210000Z` or `m7e_full_20260611T230000Z` is strictly forbidden.
- Any future full rerun must be initiated under a brand-new Experiment ID: **`m7e_full_20260612T010000Z`**.
- This Milestone (M7-E.10) serves solely as a **Preflight Validation Gate** and collision check. Absolutely no live execution, model calls, Gateway connections, or output creation are performed during this phase.

---

## 2. Preflight Checklist & System Verification

The following settings have been audited and verified from `configs/models.yaml`, `experiments/strategies/arag_multi_agent.py`, and the active codebase:

| Verification Item | Target Value | Actual Configured Value | Status |
| :--- | :--- | :--- | :--- |
| **Default Provider** | `hermes_vertex_gateway` | `hermes_vertex_gateway` | **PASSED** (Matches `configs/models.yaml`) |
| **Default Model** | `google/gemini-3.5-flash` | `google/gemini-3.5-flash` | **PASSED** (Matches `configs/models.yaml`) |
| **API Base URL** | `http://127.0.0.1:8787/v1` | `http://127.0.0.1:8787/v1` | **PASSED** (Matches `configs/models.yaml`) |
| **Planner Initial Budget** | `3` | `3` | **PASSED** (Verified in `arag_multi_agent.py`) |
| **Coder Initial Budget** | `2` | `2` | **PASSED** (Verified in `arag_multi_agent.py`) |
| **Reviewer Initial Budget** | `1` | `1` | **PASSED** (Verified in `arag_multi_agent.py`) |

---

## 3. Collision Check (Clean Slate Verification)

To ensure a pristine environment free from previous execution debris, we have verified that all workspace and output paths associated with the new Experiment ID (`m7e_full_20260612T010000Z`) **do NOT exist**:

- `results/raw/m7e_full_20260612T010000Z.jsonl` ➔ **Does NOT exist (Slate Clean)**
- `results/raw/artifacts/m7e_full_20260612T010000Z` ➔ **Does NOT exist (Slate Clean)**
- `results/raw/retrieval/m7e_full_20260612T010000Z` ➔ **Does NOT exist (Slate Clean)**
- `results/raw/diagnostics/m7e_full_20260612T010000Z` ➔ **Does NOT exist (Slate Clean)**
- `results/derived/m7e_full_20260612T010000Z.csv` ➔ **Does NOT exist (Slate Clean)**
- `results/derived/m7e_full_20260612T010000Z_summary.md` ➔ **Does NOT exist (Slate Clean)**
- `workspaces/m7e_full_20260612T010000Z` ➔ **Does NOT exist (Slate Clean)**

---

## 4. Frozen Hash & Traceability Verification

We recalculated and verified the SHA-256 hashes of all historical, frozen experimental artifacts. They remain 100% untouched and preserved:

- **M7-D Smoke Gate Report:** `results/raw/gates/m7d_smoke_20260611T123000Z.json`
  - SHA-256: `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a` (Unchanged)
- **M7-D Smoke Raw JSONL:** `results/raw/m7d_smoke_20260611T123000Z.jsonl`
  - SHA-256: `74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c` (Unchanged)
- **M7-E.3 Partial Raw JSONL:** `results/raw/m7e_full_20260611T210000Z.jsonl`
  - SHA-256: `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638` (Unchanged)
- **M7-E.7 Partial Raw JSONL:** `results/raw/m7e_full_20260611T230000Z.jsonl`
  - SHA-256: `d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7` (Unchanged)

---

## 5. Frozen PowerShell / Bash Command Draft

The following exact command is drafted for the upcoming **Milestone 7-E.11 final rerun**. This command is strictly for reference and **MUST NOT be executed** during this preflight phase.

```bash
# Set Live Execution and Run-Once Guards
export ARAG_RUN_LIVE_GATEWAY=1
export ARAG_EXECUTE_FULL_RUN_ONCE=1

# Ensure Fake Full Run Provider is DISABLED (Run on real Gateway)
unset ARAG_USE_FAKE_FULL_RUN_PROVIDER

# Execute Final Full Rerun (45-run experiment)
python -B -m experiments.cli live-run \
  --repo-root . \
  --approved-smoke-report results/raw/gates/m7d_smoke_20260611T123000Z.json \
  --approved-smoke-sha256 a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a \
  --full-experiment-id m7e_full_20260612T010000Z \
  --human-approval FULL_RUN \
  --approved-input-token-budget 1000000 \
  --approved-output-token-budget 500000 \
  --approved-wall-clock-seconds 3600 \
  --allow-unknown-cost
```

---

## 6. Stop Point & Operator Verification Block

> 🛑 **STOP POINT: WAITING FOR EXPLICIT OPERATOR APPROVAL** 🛑
>
> All preflight checklist audits, directory collision checks, budget policy verification, and frozen artifact hash assertions have successfully passed. 
> 
> **CRITICAL GUARDRAIL:** Under no circumstances should the operator or any automated agent execute the drafted final rerun command or initiate any Gateway model calls without a separate, explicit command and approval. The system is securely paused at the gate of Milestone 7-E.10.

---

## 7. Post-Execution Result Update (M7-E.11)

- **Operator Approval:** Received on Friday, June 12, 2026.
- **Rerun Execution Outcome:** Executed via Milestone 7-E.11 on the real Gateway. Resulted in a **Controlled Abort** due to budget enforcement (T02 E rep01 reached retrieval budget of 3 and aborted on the 4th query).
- **Execution Report:** For detailed logs, metrics, and audit analysis, see [Milestone 7-E.11 Abort Audit Report](M7E11_abort_audit.md).

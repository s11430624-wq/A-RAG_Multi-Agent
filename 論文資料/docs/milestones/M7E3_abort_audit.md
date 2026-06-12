# M7-E.3 Controlled Abort Audit & Resume Decision Plan

## 1. Execution Status & Overview

- **Milestone Target:** M7-E.3 Full-Run Live Execution
- **Execution Status:** **Controlled Abort** (Fail-Closed triggered)
- **Status Statement:** **M7-E.3 full 45-run is not complete.** The execution was intentionally aborted mid-way by the safety and format guardrails. No partial records were lost; exactly 7 completed, schema-valid, and tested runs were safely preserved.
- **Full Experiment ID:** `m7e_full_20260611T210000Z`
- **Failed Run ID:** `m7e_full_20260611T210000Z__T01__E__rep02__seed42`
- **Abort Reason:** `StrategyResponseError: Reviewer envelope is invalid` (Reviewer failed to output correct strict JSON envelope structure with `verdict` and `issues`).
- **Raw JSONL Path:** `results/raw/m7e_full_20260611T210000Z.jsonl`
- **Raw JSONL SHA-256:** `c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638`

---

## 2. Corrected Metrics & Distribution

### Finalized Records Metrics (7 Runs Completed)
- **Completed Records Count:** 7
- **Strategy Distribution:** Strategy A = 3, Strategy C = 3, Strategy E = 1
- **Task Distribution:** Task T01 = 7 (All 7 completed runs belong to task T01)
- **Success Metrics:**
  - `valid_run` = 7
  - `infra_error` = 0
- **Resource Usage (Finalized 7 Runs):**
  - **Completed Input Tokens:** 50,965 tokens
  - **Completed Output Tokens:** 52,389 tokens
  - **Completed Tool Calls:**
    - Strategy A: 0
    - Strategy C: 0
    - Strategy E: 2 (occurring in `rep01`)

### Call Records & Provider Attempts
- **Finalized Artifact Manifests Count:** 7
- **Finalized `provider_attempt_count` Sum:** 31 (summed over the 7 finalized manifests)
- **Finalized `call_records` Count Sum:** 31 (summed over the 7 finalized manifests)
- **Failed Run Attempts:** **unknown / not finalized** (Since the failed run `m7e_full_20260611T210000Z__T01__E__rep02__seed42` aborted before writing its finalized manifest to disk, its exact provider attempt count is not recorded in the durable finalized artifact bundle).

### Retrieval Logs Status
- **Strategy A / C:** No retrieval logs generated (as per strategy specifications, retrieval is 0).
- **Strategy E:** 
  - `m7e_full_20260611T210000Z__T01__E__rep01__seed42.jsonl`: Completed (2 lines, 34 tokens). Matches the completed JSONL record perfectly.
  - `m7e_full_20260611T210000Z__T01__E__rep02__seed42.jsonl`: **Partial / In-Progress Audit Artifact** (3 lines, 51 tokens). Exists on disk, but has no corresponding completed raw JSONL record. This is a partial artifact captured during the active aborted run.

---

## 3. Read-Only Consistency Validation

An automated, read-only validation check was performed over the preserved artifacts. The results are as follows:

| Verification Item | Check Description | Result |
| :--- | :--- | :--- |
| **Raw JSONL Schema Validity** | Every line of the raw JSONL file matches `contracts/result.schema.json`. | **PASSED** (Validated via jsonschema) |
| **Artifact Paths Existence** | All 7 `artifact_path` pointers listed in the JSONL exist physically. | **PASSED** |
| **Finalized Manifest Integrity** | Every `artifact_files` listed in all 7 `manifest.json` exists with matching SHA-256 hash. | **PASSED** (100% hash consistency verified) |
| **A/C Retrieval Logs** | No retrieval logs exist for Strategy A or Strategy C. | **PASSED** (Retrieval matches spec) |
| **E rep01 Alignment** | E rep01 retrieval log aligns precisely with its finalized JSONL record. | **PASSED** |
| **E rep02 Partial Log** | E rep02 retrieval log exists without completed JSONL record (partial artifact). | **PASSED** (Identified as expected partial residue) |
| **No Derived Outputs** | No files matching `*m7e_full*` exist under `results/derived/`. | **PASSED** (Correctly prevented mid-abort data pollution) |
| **Workspace Residue Cleanliness**| The transient workspace directory is completely absent on disk. | **PASSED** (No dirty workspaces left) |
| **Frozen Smoke Integrity** | Frozen smoke report path and hashes are 100% unchanged. | **PASSED** (No mutation of smoke gate results) |

---

## 4. Root Cause Evidence

During the execution of run `m7e_full_20260611T210000Z__T01__E__rep02__seed42`, the orchestrator invoked the Reviewer agent to perform final verification. 

- **Evidence Availability:**
  - **Failed reviewer raw response is not available in finalized artifact bundle.** (Because the execution aborted and was discarded prior to finalize and fsync).
  - **Abort reason currently comes from CLI/runtime report.**
  - **Future Hardening:** For future milestones, implementing a durable abort log or diagnostic bucket (e.g., `results/raw/diagnostics/`) for active failed runs is highly recommended to capture raw LLM responses before fail-closed deletion.
- **Abstract Mismatch Reason:**
  The runtime reports a mismatch in JSON envelope keys. The orchestrator expects the Reviewer envelope to contain exactly `{"verdict", "issues"}` keys. However, the model returned an invalid structure or missing keys (likely returning extra keys, a raw markdown code block envelope, or empty dict due to strict token restrictions), causing the strategy parser to raise `StrategyResponseError: Reviewer envelope is invalid`.

---

## 5. Resume Decision Matrix

To complete the experiment in the future, the operator faces three options:

| Criteria / Dimension | Option A: Preserve and Halt (不 Resume) | Option B: Hardened Resume (續傳同 ID) | Option C: Restart from Scratch (新 ID 重跑) |
| :--- | :--- | :--- | :--- |
| **Description** | Keep the aborted dataset as live evidence. Do not run any further tasks. | Fix parser/prompt formatting; resume from 7 completed records with the same experiment ID. | Keep aborted run as archive. Assign a new experiment ID and run all 45 runs from scratch. |
| **Fairness & Consistency** | **High** (No mixed prompts/code rules are introduced in the middle of a dataset). | **Medium** (Later runs might benefit from updated format guidelines/hardening). | **High** (Uniform code version, environment, and rules applied to all 45 runs). |
| **Data Integrity** | **Partial** (7/45 valid records, but dataset is incomplete). | **High** (Full 45 runs completed, no gaps). | **High** (Full 45 runs completed, no gaps). |
| **Cost Efficiency** | **High** (No further model/Gateway calls; $0 cost). | **High** (Saves the cost of the first 7 runs; only pays for remaining 38 runs). | **Low** (Discards the first 7 runs, pays for 45 runs again). |
| **Reproducibility** | **High** (Frozen aborted state is completely reproducible). | **Medium** (Hard to reproduce the exact "middle resume" environment state without detailed logs). | **High** (Deterministic scheduler seed ensures complete reproducibility). |

### Recommendation
**Preserve Option A for now.** Do not resume or rerun until the Reviewer parser or prompt formatting has been carefully audited and fixed in an isolated environment. Once fixed, **Option C** is highly recommended for final scientific reports to guarantee dataset uniformity and maximum statistical fairness, whereas **Option B** should be reserved only if API budget constraints are extremely tight.

---

## 6. Verification & Frozen Artifacts Protection

To guarantee that the aborted experiment left no corrupting residues and that the frozen smoke artifacts remain untouched:
- Executed local offline gate tests: `python -B -m pytest tests/live/test_full_run_gate.py tests/live/test_smoke_freeze_revalidation.py -q`
- **Result:** **All local offline tests passed successfully.**
- **Conclude:** No frozen smoke artifacts were modified. No new `m7e_full` records were created during this audit. The integrity of the codebase and results is fully preserved.

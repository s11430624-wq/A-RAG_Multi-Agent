# Milestone 7-E.20 Acceptance Criteria Document (Option D+ Revision)

## 1. Planned Deliverables & Status

| Area | Planned File / Action | Status |
| :--- | :--- | :---: |
| Decision Plan | `docs/superpowers/plans/2026-06-12-m7e20-coder-retrieval-policy.md` | **Completed (Option D+ Revised)** |
| Acceptance Doc | `docs/milestones/M7E20_acceptance.md` | **Completed (Option D+ Revised)** |
| General acceptance | Update `docs/milestones/M7_acceptance.md` status to include M7-E.20 | **Completed** |
| Implementation | No modifications of production code, tests, schemas, configs, prompts | **Completed (Enforced)** |
| Rerun Block | No live rerun, smoke-run, resume, or Gateway/model connections | **Completed (Enforced)** |

---

## 2. Acceptance Matrix (M7E20-001 to M7E20-015)

| ID | Requirement | Verification Method | Status |
| :--- | :--- | :--- | :---: |
| **M7E20-001** | **Depth Analysis** | Complete analysis of the existing strict role/phase isolation variables (`visible_evidence`, `self._coder_evidence_ids`, etc.) and why Coder/initial fails. | Verify in section 1 of Decision Plan. | **Completed** |
| **M7E20-002** | **Five Options Compared** | Detailed evaluation of five candidate options (Option A to D+) across 11 key dimensions. | Verify in section 2 of Decision Plan. | **Completed** |
| **M7E20-003** | **Option D+ Selection** | Recommended decision is Option D+: single-way read-only Planner evidence inheritance with Coder/initial budget raised to 3, no shared auth or cross-role cache. | Verify in section 1.5 of Decision Plan. | **Completed** |
| **M7E20-004** | **Strict Cache Isolation** | Cache keys remain role/phase isolated. Coder cannot hit Planner cache. Duplicate Coder/initial queries are cached only inside Coder's own scope. | Verify in section 1.2 of Decision Plan. | **Completed** |
| **M7E20-005** | **No Auth Inheritance** | Coder does not inherit Planner's `SearchAuthorization`. Coder must perform its own searches to authorize its own `chunk_read` actions. | Verify in section 1.3 of Decision Plan. | **Completed** |
| **M7E20-006** | **Reviewer Purity Guard** | Reviewer only receives `self._coder_evidence_ids` (strictly Coder-created evidence). Reviewer cannot view or cite Planner-created evidence. | Verify in section 1.4 of Decision Plan. | **Completed** |
| **M7E20-007** | **Repair Round Purity** | Repair phases only inherit `self._coder_evidence_ids` and do not implicitly gain Planner's initial evidence. | Verify in section 1.5 of Decision Plan. | **Completed** |
| **M7E20-008** | **Zero-Retrieval Baseline Guard** | Strict isolation is preserved for strategies A and C, ensuring they remain zero-retrieval. | Verify in section 4 of Decision Plan. | **Completed** |
| **M7E20-009** | **Fifteen TDD Test Cases** | Detailed specification of 15 distinct, automated test cases to guide M7-E.21 green implementation. | Verify in section 4 of Decision Plan. | **Completed** |
| **M7E20-010** | **Fail-Closed Boundary** | Clear budget failure boundary (4th distinct Coder query) is defined and will be tested before hit. | Verify in section 4 of Decision Plan. | **Completed** |
| **M7E20-011** | **No Code/Config Changes** | Verification that no production python files or configs are changed in this planning step. | Verify git workspace status and test suite execution. | **Completed** |
| **M7E20-012** | **No Active Gateway Call** | No socket connections or Gateway requests are made during this planning stage. | Verify offline test suite runs exclusively. | **Completed** |
| **M7E20-013** | **No Output Modification** | All historical frozen outputs and results remain unchanged and verified. | Verify in section 6 of Decision Plan. | **Completed** |
| **M7E20-014** | **New Experiment ID Path** | Future executions are restricted to a new canonical experiment ID (`m7e_full_20260612T040000Z`) with no resume. | Verify in section 5 of Decision Plan. | **Completed** |
| **M7E20-015** | **Physical Stop Point Locked** | Explicit confirmation that all live reruns are blocked and the system is locked until M7-E.21 implementation is approved. | Verify in section 5 of Decision Plan. | **Completed** |

---

## 3. Compliance & Security Declarations

- **No Code/Config Changes:** No Python files under `experiments/` or `tests/`, YAML configurations, JSON files, or prompts have been edited or modified in this planning phase.
- **No Network / Live Execution:** No active network request to the local/remote Gateway (`127.0.0.1:8787`) was performed. No model call was made.
- **No Output Overwrites:** No frozen outputs or historical result files have been modified.
- **No Residue:** No temporary workspaces, diagnostics, or partial output directories have been created.
- **Continuous Unique IDs:** All acceptance check IDs are unique, starting from `M7E20-001` through `M7E20-015`, ensuring non-overlapping audit records.

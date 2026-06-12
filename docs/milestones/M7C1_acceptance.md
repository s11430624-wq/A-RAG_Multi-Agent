# Milestone 7-C.1 Acceptance Plan: Reasoning Token Accounting Decision

**Status:** Completed (Decision Plan Formulated & Fail-Closed Preserved)  
**Date:** 2026-06-11  

---

## 1. M7-C.1 Acceptance Matrix

| ID | Area | Requirement | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| **M7C1-001** | Decision Document | A dedicated reasoning token accounting decision plan document must exist. | Check `docs/superpowers/plans/2026-06-11-m7c1-reasoning-token-accounting.md` | Completed |
| **M7C1-002** | Option Comparison | Document must compare Option A (Strict OpenAI), Option B (Usage Normalization), and Option C (Schema Extension). | Audit section 2 of the decision document | Completed |
| **M7C1-003** | Recommended Path | Choose and detail a single recommended path (Option B recommended). | Audit section 3 of the decision document | Completed |
| **M7C1-004** | Normalization Invariant | Define strict mathematical invariants for Option B ($input + output == total$). | Audit section 3.(1) of the decision document | Completed |
| **M7C1-005** | Audit Preservation | Define the exact location and schema-free structure for raw token audit fields (stored in ArtifactManifest `call_records`). | Audit section 3 of the decision document | Completed |
| **M7C1-006** | No Code Modification | No production code, parser, runner, or test logic may be modified in M7-C.1. | Run `git status` to ensure zero code modification | Completed |
| **M7C1-007** | Isolated Context | No live API gateway connections, live probes, or model calls may be performed. | Process audit of current session history | Completed |
| **M7C1-008** | Phase Gates | M7-D (Smoke Runs) and subsequent phases must remain **Blocked / Planned** until the decision is approved and implementation/tests are completed. | Review `docs/milestones/M7_acceptance.md` | Completed |

---

## 2. 邊界與安全性宣告

1. **零程式碼修改：** 本階段為純粹的決策規劃與不變量合約設計，絕不包含任何程式碼實作。
2. **零網路與模型請求：** 完全在離線狀態下進行分析，絕不發起任何 HTTP、gRPC 請求或 LLM 推論。
3. **M7-D Smoke 阻斷狀態：** 由於實作尚未啟動，M7-D 階段目前依舊處於 **Blocked** 狀態，不允許准入。

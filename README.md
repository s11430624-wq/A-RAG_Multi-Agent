# A-RAG × Autonomous AI Agents 整合實驗專案

本專案旨在探討如何將 **A-RAG 的階層式檢索能力** 整合至 **Planner–Coder–Reviewer 多 Agent 程式開發流程** 中，藉以驗證檢索對降低 API 幻覺、提升測試通過率與需求符合度的實際成效。

## 專案目標與 MVP 範疇
建立一個小型學生資訊管理系統的程式庫（`student_system`），針對 5 題 Coding Tasks，比較三種方法的實作表現：
1. **Strategy A (Single LLM)**：無檢索、無多 Agent 的單一模型基準。
2. **Strategy C (Multi-Agent)**：Planner–Coder–Reviewer 流程，無檢索。
3. **Strategy E (Multi-Agent + A-RAG)**：Planner–Coder–Reviewer 流程，整合 keyword_search、semantic_search 與 chunk_read 階層式檢索。

## 目前進度：M5「Provider、Prompts 與 A/C/E Strategies」
目前已完成 Milestone 1 至 Milestone 5。M5 新增：
- 無 credential、transport-injected 的 OpenAI-compatible Provider abstraction
- 五份版本化 prompt templates 與 byte-accurate hash
- Strategy A、C、E 的 deterministic session 與 repair boundary
- Strategy E 的 bounded M4 retrieval 與 evidence isolation
- Provider attempt audit、metrics 與 write-once artifact finalization
- 完整離線測試；未進入 M6，未啟用 live model 或網路呼叫

## 目錄結構
```text
.
├── configs/                  # 設定檔目錄 (YAML)
│   ├── experiment.yaml       # 實驗控制參數
│   └── models.yaml           # 模型與 API Provider 配置
├── contracts/                # 系統契約 JSON Schema
│   ├── task.schema.json      # 任務定義格式
│   ├── result.schema.json    # 實驗結果記錄格式
│   └── retrieval-log.schema.json # 檢索日誌格式
├── docs/                     # 文件
│   ├── experiment-contract.md # 實驗契約規範
│   ├── manual-review-rubric.md # 人工評分標準
│   ├── milestones/
│   │   └── M1_acceptance.md  # 驗收報告
│   └── superpowers/specs/    # 規格設計
├── tests/                    # 測試
│   └── contracts/            # 針對 JSON Schema 的測試
└── [其他空目錄/ .gitkeep]
```

## 測試執行方法
要驗證契約 schema 是否符合 Draft 2020-12 規範並正確過濾不合規資料，請於本機執行：
```bash
python -m pytest tests/contracts -v
```

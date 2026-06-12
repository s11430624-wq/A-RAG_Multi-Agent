# 手動 Run 紀錄

每跑一筆就複製一份這個模板。檔名建議：

```text
manual_runs/<TASK_ID>/<TASK_ID>_<STRATEGY>_rep<NN>.md
```

範例：

```text
manual_runs/T01/T01_A_rep01.md
```

## Metadata

- experiment_id:
- task_id:
- strategy: A / C / E
- repetition:
- model:
- operator:
- date_time:
- session_links:

## Strategy Setting

- agent_setup:
- tool_access:
- rag_enabled: true / false
- allowed_corpus:
- forbidden_sources:
- max_repair_rounds:
- workspace_policy_confirmed: true / false
- files_to_modify:

## 給 Agent 的輸入

### Task

```text
<貼上 task description>
```

### Starter Code / Excerpts

```text
<貼上 starter code 或相關 excerpt>
```

### Public Test Command

```text
<貼上 public test command>
```

## Interaction Log

### Round 0

#### Agent Responses

```text
<貼上各角色輸出>
```

#### Patch

```diff
<貼上 patch>
```

#### Public Test Result

```text
<貼上 public feedback>
```

### Round 1

#### Feedback Given

```text
<只貼 public feedback，不可貼 hidden result>
```

#### Agent Responses

```text
<貼上各角色輸出>
```

#### Patch

```diff
<貼上 patch>
```

#### Public Test Result

```text
<貼上 public feedback>
```

### Round 2

#### Feedback Given

```text
<只貼 public feedback，不可貼 hidden result>
```

#### Agent Responses

```text
<貼上各角色輸出>
```

#### Patch

```diff
<貼上 patch>
```

#### Public Test Result

```text
<貼上 public feedback>
```

## RAG Log

如果是 Strategy A 或 C，寫：

```text
RAG not allowed; no RAG used.
```

如果是 Strategy E，貼上已填好的 [RAG 紀錄模板](rag_log_template.md)。

## Final Output

- changed_files:
- final_public_passed: true / false
- public_passed_count:
- public_total_count:
- stop_reason:

### Final Patch

```diff
<貼上 final patch>
```

## Evaluator Result

- hidden_passed_count:
- hidden_total_count:
- valid_run:
- infra_error:
- error_type:
- stop_reason:

## Manual Notes

- operator_notes:
- unexpected_behavior:
- rule_violations:
- forbidden_path_requests:
- out_of_scope_file_modifications:

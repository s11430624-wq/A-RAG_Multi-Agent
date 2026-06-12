# Manual Run Record

## Metadata

- experiment_id: manual_hermes_eval
- task_id: T03
- strategy: E
- repetition: rep03
- model:
- operator:
- date_time:
- session_links:

## Strategy Setting

- agent_setup: E
- tool_access:
- rag_enabled: true
- allowed_corpus: rag_corpus/
- forbidden_sources: hidden tests, reference patches, previous runs, results, workspaces, repo-external files
- max_repair_rounds: 2
- workspace_policy_confirmed: false

## Files In This Package

- task_packet.md
- workspace_policy.md
- 00_shared_experiment_protocol.md
- persona files for Strategy E
- rag_corpus/

## Interaction Log

### Round 0

#### Agent Responses

```text

```

#### Patch

```diff

```

#### Public Test Result

```text

```

### Round 1

#### Feedback Given

```text

```

#### Agent Responses

```text

```

#### Patch

```diff

```

#### Public Test Result

```text

```

### Round 2

#### Feedback Given

```text

```

#### Agent Responses

```text

```

#### Patch

```diff

```

#### Public Test Result

```text

```

## RAG Log

Paste RAG query records here.

## Final Output

- changed_files:
- final_public_passed: true / false
- public_passed_count:
- public_total_count:
- stop_reason:

### Final Patch

```diff

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

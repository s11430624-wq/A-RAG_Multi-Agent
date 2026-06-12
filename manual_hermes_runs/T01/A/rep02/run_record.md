# Manual Run Record

## Metadata

- experiment_id: manual_hermes_eval
- task_id: T01
- strategy: A
- repetition: rep02
- model: manual_hermes
- operator: s9207 / Codex validation
- date_time: 2026-06-12
- session_links:

## Strategy Setting

- agent_setup: A
- tool_access: manual package only
- rag_enabled: false
- allowed_corpus: None
- forbidden_sources: hidden tests, reference patches, previous runs, results, workspaces, repo-external files
- max_repair_rounds: 2
- workspace_policy_confirmed: true

## Files In This Package

- task_packet.md
- run_record.md
- output_patch.diff

## Interaction Log

### Round 0

#### Agent Responses

```text
Agent produced a calculate_pass_rate implementation for student_system/src/grade.py.
```

#### Patch

```diff
See output_patch.diff
```

#### Public Test Result

```text
Initial submitted patch was not directly valid as a final patch file:
- contained UTF-8 BOM
- treated existing grade.py as /dev/null new file
- hunk count would omit the final return line
Operator/Codex normalized patch formatting and hunk count without changing solution logic.
```

### Round 1

#### Feedback Given

```text
Patch file normalized to a standard unified diff against existing student_system/src/grade.py.
```

#### Agent Responses

```text
No additional agent response; operator-side patch format repair only.
```

#### Patch

```diff
See final output_patch.diff
```

#### Public Test Result

```text
2 passed in 0.03s
```

### Round 2

#### Feedback Given

```text
Not used.
```

#### Agent Responses

```text
Not used.
```

#### Patch

```diff
Not used.
```

#### Public Test Result

```text
Not used.
```

## RAG Log

RAG not allowed; no RAG used.

## Final Output

- changed_files: student_system/src/grade.py
- final_public_passed: true
- public_passed_count: 2
- public_total_count: 2
- stop_reason: public_passed_after_format_repair

### Final Patch

```diff
See output_patch.diff
```

## Evaluator Result

- hidden_passed_count: 3
- hidden_total_count: 3
- valid_run: true
- infra_error: false
- error_type: none
- stop_reason: public_passed_after_format_repair

## Manual Notes

- operator_notes: Verified by applying final output_patch.diff to a clean temporary git clone from HEAD, then running public and hidden T01 tests.
- unexpected_behavior: Original patch was semantically correct but not directly usable as-is because of diff formatting/header issues.
- rule_violations: none recorded
- forbidden_path_requests: none recorded
- out_of_scope_file_modifications: none

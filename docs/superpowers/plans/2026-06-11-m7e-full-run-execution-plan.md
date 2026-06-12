# Milestone 7-E.1: Full-Run Execution Plan

## 1. Scope
- **Full Run Size:** 45 runs
- **Tasks Included:** T01, T02, T03, T04, T05 (5 tasks)
- **Strategies Included:** A, C, E (15 runs per strategy)
- **Repetitions:** 3 reps per task/strategy combination (5 tasks * 3 strategies * 3 reps = 45 runs)
- **Model:** `google/gemini-3.5-flash`
- **Provider:** `hermes_vertex_gateway`
- **Seed Policy:** Existing scheduler deterministic seed policy (shared seed `42` for all scheduled runs)
- **Output Experiment ID Format:** must match regex `^m7e_full_[0-9]{8}T[0-9]{6}Z$`

## 2. Approval Prerequisites
- **Gate M7-E.0 Validation:** Prior to any execution, the CLI approval validator must pass.
- **Smoke Report Integrity Binding:** The execution is strictly bound to:
  - **Smoke Report Path:** `results/raw/gates/m7d_smoke_20260611T123000Z.json`
  - **Smoke Report SHA-256:** `a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a`
- **Required Approval Flag:** Explicitly pass `--human-approval FULL_RUN` on the command line.
- **Cost Allowance Flag:** Explicitly pass `--allow-unknown-cost` because the frozen smoke run's risk flags include `unknown_cost`. If missing, execution fails closed.
- **Budget Values Enforced:** Must provide explicit, strictly positive values for token budgets (input/output) and wall-clock budget.
- **No Path Collision:** Reject execution if any of the following output targets already exist (fail-closed preflight):
  - Output JSONL: `results/raw/<full_experiment_id>.jsonl`
  - Artifacts Directory: `results/raw/artifacts/<full_experiment_id>/`
  - Retrieval Logs Directory: `results/raw/retrieval/<full_experiment_id>/`

## 3. Execution Architecture
### A. Executor Design Options
- **Option A: FullRunExecutor separate from SmokeExecutor**
  - Pro: Easy to keep isolated; less risk of breaking the frozen Smoke run logic.
  - Con: Code duplication. Any updates to live communication, error handling, and orchestration would have to be maintained in two places.
- **Option B: Generalize SmokeExecutor into LiveExperimentExecutor**
  - Pro: Unified interface. Both smoke runs (3 runs) and full runs (45 runs) leverage the same robust execution path, budget tracker, and recovery/resume engine. Reduces surface area for bugs.
  - Con: Requires careful engineering to prevent a live experiment run from accidentally writing to smoke paths or mutating frozen smoke report/JSONL artifacts.
### B. Recommendation
We recommend **Option B: Generalize SmokeExecutor into LiveExperimentExecutor**. By introducing parameterized paths, boundaries, and budget limits, a single unified Live executor maximizes code reuse, consistency, and testing coverage. To preserve frozen smoke files, the executor will strictly enforce directory boundaries based on the `experiment_id` and fail-closed if there is any overlap.

## 4. Budget Policy
- **Maximum Provider Attempts:**
  - Let's analyze the requirements:
    - Strategy A: max 3 calls per run
    - Strategy C: max 5 calls per run
    - Strategy E: max 14 calls per run
    - Total runs per strategy: 15 runs (5 tasks * 3 reps)
    - Total calls per strategy (worst-case logical limit):
      - Strategy A: 15 * 3 = 45 calls
      - Strategy C: 15 * 5 = 75 calls
      - Strategy E: 15 * 14 = 210 calls
      - Total worst-case logical calls = 45 + 75 + 210 = 330 calls.
  - **Proposed Budget Limit:** We set the max total call attempts to exactly **330**. There is zero headroom for retry loops at the provider/connection level because the budget is tight and retry logic is handled under strict constraint budgets.
- **Token Budgets (Based on Smoke Baseline):**
  - Observed Smoke run token usage (3 runs: T01 for A, C, E):
    - Input: 28,782 tokens (average ~9,594 per run)
    - Output: 22,390 tokens (average ~7,463 per run)
  - Scaling 15x would suggest:
    - Input: ~432,000 tokens
    - Output: ~336,000 tokens
  - To account for larger tasks (T02-T05 can have longer problem contexts and intermediate attempts), we use the approved model budget hard caps of:
    - Input Token Budget: **1,000,000** tokens (approx. 2.3x baseline)
    - Output Token Budget: **500,000** tokens (approx. 1.5x baseline)
  - **Wall-Clock Seconds:** **3600.0** seconds (1 hour).
  - **Unknown Cost Policy:** Cost remains unknown (flag `unknown_cost`). Budget tracker falls back to token counts, wall-clock, and provider attempt budget, and operator must explicitly approve by passing `--allow-unknown-cost`.

## 5. Abort Policy
If any of the following occur during execution:
- Provider connection/transport error (outside retry allowance)
- Missing or malformed token usage in model responses
- JSON schema validation failure of a finished run record
- Artifact manifest mismatch or physical hashing mismatch of written outputs
- Leakage detection sentinel trigger (e.g. credentials, bearer token, hidden tests in outputs)
- Any budget limit exceeded (total input tokens > 1M, output tokens > 500k, time > 3600s, attempts > 330, or consecutive infra failures >= 3)
- Writer failure or disk-write fsync error

The executor must:
1. **Immediate Halt:** Stop scheduling future runs immediately.
2. **Preserve Valid Data:** Keep all completed and schema-valid JSONL records already written to disk.
3. **No Partial Writes:** Do not write any incomplete/failed run records to the JSONL.
4. **Produce Abort Summary:** Print and save an execution abort summary describing the exact failure cause, budget consumption state, and next steps.
5. **Fail-closed Exit:** Exit with non-zero exit code:
   - **Exit Code 3:** Budget exceeded abort.
   - **Exit Code 4:** Leakage or security abort.
   - **Exit Code 5:** Schema or integrity mismatch abort.
   - **Exit Code 6:** Transport or infra abort.

## 6. Resume Policy
- **Skip Logic:** On resume, the scheduler reads the target raw JSONL (`results/raw/<full_experiment_id>.jsonl`) and skips any `run_id` that is already fully recorded, completed, and schema-valid.
- **Audit Verification:** Re-verify the smoke report hash (`smoke_report_sha256`) and re-run all validation preflight checks before resuming.
- **Configuration Snapshot Consistency:** Verify that current configs/models/task files match the hash snapshot recorded at the start of the experiment.
- **Fail-Closed on Malformed JSONL:** If the existing JSONL has duplicate records, malformed JSON, or missing artifact folders, reject resume and exit.
- **Leakage / History Isolation:** Completed runs' prompts, responses, or intermediate test logs must NEVER be loaded as strategy inputs or context for subsequent runs.
- **Rerun Restriction:** Do not rerun completed runs under the same `experiment_id` unless a completely new `experiment_id` is supplied.

## 7. Output Contract
- **Raw JSONL:** `results/raw/<full_experiment_id>.jsonl` (each record written with fsync upon run completion, append-only/exclusive-create)
- **Artifacts:** `results/raw/artifacts/<full_experiment_id>/`
- **Retrieval Logs:** `results/raw/retrieval/<full_experiment_id>/`
- **Derived CSV:** Generated after complete 45-run run-through.
- **Summary Report:** Generated after raw JSONL is fully closed.
- **Review Package Generation:** Manual review package is produced from raw JSONL *after* the entire 45-run execution is finalized (or aborted and declared complete), never dynamically during strategy runtime.

## 8. Leakage Controls
- **Hidden Tests:** Kept strictly inside the evaluator process and not visible to strategy or model context.
- **Search Deny-list:** Deny indexing or reading of output directories (`results/raw/`, `results/raw/artifacts/`) from previous or ongoing runs during retrieval operations.
- **Strategy Permissions:**
  - Strategies A and C: 0 retrieval allowed.
  - Strategy E: retrieval allowed strictly within the defined background corpus only.
- **Workspaces Isolation:** Active run directory is cleared and rebuilt from the starting codebase snapshot; workspaces of other runs are completely inaccessible.

## 9. TDD Plan
The following TDD cases must be implemented in the testing phase before full execution:
1. **test_full_run_scheduler_scope:** Verifies scheduler plans exactly 45 runs with correct ordering (T01-T05, A/C/E, 3 reps) and deterministic seeds.
2. **test_full_run_budget_reservation:** Verifies the budget limits initialize correctly to 330 call attempts, 1M input tokens, 500k output tokens, and 3600s wall-clock time.
3. **test_executor_abstraction:** Verifies that the Generalized `LiveExperimentExecutor` correctly routes paths, keeps smoke paths frozen, and rejects overlap.
4. **test_abort_on_leakage:** Verifies that when a simulated credentials pattern or hidden test is injected, execution stops immediately, doesn't record the bad run, and exits with code 4.
5. **test_abort_on_budget_exceeded:** Verifies that exceeding input token budget immediately terminates scheduling and exits with code 3.
6. **test_resume_valid_completed_records:** Verifies that a resume run successfully parses valid JSONL records and schedules only the remaining pending runs.
7. **test_resume_rejects_malformed_jsonl:** Verifies that resume fails closed if existing JSONL has duplicates or syntax errors.
8. **test_output_collision_preflight:** Verifies that if any planned target path exists, the execution fails closed before calling the provider.
9. **test_derived_outputs_post_execution:** Verifies that manual review package and derived CSV/markdown summaries are generated only after run completion and match raw JSONL contents.
10. **test_full_run_disabled:** Verifies that actual full-run execution remains hard-disabled in the CLI (returns code 2 or error) until explicit activation in M7-E.2.

## 10. Explicit Non-Goals
- **No Live Execution:** No gateway or model calls are executed during Milestone M7-E.1.
- **No State Mutation:** Frozen smoke artifacts (JSONL, report, manifests, retrieval logs) under `m7d_smoke_20260611T123000Z` must remain completely untouched.
- **No Schema Changes:** The JSON contract for results and artifacts remains frozen.

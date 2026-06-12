# M7-D Smoke Run Execution Plan

> **For agentic workers:** This document is an approval-gated execution plan. M7-D.0 must not execute `live-smoke`, any strategy, retrieval, or model request.

**Goal:** Define the exact three-run smoke command, isolated outputs, hard budgets, automated acceptance checks, rollback behavior, and explicit human approval boundary.

**Architecture:** `live-smoke` is a fail-closed CLI boundary. It validates two environment opt-ins, an exact human approval token, a smoke-specific experiment ID, explicit isolated paths, and hard budgets before any future execution path may be reached. M7-D.1A adds the offline-tested `SmokeExecutor`; M7-D.1B adds production Local OpenAI-Compatible Proxy composition and transport-attempt reservation without executing it. M7-D.2 one-shot 3-run live smoke completed and verified. M7-D outputs are frozen and bound by hashes. M7-E full 45-run remains Planned/Blocked pending explicit approval. Existing smoke files must not be mutated.

**Tech Stack:** Python 3.11, argparse, pytest, canonical UTF-8 JSON, SHA-256

---

## 1. Phase Boundary

M7-D.0 is plan and gate work only. M7-D.1A is offline synthetic execution and audit integration only. M7-D.1B is live-provider composition validation only.

- Do not execute `live-smoke` or `live-run`.
- Do not instantiate or execute strategies A, C, or E.
- Do not issue provider/model requests.
- Do not execute retrieval.
- Do not read hidden tests or credentials.
- Do not create result JSONL, workspaces, artifacts, retrieval logs, or a smoke gate report.
- M7-D.1A tests may create synthetic outputs only beneath pytest `tmp_path`.
- M7-D.1B may construct validated provider and transport objects but must not call `send()`, `SmokeExecutor.execute()`, strategies, evaluator, retrieval, or hidden tests.
- Real smoke execution is M7-D.2 and has been approved and successfully completed.

## 2. Fixed Smoke Scope

| Field | Required value |
| :--- | :--- |
| Run count | Exactly 3 |
| Task | `T01` only |
| Strategies | `A`, `C`, `E`, one run each |
| Repetition | `1` |
| Seed | `42` |
| Model | `GPT5.4` |
| Provider | `openai_compatible_gateway` |
| API base | `http://127.0.0.1:8787/v1` |
| Process model | Single process, sequential runs, single writer |

Any CLI option that widens tasks, strategies, repetitions, or converts the command into a full run is forbidden.

## 3. Approval Gate

All conditions are mandatory and conjunctive:

1. `ARAG_RUN_LIVE_GATEWAY=1`
2. `ARAG_ALLOW_SMOKE_RUN=1`
3. `--human-approval SMOKE_RUN`
4. `--experiment-id` exactly matches `^m7d_smoke_[0-9]{8}T[0-9]{6}Z$`
5. All output paths exactly include the same smoke experiment ID
6. All budget arguments are explicit positive integers
7. None of the target output paths already exists
8. No full-run-only flags are present

Environment variables alone can never authorize execution. During M7-D.1B, passing every production CLI and composition check prints `live-smoke composition validated, execution requires M7-D.2 approval.`, then exits with code 2.

## 4. Exact Command Draft

**DO NOT RUN DURING M7-D.0.** This is the reviewed command draft for a later separately approved smoke execution phase.

```powershell
$SmokeStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$SmokeExperimentId = "m7d_smoke_$SmokeStamp"
$env:ARAG_RUN_LIVE_GATEWAY = "1"
$env:ARAG_ALLOW_SMOKE_RUN = "1"

python -B experiments/cli.py live-smoke `
  --repo-root . `
  --experiment-id $SmokeExperimentId `
  --human-approval SMOKE_RUN `
  --raw-jsonl "results/raw/$SmokeExperimentId.jsonl" `
  --artifact-root "results/raw/artifacts/$SmokeExperimentId" `
  --retrieval-log-root "results/raw/retrieval/$SmokeExperimentId" `
  --smoke-report "results/raw/gates/$SmokeExperimentId.json" `
  --max-provider-calls 22 `
  --max-input-tokens 120000 `
  --max-output-tokens 48000 `
  --max-wall-clock-seconds 1800 `
  --consecutive-infra-failure-threshold 2
```

The current production CLI validates this shape and the live provider composition but deliberately does not execute it. Only tests may invoke `SmokeExecutor`.

## 4A. Offline Smoke Executor

M7-D.1A provides these public interfaces:

```text
SmokeExecutionRequest
SmokeExecutionResult
SmokeExecutor.execute(request) -> SmokeExecutionResult
```

The request binds the canonical experiment ID, synthetic repository root, raw JSONL, experiment-specific artifact/retrieval/report paths, `BudgetLimits`, and an injected provider transport factory. The executor:

- Uses `build_smoke_scheduler_plan` to plan exactly T01 x A/C/E with repetition 1 and seed 42.
- Runs sequentially in A, C, E order with one JSONL writer.
- Creates a fresh injected provider and production strategy session per run through `StrategyFactory`: `SingleLLMStrategySession` for A, `MultiAgentStrategySession` for C, and `ARAGMultiAgentStrategySession` for E.
- Runs every initial and repair round through `ExperimentOrchestrator` and the production `Evaluator`; each evaluation starts from a clean snapshot, and only public feedback returns to the strategy.
- Builds E's `FrozenStore` once and uses production `RetrievalFacade`, role-bound sessions, and the real retrieval JSONL writer. A and C receive no retrieval session.
- Lets the production sessions generate the worst-case logical schedule A(3) + C(5) + E(14) = 22 model calls from valid scripted planner, coder, reviewer, retrieval-request, and repair responses.
- Calls `LiveBudgetTracker.record_model_call_start()` once per logical model call and `reserve_provider_attempt()` immediately before every transport attempt. Successful, failed, timed-out, and retried attempts all consume the 22-attempt budget; attempt 23 is rejected before transport.
- Calls `record_tokens()` only after a complete normalized response. Token accounting does not increment either call counter.
- Passes the validated `ProviderConfig.provider_id` from `StrategyFactory` into `ArtifactBundleWriter`. `finalize()` writes `provider_id` in the original canonical manifest bytes and returns the SHA-256 of those exact bytes.
- Uses `ArtifactBundleWriter` and the production result builder plus `ResultJsonlWriter`; no executor-authored or post-finalize manifest rewrite, retrieval log, or result record is permitted.
- Treats `manifest.json` as the final exclusive-created artifact. After `finalize()` succeeds, no component may stage, recreate, or modify any artifact-bundle file.
- Aborts on any infrastructure, usage, normalization, leakage, retrieval, or budget failure; incomplete run output is removed while prior schema-valid records remain.
- Marks the returned execution result quarantined and does not create a smoke report on abort.

The only fake components in M7-D.1A are provider transport/responses, the clock when a test injects one, and deterministic synthetic repository fixtures under pytest `tmp_path`. No network, credential lookup, or production output root is used.

## 4B. Live Smoke Composition Wiring

M7-D.1B provides these public interfaces:

```text
build_live_smoke_provider_factory(config, env=...)
build_live_smoke_request(...)
validate_live_smoke_composition(request, env=...)
LiveSmokeComposition
AttemptReservingTransport
```

The composition root:

- Loads live `ExperimentConfig` and the validated `ProviderConfig` from repository YAML.
- Requires provider `openai_compatible_gateway`, model `GPT5.4`, seed 42, and exact API base `http://127.0.0.1:8787/v1`.
- Calls `LiveProviderFactory.create_provider()` once for each planned A/C/E run, producing three independent `OpenAICompatibleProvider` instances.
- Uses the existing no-auth loopback transport with `credential_provider=None`; no credential provider is loaded and no Authorization header is present.
- Wraps the HTTP transport with `AttemptReservingTransport`. The wrapper calls `ProviderAttemptHooks.reserve_provider_attempt()` immediately before every underlying `send()`, including retries. Attempt 23 fails before the sender is reached.
- Rejects mode/provider/model/seed/API-base mismatches, runtime endpoint drift, localhost aliases, port 8788, Cloudflare endpoints, credential-like configuration, Authorization injection, noncanonical paths, and nonapproved budgets.
- Performs readiness validation by constructing and inspecting providers only. It does not probe a port, open a socket, send HTTP, call a model, execute a strategy, create output directories, or invoke `SmokeExecutor.execute()`.

M7-D.2 one-shot 3-run live smoke completed and verified. M7-D outputs are frozen and bound by hashes. M7-E full 45-run remains Planned/Blocked pending explicit approval. Existing smoke files must not be mutated.

Successful synthetic execution writes only below the request's pytest repository:

```text
results/raw/m7d_smoke_<timestamp>.jsonl
results/raw/artifacts/m7d_smoke_<timestamp>/<run_id>/manifest.json
results/raw/retrieval/m7d_smoke_<timestamp>/<E-run-id>.jsonl
results/raw/gates/m7d_smoke_<timestamp>.json
workspaces/m7d_smoke_<timestamp>/<run_id>/
```

## 5. Output Isolation

For `m7d_smoke_<timestamp>`, the only approved future outputs are:

```text
results/raw/m7d_smoke_<timestamp>.jsonl
results/raw/artifacts/m7d_smoke_<timestamp>/
results/raw/retrieval/m7d_smoke_<timestamp>/
results/raw/gates/m7d_smoke_<timestamp>.json
workspaces/m7d_smoke_<timestamp>/
```

- The smoke experiment ID must differ from every full-run experiment ID.
- The experiment ID is a plain canonical identifier, never a path. Traversal segments, slash or backslash, absolute paths, drive prefixes, URL encoding, mixed case, suffixes, and any merely smoke-containing noncanonical name are rejected.
- Exclusive creation is required. Existing files or directories cause rejection; resume requires a separately reviewed command and must not silently reuse a new smoke ID.
- Raw JSONL, manifests, and retrieval logs must remain under their smoke-specific roots.
- Each resolved path is independently checked with `Path.relative_to()` against its exact approved root before the canonical filename/path comparison:
  - Raw JSONL: `repo_root/results/raw/`
  - Artifact root: `repo_root/results/raw/artifacts/`
  - Retrieval root: `repo_root/results/raw/retrieval/`
  - Smoke report: `repo_root/results/raw/gates/`
- The canonical gate report binds the exact output bytes using `source_jsonl_sha256`, `artifact_manifest_set_sha256`, and `retrieval_log_set_sha256`.
- A path resolving outside the repository or overlapping a non-smoke/full-run path is a technical rejection.

## 6. Hard Budget

| Limit | Value | Enforcement |
| :--- | ---: | :--- |
| `max_provider_calls` | 22 | Provider transport-attempt ceiling. A(3) + C(5) + E(14) = 22 logical calls when every call succeeds first try; failures and retries also consume attempts, and attempt 23 is blocked before transport |
| `max_input_tokens` | 120000 | Abort when the next accounted call would exceed the total |
| `max_output_tokens` | 48000 | Abort when the next accounted call would exceed the total |
| `max_wall_clock_seconds` | 1800 | Abort after 30 minutes |
| Consecutive infrastructure failure threshold | 2 | Abort on the second consecutive infrastructure failure |

These five values are an exact approved tuple. A larger or smaller CLI value is rejected because either direction is an unreviewed budget-contract change.

`model_call_count` and `provider_attempt_count` are reported separately. The hard safety budget monitors `provider_attempt_count`. This deliberately gives the approved 22-logical-call worst-case schedule no retry headroom: any retry that would require attempt 23 aborts before transport. Increasing the ceiling to 23, 66, or any other value requires a separately approved M7-D.0 budget amendment and is outside M7-D.1B.

Pricing is not estimated. If provider pricing is absent, `cost_known=false` and `risk_flags` includes `unknown_cost`; this risk flag does not become a fabricated cost and does not erase technical failures.

## 7. Expected Output Checks

A future smoke can pass the automated gate only when all checks pass:

- Raw JSONL has exactly 3 newline-delimited records.
- There is exactly one record for each of A, C, and E; every record is `T01`, repetition 1, seed 42, and the approved model/provider.
- Every record validates against `contracts/result.schema.json`.
- `valid_run` may be true or represent an experimental failure, but `infra_error` must be false.
- `usage_complete` is true and both input and output token counts are nonzero.
- The token invariant holds for every provider call and aggregate totals.
- Each run has an artifact manifest whose hashes and run identity match the result record.
- A and C have `tool_calls == 0` and no retrieval log.
- E has retrieval evidence, schema-valid logs, allowed-corpus provenance, and denylist checks.
- No hidden-test content/path, reference patch, credential, authorization header, or credential-like string appears in outputs.

## 8. Canonical Smoke Gate Report

The future report is exclusive-created canonical UTF-8 JSON with sorted keys and a trailing newline. It includes at least:

```text
smoke_experiment_id
source_jsonl_sha256
artifact_manifest_set_sha256
retrieval_log_set_sha256
total_input_tokens
total_output_tokens
total_provider_calls
cost_known
automated_gate_passed
risk_flags
rejection_reasons
```

`risk_flags` includes `unknown_cost` when pricing is absent. `rejection_reasons` contains only technical validation failures, never an invented cost estimate or a manual preference.

## 9. Fail-Closed and Rollback

Immediately stop the smoke sequence and prohibit full run when any of these occurs:

- Missing/incomplete usage or a token invariant failure
- Unauthorized retrieval, hidden path/content leak, reference patch leak, or credential-like output
- Malformed JSONL or a record count other than 3
- Schema failure, artifact manifest mismatch, or hash mismatch
- A/C retrieval tool calls or logs
- Missing or invalid E retrieval evidence
- Output path overlap, path escape, or an existing target
- Any hard budget limit or circuit-breaker threshold

Rollback is containment, not deletion:

1. Stop before the next provider call.
2. Do not start or approve `live-run`.
3. Preserve only already completed schema-valid records for forensic review.
4. Quarantine the smoke experiment ID as failed; do not append or overwrite under a replacement command without review.
5. Record technical rejection reasons in the canonical report only if report generation itself is safe and separately reached.
6. Unset both live environment gates after the operator finishes the approved session.

## 10. M7-D.0 Verification

These commands exercise unit/integration gates, composition wiring, and the injected fake executor without executing live smoke:

```powershell
Remove-Item Env:ARAG_RUN_LIVE_GATEWAY -ErrorAction SilentlyContinue
Remove-Item Env:ARAG_ALLOW_SMOKE_RUN -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m pytest tests/live tests/leakage -q
python -B -m pytest -q --ignore=tests/runtime/test_evaluator_integration.py
```

Residue acceptance requires no new files beneath `results/raw`, `results/derived`, `results/reviews`, or `workspaces` other than their pre-existing `.gitkeep` files.

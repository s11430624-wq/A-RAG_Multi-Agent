# Milestone 5 Acceptance: Provider, Prompt Templates, and A/C/E Strategies

**Status:** Completed (2026-06-11)

All 161 acceptance items were verified by focused tests, full regression,
attack/leakage tests, or reviewed static scans. No live model or network call
was used.

## 1. Deliverables

| Area | Files | Status |
| :--- | :--- | :--- |
| Provider package | `experiments/providers/` modules defined by the M5 plan | Completed |
| Prompt templates | Five versioned files under `experiments/prompts/` | Completed |
| Strategy package | `experiments/strategies/` modules defined by the M5 plan | Completed |
| Provider tests | `tests/providers/` | Completed |
| Strategy tests | `tests/strategies/` | Completed |
| Leakage tests | `tests/leakage/test_strategy_leakage.py` | Completed |
| Optional live smoke | `tests/live/test_gateway_smoke.py`, skipped by default | Completed |
| Existing contracts/config/tasks | Unchanged | Completed unchanged |

## 2. Acceptance Matrix

| ID | Acceptance item | Verification | Status |
| :--- | :--- | :--- | :--- |
| M5-01 | Provider configuration is strictly validated | Invalid YAML/config fixtures fail closed | Completed |
| M5-02 | Config and provider objects contain no credentials | Object graph and serialized scan | Completed |
| M5-03 | A/C/E share one provider instance | Identity assertion | Completed |
| M5-04 | A/C/E share model ID, temperature, top_p, max output tokens, timeout, and seed | Captured request equality | Completed |
| M5-05 | `ModelRequest` and `ModelResponse` are immutable | Dataclass mutation tests | Completed |
| M5-06 | Provider timeout comes only from experiment config | Request capture test | Completed |
| M5-07 | Seed support is explicit | Supported/unsupported capability tests | Completed |
| M5-08 | Provider request ID is recorded when available | Response/call record assertion | Completed |
| M5-09 | Missing request ID remains null | Missing metadata fixture | Completed |
| M5-10 | Provider usage is recorded only when supplied | Usage source assertions | Completed |
| M5-11 | Missing usage remains null internally | Missing usage fixture | Completed |
| M5-12 | Missing usage is never exported as fake precise zero | Projection raises usage-unavailable error | Completed |
| M5-13 | Estimated cost is null without pricing config | Metrics assertion | Completed |
| M5-14 | Model latency excludes retrieval setup and test time | Clock-controlled test | Completed |
| M5-15 | Transport failure retry count is fixed | Three-attempt scripted transport | Completed |
| M5-16 | Retry backoff is exactly 0.25 then 0.50 seconds | Fake sleeper assertion | Completed |
| M5-17 | Only classified transport/gateway failures retry | Status/exception matrix | Completed |
| M5-18 | Empty response is not retried | Provider call count assertion | Completed |
| M5-19 | Malformed response is not retried | Provider call count assertion | Completed |
| M5-20 | Invalid patch/content error is not retried | Strategy/parser integration assertion | Completed |
| M5-21 | Authentication failure is not retried and leaks no credential | Error and scan test | Completed |
| M5-22 | Cancellation stops attempts and backoff | Cancellation token tests | Completed |
| M5-23 | FakeProvider is deterministic | Repeated sequence test | Completed |
| M5-24 | ScriptedProvider supports every required failure/success outcome | Outcome matrix test | Completed |
| M5-25 | Ordinary pytest performs zero network calls | Network-denial monkeypatch/static scan | Completed |
| M5-26 | Live gateway smoke explicitly skips when `ARAG_RUN_LIVE_GATEWAY != 1` | Collected test reports skipped with env unset | Completed |
| M5-27 | Full task dict never enters strategy constructors | Signature and runtime type tests | Completed |
| M5-28 | Full task dict never enters Provider requests | Captured request scan | Completed |
| M5-29 | A/C/E receive identical `ModelVisibleTask` | Equality assertion | Completed |
| M5-30 | Starter files are Snapshot-verified | Synthetic hash mismatch test | Completed |
| M5-31 | Model-visible starter paths are safe and tracked | Escape/untracked path tests | Completed |
| M5-32 | Required evidence sentinel never enters visible task | Sentinel scan | Completed |
| M5-33 | Grading sentinel never enters visible task | Sentinel scan | Completed |
| M5-34 | Hidden ID/test sentinel never enters visible task | Sentinel scan | Completed |
| M5-35 | Public test paths do not enter prompts | Rendered prompt scan | Completed |
| M5-36 | Evaluator private audit never enters strategy/provider | Type and sentinel tests | Completed |
| M5-37 | Other-run artifacts never become inputs | Cross-run isolation test | Completed |
| M5-38 | Prompt template hash uses raw UTF-8 bytes | Independent SHA-256 assertion | Completed |
| M5-39 | Rendered prompt hash uses exact rendered bytes | Independent SHA-256 assertion | Completed |
| M5-40 | Prompt hashes are stable across repeated rendering | Determinism test | Completed |
| M5-41 | C/E use identical raw Planner/Coder/Reviewer/Repair template bytes | Raw-byte equality assertions | Completed |
| M5-42 | Prompt delimiters separate task, starter, feedback, and evidence | Exact rendered sections | Completed |
| M5-43 | Data blocks are explicitly non-instructional | Template assertion | Completed |
| M5-44 | Patch prompts prohibit Markdown fences and commentary | Template/parser tests | Completed |
| M5-45 | Patch parser accepts only pure unified diff | Positive/negative parser matrix | Completed |
| M5-46 | Empty/commentary output maps to empty response | Parser classification test | Completed |
| M5-47 | Malformed diff intent maps to invalid patch | Parser classification test | Completed |
| M5-48 | Patch parser performs no silent repair | Original text/error assertion | Completed |
| M5-49 | Planner parser rejects additional/unknown fields | Strict JSON tests | Completed |
| M5-50 | Planner files remain inside visible modification allowlist | Parser test | Completed |
| M5-51 | Reviewer pass requires zero issues | Parser test | Completed |
| M5-52 | Reviewer fail requires bounded issues | Parser test | Completed |
| M5-53 | Reviewer rejects unknown category/additional fields | Parser test | Completed |
| M5-54 | Reviewer feedback size is bounded | Oversized fixture | Completed |
| M5-55 | C Reviewer evidence IDs must be empty | Forged evidence test | Completed |
| M5-56 | E Reviewer evidence IDs must belong to current evidence ledger | Unknown/cross-run ID tests | Completed |
| M5-57 | Reviewer never outputs or applies a patch | Flow and parser assertions | Completed |
| M5-58 | Reviewer fail does not trigger pre-test revision | Provider call schedule assertion | Completed |
| M5-59 | Strategy A performs one initial patch-producing call | ScriptedProvider call count | Completed |
| M5-60 | Strategy A has no Planner or Reviewer call | Role record assertion | Completed |
| M5-61 | Strategy A has no retrieval object or Evidence block | Construction and prompt scan | Completed |
| M5-62 | Strategy C follows Planner-Coder-Reviewer order | Role record assertion | Completed |
| M5-63 | Strategy C sends initial Coder patch unchanged to caller | Patch identity assertion | Completed |
| M5-64 | Strategy C never constructs M4 facade/session | Monkeypatch constructor denial | Completed |
| M5-65 | Strategy E uses the same role order and templates as C | Role/template hash comparison | Completed |
| M5-66 | Strategy E builds one shared frozen store | Builder counter and identity test | Completed |
| M5-67 | E repair rounds reuse the same store | Identity and filesystem-read denial | Completed |
| M5-68 | Structured retrieval requests are provider-neutral JSON | Parser and captured response test | Completed |
| M5-69 | Unknown retrieval fields/actions/tools are rejected | Parser matrix | Completed |
| M5-70 | Retrieval calls are capped per role and phase | Budget exhaustion tests | Completed |
| M5-71 | Retrieval search top_k is capped at 3 | Parser/runtime tests | Completed |
| M5-72 | Chunk read is limited to prior search results | Unauthorized chunk test | Completed |
| M5-73 | Retrieval cannot enter an infinite loop | Scripted repeated-request test | Completed |
| M5-74 | Every E retrieval call uses M4 logging | JSONL count/schema assertions | Completed |
| M5-75 | Evidence records include file path, chunk ID, content hash, and text | Evidence object assertion | Completed |
| M5-76 | Evidence is inserted only in explicit data blocks | Rendered prompt assertion | Completed |
| M5-77 | Required evidence is not used for query generation or success | Sentinel and monkeypatch tests | Completed |
| M5-78 | A/C tool calls and retrieved tokens are zero | Metrics assertion | Completed |
| M5-79 | A/C retrieval success is null | Metrics assertion | Completed |
| M5-80 | E retrieval success follows operational definition | Empty/non-empty evidence cases | Completed |
| M5-81 | Repairs accept only `SanitizedPublicFeedback` | Runtime type rejection tests | Completed |
| M5-82 | Public feedback appears only in repair prompts | Initial prompt scan | Completed |
| M5-83 | Hidden summaries cannot trigger or influence repairs | Type/sentinel tests | Completed |
| M5-84 | Strategies cannot create their own repair rounds | Counter and interface tests | Completed |
| M5-85 | Repair rounds are capped at two | Third-call rejection test | Completed |
| M5-86 | A repair uses the same Single LLM role | Call record assertion | Completed |
| M5-87 | C/E repair is Coder-only | Call record assertion | Completed |
| M5-88 | C/E repair may receive initial Reviewer feedback only after public failure | Prompt phase test | Completed |
| M5-89 | Per-call prompt/response hashes and retry counts are recorded | Call record assertions | Completed |
| M5-90 | Aggregate token/latency/tool metrics are exact | Scripted usage/clock tests | Completed |
| M5-91 | Artifact paths reject traversal, sibling-prefix, and symlink/junction escape | Path attack tests | Completed |
| M5-92 | Artifact files are write-once and manifest is written last | Existing-file/failure tests | Completed |
| M5-93 | Artifact failure rolls back files created by that bundle | Partial failure test | Completed |
| M5-94 | Artifact rollback failure reports integrity unknown | Error message assertion | Completed |
| M5-95 | Artifacts contain no credentials | Recursive content scan | Completed |
| M5-96 | Artifacts contain no hidden/evaluator-only sentinels | Recursive content scan | Completed |
| M5-97 | Artifacts never feed a later strategy run | Cross-run read denial | Completed |
| M5-98 | Current result schema remains unchanged | Hash/diff check | Completed |
| M5-99 | Current task/config files remain unchanged | Hash/diff check | Completed |
| M5-100 | M1-M4 regression remains green | Full pytest | Completed |
| M5-101 | No M6 CLI, batch runner, repetition scheduler, or result JSONL loop exists | Static scan and file list | Completed |
| M5-102 | No cache, JSONL, test artifact, or synthetic repo residue remains | Physical scan | Completed |
| M5-103 | Response classifier recognizes retrieval only for a complete JSON object with `action=retrieve` | Exact-envelope classifier matrix | Completed |
| M5-104 | Planner and Reviewer final JSON are never misclassified as retrieval | Role-aware JSON fixtures | Completed |
| M5-105 | Markdown, JSON plus text, diff plus text, partial content, and wrong-role envelopes are invalid | No-extraction negative matrix | Completed |
| M5-106 | A role without a valid final response fails and never reuses its last retrieval request as output | Retrieval-then-exhausted script | Completed |
| M5-107 | Retrieval after role/phase budget exhaustion fails closed with no tool, log, or further Provider call | Counter and JSONL assertions | Completed |
| M5-108 | Strategy A uses 1 initial call, 1 per requested repair, and at most 3 total | Exact schedule tests | Completed |
| M5-109 | Strategy C uses Planner 1, Coder 1, Reviewer 1, repair Coder 1, and at most 5 total | Exact schedule tests | Completed |
| M5-110 | Strategy E uses Planner/Coder up to 3, Reviewer up to 2, repair Coder up to 3, and at most 14 total | Exact schedule tests | Completed |
| M5-111 | Provider calls and accepted retrieval tool calls are counted separately | Scripted continuation counters | Completed |
| M5-112 | Provider call indices are run-global, contiguous from 1, and transport retries remain attempts of one call | Multi-role retry fixture | Completed |
| M5-113 | Reviewer fail adds no initial Coder call and unused repair capacity consumes no call | No-repair and reviewer-fail fixtures | Completed |
| M5-114 | Transport request/response ownership, canonical JSON bytes, public headers, timeout, and IDs match the declared frozen types | Exact object and captured transport tests | Completed |
| M5-115 | Authorization is injected only by unsaved live transport immediately before send and is never serialized | Transport boundary and artifact scan | Completed |
| M5-116 | Fake transport/provider requires no credential or environment lookup | Environment denial test | Completed |
| M5-117 | Cancellation is checked before attempts, after transport, and before backoff | Cancellation timing matrix | Completed |
| M5-118 | All declared Provider, strategy, ledger, classification, manifest, and projection dataclasses have exact frozen fields | Dataclass field and mutation tests | Completed |
| M5-119 | Evidence IDs are unique and monotonically increasing across one run and keyed by run/task/role/phase | Ledger sequence tests | Completed |
| M5-120 | Evidence and search authorization cannot cross role, phase, run, or task | Four-boundary attack matrix | Completed |
| M5-121 | Reviewer sees only evidence IDs explicitly attached to Coder provenance and inherits no search authorization | Reviewer prompt and chunk-read tests | Completed |
| M5-122 | Repair Coder may view initial Coder evidence read-only but must search again for repair-phase chunk authorization | Repair ledger tests | Completed |
| M5-123 | C/E raw role templates are identical and use one `CapabilityContext` placeholder contract | Template byte and renderer tests | Completed |
| M5-124 | Removing only CAPABILITY/EVIDENCE_DATA blocks makes C/E rendered bytes identical | Canonical rendered-byte comparison | Completed |
| M5-125 | C omits EVIDENCE_DATA and E with no evidence renders exactly `[]` | Exact section assertion | Completed |
| M5-126 | Canonical JSON escaping prevents all reserved closing-delimiter breakout while remaining reversible | Delimiter and decode tests | Completed |
| M5-127 | Prompt injection sentinels remain data and prompt hash covers final sent bytes | Captured bytes and independent hash | Completed |
| M5-128 | Every Provider attempt records latency and successful generate latency includes attempts plus fixed backoff | Fake clock audit | Completed |
| M5-129 | Strategy model latency includes failed/cancelled Provider elapsed time but excludes retrieval/setup time | Mixed outcome clock test | Completed |
| M5-130 | Every continuation creates a call record and usage totals include retrieval-request responses | Multi-continuation usage test | Completed |
| M5-131 | Any successful call with missing usage makes aggregate input/output null | Mixed complete/missing fixture | Completed |
| M5-132 | Bool, negative, or contradictory total-token usage fails closed | Usage validation matrix | Completed |
| M5-133 | Failed/cancelled calls create attempt audit but no `ModelCallRecord` without a valid response | Record-shape assertions | Completed |
| M5-134 | Artifact manifest contains every specified identity, hash, request, call, usage, retry, retrieval, timestamp, and version field | Exact manifest schema test | Completed |
| M5-135 | Manifest uses relative paths, excludes itself from its hash map, verifies files first, and is written last | Hash mismatch and partial-bundle tests | Completed |
| M5-136 | Artifact leakage checks use typed provenance and do not reject ordinary source merely containing `token` or `secret` | Benign-source and forbidden-metadata tests | Completed |
| M5-137 | Result projection succeeds only with complete usage and otherwise raises `ProviderUsageUnavailableError` | Complete/missing projection tests | Completed |
| M5-138 | A/C projection uses real Provider usage and never substitutes retrieval zeros for model tokens | A/C metrics fixtures | Completed |
| M5-139 | Importing live tests reads no credentials or network and live transport is constructed only after explicit opt-in inside the test | Import guard and constructor spy | Completed |
| M5-140 | Invalid role output and final parser errors raise `StrategyResponseError` without Provider retry | Call-count and error tests | Completed |
| M5-141 | Only `finish_reason=stop` may enter `ResponseEnvelopeClassifier` | Finish-reason gate spy | Completed |
| M5-142 | `length`, `content_filter`, `tool_request`, and `unknown` raise non-retryable `ProviderFinishReasonError` | Finish-reason error matrix | Completed |
| M5-143 | Provider-native `tool_request` is never accepted as M5 retrieval | Native-tool negative fixture | Completed |
| M5-144 | Non-stop responses execute no retrieval, enter no parser, and create no `ModelCallRecord` | Tool/parser/call-record spies | Completed |
| M5-145 | A truncated response that resembles a valid diff or JSON still fails when finish reason is non-stop | Truncated diff/Planner/Reviewer/retrieval fixtures | Completed |
| M5-146 | Rejected finish reasons retain sanitized response hash, finish reason, elapsed time, and complete attempts in immutable private failure audit before staged rollback | Failure-audit and rollback assertion | Completed |
| M5-147 | `ModelRequest.call_index` is run-global and every returned attempt record uses that same index | Multi-call retry identity test | Completed |
| M5-148 | Successful `ModelResponse` atomically carries immutable complete attempt records | Successful retry-then-response test | Completed |
| M5-149 | Every final Provider failure and cancellation exposes immutable attempt records and elapsed seconds through the raised error | Failure/cancellation audit tests | Completed |
| M5-150 | Provider audit uses no mutable last-call, global, callback, or thread-local side channel | Concurrent/sequential overwrite guard | Completed |
| M5-151 | Finish/content failures preserve attempt audit but create no successful model-call record | Metrics collector failure fixtures | Completed |
| M5-152 | Generate methods stage write-once artifacts and never create manifest or expose artifact path | Pre-finalization filesystem/output assertions | Completed |
| M5-153 | Initial-only and initial-repair1-repair2 flows finalize by validating hashes and exclusive-creating manifest last | Lifecycle success matrix | Completed |
| M5-154 | Finalization returns metrics, artifact path, and exact manifest SHA-256, and only then permits result projection | Finalization/projection assertions | Completed |
| M5-155 | Finalize before a successful initial patch or during an active turn fails without sealing or corrupting staged state | Early-finalize tests | Completed |
| M5-156 | Duplicate finalize and every generate after finalize fail with sealed-session errors | Post-finalization state tests | Completed |
| M5-157 | Close without finalize and terminal failure immediately roll back the session staged bundle and leave no manifest | Rollback and residue assertions | Completed |
| M5-158 | Close after successful finalize releases memory without deleting or altering the finalized bundle | Finalized-close hash test | Completed |
| M5-159 | Every request has `system_prompt == ""` and the complete versioned template output only in `user_prompt` | Captured request assertions | Completed |
| M5-160 | Rendered prompt hash and staged prompt artifact are byte-for-byte derived from the exact sent user-prompt UTF-8 bytes | Independent hash and artifact comparison | Completed |
| M5-161 | Provider adapter adds no hidden system instruction, prefix, suffix, separator, or wrapper | Captured pre/post-adapter byte test | Completed |

## 3. Verification Results

Final focused verification on 2026-06-11:

| Command | Result |
| :--- | :--- |
| `python -B -m pytest tests/providers -v` | 32 passed in 0.13s |
| `python -B -m pytest tests/strategies -v` | 51 passed in 0.69s |
| `python -B -m pytest tests/leakage -v` | 18 passed in 5.46s |
| `python -B -m pytest tests/retrieval -v` | 55 passed in 0.45s |
| `python -B -m pytest tests/contracts tests/m2 tests/runtime -v` | 89 passed in 18.12s |
| `python -B -m pytest tests/live/test_gateway_smoke.py -v` | 1 skipped in 0.01s, explicit opt-in absent |
| Complete run 1: `python -B -m pytest -q` | 245 passed, 1 skipped in 23.58s |
| Complete run 2: `python -B -m pytest -q` | 245 passed, 1 skipped in 23.69s |

All commands used `PYTHONDONTWRITEBYTECODE=1`. There were zero failures, zero
errors, and zero unexpected warnings.

Run twice:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/providers -v
python -B -m pytest tests/strategies -v
python -B -m pytest tests/leakage -v
python -B -m pytest tests/retrieval -v
python -B -m pytest tests/contracts tests/m2 tests/runtime -v
python -B -m pytest -q
```

The live gateway smoke test must report skipped unless explicitly opted in and must never be needed for M5 acceptance.

## 4. Known Limitations

- Detailed provider metadata remains in the finalized artifact manifest because the current result schema has no matching fields.
- Missing provider usage remains `None`; result projection fails closed rather than inventing token counts.
- Gateway compatibility is offline-contract-tested only. The live smoke test is deliberately skipped without explicit opt-in, and live transport selection remains M6 work.
- Evaluator callback orchestration, batch execution, result JSONL, resume, and repetitions remain M6 work.

## 5. Completion Confirmation

- All 161 acceptance items are Completed.
- M5 provider, prompt, strategy, and corresponding test files were implemented.
- Existing schema, config, tasks, student-system, runtime, evaluator, retrieval implementation, and M1-M4 behavior were not modified.
- No model, API, Hermes, Vertex AI, gateway, or network call was made.
- M6 was not entered.

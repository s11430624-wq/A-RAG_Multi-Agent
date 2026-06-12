# M7-E.24 Gateway 429 Recovery and Batch Throttling Decision Plan

**Status:** Decision Completed / Implementation Not Started / Live Execution Blocked

**Incident:** M7-E.23 controlled abort at `T02 / E / rep01`

**Observed error:** `ProviderTransportError: HTTP Error 429: Too Many Requests`

## 1. Scope and Non-Execution Boundary

M7-E.24 is a planning-only milestone. It does not modify production code, tests, schemas, YAML configuration, task definitions, prompts, or frozen experiment outputs.

This milestone must not:

- resume `m7e_full_20260612T040000Z`;
- execute another live-run, smoke-run, or probe;
- connect to `127.0.0.1:8787`;
- call a model;
- create a new raw JSONL, artifact bundle, retrieval log, diagnostic, derived output, or workspace.

## 2. Physical Root Cause Analysis

### 2.1 HTTP 429 never reaches the Provider status classifier

`OpenAICompatibleProvider` already declares `429`, `502`, `503`, and `504` retryable. That logic only runs when the transport returns a `TransportResponse`.

The live `OpenAICompatibleHttpTransport` instead catches `urllib.error.HTTPError` and raises `ProviderTransportError`. Therefore a real 429:

1. never becomes a `TransportResponse(status_code=429, ...)`;
2. never reaches `OpenAICompatibleProvider._status_error()`;
3. never uses the Provider's retry loop;
4. aborts the active run immediately.

The existing fake Provider tests return status-bearing responses directly, so they do not reproduce this real `urllib` boundary.

### 2.2 Existing retry delays are unsuitable for quota recovery

The current Provider profile fixes:

```text
max_attempts=3
retry_backoff_seconds=(0.25, 0.50)
```

These delays are suitable for brief connection faults but not a server quota window. The live transport allowlists rate-limit headers but does not allowlist `Retry-After`, and the Provider does not consume any rate-limit response header.

### 2.3 There is no shared live pacing across Provider instances

The full run creates independent Provider instances for different runs. Attempt reservation is shared, but request pacing is not. The executor moves directly from one completed run to the next.

Consequences:

- A/C/E share the Gateway quota but do not share a pacing state.
- A later strategy can encounter quota accumulated by earlier runs.
- A retry in one Provider cannot coordinate with requests from another Provider.

### 2.4 The approved attempt budget has no retry headroom

`330` is both:

- the maximum logical-call schedule for 45 runs; and
- the current physical Provider-attempt ceiling.

Any retry consumes an additional physical attempt. Therefore the current attempt budget contradicts the existence of retry behavior.

### 2.5 Failed active-run attempt evidence is not durable

Completed manifests preserve attempt records. A failed active run has no finalized manifest, so the exact failed attempt count, selected backoff, and safe rate-limit metadata are not durably available.

The M7-E.23 CLI error proves the final 429, but it does not provide a complete canonical failed-attempt audit.

## 3. Options

### Option A: Preserve current behavior and halt the experiment

- No implementation risk.
- Strong fail-closed behavior.
- Cannot produce the 45-run dataset.
- Does not resolve the mismatch between real `urllib` behavior and Provider retry tests.

**Decision:** Not selected.

### Option B: Normalize HTTP errors only

Return retryable HTTP responses from the transport so the existing Provider retry loop runs.

- Small change.
- Fixes the real/fake transport mismatch.
- Still retries 429 after only `0.25` and `0.50` seconds.
- Still has no shared pacing or retry-attempt budget.

**Decision:** Necessary but insufficient.

### Option C: Add fixed inter-run delay only

Sleep after every completed run without changing HTTP status propagation.

- Simple and strategy-neutral.
- May reduce request density.
- A real 429 still aborts immediately.
- A fixed delay cannot respond to an actual server reset window.

**Decision:** Insufficient alone.

### Option D: Live-only bounded 429 recovery with shared pacing

Combine:

1. correct HTTP status propagation;
2. bounded `Retry-After` handling;
3. shared live pacing across all Provider instances;
4. an explicit physical-attempt budget amendment;
5. durable sanitized failure audit.

Offline/default Provider behavior remains unchanged unless a live rate-limit policy is explicitly injected.

**Decision:** Recommended.

### Option E: Resume the partial M7-E.23 dataset after a local patch

- Lowest additional model cost.
- Mixes pre-policy and post-policy observations in one experiment ID.
- Breaks the established new-ID scientific consistency rule.

**Decision:** Rejected. `m7e_full_20260612T040000Z` remains frozen.

## 4. Recommended Option D Contract

### 4.1 HTTP transport contract

For `urllib.error.HTTPError`:

- `401` and `403` remain authentication failures.
- Other HTTP statuses return a bounded `TransportResponse`.
- Response body reads remain limited by `max_response_bytes`.
- Only allowlisted response headers are retained.
- `Retry-After` is added to the case-insensitive response-header allowlist.
- No Authorization value, credential, raw request body, or unrestricted response header enters logs or errors.

This allows the Provider to classify `429/502/503/504` using its existing status boundary.

### 4.2 Live retry-delay resolver

Add an optional Provider dependency:

```python
RetryDelayResolver = Callable[
    [int, TransportResponse, float],
    float,
]
```

The default is `None`, preserving the existing M5 fixed `0.25/0.50` behavior for offline tests and non-live composition.

The live resolver rules are:

1. Only retry statuses already approved by `_RETRYABLE_STATUSES`.
2. For `429`, parse `Retry-After` as either:
   - non-negative integer delta seconds; or
   - an RFC-compliant HTTP date.
3. Clamp the chosen delay to `1 <= delay <= 120` seconds.
4. If `Retry-After` is absent or malformed, use:
   - first 429 retry: `30` seconds;
   - second 429 retry: `60` seconds.
5. For `502/503/504`, retain fixed `0.25/0.50` seconds.
6. The selected delay is stored in `ProviderAttemptRecord.backoff_seconds_after`.
7. Cancellation and wall-clock budget are checked before and after sleep.
8. A third failed attempt remains a final fail-closed Provider error.

### 4.3 Shared live request pacer

One `LiveRateLimiter` instance is created for the entire 45-run execution and injected into every A/C/E Provider transport.

```python
@dataclass(frozen=True)
class LiveRateLimitPolicy:
    minimum_attempt_interval_seconds: float
    inter_run_cooldown_seconds: float
    retry_after_min_seconds: float
    retry_after_max_seconds: float
    fallback_429_delays: tuple[float, float]


class LiveRateLimiter:
    def wait_before_attempt(self, *, cancellation: object | None = None) -> float: ...
    def wait_after_completed_run(self, *, cancellation: object | None = None) -> float: ...
    def resolve_retry_delay(
        self,
        attempt_index: int,
        response: TransportResponse,
        now_epoch_seconds: float,
    ) -> float: ...
```

Approved initial policy:

```text
minimum_attempt_interval_seconds=1
inter_run_cooldown_seconds=10
retry_after_min_seconds=1
retry_after_max_seconds=120
fallback_429_delays=(30, 60)
```

Ordering before every physical send:

```text
shared limiter wait
-> wall-clock check
-> reserve provider attempt
-> transport send
```

The wait itself must not consume a Provider attempt.

After every successfully finalized run, all strategies receive the same 10-second cooldown. No strategy-specific pacing is permitted.

### 4.4 Budget amendment

The current `330` physical-attempt ceiling cannot support retry.

For the next newly approved full run:

```text
logical-call schedule ceiling: 330
physical provider-attempt ceiling: 660
per-logical-call max attempts: 3
input token budget: 1,000,000
output token budget: 500,000
wall-clock budget: 5,400 seconds
consecutive infrastructure failure threshold: 2
gateway final-failure threshold: 2
```

`660` provides aggregate headroom for one additional physical attempt per worst-case logical call while preserving a strict global cap. It does not authorize unlimited retries.

Changing `330 -> 660` and `3600 -> 5400` requires a new explicit operator approval. The previous M7-E.23 approval is consumed and cannot authorize these values.

### 4.5 Durable provider-failure audit

Before active-run rollback removes staged artifacts, write one exclusive-create canonical audit file:

```text
results/raw/diagnostics/{experiment_id}/{run_id}/provider_failure.json
```

Allowed fields:

```python
@dataclass(frozen=True)
class ProviderFailureDiagnostic:
    diagnostic_version: str
    experiment_id: str
    run_id: str
    task_id: str
    strategy: str
    provider_id: str
    model: str
    error_class: str
    sanitized_error_code: str
    final_http_status: int | None
    attempt_count: int
    attempt_records: tuple[ProviderAttemptRecord, ...]
    allowlisted_rate_limit_headers: tuple[tuple[str, str], ...]
    elapsed_seconds: float
```

Rules:

- canonical UTF-8 JSON, sorted keys, compact separators, one trailing LF;
- exclusive-create, never overwrite;
- no raw prompt, raw response body, Authorization, credential, absolute path, traceback, hidden-test path, or reference-patch path;
- a diagnostic write failure must not leak details to stdout/stderr;
- diagnostic integrity failure still aborts execution.

### 4.6 Dataset and rerun policy

- Do not resume `m7e_full_20260612T040000Z`.
- Do not generate derived outputs from its 15-record partial dataset.
- M7-E.23 raw JSONL SHA-256 remains frozen:

```text
fa06ca6cbd216d8e63f2aa2300334fa4b49c673e21a77591b790d32b6426b03d
```

- A future execution requires:
  1. M7-E.25 offline TDD implementation;
  2. M7-E.26 new-ID preflight;
  3. a new canonical experiment ID;
  4. exact operator approval for the amended budgets.

## 5. M7-E.25 TDD Scope

M7-E.25 must add offline tests for:

1. real `urllib.error.HTTPError(429)` becomes a bounded status response;
2. `401/403` remain authentication failures;
3. HTTP error bodies still obey the 10 MB limit;
4. `Retry-After` is allowlisted case-insensitively;
5. delta-seconds parsing;
6. HTTP-date parsing;
7. malformed or negative `Retry-After` fallback;
8. delay clamping at 1 and 120 seconds;
9. absent-header fallback delays `30/60`;
10. `502/503/504` retain fixed `0.25/0.50`;
11. default non-live Provider behavior remains unchanged;
12. one shared limiter is used by all A/C/E providers;
13. limiter wait occurs before attempt reservation;
14. waiting does not increment attempt count;
15. every retry send reserves exactly one attempt;
16. attempt 661 fails before sender execution;
17. the 10-second inter-run cooldown applies equally to A/C/E;
18. wall-clock and cancellation checks surround waits;
19. final 429 still aborts and writes no completed result record;
20. canonical provider-failure diagnostic contains complete sanitized attempts;
21. diagnostics reject secrets, absolute paths, hidden-test paths, and raw bodies;
22. diagnostic exclusive-create and failure behavior;
23. frozen M7-D and M7-E hashes remain unchanged;
24. no live socket or credential access occurs in tests.

## 6. Stop Point

M7-E.24 ends here.

Do not implement, preflight, or execute another live run until M7-E.25 is separately started.


# Milestone 7-E.4: Reviewer Envelope Hardening Plan

## 1. Problem Statement

During the execution of **Milestone 7-E.3 (Real Full-Run)**, the 45-run live experiment triggered a **Controlled Abort (Fail-Closed)** during its 8th run (`m7e_full_20260611T210000Z__T01__E__rep02__seed42`) due to `StrategyResponseError: Reviewer envelope is invalid`.

### Challenges and Vulnerabilities in Live Environments:
1. **Response Format Volatility:** While local dry-runs and smoke tests (using fakes/mocks) consistently output exact JSON schemas, real-world LLMs (such as `google/gemini-3.5-flash` under specific prompt contexts or token bounds) exhibit styling variability.
2. **Parser Strictness:** The existing production parser expects the Reviewer's JSON response envelope to contain *exactly* the keys `{"verdict", "issues"}` with absolutely no extra text, leading characters, or additional keys.
3. **Common Deviation Patterns:**
   - **Markdown Code Fences:** Models frequently wrap JSON objects in markdown blocks (e.g., ` ```json ... ``` `).
   - **Extra Meta-Keys:** Models inject reasoning traces or explanations into keys like `"thoughts"`, `"explanation"`, `"rationale"`, or `"reasoning"`.
   - **Casing and Formatting:** Values of `verdict` may appear in lowercase or mixed case (e.g., `"pass"`, `"Fail"`).
   - **Conversational Text wrappers:** "Here is the JSON output you requested..." before/after the JSON payload.
   - **Syntactic Invalidity:** Empty responses or broken JSON brackets due to context window/token truncation.
4. **Diagnostic Blank Spots:** The fail-closed mechanism is correct for protecting dataset purity, but because aborted runs do not finalize their artifact directory, the **failed raw response is discarded** rather than logged. This leaves a diagnostic blank spot where operators cannot easily analyze the exact root cause of the failure.

---

## 2. Scope Boundaries

To prevent any pollution or compromise of current code and dataset integrity, we enforce **strict scope boundaries** for this planning stage:
- **No Execution / Rerun / Resume:** No active model or gateway calls are made. No live run resumes.
- **No Code/Implementation Changes:** Production code (`parser.py`, `prompt.py`, `strategy.py`, etc.) is NOT modified. This round is **strictly for architectural design, analysis, and planning**.
- **No Dataset Modification:** Existing raw results, JSONL, artifacts, retrieval logs, and frozen smoke outputs of M7-D/M7-E.3 are kept **entirely read-only and immutable**.
- **No Hidden Test Access:** Hidden test files remain completely uninspected and isolated.

---

## 3. Design Options Comparison

To address these vulnerabilities, we analyze five design options:

### Option A: Keep strict parser unchanged, only strengthen reviewer prompt
- **Description:** Leave parser code as is. Revise and heavily weight prompt guidelines demanding exact JSON format.
- **Leakage Risk:** **Low** (No changes to tools/parsers).
- **Fairness Risk:** **Low** (No change in evaluator/parser rules).
- **Parser Complexity:** **None** (0 lines of code changed).
- **Live Robustness:** **Low** (Prompt steering is not 100% reliable for raw API outputs).
- **Auditability:** **Low** (Still discards failed raw responses; no diagnostic trace).
- **Strategy Compatibility:** **High** (Perfect compatibility).
- **New Experiment ID Required:** Yes, if re-run.

### Option B: Add safe fenced-JSON extraction, but still reject extra keys
- **Description:** Add regex/parser extraction to strip ` ```json ` and ` ``` ` fences. If extracted content is valid JSON, check keys. Reject extra keys.
- **Leakage Risk:** **Low** (Only strips markdown format markers; does not affect text data).
- **Fairness Risk:** **Low** (Only normalizes markdown syntax, does not change evaluation semantic).
- **Parser Complexity:** **Low** (Minimal regex utility added to parsing utility).
- **Live Robustness:** **Medium** (Robust against formatting wrappers, but still fails if model adds keys).
- **Auditability:** **Low** (Still no failed response logs).
- **Strategy Compatibility:** **High** (Keeps strategy contract key integrity).
- **New Experiment ID Required:** Yes, if used.

### Option C: Accept extra keys by filtering to verdict/issues
- **Description:** Parse whatever JSON dictionary is returned. Extract `verdict` and `issues`, discarding any other keys like `thoughts` or `explanation`.
- **Leakage Risk:** **Medium** (If the extra keys contain information that could bypass future checks, though very minor).
- **Fairness Risk:** **High** (Accepting models that write explanations in extra fields relaxes the constraint, potentially altering strategy evaluation behavior compared to strict runs).
- **Parser Complexity:** **Medium** (Requires filtering of dictionary keys).
- **Live Robustness:** **High** (Accepts extra fields without throwing exceptions).
- **Auditability:** **Low** (Still lacks diagnostic logging of failed runs).
- **Strategy Compatibility:** **Medium** (Might break strict assertion expectations in older M5 strategy tests that enforce zero extra fields).
- **New Experiment ID Required:** Yes, if used.

### Option D: Add durable abort diagnostic logging for active failed run responses
- **Description:** Implement a diagnostic logger. If a run fails validation, write the raw model response, run ID, and exception traceback to a dedicated non-strategy-visible directory (`results/raw/diagnostics/`).
- **Leakage Risk:** **Low** (Completely isolated directory; inaccessible to retrieval, evaluator, and strategies).
- **Fairness Risk:** **None** (Does not affect execution parameters).
- **Parser Complexity:** **Medium** (Exception handling logic in the orchestrator is updated).
- **Live Robustness:** **Low** (Does not fix formatting errors; just records them).
- **Auditability:** **Extremely High** (Provides exact evidence of failures).
- **Strategy Compatibility:** **High** (No impact on strategy execution).
- **New Experiment ID Required:** No (can be added safely as a pure observability feature).

### Option E: Combine prompt hardening + fenced extraction + durable abort log (Recommended)
- **Description:** Apply a multi-layered approach: harden prompt, implement fenced-JSON extraction (while strictly rejecting extra keys to maintain key fairness), normalize verdict casing (e.g. `"pass"` to `"PASS"`), and write durable abort diagnostic logs.
- **Leakage/Fairness Risk:** **Low/None** (Rejects extra keys, maintains strict evaluation, completely isolates diagnostic logs).
- **Parser Complexity:** **Medium** (Standard modular regex extractor + casing helper).
- **Live Robustness:** **Extremely High** (Protects against formatting and casing variance while upholding strict logical rules).
- **Auditability:** **Extremely High** (Maintains a durable diagnostic audit log).
- **Strategy Compatibility:** **High** (Strict contract of `{"verdict", "issues"}` is fully preserved).
- **New Experiment ID Required:** Yes.

---

## 4. Architectural Recommendation

We recommend implementing **Option E** as the optimal path forward:

1. **Prompt Hardening:** Modify the Reviewer system prompt to instruct the model to produce *strictly and only* a JSON object, explicitly forbidding introduction text, markdown fences, and auxiliary keys.
2. **Safe Parser Hardening:**
   - Implement `extract_fenced_json(text: str) -> str` to safely strip markdown code fences. It must fail if there is text before or after the fenced block, or if multiple JSON blocks are found.
   - Accept the JSON object only if it maps *exactly* to the keys `{"verdict", "issues"}` with **zero extra keys allowed**. This preserves the fairness and parity of Strategy A, C, and E.
   - Normalize string case for the verdict (e.g. converting `"pass"` -> `"PASS"`, `"fail"` -> `"FAIL"` case-insensitively).
3. **Durable Abort Diagnostic Logging:**
   - Create `results/raw/diagnostics/{experiment_id}/{run_id}/`.
   - If `StrategyResponseError` or other parser exceptions occur, dump the raw response content, hash, role, exception type, and timestamp with exclusive-create (`x` mode) semantics.
   - **Isolation Guarantee:** Ensure this directory is strictly blocked from strategies, retrieval corpus, and evaluator input directories.
4. **Experiment Isolation Rule:**
   - **M7-E.3 partial results remain 100% frozen and untouched.**
   - Future final runs must discard the aborted `m7e_full_20260611T210000Z` ID and assign a **brand new experiment ID**, initiating a full 45-run pipeline from scratch to guarantee statistical fairness, completeness, and cleanliness of the final dataset.

---

## 5. Acceptance Criteria for Future M7-E.5 Implementation

When M7-E.5 (Implementation) is activated, the hardened code must satisfy these exact criteria:

### Reviewer Parser Requirements

| Case | Input Text | Expected Action | Resulting Object |
| :--- | :--- | :--- | :--- |
| **A** | `{"verdict":"PASS","issues":[]}` | Accept directly | `{"verdict":"PASS","issues":[]}` |
| **B** | ` ```json\n{"verdict":"PASS","issues":[]}\n``` ` | Extract & Accept | `{"verdict":"PASS","issues":[]}` |
| **C** | `{"verdict":"pass","issues":[]}` | Normalize case | `{"verdict":"PASS","issues":[]}` |
| **D** | `{"verdict":"PASS","issues":[],"thoughts":"looks good"}` | **Reject** (Extra keys) | Raises `StrategyResponseError` |
| **E** | `Here is the JSON:\n{"verdict":"PASS","issues":[]}` | **Reject** (Text before object) | Raises `StrategyResponseError` |
| **F** | `{"verdict":"PASS","issues":[]}\nSome other text` | **Reject** (Text after object) | Raises `StrategyResponseError` |
| **G** | `{"issues":[]}` | **Reject** (Missing verdict) | Raises `StrategyResponseError` |
| **H** | `{"verdict":"PASS"}` | **Reject** (Missing issues) | Raises `StrategyResponseError` |
| **I** | `{"verdict":"PASS","issues":"none"}` | **Reject** (Issues is not a list) | Raises `StrategyResponseError` |
| **J** | `{"verdict":"MAYBE","issues":[]}` | **Reject** (Invalid verdict value) | Raises `StrategyResponseError` |
| **K** | `{"verdict":"PASS","issues":[]} {"verdict":"FAIL"}` | **Reject** (Multiple JSON structures) | Raises `StrategyResponseError` |
| **L** | `""` or `null` | **Reject** (Empty response) | Raises `StrategyResponseError` |

### Durable Abort Diagnostic Log Requirements

1. **Trigger Condition:** Written **only** on run-level validation/parser exceptions during live experiments.
2. **Access Security:** Written to `results/raw/diagnostics/{experiment_id}/{run_id}/raw_response.json` (or similar). It must be **100% invisible** to strategies, retrieval corpora, prompts, and evaluation workspaces.
3. **Written Payload:** Must contain:
   - `run_id` and role (`reviewer`).
   - Raw response content (verbatim).
   - SHA-256 hash of the raw response.
   - Captured exception type and message.
   - Timestamp.
4. **Leakage Safeguards:** Must **never** include hidden test suites, grading keys, or reference gold standard patches in the diagnostic logs.
5. **Write Mode:** Must use exclusive-create mode (`x` or similar) to prevent overwriting existing diagnostic logs in multi-run scenarios.

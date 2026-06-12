# M4 Allowed Corpus Retrieval Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline, deterministic, task-scoped retrieval layer that only Strategy E can use and that never indexes hidden tests, reference patches, workspaces, results, prior run artifacts, model outputs, repaired code, or evaluator-only evidence.

**Architecture:** M4 adds a new `experiments/retrieval/` package behind a fail-closed `RetrievalFacade`. A per-task frozen corpus is built from `experiments/tasks.json.allowed_corpus` and immutable `student_system/SNAPSHOT.json` contents, then exposed through `keyword_search`, deterministic TF-IDF cosine `semantic_search`, and strict `chunk_read`. Every tool call writes an append-only record conforming to `contracts/retrieval-log.schema.json`.

**Tech Stack:** Python 3.11 standard library, existing `jsonschema` dependency, existing `experiments.runtime.guards.SecurityGuards`, pytest. No network, model API, embedding API, Hermes, OpenAI-Compatible AI, downloaded model, or new runtime dependency.

---

## 0. Scope Guard

This document is the M4 design and implementation plan only. It does not implement M4 feature code.

Allowed files for this planning round:

- `docs/superpowers/plans/2026-06-11-m4-retrieval-layer.md`
- `docs/milestones/M4_acceptance.md`

Files planned for later M4 implementation:

- Create: `experiments/retrieval/__init__.py`
- Create: `experiments/retrieval/models.py`
- Create: `experiments/retrieval/guards.py`
- Create: `experiments/retrieval/corpus.py`
- Create: `experiments/retrieval/chunking.py`
- Create: `experiments/retrieval/keyword.py`
- Create: `experiments/retrieval/semantic.py`
- Create: `experiments/retrieval/logging.py`
- Create: `experiments/retrieval/service.py`
- Create: `tests/retrieval/conftest.py`
- Create: `tests/retrieval/test_corpus_builder.py`
- Create: `tests/retrieval/test_chunking.py`
- Create: `tests/retrieval/test_keyword_search.py`
- Create: `tests/retrieval/test_semantic_search.py`
- Create: `tests/retrieval/test_chunk_read.py`
- Create: `tests/retrieval/test_retrieval_logging.py`
- Create: `tests/retrieval/test_retrieval_permissions.py`
- Create: `tests/leakage/test_retrieval_leakage.py`

Files that must not be modified in M4 unless a true contract blocker is first documented:

- `contracts/*.schema.json`
- `experiments/tasks.json`
- M1-M3 runtime, evaluator, schema, and task fixtures
- `student_system/SNAPSHOT.json`
- hidden tests and reference patches

## 1. Repository Findings From Required Reading

Actually inspected files:

- `README.md`
- `pyproject.toml`
- `docs/experiment-contract.md`
- `docs/superpowers/specs/2026-06-10-arag-multi-agent-mvp-design.md`
- `docs/superpowers/plans/2026-06-11-m3-runtime-evaluator.md`
- `docs/milestones/M3_acceptance.md`
- `contracts/task.schema.json`
- `contracts/retrieval-log.schema.json`
- `contracts/result.schema.json`
- `experiments/tasks.json`
- `experiments/runtime/guards.py`
- `experiments/runtime/workspace.py`
- `tests/leakage/test_leakage_prevent.py`
- `tests/contracts/test_retrieval_log_schema.py`
- `student_system/SNAPSHOT.json`
- Repository listing via `rg --files`

Additional current-state checks:

- `AGENTS.md` is not present at repository root. The active AGENTS instructions are the user-provided message for `C:\上課檔案\報告\A-RAG_Multi-Agent`.
- `experiments/retrieval/` is missing.
- `tests/retrieval/` is missing.
- The directory is not currently a git repository, so implementation workers should not require commits unless the workspace is later initialized or attached to git.
- M3 acceptance records two full runs of `102 passed`, but M4 workers must re-run current regression tests after implementation instead of assuming that old result is still current.

## 2. Recommended M4 Architecture

### Module Boundaries

`experiments/retrieval/models.py`

- Owns dataclasses, enums, error classes, and typed return objects.
- Contains no filesystem traversal or scoring logic.

`experiments/retrieval/guards.py`

- Owns retrieval-specific denylist checks and Strategy permission checks.
- Reuses `experiments.runtime.guards.SecurityGuards.assert_safe_path` for resolved path containment.
- Fails closed for Strategy A/C, unknown roles, unsafe corpus paths, symlink/junction escapes, sibling-prefix escapes, sensitive roots, and cache/artifact paths.

`experiments/retrieval/corpus.py`

- Builds a `FrozenCorpus` for one `RetrievalTaskSpec` from `allowed_corpus`.
- Reads content only from repo-root-relative paths that are both present in `allowed_corpus` and present in `student_system/SNAPSHOT.json`, except public tests may be included only when explicitly listed and snapshot-tracked.
- Does not read from run workspaces.
- Does not read patched files.
- Does not accept a full task dictionary or evaluator-only fields.
- Verifies each raw file byte hash against `SNAPSHOT.json` before UTF-8 decoding or LF normalization.

`experiments/retrieval/chunking.py`

- Converts frozen UTF-8 text into deterministic chunks.
- Provides file/content hash helpers and stable chunk IDs.

`experiments/retrieval/keyword.py`

- Builds an immutable `KeywordIndex` from `FrozenCorpus`.
- Provides deterministic lexical search over chunk text and path metadata.
- Uses token frequency scoring plus exact phrase/path boosts.

`experiments/retrieval/semantic.py`

- Builds an immutable `SemanticIndex` from `FrozenCorpus`.
- Provides deterministic offline TF-IDF cosine similarity.
- It is semantic-like lexical vector search, not neural embedding search.

`experiments/retrieval/logging.py`

- Builds schema-valid retrieval log dicts.
- Validates with `contracts/retrieval-log.schema.json`.
- Owns append-only JSONL writing.
- Sanitizes paths and excerpts before validation and write.
- Does not log invalid calls, permission denials, path escapes, corpus build failures, or unknown chunk/file errors because the current schema has no error/status fields.
- Applies log output allowlist rules independent from corpus source denylist rules.

`experiments/retrieval/service.py`

- Owns `RetrievalFacade` and `RetrievalSession`.
- `RetrievalFacade.build_store(...)` creates a frozen, role-independent retrieval store containing corpus and indexes.
- `RetrievalFacade.create_session(...)` creates a role-bound view over an existing frozen store.
- Exposes the three public tools and enforces permissions before all operations.
- Records successful calls and valid empty-result calls only.

### Data Flow

1. Runtime loads full task metadata outside the retrieval layer.
2. Runtime constructs `RetrievalTaskSpec(task_id=..., allowed_corpus=...)` outside the retrieval layer.
3. Strategy E calls `RetrievalFacade.build_store(spec, repo_root)` once per run/task.
4. Strategy A/C attempts to build, create, or call retrieval fail closed.
5. `CorpusBuilder` resolves each `allowed_corpus` path against repo root.
6. Guards verify repo-root-relative syntax, deterministic denylist exclusion, real resolved containment, and snapshot membership.
7. Builder reads immutable starter snapshot file bytes from repo root, verifies raw SHA-256 against `SNAPSHOT.json`, then decodes and normalizes.
8. Chunker normalizes and chunks content deterministically.
9. Keyword and semantic indexes are built once into `FrozenRetrievalStore`; `FrozenCorpus`, `KeywordIndex`, `SemanticIndex`, and `FrozenRetrievalStore` store no repo root, workspace path, file handle, or callback that can reread files.
10. Planner/Coder/Reviewer each create a role-bound `RetrievalSession` over the same `FrozenRetrievalStore` instance.
11. Valid retrieval calls emit schema-valid log records; invalid calls raise and do not write retrieval logs.
12. Repair rounds reuse the same `FrozenRetrievalStore` and must not rebuild indexes or read the filesystem.

## 3. Semantic Search Options

### Option A: Pure Standard-Library TF-IDF Cosine (Recommended for M4 MVP)

Mechanism:

- Tokenize query and chunk text with the same deterministic regex.
- Build per-chunk term frequencies.
- Compute IDF as `log((1 + n_docs) / (1 + df)) + 1`.
- Build TF-IDF vectors.
- Score by cosine similarity.
- Tie-break deterministically by file path, chunk index, then chunk ID.

Benefits:

- Offline, deterministic, Windows-friendly, no API key, no model download.
- Uses no network and cannot bias Strategy E with provider-side knowledge.
- Easy to inspect and test.
- Keeps M4 focused on retrieval safety instead of provider integration.

Limitations:

- This is lexical vector search, not neural semantic embedding.
- It will match conceptually related words only when vocabulary overlaps or code/docs share related identifiers.
- It should be described as deterministic TF-IDF/cosine semantic_search, not as true embedding search.

### Option B: New Local Embedding Dependency

Mechanism:

- Add a local embedding library and model package.
- Build chunk embeddings locally.

Benefits:

- Better natural-language semantic matching if the model exists locally.

Risks:

- Adds dependency and platform variance.
- May require model download or nontrivial installation.
- Harder to make deterministic across machines.
- Could change Strategy E fairness by adding external pretrained model knowledge beyond the controlled LLM.

### Option C: External Embedding Provider

Mechanism:

- Call a provider API to embed queries and chunks.

Benefits:

- Strong semantic retrieval quality.

Risks:

- Violates M4 no-network/no-model-provider constraint.
- Requires API keys and provider latency.
- Introduces nondeterminism, cost, and fairness concerns.
- Risks leaking allowed corpus text to an external service.

Recommendation:

- Use Option A for M4 MVP.
- Document the limitation in code and docs.
- Leave neural/local/provider embeddings as future M6+ research variants only after fairness and leakage contracts are amended.

## 4. Public Interfaces, Dataclasses, and Errors

### Enums and Dataclasses

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Strategy = Literal["A", "C", "E"]
AgentRole = Literal["Planner", "Coder", "Reviewer"]
ToolName = Literal["keyword_search", "semantic_search", "chunk_read"]

@dataclass(frozen=True)
class RetrievalTaskSpec:
    task_id: str
    allowed_corpus: tuple[str, ...]

@dataclass(frozen=True)
class CorpusFile:
    file_path: str
    snapshot_sha256: str
    normalized_sha256: str
    text: str
    byte_length: int
    line_count: int

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    file_path: str
    chunk_index: int
    start_line: int
    end_line: int
    text: str
    sha256: str
    token_count: int

@dataclass(frozen=True)
class FrozenCorpus:
    task_id: str
    snapshot_id: str
    files: tuple[CorpusFile, ...]
    chunks: tuple[Chunk, ...]
    corpus_hash: str

@dataclass(frozen=True)
class KeywordPosting:
    term: str
    chunk_id: str
    count: int

@dataclass(frozen=True)
class KeywordIndex:
    corpus_hash: str
    postings: tuple[KeywordPosting, ...]
    chunk_token_counts: tuple[tuple[str, int], ...]

@dataclass(frozen=True)
class SemanticDocumentVector:
    chunk_id: str
    weights: tuple[tuple[str, float], ...]
    norm: float

@dataclass(frozen=True)
class SemanticIndex:
    corpus_hash: str
    idf: tuple[tuple[str, float], ...]
    document_vectors: tuple[SemanticDocumentVector, ...]

@dataclass(frozen=True)
class FrozenRetrievalStore:
    corpus: FrozenCorpus
    keyword_index: KeywordIndex
    semantic_index: SemanticIndex

@dataclass(frozen=True)
class SearchHit:
    file_path: str
    chunk_id: str
    score: float
    rank: int
    excerpt: str
    content_hash: str
    token_count: int

@dataclass(frozen=True)
class SearchResult:
    tool_name: ToolName
    query: str
    hits: tuple[SearchHit, ...]
    returned_files: tuple[str, ...]
    returned_chunk_ids: tuple[str, ...]
    content_hash: str
    excerpt: str
    token_count: int

@dataclass(frozen=True)
class ChunkReadResult:
    tool_name: Literal["chunk_read"]
    query: str
    file_path: str
    chunk_id: str
    text: str
    content_hash: str
    excerpt: str
    token_count: int

@dataclass(frozen=True)
class RetrievalLogRecord:
    run_id: str
    task_id: str
    strategy: Strategy
    agent_role: AgentRole
    tool_name: ToolName
    query: str
    returned_files: tuple[str, ...]
    returned_chunk_ids: tuple[str, ...]
    content_hash: str
    excerpt: str
    timestamp: str
    token_count: int

@dataclass(frozen=True)
class RetrievalLogWriter:
    approved_log_root: Path
    log_file_path: Path
```

### Errors

```python
class RetrievalError(Exception): pass
class RetrievalPermissionError(RetrievalError): pass
class CorpusNotBuiltError(RetrievalError): pass
class CorpusPathError(RetrievalError): pass
class SnapshotIntegrityError(CorpusPathError): pass
class DenylistedCorpusError(CorpusPathError): pass
class CorpusDecodeError(CorpusPathError): pass
class RetrievalInputError(RetrievalError): pass
class SensitiveQueryError(RetrievalInputError): pass
class UnknownFileError(RetrievalInputError): pass
class UnknownChunkError(RetrievalInputError): pass
class ChunkFileMismatchError(RetrievalInputError): pass
class RetrievalLogValidationError(RetrievalError): pass
class RetrievalLogWriteError(RetrievalError): pass
```

### Facade Signatures

```python
class RetrievalFacade:
    def build_store(
        self,
        *,
        spec: RetrievalTaskSpec,
        repo_root: Path,
        strategy: Strategy,
    ) -> FrozenRetrievalStore:
        ...

    def create_session(
        self,
        *,
        run_id: str,
        strategy: Strategy,
        agent_role: AgentRole,
        store: FrozenRetrievalStore,
        log_writer: RetrievalLogWriter | None = None,
    ) -> "RetrievalSession":
        ...

class RetrievalSession:
    def keyword_search(self, query: str, top_k: int) -> SearchResult:
        ...

    def semantic_search(self, query: str, top_k: int) -> SearchResult:
        ...

    def chunk_read(self, file_path: str, chunk_id: str) -> ChunkReadResult:
        ...
```

Validation behavior:

- Empty or whitespace-only `query`: raise `RetrievalInputError` and do not write a retrieval log.
- Query containing an absolute path, hidden-test path, reference-patch path, workspace path, result path, or deterministic denylisted path: raise `SensitiveQueryError` and do not write a retrieval log.
- `bool` passed as `top_k`: raise `RetrievalInputError` because `bool` is a subclass of `int`.
- `top_k <= 0`: raise `RetrievalInputError`.
- `top_k > 20`: raise `RetrievalInputError`; M4 caps returned chunks at 20.
- Unknown `file_path`: raise `UnknownFileError`.
- Unknown `chunk_id`: raise `UnknownChunkError`.
- Known `chunk_id` with different `file_path`: raise `ChunkFileMismatchError`.
- Strategy A/C store build, session creation, or calls: raise `RetrievalPermissionError`.
- Symlink/junction escape: raise `CorpusPathError` or `DenylistedCorpusError`.
- Corpus not built: raise `CorpusNotBuiltError`.
- Snapshot raw hash mismatch: raise `SnapshotIntegrityError` and do not return a partial corpus, partial store, partial index, or retrieval log.
- Store build failure: raise the specific `RetrievalError` subtype and do not write a retrieval log.
- No search results for a valid non-sensitive query: return `SearchResult(hits=())` and write a valid log with empty returned arrays, empty excerpt, zero token_count, and empty-content SHA-256.

`RetrievalTaskSpec` must be created outside the retrieval layer. Retrieval production code, retrieval dataclasses, retrieval function parameters, and retrieval test fixtures must not accept or store a full task dictionary. Tests must include a full upstream task containing a secret sentinel and then prove that, after external conversion to `RetrievalTaskSpec`, the sentinel cannot be found in retrieval objects, logs, indexes, chunks, or search results.

## 5. Corpus Rules

### Source of Truth

- Corpus can only come from `RetrievalTaskSpec.allowed_corpus`.
- Every path must be repo-root-relative, use normalized POSIX-style `/`, and must not be absolute.
- Every included path must resolve under the repo root.
- Every included path must resolve under an approved source root, normally `student_system/`.
- Every included path must be present in `student_system/SNAPSHOT.json`.
- Public tests may be indexed only when explicitly listed in `allowed_corpus` and present in `SNAPSHOT.json`.
- Evaluator-only fields must not be passed to corpus building, query generation, ranking, reranking, logging, or agent prompts.
- Snapshot membership is not sufficient. Before indexing each file, the builder must read raw bytes, compute `snapshot_sha256`, compare it to the expected `SNAPSHOT.json` hash, and fail closed on mismatch before decoding or normalization.
- A hash mismatch must leave no `FrozenCorpus`, no `FrozenRetrievalStore`, no partial keyword index, no partial semantic index, no chunk store, and no retrieval log.

### Store and Index Lifecycle

- `FrozenCorpus` owns only immutable corpus files, chunks, and `corpus_hash`.
- `KeywordIndex` and `SemanticIndex` are derived immutable structures and live in `FrozenRetrievalStore`.
- `FrozenRetrievalStore` owns exactly one `FrozenCorpus`, one `KeywordIndex`, and one `SemanticIndex`.
- Corpus, keyword index, and semantic index are each built once per run/task.
- Planner, Coder, and Reviewer sessions must share the same `FrozenRetrievalStore` instance.
- Repair rounds must not rebuild corpus or indexes.
- `corpus_hash` is calculated only from canonical corpus file entries and does not include derived index contents.
- Indexes must be deterministically rebuildable from `FrozenCorpus`, but formal run execution must reuse the already-built store rather than rebuilding.
- All store/index dataclasses must be frozen and contain only immutable tuples/frozen dataclasses.
- Store/index objects must not contain `Path`, repo root, workspace path, log path, open handles, callbacks, lazy loaders, or any object capable of filesystem reads.

### Denylist

This denylist is the corpus source policy only. It decides what may be read and indexed as corpus. It is independent from the log output allowlist.

Path normalization for denylist:

- Convert the repo-relative path to POSIX components.
- Reject absolute paths and any `..` component before resolving.
- Compare components with Windows-safe `casefold()`.
- Resolve the final path and reject resolved escape, symlink escape, junction escape, and sibling-prefix escape.

Deny if normalized components equal the following root/prefixes:

- `evaluation/hidden_tests`
- `evaluation/reference_patches`
- `results`
- `workspaces`
- `.git`

Deny if any single component casefolds to:

- `__pycache__`
- `.pytest_cache`
- `cache`
- `caches`
- `index`
- `indexes`
- `artifact`
- `artifacts`
- `summary`
- `summaries`

Deny if the suffix casefolds to:

- `.pyc`
- `.pyo`

Do not reject a path merely because a normal filename contains substrings such as `result`, `run`, or `workspace`. If `student_system/src/result_formatter.py` or `student_system/docs/runtime_notes.md` are both in `allowed_corpus` and `SNAPSHOT.json`, they must not be denied only because of those substrings.

### Sensitive Query Detection

M4 must not reject natural-language queries merely because they contain words such as `result`, `results`, `workspace`, or `run`. Sensitive query checks apply only to path-like candidates extracted from the query.

Path-like candidates include:

- Windows absolute path candidates such as `C:\repo\file.py` or `C:/repo/file.py`.
- POSIX absolute path candidates such as `/repo/file.py`.
- Relative path tokens containing `/` or `\`.
- Tokens that start with an explicit denied prefix such as `evaluation/hidden_tests`, `evaluation/reference_patches`, `results`, `workspaces`, or `.git`.

For each path-like candidate:

1. Normalize slashes to `/`.
2. Casefold for Windows-safe comparison.
3. Apply the same root, component, suffix, absolute path, `..`, resolved escape, symlink/junction escape, and sibling-prefix escape rules used by corpus source policy when the candidate can be resolved.

Must reject and write no retrieval log:

- `read evaluation/hidden_tests/test_t01.py`
- `C:\repo\results\raw\data.jsonl`
- `workspaces/run_1/file.py`

Must not reject solely because of ordinary words:

- `summarize results`
- `explain runtime workspace isolation`
- `how should this function return result`
- `run validation logic`

## 6. Chunking Rules

### Reading and Normalization

- Read files as bytes from the immutable starter source.
- Compute `snapshot_sha256` over raw file bytes before decoding.
- Compare `snapshot_sha256` with the expected hash from `SNAPSHOT.json`.
- If the hash differs, raise `SnapshotIntegrityError` and abort without corpus/index/log output.
- Decode strictly as UTF-8.
- On `UnicodeDecodeError`, raise `CorpusDecodeError`; do not index replacement-character text.
- Normalize line endings to LF by replacing `\r\n` and `\r` with `\n`.
- Compute `normalized_sha256` over the normalized UTF-8 bytes.
- Preserve trailing newline for hashing after normalization.

### File Size and Empty Files

- Maximum accepted file size: 1 MiB per file for M4 MVP.
- Oversized allowed files raise `CorpusPathError` and abort corpus build fail-closed.
- Empty files produce one empty chunk with `start_line=1`, `end_line=1`, `text=""`, token_count `0`, and SHA-256 of empty bytes after normalization.

### Markdown Chunking

- Split on ATX headings (`#`, `##`, etc.) while keeping the heading with its section.
- If a section exceeds the chunk size, split by paragraph, then by line.
- Target size: 80 logical lines or 4,000 characters, whichever comes first.
- Overlap: 10 logical lines between split chunks from the same section.

### Python Chunking

- Use `ast.parse` when possible.
- Primary chunks are top-level class/function definitions and import/global blocks.
- If AST parsing fails, fall back to deterministic line chunking.
- Oversized AST chunks are split by logical lines using the same 80-line/4,000-character target and 10-line overlap.

### Generic Text Chunking

- Use deterministic line chunking with 80-line/4,000-character target and 10-line overlap.

### Chunk IDs and Ordering

- Sort input files by normalized repo-relative path.
- Preserve in-file chunk order by `chunk_index`.
- `chunk_id = "{file_path}#chunk_{chunk_index:04d}_{sha256[:12]}"`.
- `sha256` is computed over normalized chunk text encoded as UTF-8.
- Duplicate chunks are retained if they come from different locations; they keep distinct chunk IDs because file path and index differ.
- Same input must produce byte-for-byte identical chunk IDs and index ordering.

## 7. Ranking Rules

### Tokenization

- Lowercase text using `str.casefold()`.
- Token regex: `[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]+`.
- Split snake_case and dotted identifiers into additional terms while retaining the original token.
- Stopwords are not removed in M4; removing them would add another hidden tuning knob.

### Keyword Search

Score each chunk:

- `+5.0` for exact case-insensitive query substring in chunk text.
- `+3.0` for exact case-insensitive query substring in file path.
- `+2.0 * matched_unique_query_terms / total_unique_query_terms`.
- `+ term_frequency_sum / max(1, chunk_token_count)`.

Ranking:

1. Higher score.
2. Smaller `file_path` lexicographically.
3. Smaller `chunk_index`.
4. Smaller `chunk_id`.

Only positive-score chunks are returned. Empty result is valid and logged.

### Semantic Search

Score each chunk by deterministic TF-IDF cosine:

- `tf = raw_count / max(1, total_tokens_in_chunk)`.
- `idf = log((1 + total_chunks) / (1 + document_frequency)) + 1`.
- `vector[token] = tf * idf`.
- `score = dot(query_vector, chunk_vector) / (norm(query_vector) * norm(chunk_vector))`.

Ranking uses the same tie-breakers as keyword search. Only scores greater than `0.0` are returned.

## 8. Hashing, Excerpts, and Token Count

### Hash Types

- `snapshot_sha256`: SHA-256 of the raw file bytes, before UTF-8 decoding and before LF normalization. This must match `student_system/SNAPSHOT.json`.
- `normalized_sha256`: SHA-256 of the whole file after UTF-8 decoding and LF normalization, then re-encoding as UTF-8.
- Chunk `sha256`: SHA-256 of a single chunk's normalized text encoded as UTF-8.
- `content_hash`: SHA-256 of retrieved chunk text payloads, as defined below.
- `corpus_hash`: SHA-256 of the canonical corpus payload, as defined below.

### Corpus Hash

Canonical `corpus_hash` rules:

1. Sort corpus files by normalized repo-relative `file_path` ascending.
2. For each file, create a compact JSON entry with exactly these fields: `file_path`, `snapshot_sha256`, `normalized_sha256`.
3. JSON serialization uses UTF-8, `ensure_ascii=False`, `sort_keys=True`, and compact separators `(",", ":")`.
4. Join entries with LF (`\n`).
5. Do not append a trailing LF.
6. `corpus_hash = sha256(canonical_payload_bytes).hexdigest()`.
7. The payload must not include `run_id`, `agent_role`, timestamp, absolute path, repo root, workspace path, log path, or any callback identity.

Expected hash behavior:

- Rebuilding from the same approved snapshot input produces the same `corpus_hash`.
- LF and CRLF raw bytes produce different `snapshot_sha256`; if `SNAPSHOT.json` expects one but the file contains the other, corpus build fails before `corpus_hash`.
- If two approved snapshots differ only by raw newline bytes but both have matching snapshot entries, they may share `normalized_sha256` but must have different canonical entries because `snapshot_sha256` differs.
- Reordering input `allowed_corpus` does not change `corpus_hash` because canonical entries are path-sorted.
- Any file content change that changes `snapshot_sha256` or `normalized_sha256` changes `corpus_hash`, if the changed file is otherwise approved by the snapshot.

### Content Hash

- Single chunk: chunk SHA-256.
- Multiple chunks: canonical payload is the UTF-8 encoding of each returned chunk joined by `\n---CHUNK---\n` in returned rank order; `content_hash = sha256(payload).hexdigest()`.
- Empty result: SHA-256 of empty bytes, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### Excerpt

- Maximum excerpt length: 500 characters.
- Search excerpt: concatenate ranked snippets with `\n---\n`, then truncate.
- Chunk read excerpt: first 500 characters of the chunk text.
- Truncation: if longer than 500 characters, keep first 485 characters and append `\n... (truncated)`.
- `excerpt` may contain only actual retrieved content.
- `excerpt` must not contain error messages, exception names, permission denial text, hidden/reference paths, workspace paths, result paths, or absolute paths.
- If the actual retrieved content would require redaction to become safe, the retrieval call must fail closed instead of logging a modified excerpt.

### Token Count

- Deterministic count uses the same token regex as ranking.
- For search results, `token_count` is the sum of returned hit token counts.
- For chunk_read, `token_count` is the selected chunk token count.
- For empty valid search results, `token_count=0`.

## 9. Retrieval Log Rules

The schema requires:

- `run_id`
- `task_id`
- `strategy`
- `agent_role`
- `tool_name`
- `query`
- `returned_files`
- `returned_chunk_ids`
- `content_hash`
- `excerpt`
- `timestamp`
- `token_count`

Runtime rules:

- `returned_files` order is first appearance in returned rank order, deduplicated.
- `returned_chunk_ids` order is returned rank order.
- `timestamp` is UTC ISO 8601 with `Z`, e.g. `2026-06-11T12:00:00Z`.
- `chunk_read.query` serializes as compact JSON with sorted keys: `{"chunk_id":"...","file_path":"..."}`.
- Legal search with results writes a retrieval log.
- Legal search with no results writes a valid empty-result retrieval log: `returned_files=[]`, `returned_chunk_ids=[]`, empty-content hash, `excerpt=""`, `token_count=0`.
- Illegal input, empty query, sensitive query, permission denial, unknown file, unknown chunk, file/chunk mismatch, path escape, and corpus build failure raise explicit exceptions and do not write retrieval logs.
- Rejected events should use a future independent security audit schema if they need persistence. M4 does not add that schema.
- Hidden tests, reference patches, absolute paths, workspace paths, result paths, cache paths, and previous run artifacts must never appear in logs.
- Log validation failure raises `RetrievalLogValidationError` and prevents append.
- In-memory record builder returns dataclass/dict only.
- `RetrievalSession` does not accept an arbitrary `Path`; callers must inject a `RetrievalLogWriter | None`.
- Corpus source policy and log output policy are separate. `results/` is never corpus, but `results/raw/retrieval/` is the recommended formal retrieval log output root.
- `RetrievalLogWriter.__init__(approved_log_root: Path, log_file_path: Path)` validates the output location at construction.
- `approved_log_root` is supplied by the caller; the retrieval layer must not choose arbitrary output locations.
- `log_file_path` must have suffix `.jsonl`.
- `log_file_path.resolve()` must be inside `approved_log_root.resolve()` using `Path.is_relative_to`, preventing absolute escape, `..`, symlink/junction escape, and sibling-prefix escape.
- Log output files, even inside `results/`, must never be eligible as corpus.
- Append-only writer owns UTF-8 JSONL serialization, one object per line, and no truncation.
- M4 writer is single-process, single-writer only. Callers must use one independent JSONL per run.
- Append must not leave a malformed half-line JSON record. The required flow is: schema validate and JSON-serialize fully in memory; open the JSONL with one binary read/write append-capable handle; record `original_size`; seek EOF; write the complete UTF-8 JSON line plus LF; flush; `os.fsync`; on any failure, use the same handle to `truncate(original_size)`, then flush and `os.fsync` again before raising `RetrievalLogWriteError`.
- If rollback itself fails, raise `RetrievalLogWriteError` with a message or field that clearly marks `log_integrity_unknown=True`.
- Multi-process concurrency is explicitly unsupported in M4. A future lock file or OS-level file lock is required before shared JSONL writes are allowed.

## 10. Fairness and Timing

- Only Strategy E can build corpus, create a retrieval session, or call retrieval tools.
- Strategy A and C fail closed at build, session creation, and tool call boundaries.
- `agent_role` must be one of `Planner`, `Coder`, or `Reviewer` and is logged.
- `agent_role` is not stored in `FrozenCorpus`.
- Planner, Coder, and Reviewer create separate role-bound sessions/views over the same `FrozenCorpus` instance or the same `corpus_hash`.
- One run/task builds `FrozenCorpus` once. Repair rounds must reuse it and must not read the filesystem or rebuild indexes.
- After construction, `FrozenCorpus` must not retain `repo_root`, `workspace_path`, `log_path`, open file handles, lazy read callbacks, or any object capable of rereading source files.
- If repo source or workspace files are modified after corpus build, existing sessions must return unchanged results.
- M4 provides retrieval capability only. It does not implement Planner, Coder, Reviewer, prompts, model providers, or model calls.
- Evaluator-only fields must not enter retrieval APIs or ranking.
- Corpus build time should be recorded separately as `retrieval_setup_latency_seconds` in implementation-local metrics if needed, but not counted in `model_latency_seconds`.
- Tool call time may contribute to total run latency and retrieval-specific latency, not model latency.
- Existing `result.schema.json` has no retrieval setup latency field; M4 must not modify it. A future schema amendment can add it if the experiment needs persisted timing breakdowns.

## 11. TDD Implementation Sequence

### Task 1: Retrieval Models and Deterministic Guards

**Files:**

- Create: `experiments/retrieval/models.py`
- Create: `experiments/retrieval/guards.py`
- Create: `experiments/retrieval/__init__.py`
- Test: `tests/retrieval/test_retrieval_permissions.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from experiments.retrieval.guards import assert_strategy_e, is_denylisted_repo_path
from experiments.retrieval.models import RetrievalPermissionError, RetrievalTaskSpec

def test_retrieval_task_spec_contains_only_allowed_fields():
    spec = RetrievalTaskSpec(task_id="T01", allowed_corpus=("student_system/API_SPEC.md",))
    assert spec.task_id == "T01"
    assert spec.allowed_corpus == ("student_system/API_SPEC.md",)

def test_strategy_a_and_c_fail_closed_at_guard_boundary():
    for strategy in ("A", "C"):
        with pytest.raises(RetrievalPermissionError):
            assert_strategy_e(strategy)

def test_strategy_e_passes_guard_boundary():
    assert_strategy_e("E") is None

def test_denylist_is_component_based_not_substring_based():
    assert is_denylisted_repo_path("results/raw/results.jsonl")
    assert is_denylisted_repo_path("student_system/cache/API_SPEC.md")
    assert not is_denylisted_repo_path("student_system/src/result_formatter.py")
    assert not is_denylisted_repo_path("student_system/docs/runtime_notes.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

Expected: FAIL because `experiments.retrieval.models` and `experiments.retrieval.guards` do not exist.

- [ ] **Step 3: Minimal implementation**

Create the package, dataclasses, errors, `assert_strategy_e(strategy)`, and deterministic component-based denylist helpers.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

Expected: PASS for model and guard tests.

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

Expected: PASS.

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

Expected: PASS.

- [ ] **Step 7: Clean cache/temp**

Run: `Get-ChildItem -Recurse -Force -Include '__pycache__','.pytest_cache','*.pyc' | Remove-Item -Recurse -Force`

- [ ] **Step 8: Record real result**

Update `docs/milestones/M4_acceptance.md` with actual command output only after implementation.

### Task 2: Test Fixtures and External Task Spec Conversion

**Files:**

- Create: `tests/retrieval/conftest.py`
- Test: `tests/retrieval/test_retrieval_permissions.py`

- [ ] **Step 1: Write failing tests**

```python
def test_external_conversion_drops_secret_sentinel(full_task_with_secret_sentinel, retrieval_task_spec):
    sentinel = full_task_with_secret_sentinel["secret_sentinel"]
    assert sentinel not in repr(retrieval_task_spec)
    assert retrieval_task_spec.task_id == "T01"
    assert retrieval_task_spec.allowed_corpus == ("student_system/API_SPEC.md",)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

Expected: FAIL because `tests/retrieval/conftest.py` fixtures do not exist.

- [ ] **Step 3: Minimal implementation**

Create `repo_root`, `retrieval_task_spec`, `full_task_with_secret_sentinel`, `synthetic_repo_root`, `synthetic_retrieval_task_spec`, and `build_synthetic_repo` fixtures/helpers. The conversion fixture must construct `RetrievalTaskSpec` outside retrieval production code and pass only `task_id` plus `allowed_corpus`. Synthetic repo helpers must create a complete temporary `student_system/SNAPSHOT.json` and matching source files under `tmp_path`.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove `__pycache__`, `.pytest_cache`, `*.pyc`, and any retrieval index cache.

- [ ] **Step 8: Record real result**

Record actual pass/fail counts in M4 acceptance.

### Task 3: Corpus Builder, Snapshot Integrity, and Canonical Corpus Hash

**Files:**

- Create: `experiments/retrieval/corpus.py`
- Create: `experiments/retrieval/chunking.py`
- Test: `tests/retrieval/test_corpus_builder.py`
- Test: `tests/retrieval/test_chunking.py`
- Test: `tests/leakage/test_retrieval_leakage.py`

- [ ] **Step 1: Write failing tests**

```python
import json
import pytest
from experiments.retrieval.corpus import CorpusBuilder
from experiments.retrieval.chunking import chunk_file_text
from experiments.retrieval.models import DenylistedCorpusError, SnapshotIntegrityError

def test_markdown_chunk_ids_are_deterministic():
    text = "# API\n\nDetails\r\n## Usage\nCall function\n"
    a = chunk_file_text("student_system/API_SPEC.md", text)
    b = chunk_file_text("student_system/API_SPEC.md", text.replace("\r\n", "\n"))
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert all(c.file_path == "student_system/API_SPEC.md" for c in a)

def test_empty_file_produces_one_empty_chunk():
    chunks = chunk_file_text("student_system/EMPTY.md", "")
    assert len(chunks) == 1
    assert chunks[0].text == ""
    assert chunks[0].token_count == 0

def test_duplicate_chunks_are_retained_with_distinct_ids():
    left = chunk_file_text("student_system/A.md", "same\n")
    right = chunk_file_text("student_system/B.md", "same\n")
    assert left[0].sha256 == right[0].sha256
    assert left[0].chunk_id != right[0].chunk_id

def test_allowed_corpus_builds_from_snapshot(retrieval_task_spec, repo_root):
    corpus = CorpusBuilder(repo_root).build(retrieval_task_spec)
    assert corpus.task_id == "T01"
    assert {f.file_path for f in corpus.files} == set(retrieval_task_spec.allowed_corpus)

def test_snapshot_hash_mismatch_fails_closed(synthetic_repo_root, synthetic_retrieval_task_spec):
    target = synthetic_repo_root / "student_system/API_SPEC.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nMUTATED", encoding="utf-8")
    with pytest.raises(SnapshotIntegrityError):
        CorpusBuilder(synthetic_repo_root).build(synthetic_retrieval_task_spec)

def test_corpus_hash_is_stable_for_same_snapshot(synthetic_repo_root, synthetic_retrieval_task_spec):
    left = CorpusBuilder(synthetic_repo_root).build(synthetic_retrieval_task_spec)
    right = CorpusBuilder(synthetic_repo_root).build(synthetic_retrieval_task_spec)
    assert left.corpus_hash == right.corpus_hash
    assert "run_" not in left.corpus_hash

def test_denied_paths_fail_before_partial_corpus(repo_root):
    from experiments.retrieval.models import RetrievalTaskSpec
    spec = RetrievalTaskSpec("T01", ("evaluation/hidden_tests/test_t01.py",))
    with pytest.raises(DenylistedCorpusError):
        CorpusBuilder(repo_root).build(spec)

def test_lf_crlf_raw_snapshot_hash_difference_uses_synthetic_repo(tmp_path):
    lf_root = build_synthetic_repo(tmp_path / "lf", newline="\n")
    crlf_root = build_synthetic_repo(tmp_path / "crlf", newline="\r\n")
    spec = RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",))
    assert CorpusBuilder(lf_root).build(spec).corpus_hash != CorpusBuilder(crlf_root).build(spec).corpus_hash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_corpus_builder.py tests/retrieval/test_chunking.py tests/leakage/test_retrieval_leakage.py -v`

Expected: FAIL because corpus and chunking modules do not exist.

- [ ] **Step 3: Minimal implementation**

Implement snapshot loading, raw SHA-256 verification, repo-root-relative validation, deterministic denylist, UTF-8 decoding, LF normalization, canonical `corpus_hash`, Markdown/Python/generic chunking, chunk IDs, ordering, token counts, and empty-file behavior. All mutation tests must create and mutate a full synthetic repo under `tmp_path`; they must not modify, overwrite, or monkeypatch the real `student_system/SNAPSHOT.json`, real `student_system` files, or `experiments/tasks.json`.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_corpus_builder.py tests/retrieval/test_chunking.py tests/leakage/test_retrieval_leakage.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 4: Service Lifecycle and Role-Bound Sessions

**Files:**

- Create: `experiments/retrieval/service.py`
- Modify: `tests/retrieval/conftest.py`
- Test: `tests/retrieval/test_retrieval_permissions.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from experiments.retrieval.models import RetrievalPermissionError
from experiments.retrieval.service import RetrievalFacade

def test_strategy_a_and_c_fail_closed_at_build_and_create(retrieval_task_spec, repo_root):
    facade = RetrievalFacade()
    for strategy in ("A", "C"):
        with pytest.raises(RetrievalPermissionError):
            facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy=strategy)

def test_three_roles_share_same_frozen_store(retrieval_task_spec, repo_root):
    facade = RetrievalFacade()
    store = facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")
    sessions = [
        facade.create_session(run_id="run_t01", strategy="E", agent_role=role, store=store)
        for role in ("Planner", "Coder", "Reviewer")
    ]
    assert {s.store.corpus.corpus_hash for s in sessions} == {store.corpus.corpus_hash}
    assert all(s.store is store for s in sessions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

- [ ] **Step 3: Minimal implementation**

Implement `RetrievalFacade.build_store`, `RetrievalFacade.create_session`, role-bound sessions, and fail-closed Strategy A/C boundaries.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_retrieval_permissions.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 5: Keyword Search and Query Validation

**Files:**

- Create: `experiments/retrieval/keyword.py`
- Modify: `experiments/retrieval/service.py`
- Test: `tests/retrieval/test_keyword_search.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from experiments.retrieval.models import RetrievalInputError, SensitiveQueryError

def test_keyword_search_orders_exact_matches(strategy_e_session):
    result = strategy_e_session.keyword_search("calculate_pass_rate", top_k=3)
    assert result.hits
    assert result.hits[0].score >= result.hits[-1].score
    assert result.returned_chunk_ids == tuple(hit.chunk_id for hit in result.hits)

def test_keyword_search_rejects_bad_top_k(strategy_e_session):
    for bad in [True, False, 0, -1, 21]:
        with pytest.raises(RetrievalInputError):
            strategy_e_session.keyword_search("api", bad)

def test_keyword_search_rejects_sensitive_query_without_log(strategy_e_session, retrieval_log_path):
    for query in [
        "read evaluation/hidden_tests/test_t01.py",
        r"C:\repo\results\raw\data.jsonl",
        "workspaces/run_1/file.py",
    ]:
        with pytest.raises(SensitiveQueryError):
            strategy_e_session.keyword_search(query, top_k=3)
    assert not retrieval_log_path.exists() or retrieval_log_path.read_text(encoding="utf-8") == ""

def test_keyword_search_does_not_reject_natural_language_result_words(strategy_e_session):
    for query in [
        "summarize results",
        "explain runtime workspace isolation",
        "how should this function return result",
        "run validation logic",
    ]:
        strategy_e_session.keyword_search(query, top_k=3)

def test_keyword_search_valid_empty_result(strategy_e_session):
    result = strategy_e_session.keyword_search("zzzz_not_present", top_k=5)
    assert result.hits == ()
    assert result.returned_files == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_keyword_search.py -v`

- [ ] **Step 3: Minimal implementation**

Implement tokenizer, query validation, keyword scorer, ranking, top_k validation, and valid no-result behavior.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_keyword_search.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 6: Deterministic TF-IDF Semantic Search

**Files:**

- Create: `experiments/retrieval/semantic.py`
- Modify: `experiments/retrieval/service.py`
- Test: `tests/retrieval/test_semantic_search.py`

- [ ] **Step 1: Write failing tests**

```python
def test_semantic_search_is_deterministic(strategy_e_session):
    a = strategy_e_session.semantic_search("course grade lookup", top_k=5)
    b = strategy_e_session.semantic_search("course grade lookup", top_k=5)
    assert [h.chunk_id for h in a.hits] == [h.chunk_id for h in b.hits]
    assert [h.score for h in a.hits] == [h.score for h in b.hits]

def test_semantic_search_uses_same_top_k_validation(strategy_e_session):
    import pytest
    from experiments.retrieval.models import RetrievalInputError
    with pytest.raises(RetrievalInputError):
        strategy_e_session.semantic_search("anything", True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_semantic_search.py -v`

- [ ] **Step 3: Minimal implementation**

Implement TF-IDF/cosine using standard library only and same ranking tie-breakers as keyword.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_semantic_search.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 7: Strict Chunk Read

**Files:**

- Modify: `experiments/retrieval/service.py`
- Test: `tests/retrieval/test_chunk_read.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from experiments.retrieval.models import UnknownFileError, UnknownChunkError, ChunkFileMismatchError

def test_chunk_read_returns_exact_chunk(strategy_e_session):
    search = strategy_e_session.keyword_search("course", top_k=1)
    hit = search.hits[0]
    read = strategy_e_session.chunk_read(hit.file_path, hit.chunk_id)
    assert read.file_path == hit.file_path
    assert read.chunk_id == hit.chunk_id
    assert read.text

def test_chunk_read_rejects_unknown_file_and_chunk(strategy_e_session):
    with pytest.raises(UnknownFileError):
        strategy_e_session.chunk_read("student_system/NOPE.md", "x")
    with pytest.raises(UnknownChunkError):
        strategy_e_session.chunk_read("student_system/API_SPEC.md", "missing")

def test_chunk_read_rejects_file_chunk_mismatch(strategy_e_session):
    hits = strategy_e_session.keyword_search("course", top_k=2).hits
    if len(hits) >= 2 and hits[0].file_path != hits[1].file_path:
        with pytest.raises(ChunkFileMismatchError):
            strategy_e_session.chunk_read(hits[1].file_path, hits[0].chunk_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_chunk_read.py -v`

- [ ] **Step 3: Minimal implementation**

Implement file/chunk lookup maps, strict mismatch checks, and JSON query serialization for logs.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_chunk_read.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 8: Retrieval Logging and Writer Atomicity

**Files:**

- Create: `experiments/retrieval/logging.py`
- Modify: `experiments/retrieval/service.py`
- Test: `tests/retrieval/test_retrieval_logging.py`
- Test: `tests/contracts/test_retrieval_log_schema.py` may be extended only if no schema change is needed.

- [ ] **Step 1: Write failing tests**

```python
import json
from jsonschema import Draft202012Validator

def test_every_tool_call_writes_schema_valid_log(strategy_e_session, retrieval_log_path, retrieval_log_schema):
    strategy_e_session.keyword_search("course", top_k=1)
    strategy_e_session.semantic_search("course", top_k=1)
    first = strategy_e_session.keyword_search("course", top_k=1).hits[0]
    strategy_e_session.chunk_read(first.file_path, first.chunk_id)

    lines = retrieval_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3
    validator = Draft202012Validator(retrieval_log_schema)
    for line in lines:
        record = json.loads(line)
        validator.validate(record)
        serialized = json.dumps(record, ensure_ascii=False)
        assert "evaluation/hidden_tests" not in serialized
        assert "evaluation/reference_patches" not in serialized
        assert ":\\\\" not in serialized

def test_empty_result_still_logs(strategy_e_session, retrieval_log_path):
    strategy_e_session.keyword_search("zzzz_not_present", top_k=3)
    record = json.loads(retrieval_log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["returned_files"] == []
    assert record["returned_chunk_ids"] == []
    assert record["token_count"] == 0

def test_invalid_call_does_not_write_log(strategy_e_session, retrieval_log_path):
    import pytest
    from experiments.retrieval.models import RetrievalInputError
    with pytest.raises(RetrievalInputError):
        strategy_e_session.keyword_search("", top_k=3)
    assert not retrieval_log_path.exists() or retrieval_log_path.read_text(encoding="utf-8") == ""

def test_writer_failure_does_not_leave_malformed_jsonl(strategy_e_session, retrieval_log_path, retrieval_log_schema, monkeypatch):
    before = retrieval_log_path.read_bytes() if retrieval_log_path.exists() else b""
    def write_half_then_fail(handle, line_bytes):
        handle.write(line_bytes[: max(1, len(line_bytes) // 2)])
        raise OSError("disk full after partial write")
    monkeypatch.setattr("experiments.retrieval.logging._write_line_once", write_half_then_fail)
    import pytest
    from experiments.retrieval.models import RetrievalLogWriteError
    with pytest.raises(RetrievalLogWriteError):
        strategy_e_session.keyword_search("course", top_k=1)
    after = retrieval_log_path.read_bytes() if retrieval_log_path.exists() else b""
    assert after == before
    for raw_line in after.splitlines():
        record = json.loads(raw_line.decode("utf-8"))
        Draft202012Validator(retrieval_log_schema).validate(record)

def test_writer_rollback_failure_reports_integrity_unknown(strategy_e_session, retrieval_log_path, monkeypatch):
    def write_half_then_fail(handle, line_bytes):
        handle.write(line_bytes[: max(1, len(line_bytes) // 2)])
        raise OSError("disk full after partial write")
    def rollback_fails(handle, original_size):
        raise OSError("truncate failed")
    monkeypatch.setattr("experiments.retrieval.logging._write_line_once", write_half_then_fail)
    monkeypatch.setattr("experiments.retrieval.logging._rollback_to_size", rollback_fails)
    import pytest
    from experiments.retrieval.models import RetrievalLogWriteError
    with pytest.raises(RetrievalLogWriteError) as exc:
        strategy_e_session.keyword_search("course", top_k=1)
    assert "log_integrity_unknown=True" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_retrieval_logging.py tests/contracts/test_retrieval_log_schema.py -v`

- [ ] **Step 3: Minimal implementation**

Implement log builder, schema validator, UTC timestamp, content hash, excerpt truncation, safe query serialization, writer path validation, and append rollback on write failure.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_retrieval_logging.py tests/contracts/test_retrieval_log_schema.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

### Task 9: Frozen Retrieval Store Across Roles and Repair Rounds

**Files:**

- Modify: `experiments/retrieval/corpus.py`
- Modify: `experiments/retrieval/service.py`
- Test: `tests/retrieval/test_corpus_builder.py`

- [ ] **Step 1: Write failing tests**

```python
def test_frozen_corpus_ignores_patched_workspace(strategy_e_session, tmp_path):
    workspace = tmp_path / "workspace"
    target = workspace / "student_system/API_SPEC.md"
    target.parent.mkdir(parents=True)
    target.write_text("patched malicious API text", encoding="utf-8")

    result = strategy_e_session.keyword_search("patched malicious", top_k=5)
    assert result.hits == ()

def test_repair_round_does_not_read_filesystem(strategy_e_session, monkeypatch):
    import pathlib
    def fail_read(*args, **kwargs):
        raise AssertionError("repair round attempted filesystem read")
    monkeypatch.setattr(pathlib.Path, "read_bytes", fail_read)
    strategy_e_session.keyword_search("course", top_k=1)

def test_upstream_secret_sentinel_absent_from_retrieval_outputs(full_task_with_secret_sentinel, strategy_e_session, retrieval_log_path):
    sentinel = full_task_with_secret_sentinel["secret_sentinel"]
    search = strategy_e_session.keyword_search("course", top_k=1)
    combined = repr(strategy_e_session.store) + repr(search)
    if search.hits:
        read = strategy_e_session.chunk_read(search.hits[0].file_path, search.hits[0].chunk_id)
        combined += repr(read)
    if retrieval_log_path.exists():
        combined += retrieval_log_path.read_text(encoding="utf-8")
    assert sentinel not in combined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m pytest tests/retrieval/test_corpus_builder.py::test_frozen_corpus_ignores_patched_workspace -v`

- [ ] **Step 3: Minimal implementation**

Ensure sessions use only in-memory `FrozenCorpus` data after construction and do not rebuild corpus/indexes across simulated repair rounds.

- [ ] **Step 4: Run local test**

Run: `python -B -m pytest tests/retrieval/test_corpus_builder.py -v`

- [ ] **Step 5: Run leakage tests**

Run: `python -B -m pytest tests/leakage -v`

- [ ] **Step 6: Run full regression**

Run: `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v`

- [ ] **Step 7: Clean cache/temp**

Remove generated caches.

- [ ] **Step 8: Record real result**

Record actual results.

## 12. Final M4 Regression Commands

After all implementation tasks:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/retrieval -v
python -B -m pytest tests/leakage -v
python -B -m pytest tests/contracts -v
python -B -m pytest -v
```

Physical residue check:

```powershell
Get-ChildItem -Recurse -Force -Include '__pycache__','.pytest_cache','*.pyc','*.pyo' |
  Select-Object -ExpandProperty FullName
```

Expected after cleanup: no output for tracked project directories.

## 13. Known Blockers and Contract Notes

- Root `AGENTS.md` is absent. Use the user-provided AGENTS instructions for this round unless a future file appears.
- The current `result.schema.json` has no field for retrieval setup latency. M4 should keep setup latency out of `model_latency_seconds` and document it in local implementation metrics or future schema notes.
- `retrieval-log.schema.json` allows `strategy` values `A`, `C`, and `E`, but M4 runtime policy must allow only `E` retrieval records. A/C values remain schema-compatible for correlation or negative tests, not as permission to retrieve.
- The existing README still says the project is at M1. Do not update it in this round because the handoff allows only the M4 plan and acceptance docs.
- No M4 worker may use evaluator-only task fields as retrieval input, despite the upstream task records containing them.

## 14. Explicit Scope Confirmation

This planning document defines M4 only.

- No M4 feature code is created by this planning document.
- No `experiments/retrieval/` file is created in this planning round.
- No `tests/retrieval/` file is created in this planning round.
- No schema is changed.
- No `tasks.json` data is changed.
- No M5 provider, prompt, agent strategy, external model call, or real model invocation is designed beyond the retrieval capability boundary.

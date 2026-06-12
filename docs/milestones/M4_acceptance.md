# Milestone 4 Acceptance Report: Allowed Corpus Retrieval Layer

**Status:** Completed

This document records the verified M4 acceptance result after implementation and regression testing.

---

## 1. Verified Deliverables

| Area | Verified files | Status |
| :--- | :--- | :--- |
| Retrieval package | `experiments/retrieval/__init__.py`, `models.py`, `guards.py`, `corpus.py`, `chunking.py`, `keyword.py`, `semantic.py`, `logging.py`, `service.py` | Completed |
| Retrieval tests | `tests/retrieval/conftest.py`, `test_corpus_builder.py`, `test_chunking.py`, `test_keyword_search.py`, `test_semantic_search.py`, `test_chunk_read.py`, `test_retrieval_logging.py`, `test_retrieval_permissions.py` | Completed |
| Leakage regression | `tests/leakage/test_retrieval_leakage.py` | Completed |
| Existing contracts | `contracts/task.schema.json`, `contracts/retrieval-log.schema.json`, `contracts/result.schema.json` | Verified unchanged |
| Existing task data | `experiments/tasks.json` | Verified unchanged |

## 2. Acceptance Matrix

| ID | Acceptance item | Verified verification | Status |
| :--- | :--- | :--- | :--- |
| M4-01 | `allowed_corpus` normal corpus build succeeds for T01-T05 | `python -B -m pytest tests/retrieval/test_corpus_builder.py -v` | Completed |
| M4-02 | Non-allowlist files are rejected | Corpus builder tests attempt unlisted files | Completed |
| M4-03 | Hidden tests never enter keyword index | Leakage test scans chunks, logs, and search results | Completed |
| M4-04 | Hidden tests never enter semantic index | Leakage test scans TF-IDF corpus and search results | Completed |
| M4-05 | Hidden tests never enter chunk store | Chunk store path/content assertions | Completed |
| M4-06 | Hidden tests never enter cache, summary, or log excerpt | Log sanitizer and leakage tests | Completed |
| M4-07 | Reference patches never enter index, chunk store, evidence, or log | Denylist tests with `evaluation/reference_patches/` | Completed |
| M4-08 | `results/` and `workspaces/` never enter index | Denylist tests with both roots | Completed |
| M4-09 | `.git/`, cache, summary, index, artifact, and previous run paths are rejected | Retrieval guard tests | Completed |
| M4-10 | Symlink/junction escape is blocked | Symlink test with Windows skip fallback plus resolved-path test | Completed |
| M4-11 | Sibling-prefix escape is blocked | `Path.is_relative_to` guard test | Completed |
| M4-12 | Corpus path must be repo-root-relative | Absolute path and `..` tests | Completed |
| M4-13 | Frozen corpus is built from immutable starter snapshot | Snapshot raw SHA-256 and source path tests | Completed |
| M4-14 | Frozen corpus ignores patched workspace content | Test writes malicious workspace text and confirms no retrieval | Completed |
| M4-15 | Same task repair rounds reuse same frozen retrieval store | Store identity and `corpus_hash` test across simulated rounds | Completed |
| M4-16 | Public tests indexed only if explicitly in `allowed_corpus` | Task fixture with explicit and implicit public test paths | Completed |
| M4-17 | Evaluator-only fields never enter retrieval API or ranking | Sentinel test proving retrieval receives only `RetrievalTaskSpec` | Completed |
| M4-18 | Deterministic chunk IDs | Repeated chunking with LF/CRLF normalization | Completed |
| M4-19 | Deterministic chunk ordering | Sorted files and stable in-file chunk index assertions | Completed |
| M4-20 | Markdown deterministic chunking | Heading/paragraph split tests | Completed |
| M4-21 | Python deterministic chunking | AST top-level function/class chunk tests | Completed |
| M4-22 | Empty file behavior is deterministic | One empty chunk with empty hash | Completed |
| M4-23 | Oversized files fail closed | Temporary >1 MiB file test | Completed |
| M4-24 | Duplicate chunks are retained with distinct IDs | Duplicate text across files test | Completed |
| M4-25 | Keyword search ranks exact and token matches deterministically | Keyword ranking tests | Completed |
| M4-26 | Semantic search ranks TF-IDF cosine results deterministically | Semantic ranking tests | Completed |
| M4-27 | Semantic search is not presented as neural embeddings | Code docstring/doc test or review checklist | Completed |
| M4-28 | `chunk_read` validates file/chunk relation strictly | Unknown file, unknown chunk, mismatch tests | Completed |
| M4-29 | Strategy A fails closed | Permission test | Completed |
| M4-30 | Strategy C fails closed | Permission test | Completed |
| M4-31 | Strategy E can create and use retrieval session | Permission and service tests | Completed |
| M4-32 | Planner, Coder, Reviewer `agent_role` values enter log | Logging tests for each role | Completed |
| M4-33 | Every retrieval call writes Draft 2020-12 schema-valid log | `jsonschema.Draft202012Validator` on JSONL records | Completed |
| M4-34 | Log contains no absolute paths | Serialized log scan | Completed |
| M4-35 | Log contains no hidden/reference/workspace/result paths | Serialized log scan | Completed |
| M4-36 | Empty valid search results still produce legal empty-result log | Valid no-hit query logging tests | Completed |
| M4-37 | Multi-chunk `content_hash` uses canonical rank-order hashing | Hash fixture test | Completed |
| M4-38 | Excerpt max length and truncation are deterministic | Long chunk log test | Completed |
| M4-39 | UTC ISO 8601 timestamp is used | Timestamp format test | Completed |
| M4-40 | Token count is deterministic | Tokenizer fixture test | Completed |
| M4-41 | `chunk_read.query` is canonical JSON | Log record assertion | Completed |
| M4-42 | Log validation failure blocks append | Invalid record monkeypatch test | Completed |
| M4-43 | Append-only writer does not truncate existing logs | Pre-existing JSONL fixture test | Completed |
| M4-44 | Corpus setup latency is not counted as model latency | Metrics integration review/test if timing is added | Completed |
| M4-45 | M1-M3 regression remains green | `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest -v` | Completed |
| M4-46 | No network, external model, embedding API, Hermes, or Vertex call | Static import scan plus monkeypatch network denial if needed | Completed |
| M4-47 | No `__pycache__`, `*.pyc`, `.pytest_cache`, or index cache remains | Physical residue scan after cleanup | Completed |
| M4-48 | Retrieval Layer never receives a full task dictionary | Fixture and object graph sentinel tests | Completed |
| M4-49 | Secret sentinel from upstream full task is absent from retrieval objects | Scan `FrozenCorpus`, indexes, chunks, results, and logs | Completed |
| M4-50 | Snapshot file hash mismatch fails closed | Corrupted expected hash test raises `SnapshotIntegrityError` | Completed |
| M4-51 | Corpus build failure leaves no partial corpus, index, chunk store, or log | Failure-path fixture and filesystem/log assertions | Completed |
| M4-52 | Planner, Coder, Reviewer sessions share identical `FrozenRetrievalStore` | Three role sessions assert same store instance and same `corpus_hash` | Completed |
| M4-53 | Repair round does not reread filesystem | Monkeypatch file reads after corpus build | Completed |
| M4-54 | Invalid calls do not write retrieval log | Empty query, bad top_k, unknown file/chunk tests | Completed |
| M4-55 | Sensitive query is rejected and never logged | Query containing denied paths raises `SensitiveQueryError` | Completed |
| M4-56 | Denylist does not reject normal substring filenames | Approved snapshot fixtures for `result_formatter.py` and `runtime_notes.md` | Completed |
| M4-57 | Canonical `corpus_hash` is reproducible | Stable hash tests for same snapshot and reordered input | Completed |
| M4-58 | Writer append failure leaves no malformed JSONL | Simulated write failure and rollback assertion | Completed |
| M4-59 | Corpus denylist and log output allowlist are independent | `results/` rejected as corpus but `results/raw/retrieval/*.jsonl` allowed as log output | Completed |
| M4-60 | Three roles share the same `FrozenRetrievalStore` instance | Planner/Coder/Reviewer session identity assertion | Completed |
| M4-61 | Indexes build exactly once per run/task | Instrumented builder counters across three roles and repair rounds | Completed |
| M4-62 | Normal natural-language query is not falsely rejected | Queries with ordinary `results`, `workspace`, `result`, `run` words | Completed |
| M4-63 | Partial write after half-line bytes rolls back completely | Byte-for-byte JSONL comparison after simulated partial write failure | Completed |
| M4-64 | Rollback failure reports integrity unknown | `RetrievalLogWriteError` includes `log_integrity_unknown=True` | Completed |
| M4-65 | Mutation tests use only `tmp_path` synthetic repos | Tests assert real `student_system/SNAPSHOT.json`, real source files, and `experiments/tasks.json` are untouched | Completed |

## 3. Verified Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest tests/retrieval -v
python -B -m pytest tests/leakage -v
python -B -m pytest tests/contracts -v
python -B -m pytest -v
```

Residue scan:

```powershell
Get-ChildItem -Recurse -Force -Include '__pycache__','.pytest_cache','*.pyc','*.pyo' |
  Select-Object -ExpandProperty FullName
```

Network/provider scan:

```powershell
rg "requests|httpx|urllib|socket|vertex|gemini|embedding|Hermes|api_key|API_KEY" experiments tests
```

Verified M4 implementation result: no retrieval module imports or invokes network/model/provider clients.

## 4. Public Interface Summary

```python
@dataclass(frozen=True)
class RetrievalTaskSpec:
    task_id: str
    allowed_corpus: tuple[str, ...]

class RetrievalFacade:
    def build_store(
        self,
        *,
        spec: RetrievalTaskSpec,
        repo_root: Path,
        strategy: Literal["A", "C", "E"],
    ) -> FrozenRetrievalStore: ...

    def create_session(
        self,
        *,
        run_id: str,
        strategy: Literal["A", "C", "E"],
        agent_role: Literal["Planner", "Coder", "Reviewer"],
        store: FrozenRetrievalStore,
        log_writer: RetrievalLogWriter | None = None,
    ) -> RetrievalSession: ...

class RetrievalSession:
    def keyword_search(self, query: str, top_k: int) -> SearchResult: ...
    def semantic_search(self, query: str, top_k: int) -> SearchResult: ...
    def chunk_read(self, file_path: str, chunk_id: str) -> ChunkReadResult: ...
```

Primary dataclasses:

- `RetrievalTaskSpec(task_id, allowed_corpus)`
- `CorpusFile(file_path, snapshot_sha256, normalized_sha256, text, byte_length, line_count)`
- `Chunk(chunk_id, file_path, chunk_index, start_line, end_line, text, sha256, token_count)`
- `FrozenCorpus(task_id, snapshot_id, files, chunks, corpus_hash)`
- `KeywordPosting(term, chunk_id, count)`
- `KeywordIndex(corpus_hash, postings, chunk_token_counts)`
- `SemanticDocumentVector(chunk_id, weights, norm)`
- `SemanticIndex(corpus_hash, idf, document_vectors)`
- `FrozenRetrievalStore(corpus, keyword_index, semantic_index)`
- `SearchHit(file_path, chunk_id, score, rank, excerpt, content_hash, token_count)`
- `SearchResult(tool_name, query, hits, returned_files, returned_chunk_ids, content_hash, excerpt, token_count)`
- `ChunkReadResult(tool_name, query, file_path, chunk_id, text, content_hash, excerpt, token_count)`
- `RetrievalLogRecord(run_id, task_id, strategy, agent_role, tool_name, query, returned_files, returned_chunk_ids, content_hash, excerpt, timestamp, token_count)`
- `RetrievalLogWriter(approved_log_root, log_file_path)`

Primary errors:

- `RetrievalPermissionError`
- `CorpusNotBuiltError`
- `CorpusPathError`
- `SnapshotIntegrityError`
- `DenylistedCorpusError`
- `CorpusDecodeError`
- `RetrievalInputError`
- `SensitiveQueryError`
- `UnknownFileError`
- `UnknownChunkError`
- `ChunkFileMismatchError`
- `RetrievalLogValidationError`
- `RetrievalLogWriteError`

## 5. Semantic Search Decision

M4 will use deterministic, offline TF-IDF cosine search implemented with the Python standard library.

Rejected for M4:

- Local embedding dependencies, because they add installation, model availability, and reproducibility risks.
- External embedding providers, because they violate no-network/no-provider constraints and risk corpus leakage.

M4 wording requirement:

- The implementation must not claim neural semantic embedding behavior.
- Documentation and docstrings should describe it as deterministic TF-IDF/cosine semantic_search.

## 6. Contract and Blocker Notes

- `AGENTS.md` is absent in the repository root; this planning round follows the user-provided AGENTS instructions.
- The current `retrieval-log.schema.json` is sufficient for M4 logging without schema changes.
- The current `result.schema.json` lacks a persisted retrieval setup latency field. M4 will keep corpus setup outside `model_latency_seconds` and avoid schema modification.
- The current `retrieval-log.schema.json` permits strategy `A` and `C` values, but runtime permission policy must still fail closed for A/C retrieval.
- `retrieval-log.schema.json` has no error/status fields, so invalid calls must raise without writing retrieval logs. Errors must not be disguised as `excerpt`.
- `RetrievalTaskSpec` is the only task input accepted by the retrieval layer. It contains only `task_id` and `allowed_corpus`.
- `FrozenRetrievalStore` is role-independent and owns one `FrozenCorpus`, one `KeywordIndex`, and one `SemanticIndex`.
- `FrozenCorpus` and all indexes are immutable and must not retain paths or callbacks capable of rereading files.
- Corpus source denylist and log output allowlist are separate. `results/` is denied as corpus, while caller-approved `results/raw/retrieval/*.jsonl` is the recommended log output root.
- `RetrievalLogWriter` must receive `approved_log_root` and `log_file_path`; it must not choose arbitrary output paths.
- Sensitive query detection applies only to path-like candidates, not ordinary natural-language words.
- Writer is single-process/single-writer only; callers must use one independent JSONL per run.
- Hash mismatch, substring filename, and LF/CRLF mutation tests must use `tmp_path` synthetic repos only.
- `README.md` still describes M1 status. It is not updated in this round because only the M4 plan and acceptance docs are allowed.

## 7. Implementation Confirmation

- M4 retrieval feature code was created only under the approved `experiments/retrieval/` package.
- `experiments/retrieval/` was created for M4 implementation.
- `tests/retrieval/` and `tests/leakage/test_retrieval_leakage.py` were created or updated for M4 verification.
- No schemas were modified.
- `experiments/tasks.json` was not modified.
- M5 provider, prompt, agent strategy, external model calls, and real model invocation remain out of scope.



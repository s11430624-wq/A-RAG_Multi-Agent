from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Strategy = Literal["A", "C", "E"]
AgentRole = Literal["Planner", "Coder", "Reviewer"]
ToolName = Literal["keyword_search", "semantic_search", "chunk_read"]


class RetrievalError(Exception):
    pass


class RetrievalPermissionError(RetrievalError):
    pass


class CorpusNotBuiltError(RetrievalError):
    pass


class CorpusPathError(RetrievalError):
    pass


class SnapshotIntegrityError(CorpusPathError):
    pass


class DenylistedCorpusError(CorpusPathError):
    pass


class CorpusDecodeError(CorpusPathError):
    pass


class RetrievalInputError(RetrievalError):
    pass


class SensitiveQueryError(RetrievalInputError):
    pass


class UnknownFileError(RetrievalInputError):
    pass


class UnknownChunkError(RetrievalInputError):
    pass


class ChunkFileMismatchError(RetrievalInputError):
    pass


class RetrievalLogValidationError(RetrievalError):
    pass


class RetrievalLogWriteError(RetrievalError):
    pass


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


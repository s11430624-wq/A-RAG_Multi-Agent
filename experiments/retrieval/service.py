from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from experiments.retrieval.corpus import CorpusBuilder
from experiments.retrieval.guards import assert_agent_role, assert_query_safe, assert_strategy_e
from experiments.retrieval.keyword import build_keyword_index, keyword_search
from experiments.retrieval.logging import RetrievalLogWriter, make_log_record
from experiments.retrieval.models import (
    FrozenRetrievalStore,
    ChunkFileMismatchError,
    ChunkReadResult,
    RetrievalInputError,
    RetrievalTaskSpec,
    SearchResult,
    UnknownChunkError,
    UnknownFileError,
)
from experiments.retrieval.semantic import build_semantic_index, semantic_search


class RetrievalFacade:
    def build_store(self, *, spec: RetrievalTaskSpec, repo_root: Path, strategy: Any) -> FrozenRetrievalStore:
        assert_strategy_e(strategy)
        corpus = CorpusBuilder(repo_root).build(spec)
        keyword_index = build_keyword_index(corpus)
        semantic_index = build_semantic_index(corpus)
        return FrozenRetrievalStore(corpus=corpus, keyword_index=keyword_index, semantic_index=semantic_index)

    def create_session(
        self,
        *,
        run_id: str,
        strategy: Any,
        agent_role: Any,
        store: FrozenRetrievalStore,
        log_writer: RetrievalLogWriter | None = None,
    ) -> "RetrievalSession":
        assert_strategy_e(strategy)
        assert_agent_role(agent_role)
        if not isinstance(store, FrozenRetrievalStore):
            raise RetrievalInputError("store must be a FrozenRetrievalStore")
        return RetrievalSession(run_id=run_id, strategy=strategy, agent_role=agent_role, store=store, log_writer=log_writer)


class RetrievalSession:
    def __init__(
        self,
        *,
        run_id: str,
        strategy: str,
        agent_role: str,
        store: FrozenRetrievalStore,
        log_writer: RetrievalLogWriter | None = None,
    ):
        if not isinstance(store, FrozenRetrievalStore):
            raise RetrievalInputError("store must be a FrozenRetrievalStore")
        self.run_id = run_id
        self.strategy = strategy
        self.agent_role = agent_role
        self.store = store
        self.log_writer = log_writer

    def keyword_search(self, query: str, top_k: int) -> SearchResult:
        self._assert_call_allowed()
        _validate_query_and_top_k(query, top_k)
        result = keyword_search(self.store.corpus, query, top_k)
        self._append_log(result)
        return result

    def semantic_search(self, query: str, top_k: int) -> SearchResult:
        self._assert_call_allowed()
        _validate_query_and_top_k(query, top_k)
        result = semantic_search(self.store.corpus, self.store.semantic_index, query, top_k)
        self._append_log(result)
        return result

    def chunk_read(self, file_path: str, chunk_id: str) -> ChunkReadResult:
        self._assert_call_allowed()
        files = {item.file_path for item in self.store.corpus.files}
        if file_path not in files:
            raise UnknownFileError(f"unknown corpus file: {file_path}")
        chunks = {chunk.chunk_id: chunk for chunk in self.store.corpus.chunks}
        if chunk_id not in chunks:
            raise UnknownChunkError(f"unknown chunk_id: {chunk_id}")
        chunk = chunks[chunk_id]
        if chunk.file_path != file_path:
            raise ChunkFileMismatchError(f"chunk {chunk_id} does not belong to {file_path}")
        query = json.dumps({"chunk_id": chunk_id, "file_path": file_path}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        result = ChunkReadResult(
            tool_name="chunk_read",
            query=query,
            file_path=file_path,
            chunk_id=chunk_id,
            text=chunk.text,
            content_hash=chunk.sha256,
            excerpt=chunk.text if len(chunk.text) <= 500 else chunk.text[:485] + "\n... (truncated)",
            token_count=chunk.token_count,
        )
        self._append_log(result)
        return result

    def _append_log(self, result: SearchResult | ChunkReadResult) -> None:
        self._assert_call_allowed()
        if self.log_writer is None:
            return
        self.log_writer.append(
            make_log_record(
                run_id=self.run_id,
                task_id=self.store.corpus.task_id,
                strategy=self.strategy,
                agent_role=self.agent_role,
                result=result,
            )
        )

    def _assert_call_allowed(self) -> None:
        assert_strategy_e(self.strategy)
        assert_agent_role(self.agent_role)
        if not isinstance(self.store, FrozenRetrievalStore):
            raise RetrievalInputError("store must be a FrozenRetrievalStore")


def _validate_query_and_top_k(query: str, top_k: int) -> None:
    if not isinstance(query, str) or not query.strip():
        raise RetrievalInputError("query must be a non-empty string")
    assert_query_safe(query)
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise RetrievalInputError("top_k must be an integer")
    if top_k <= 0:
        raise RetrievalInputError("top_k must be positive")
    if top_k > 20:
        raise RetrievalInputError("top_k must be at most 20")

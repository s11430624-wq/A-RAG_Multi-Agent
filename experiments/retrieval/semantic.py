"""Deterministic standard-library TF-IDF cosine search for M4 semantic_search."""

from __future__ import annotations

import math
from collections import Counter

from experiments.retrieval.chunking import token_counts
from experiments.retrieval.keyword import _search_result, _truncate_excerpt
from experiments.retrieval.models import FrozenCorpus, SearchHit, SemanticDocumentVector, SemanticIndex


def build_semantic_index(corpus: FrozenCorpus) -> SemanticIndex:
    chunk_counts = {chunk.chunk_id: token_counts(chunk.text) for chunk in corpus.chunks}
    document_frequency: Counter[str] = Counter()
    for counts in chunk_counts.values():
        for term in counts:
            document_frequency[term] += 1
    total_chunks = len(corpus.chunks)
    idf = {
        term: math.log((1 + total_chunks) / (1 + frequency)) + 1
        for term, frequency in sorted(document_frequency.items())
    }
    vectors: list[SemanticDocumentVector] = []
    for chunk in corpus.chunks:
        counts = chunk_counts[chunk.chunk_id]
        total = max(1, sum(counts.values()))
        weights = tuple(sorted((term, (count / total) * idf[term]) for term, count in counts.items()))
        norm = math.sqrt(sum(weight * weight for _, weight in weights))
        vectors.append(SemanticDocumentVector(chunk_id=chunk.chunk_id, weights=weights, norm=norm))
    return SemanticIndex(
        corpus_hash=corpus.corpus_hash,
        idf=tuple(sorted(idf.items())),
        document_vectors=tuple(vectors),
    )


def semantic_search(corpus: FrozenCorpus, index: SemanticIndex, query: str, top_k: int):
    query_counts = token_counts(query)
    idf = dict(index.idf)
    total_query_terms = max(1, sum(query_counts.values()))
    query_weights = {
        term: (count / total_query_terms) * idf.get(term, 0.0)
        for term, count in query_counts.items()
        if term in idf
    }
    query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values()))
    if query_norm == 0.0:
        return _search_result("semantic_search", query, ())

    chunks = {chunk.chunk_id: chunk for chunk in corpus.chunks}
    hits: list[SearchHit] = []
    for vector in index.document_vectors:
        if vector.norm == 0.0:
            continue
        weights = dict(vector.weights)
        dot = sum(query_weights[term] * weights.get(term, 0.0) for term in query_weights)
        score = dot / (query_norm * vector.norm)
        if score <= 0.0:
            continue
        chunk = chunks[vector.chunk_id]
        hits.append(
            SearchHit(
                file_path=chunk.file_path,
                chunk_id=chunk.chunk_id,
                score=score,
                rank=0,
                excerpt=_truncate_excerpt(chunk.text),
                content_hash=chunk.sha256,
                token_count=chunk.token_count,
            )
        )
    ranked = sorted(hits, key=lambda hit: (-hit.score, hit.file_path, _chunk_index(hit.chunk_id), hit.chunk_id))[:top_k]
    ranked = tuple(
        SearchHit(
            file_path=hit.file_path,
            chunk_id=hit.chunk_id,
            score=hit.score,
            rank=index + 1,
            excerpt=hit.excerpt,
            content_hash=hit.content_hash,
            token_count=hit.token_count,
        )
        for index, hit in enumerate(ranked)
    )
    chunk_texts = {chunk.chunk_id: chunk.text for chunk in corpus.chunks}
    return _search_result("semantic_search", query, ranked, chunk_texts)


def _chunk_index(chunk_id: str) -> int:
    marker = "#chunk_"
    if marker not in chunk_id:
        return 0
    return int(chunk_id.split(marker, 1)[1].split("_", 1)[0])

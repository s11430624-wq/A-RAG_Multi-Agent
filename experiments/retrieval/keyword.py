from __future__ import annotations

import hashlib

from experiments.retrieval.chunking import token_counts
from experiments.retrieval.models import FrozenCorpus, KeywordIndex, KeywordPosting, SearchHit, SearchResult

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def build_keyword_index(corpus: FrozenCorpus) -> KeywordIndex:
    postings: list[KeywordPosting] = []
    counts: list[tuple[str, int]] = []
    for chunk in corpus.chunks:
        chunk_counts = token_counts(chunk.text)
        counts.append((chunk.chunk_id, chunk.token_count))
        for term, count in sorted(chunk_counts.items()):
            postings.append(KeywordPosting(term=term, chunk_id=chunk.chunk_id, count=count))
    return KeywordIndex(
        corpus_hash=corpus.corpus_hash,
        postings=tuple(postings),
        chunk_token_counts=tuple(sorted(counts)),
    )


def keyword_search(corpus: FrozenCorpus, query: str, top_k: int) -> SearchResult:
    query_lower = query.casefold()
    query_terms = set(token_counts(query).keys())
    hits: list[SearchHit] = []
    for chunk in corpus.chunks:
        score = 0.0
        text_lower = chunk.text.casefold()
        path_lower = chunk.file_path.casefold()
        if query_lower in text_lower:
            score += 5.0
        if query_lower in path_lower:
            score += 3.0
        chunk_counts = token_counts(chunk.text)
        if query_terms:
            matched = query_terms.intersection(chunk_counts)
            score += 2.0 * len(matched) / len(query_terms)
            score += sum(chunk_counts[term] for term in query_terms) / max(1, chunk.token_count)
        if score > 0.0:
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
    ranked = [
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
    ]
    chunk_texts = {chunk.chunk_id: chunk.text for chunk in corpus.chunks}
    return _search_result("keyword_search", query, tuple(ranked), chunk_texts)


def _chunk_index(chunk_id: str) -> int:
    marker = "#chunk_"
    if marker not in chunk_id:
        return 0
    suffix = chunk_id.split(marker, 1)[1].split("_", 1)[0]
    return int(suffix)


def _search_result(
    tool_name: str,
    query: str,
    hits: tuple[SearchHit, ...],
    chunk_texts: dict[str, str] | None = None,
) -> SearchResult:
    files: list[str] = []
    for hit in hits:
        if hit.file_path not in files:
            files.append(hit.file_path)
    chunk_ids = tuple(hit.chunk_id for hit in hits)
    token_count = sum(hit.token_count for hit in hits)
    if hits:
        text_lookup = chunk_texts or {}
        payload = "\n---CHUNK---\n".join(text_lookup.get(hit.chunk_id, hit.excerpt) for hit in hits).encode("utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
        excerpt = _truncate_excerpt("\n---\n".join(hit.excerpt for hit in hits))
    else:
        content_hash = EMPTY_SHA256
        excerpt = ""
    return SearchResult(
        tool_name=tool_name,  # type: ignore[arg-type]
        query=query,
        hits=hits,
        returned_files=tuple(files),
        returned_chunk_ids=chunk_ids,
        content_hash=content_hash,
        excerpt=excerpt,
        token_count=token_count,
    )


def _truncate_excerpt(text: str) -> str:
    if len(text) <= 500:
        return text
    return text[:485] + "\n... (truncated)"

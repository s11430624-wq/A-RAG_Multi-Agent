import hashlib

import pytest

from experiments.retrieval.models import RetrievalInputError, SensitiveQueryError


def test_keyword_search_orders_exact_matches(strategy_e_session):
    result = strategy_e_session.keyword_search("get_grades_by_course", top_k=3)

    assert result.tool_name == "keyword_search"
    assert result.hits
    assert result.hits[0].score >= result.hits[-1].score
    assert result.returned_chunk_ids == tuple(hit.chunk_id for hit in result.hits)
    assert "student_system/API_SPEC.md" in result.returned_files


def test_keyword_search_rejects_bad_top_k(strategy_e_session):
    for bad in (True, False, 1.5, "3", 0, -1, 21):
        with pytest.raises(RetrievalInputError):
            strategy_e_session.keyword_search("api", bad)


def test_keyword_search_rejects_sensitive_query_without_log(strategy_e_session, retrieval_log_path):
    for query in (
        "read evaluation/hidden_tests/test_t01.py",
        r"C:\repo\results\raw\data.jsonl",
        "workspaces/run_1/file.py",
        "please inspect (evaluation/reference_patches/T01.diff).",
    ):
        with pytest.raises(SensitiveQueryError):
            strategy_e_session.keyword_search(query, top_k=3)

    assert not retrieval_log_path.exists()


def test_keyword_search_does_not_reject_natural_language_result_words(strategy_e_session):
    for query in (
        "summarize results",
        "explain runtime workspace isolation",
        "how should this function return result",
        "run validation logic",
    ):
        strategy_e_session.keyword_search(query, top_k=3)


def test_keyword_search_valid_empty_result(strategy_e_session):
    result = strategy_e_session.keyword_search("xqzv", top_k=5)

    assert result.hits == ()
    assert result.returned_files == ()
    assert result.returned_chunk_ids == ()
    assert result.token_count == 0


def test_keyword_tie_break_is_stable(build_synthetic_repo, tmp_path):
    from experiments.retrieval.models import RetrievalTaskSpec
    from experiments.retrieval.service import RetrievalFacade

    root = build_synthetic_repo(
        tmp_path / "repo",
        extra_files={
            "student_system/A.md": b"alpha beta\n",
            "student_system/B.md": b"alpha beta\n",
        },
    )
    spec = RetrievalTaskSpec("T01", ("student_system/B.md", "student_system/A.md"))
    facade = RetrievalFacade()
    store = facade.build_store(spec=spec, repo_root=root, strategy="E")
    session = facade.create_session(run_id="run_tie", strategy="E", agent_role="Planner", store=store)

    first = session.keyword_search("alpha", top_k=2)
    second = session.keyword_search("alpha", top_k=2)

    assert [hit.chunk_id for hit in first.hits] == [hit.chunk_id for hit in second.hits]
    assert first.hits[0].file_path == "student_system/A.md"


def test_multi_chunk_content_hash_uses_full_rank_order_text(build_synthetic_repo, tmp_path):
    from experiments.retrieval.models import RetrievalTaskSpec
    from experiments.retrieval.service import RetrievalFacade

    long_a = ("alpha " + "a" * 620 + " unique_a\n").encode("utf-8")
    long_b = ("alpha " + "b" * 620 + " unique_b\n").encode("utf-8")
    root = build_synthetic_repo(
        tmp_path / "repo",
        extra_files={
            "student_system/A.md": long_a,
            "student_system/B.md": long_b,
        },
    )
    spec = RetrievalTaskSpec("T01", ("student_system/A.md", "student_system/B.md"))
    store = RetrievalFacade().build_store(spec=spec, repo_root=root, strategy="E")
    session = RetrievalFacade().create_session(run_id="run_hash", strategy="E", agent_role="Reviewer", store=store)

    result = session.keyword_search("alpha", top_k=2)
    chunks = {chunk.chunk_id: chunk for chunk in store.corpus.chunks}
    payload = "\n---CHUNK---\n".join(chunks[chunk_id].text for chunk_id in result.returned_chunk_ids).encode("utf-8")

    assert result.content_hash == hashlib.sha256(payload).hexdigest()

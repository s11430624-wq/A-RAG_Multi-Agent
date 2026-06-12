import inspect

import pytest

from experiments.retrieval.models import RetrievalInputError


def test_semantic_search_is_deterministic(strategy_e_session):
    first = strategy_e_session.semantic_search("course grade lookup", top_k=5)
    second = strategy_e_session.semantic_search("course grade lookup", top_k=5)

    assert [hit.chunk_id for hit in first.hits] == [hit.chunk_id for hit in second.hits]
    assert [hit.score for hit in first.hits] == [hit.score for hit in second.hits]


def test_semantic_search_uses_same_top_k_validation(strategy_e_session):
    for bad in (True, 1.5, "3", 0, -1, 21):
        with pytest.raises(RetrievalInputError):
            strategy_e_session.semantic_search("anything", bad)


def test_semantic_search_returns_stable_tie_breaks(build_synthetic_repo, tmp_path):
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
    session = facade.create_session(run_id="run_semantic_tie", strategy="E", agent_role="Planner", store=store)

    result = session.semantic_search("alpha beta", top_k=2)

    assert [hit.file_path for hit in result.hits] == ["student_system/A.md", "student_system/B.md"]


def test_semantic_module_describes_tfidf_not_neural_embeddings():
    import experiments.retrieval.semantic as semantic

    source = inspect.getsource(semantic).casefold()
    assert "tf-idf" in source or "tfidf" in source
    assert "neural embedding" not in source

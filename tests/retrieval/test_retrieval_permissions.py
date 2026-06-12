import pytest

from experiments.retrieval.guards import assert_agent_role, assert_strategy_e, is_denylisted_repo_path
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import RetrievalInputError, RetrievalPermissionError, RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade, RetrievalSession


def test_retrieval_task_spec_contains_only_allowed_fields():
    spec = RetrievalTaskSpec(task_id="T01", allowed_corpus=("student_system/API_SPEC.md",))

    assert spec.task_id == "T01"
    assert spec.allowed_corpus == ("student_system/API_SPEC.md",)


def test_strategy_a_and_c_fail_closed_at_guard_boundary():
    for strategy in ("A", "C"):
        with pytest.raises(RetrievalPermissionError):
            assert_strategy_e(strategy)


def test_invalid_strategy_values_fail_closed_at_guard_boundary():
    for strategy in (True, False, None, "", "B", "E "):
        with pytest.raises(RetrievalPermissionError):
            assert_strategy_e(strategy)


def test_strategy_e_passes_guard_boundary():
    assert_strategy_e("E") is None


def test_agent_role_validation_rejects_case_errors_and_unknown_roles():
    for role in ("planner", "PLANNER", "Designer", "", None, True):
        with pytest.raises(RetrievalPermissionError):
            assert_agent_role(role)


def test_agent_role_validation_accepts_only_known_roles():
    for role in ("Planner", "Coder", "Reviewer"):
        assert_agent_role(role) is None


def test_denylist_is_component_based_not_substring_based():
    assert is_denylisted_repo_path("results/raw/results.jsonl")
    assert is_denylisted_repo_path("RESULTS/raw/results.jsonl")
    assert is_denylisted_repo_path("student_system/cache/API_SPEC.md")
    assert is_denylisted_repo_path("student_system\\CaChE\\API_SPEC.md")
    assert is_denylisted_repo_path("student_system/src/module.pyc")
    assert not is_denylisted_repo_path("student_system/src/result_formatter.py")
    assert not is_denylisted_repo_path("student_system/docs/runtime_notes.md")


def test_external_conversion_drops_secret_sentinel(full_task_with_secret_sentinel, retrieval_task_spec):
    sentinel = full_task_with_secret_sentinel["secret_sentinel"]

    assert sentinel not in repr(retrieval_task_spec)
    assert retrieval_task_spec.task_id == "T01"
    assert retrieval_task_spec.allowed_corpus == ("student_system/API_SPEC.md",)


def test_strategy_a_and_c_fail_closed_at_build_and_create(retrieval_task_spec, repo_root):
    facade = RetrievalFacade()
    for strategy in ("A", "C", True, None, "", "B"):
        with pytest.raises(RetrievalPermissionError):
            facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy=strategy)

    store = facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")
    for strategy in ("A", "C", True, None, "", "B"):
        with pytest.raises(RetrievalPermissionError):
            facade.create_session(run_id="run_t01", strategy=strategy, agent_role="Planner", store=store)


def test_three_roles_share_same_frozen_store(retrieval_task_spec, repo_root):
    facade = RetrievalFacade()
    store = facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")

    sessions = [
        facade.create_session(run_id="run_t01", strategy="E", agent_role=role, store=store)
        for role in ("Planner", "Coder", "Reviewer")
    ]

    assert {session.store.corpus.corpus_hash for session in sessions} == {store.corpus.corpus_hash}
    assert all(session.store is store for session in sessions)


def test_create_session_rejects_invalid_agent_role(retrieval_task_spec, repo_root):
    facade = RetrievalFacade()
    store = facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")

    for role in ("planner", "PLANNER", "Unknown", True, None):
        with pytest.raises(RetrievalPermissionError):
            facade.create_session(run_id="run_t01", strategy="E", agent_role=role, store=store)


def test_create_session_rejects_non_frozen_store():
    with pytest.raises(RetrievalInputError):
        RetrievalFacade().create_session(
            run_id="run_bad_store",
            strategy="E",
            agent_role="Planner",
            store={"corpus": "not frozen"},
        )


def test_indexes_build_once_and_repair_sessions_reuse_store(monkeypatch, retrieval_task_spec, repo_root):
    import experiments.retrieval.service as service

    calls = {"keyword": 0, "semantic": 0}
    original_keyword = service.build_keyword_index
    original_semantic = service.build_semantic_index

    def counted_keyword(corpus):
        calls["keyword"] += 1
        return original_keyword(corpus)

    def counted_semantic(corpus):
        calls["semantic"] += 1
        return original_semantic(corpus)

    monkeypatch.setattr(service, "build_keyword_index", counted_keyword)
    monkeypatch.setattr(service, "build_semantic_index", counted_semantic)

    facade = RetrievalFacade()
    store = facade.build_store(spec=retrieval_task_spec, repo_root=repo_root, strategy="E")
    sessions = [
        facade.create_session(run_id=f"run_round_{index}", strategy="E", agent_role=role, store=store)
        for index, role in enumerate(("Planner", "Coder", "Reviewer"))
    ]
    for session in sessions:
        session.keyword_search("API SPEC", top_k=1)
        session.semantic_search("API SPEC", top_k=1)

    assert calls == {"keyword": 1, "semantic": 1}
    assert all(session.store is store for session in sessions)


def test_direct_session_strategy_a_fails_at_tool_call_boundary(strategy_e_store):
    session = RetrievalSession(
        run_id="run_direct_a",
        strategy="A",
        agent_role="Planner",
        store=strategy_e_store,
    )
    first_chunk = strategy_e_store.corpus.chunks[0]

    calls = (
        lambda: session.keyword_search("API SPEC", top_k=1),
        lambda: session.semantic_search("API SPEC", top_k=1),
        lambda: session.chunk_read(first_chunk.file_path, first_chunk.chunk_id),
    )
    for call in calls:
        with pytest.raises(RetrievalPermissionError):
            call()


def test_mutated_session_strategy_fails_at_tool_call_boundary(strategy_e_store, approved_log_root):
    log_path = approved_log_root / "mutated_strategy.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    session = RetrievalFacade().create_session(
        run_id="run_mutated_a",
        strategy="E",
        agent_role="Planner",
        store=strategy_e_store,
        log_writer=writer,
    )
    session.strategy = "A"
    first_chunk = strategy_e_store.corpus.chunks[0]

    calls = (
        lambda: session.keyword_search("API SPEC", top_k=1),
        lambda: session.semantic_search("API SPEC", top_k=1),
        lambda: session.chunk_read(first_chunk.file_path, first_chunk.chunk_id),
    )
    for call in calls:
        with pytest.raises(RetrievalPermissionError):
            call()

    assert not log_path.exists() or log_path.read_bytes() == b""


def test_direct_session_invalid_role_fails_before_log(strategy_e_store, approved_log_root):
    log_path = approved_log_root / "direct_invalid_role.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    session = RetrievalSession(
        run_id="run_direct_role",
        strategy="E",
        agent_role="planner",
        store=strategy_e_store,
        log_writer=writer,
    )

    with pytest.raises(RetrievalPermissionError):
        session.keyword_search("API SPEC", top_k=1)

    assert not log_path.exists() or log_path.read_bytes() == b""


def test_mutated_session_invalid_role_fails_before_log(strategy_e_store, approved_log_root):
    log_path = approved_log_root / "mutated_invalid_role.jsonl"
    writer = RetrievalLogWriter(approved_log_root=approved_log_root, log_file_path=log_path)
    session = RetrievalFacade().create_session(
        run_id="run_mutated_role",
        strategy="E",
        agent_role="Reviewer",
        store=strategy_e_store,
        log_writer=writer,
    )
    session.agent_role = "planner"

    with pytest.raises(RetrievalPermissionError):
        session.semantic_search("API SPEC", top_k=1)

    assert not log_path.exists() or log_path.read_bytes() == b""

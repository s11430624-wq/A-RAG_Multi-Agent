import hashlib
import json
from pathlib import Path

import pytest

from experiments.providers.fake import FakeProvider
from experiments.providers.models import ModelParameters, Usage
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade
from experiments.strategies.arag_multi_agent import ARAGMultiAgentStrategySession
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.models import ModelVisibleTask, StarterFile
from experiments.strategies.multi_agent import MultiAgentStrategySession
from experiments.strategies.parsers import RetrievalBudgetExceededError, StrategyResponseError
from experiments.strategies.single_llm import SingleLLMStrategySession

PLAN = '{"files_to_modify":["student_system/src/grade.py"],"implementation_steps":["change"],"risks":[]}'
DIFF = "--- a/student_system/src/grade.py\n+++ b/student_system/src/grade.py\n@@ -1 +1 @@\n-old\n+new\n"
REVIEW = '{"issues":[],"verdict":"pass"}'
SEARCH = '{"action":"retrieve","query":"get_grades_by_course","tool":"keyword_search","top_k":1}'


def _task():
    return ModelVisibleTask(
        "T01",
        "change",
        (StarterFile("student_system/src/grade.py", "old\n", "a" * 64),),
        ("student_system/src/grade.py",),
        ("new",),
        (),
    )


def _build(tmp_path: Path, repo_root: Path, responses):
    facade = RetrievalFacade()
    store = facade.build_store(
        spec=RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)),
        repo_root=repo_root,
        strategy="E",
    )
    log_root = tmp_path / "logs"
    log_writer = RetrievalLogWriter(
        approved_log_root=log_root,
        log_file_path=log_root / "retrieval.jsonl",
    )
    provider = FakeProvider(responses=responses, usage=Usage(1, 1, 2, "provider"))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-e", task_id="T01", strategy="E", model="m", provider_id="provider", seed=42)
    session = ARAGMultiAgentStrategySession(
        run_id="run-e",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
        store=store,
        retrieval_facade=facade,
        log_writer=log_writer,
    )
    return session, provider, store, log_root / "retrieval.jsonl"


def test_strategy_e_continuations_share_store_and_separate_tool_calls(tmp_path, project_root):
    session, provider, store, log_path = _build(
        tmp_path,
        project_root,
        (SEARCH, PLAN, SEARCH, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.metrics.model_call_count == 5
    assert output.metrics.tool_calls == 2
    assert [request.call_index for request in provider.requests] == [1, 2, 3, 4, 5]
    assert all(role_session.store is store for role_session in session.role_sessions.values())
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2
    assert "<EVIDENCE_DATA>[" in provider.requests[1].user_prompt


def test_retrieval_budget_exhaustion_stops_without_sixth_tool_or_provider_call(tmp_path, project_root):
    # With Planner/initial budget=5, the 6th distinct search query triggers budget exhaustion.
    s1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    s2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    s3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    s4 = '{"action":"retrieve","query":"query4","tool":"keyword_search","top_k":1}'
    s5 = '{"action":"retrieve","query":"query5","tool":"keyword_search","top_k":1}'
    s6 = '{"action":"retrieve","query":"query6","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (s1, s2, s3, s4, s5, s6, PLAN),
    )

    with pytest.raises(RetrievalBudgetExceededError):
        session.generate_initial_patch()

    assert len(provider.requests) == 6
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5



def test_evidence_ledger_is_run_task_role_phase_scoped(tmp_path, project_root):
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (SEARCH, PLAN, DIFF, REVIEW),
    )
    session.generate_initial_patch()

    items = session.evidence_ledger.items
    assert items
    assert all(item.run_id == "run-e" and item.task_id == "T01" for item in items)
    assert all(item.role == "Planner" and item.phase == "initial" for item in items)
    assert len({item.evidence_id for item in items}) == len(items)


def test_retrieval_request_is_provider_neutral_json():
    parsed = json.loads(SEARCH)
    assert parsed == {
        "action": "retrieve",
        "query": "get_grades_by_course",
        "tool": "keyword_search",
        "top_k": 1,
    }


def test_strategy_e_planner_initial_third_retrieval_allowed(tmp_path, project_root):
    # A 3rd retrieval request remains valid under the Planner/initial budget of 5.
    # The responses are 3 SEARCH requests, 1 PLAN request, 1 DIFF request, and 1 REVIEW.
    s1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    s2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    s3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (s1, s2, s3, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    
    assert len(provider.requests) == 6
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3
    assert output.metrics.tool_calls == 3
    assert output.patch == DIFF


def test_strategy_e_planner_initial_five_distinct_retrievals_allowed(tmp_path, project_root):
    queries = tuple(
        f'{{"action":"retrieve","query":"query{i}","tool":"keyword_search","top_k":1}}'
        for i in range(1, 6)
    )
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (*queries, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.metrics.tool_calls == 5
    assert len(provider.requests) == 8
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5


def test_strategy_e_planner_initial_sixth_distinct_retrieval_fails_closed(tmp_path, project_root):
    queries = tuple(
        f'{{"action":"retrieve","query":"query{i}","tool":"keyword_search","top_k":1}}'
        for i in range(1, 7)
    )
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (*queries, PLAN),
    )

    with pytest.raises(RetrievalBudgetExceededError):
        session.generate_initial_patch()

    assert len(provider.requests) == 6
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5



def test_strategy_e_planner_initial_fourth_retrieval_allowed(tmp_path, project_root):
    # A 4th retrieval request should now be allowed by the Planner/initial budget of 5.
    s1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    s2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    s3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    s4 = '{"action":"retrieve","query":"query4","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (s1, s2, s3, s4, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.patch == DIFF
    assert output.metrics.tool_calls == 4
    assert len(provider.requests) == 7
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 4


def test_strategy_e_duplicate_keyword_search_reuses_cached_empty_result_without_budget_decrement(tmp_path, project_root):
    # If the Planner issues identical keyword search queries, the 2nd and subsequent identical queries
    # should be intercepted, reusing the cached empty result without consuming budget.
    # Responses: SEARCH, SEARCH, SEARCH, PLAN, DIFF, REVIEW.
    # Here, we do 3 identical SEARCH queries. With cache, it only consumes 1 budget,
    # so we still have 2 budget left. Thus, it easily completes.
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    assert len(provider.requests) == 6
    assert output.metrics.tool_calls == 1  # only 1 distinct call, others are cached
    # Since only 1 distinct call was made, only 1 log record should be written.
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_strategy_e_third_cache_hit_fails_closed_before_another_model_call(tmp_path, project_root):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, search_dup, search_dup, PLAN),
    )

    with pytest.raises(
        RetrievalBudgetExceededError,
        match="Planner/initial cached retrieval repetition limit exceeded",
    ):
        session.generate_initial_patch()

    assert len(provider.requests) == 4
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_strategy_e_retrieval_request_is_not_printed_to_stdout_or_stderr(tmp_path, project_root, capsys):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate SECRET_SENTINEL","tool":"keyword_search","top_k":1}'
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    captured = capsys.readouterr()
    assert "RAW RETRIEVAL REQUEST" not in captured.out
    assert "RAW RETRIEVAL REQUEST" not in captured.err
    assert "SECRET_SENTINEL" not in captured.out
    assert "SECRET_SENTINEL" not in captured.err


def test_strategy_e_duplicate_keyword_search_does_not_write_duplicate_retrieval_log(tmp_path, project_root):
    # This verifies that cached requests do not log duplicate lines to retrieval.jsonl.
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()
    # Should only log 1 line for the unique query
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_strategy_e_after_duplicate_empty_result_can_use_new_query_with_remaining_budget(tmp_path, project_root):
    # Even if previous queries were empty, a duplicate of them shouldn't consume budget,
    # allowing subsequent distinct queries to proceed as long as distinct count <= 3.
    # We do: 3 identical queries of q1 (consumes 1 budget) + 2 distinct queries of q2 and q3 (consumes 2 budget).
    # Total distinct budget consumed = 3. Should complete successfully!
    q1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    q2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    q3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (q1, q1, q1, q2, q3, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    assert output.patch == DIFF
    assert output.metrics.tool_calls == 3  # only 3 distinct calls


def test_strategy_e_duplicate_queries_still_do_not_consume_budget_after_budget_5(tmp_path, project_root):
    q1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    q2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    q3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    q4 = '{"action":"retrieve","query":"query4","tool":"keyword_search","top_k":1}'
    q5 = '{"action":"retrieve","query":"query5","tool":"keyword_search","top_k":1}'
    session, _provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (q1, q1, q1, q2, q3, q4, q5, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.metrics.tool_calls == 5
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 5


def test_strategy_e_six_distinct_planner_queries_still_fail_closed(tmp_path, project_root):
    # This verifies that budget is still strictly enforced. If there are 6 distinct queries,
    # it must trigger RetrievalBudgetExceededError.
    q1 = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    q2 = '{"action":"retrieve","query":"query2","tool":"keyword_search","top_k":1}'
    q3 = '{"action":"retrieve","query":"query3","tool":"keyword_search","top_k":1}'
    q4 = '{"action":"retrieve","query":"query4","tool":"keyword_search","top_k":1}'
    q5 = '{"action":"retrieve","query":"query5","tool":"keyword_search","top_k":1}'
    q6 = '{"action":"retrieve","query":"query6","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (q1, q2, q3, q4, q5, q6, PLAN),
    )

    with pytest.raises(RetrievalBudgetExceededError):
        session.generate_initial_patch()


def test_strategy_e_duplicate_semantic_search_uses_cache_same_as_keyword(tmp_path, project_root):
    # Same cache-reuse behavior must apply to semantic search.
    sem_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"semantic_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (sem_dup, sem_dup, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    assert output.metrics.tool_calls == 1
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_strategy_e_cache_key_is_role_phase_tool_query_scoped(tmp_path, project_root):
    # Cache keys must isolate tool, query, top_k, chunk/file parameters.
    # If any of these differ, they are considered distinct.
    q_key = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":1}'
    q_sem = '{"action":"retrieve","query":"query1","tool":"semantic_search","top_k":1}'
    q_diff_k = '{"action":"retrieve","query":"query1","tool":"keyword_search","top_k":2}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (q_key, q_sem, q_diff_k, PLAN, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    assert output.metrics.tool_calls == 3  # All three should be distinct and executed


def test_strategy_e_cache_does_not_cross_run_or_role(tmp_path, project_root):
    # Cache must be per-strategy-session and per-role scoped. It must not cross roles or runs.
    # Since Coder and Reviewer have different role/phase, their cache must be independent.
    # In _build, we run Planner and Coder.
    # Let's test that Coder's search with same query is distinct from Planner's search.
    # (Planner initial budget = 5, Coder initial budget = 3)
    # Planner does 1 SEARCH. Coder does same SEARCH. Since they are different roles,
    # they are both executed (budget decrements on both sides, and both are logged).
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_dup, PLAN, search_dup, DIFF, REVIEW),
    )

    output = session.generate_initial_patch()
    assert output.metrics.tool_calls == 2  # 1 for Planner, 1 for Coder
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2


class DynamicFakeProvider:
    def __init__(self, responses, session_getter=None):
        self.responses = list(responses)
        self.requests = []
        self.session_getter = session_getter
        self._position = 0

    def generate(self, request):
        from experiments.providers.models import ModelResponse, Usage, ProviderAttemptRecord
        self.requests.append(request)
        text = self.responses[self._position]
        self._position += 1
        
        if "ACTUAL_PLANNER_CHUNK_ID" in text and self.session_getter:
            session = self.session_getter()
            actual_chunk_id = None
            for item in session.evidence_ledger.items:
                if item.role == "Planner" and item.tool_name in ("keyword_search", "semantic_search"):
                    actual_chunk_id = item.chunk_id
                    break
            if actual_chunk_id:
                text = text.replace("ACTUAL_PLANNER_CHUNK_ID", actual_chunk_id)
                
        if "ACTUAL_CODER_CHUNK_ID" in text and self.session_getter:
            session = self.session_getter()
            actual_chunk_id = None
            for item in session.evidence_ledger.items:
                if item.role == "Coder" and item.tool_name in ("keyword_search", "semantic_search"):
                    actual_chunk_id = item.chunk_id
                    break
            if actual_chunk_id:
                text = text.replace("ACTUAL_CODER_CHUNK_ID", actual_chunk_id)
                
        attempt = ProviderAttemptRecord(request.call_index, 1, 0.0, 0.0, "response", None)
        return ModelResponse(
            text=text,
            finish_reason="stop",
            usage=Usage(1, 1, 2, "provider"),
            provider_request_id=f"fake-{request.call_index}",
            model=request.parameters.model,
            latency_seconds=0.0,
            retry_count=0,
            seed_applied=True,
            sanitized_metadata=(),
            attempt_records=(attempt,),
        )


def _build_dynamic(tmp_path: Path, repo_root: Path, responses, session_ref: list):
    facade = RetrievalFacade()
    store = facade.build_store(
        spec=RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)),
        repo_root=repo_root,
        strategy="E",
    )
    log_root = tmp_path / "logs"
    log_writer = RetrievalLogWriter(
        approved_log_root=log_root,
        log_file_path=log_root / "retrieval.jsonl",
    )
    provider = DynamicFakeProvider(responses=responses, session_getter=lambda: session_ref[0] if session_ref else None)
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-e", task_id="T01", strategy="E", model="m", provider_id="provider", seed=42)
    session = ARAGMultiAgentStrategySession(
        run_id="run-e",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0, 0.95, 128, 5, 42),
        artifact_writer=writer,
        store=store,
        retrieval_facade=facade,
        log_writer=log_writer,
    )
    session_ref.append(session)
    return session, provider, store, log_root / "retrieval.jsonl"


def test_a_c_strategies_remain_zero_retrieval(tmp_path, project_root):
    parameters = ModelParameters("m", 0, 0.95, 128, 5, 42)
    a_provider = FakeProvider(responses=(DIFF,), usage=Usage(1, 1, 2, "provider"))
    a_session = SingleLLMStrategySession(
        run_id="run-a",
        task=_task(),
        provider=a_provider,
        parameters=parameters,
        artifact_writer=ArtifactBundleWriter(
            tmp_path / "artifacts-a",
            run_id="run-a",
            task_id="T01",
            strategy="A",
            model="m",
            provider_id="provider",
            seed=42,
        ),
    )
    c_provider = FakeProvider(responses=(PLAN, DIFF, REVIEW), usage=Usage(1, 1, 2, "provider"))
    c_session = MultiAgentStrategySession(
        run_id="run-c",
        task=_task(),
        provider=c_provider,
        parameters=parameters,
        artifact_writer=ArtifactBundleWriter(
            tmp_path / "artifacts-c",
            run_id="run-c",
            task_id="T01",
            strategy="C",
            model="m",
            provider_id="provider",
            seed=42,
        ),
    )

    a_output = a_session.generate_initial_patch()
    c_output = c_session.generate_initial_patch()

    assert a_output.metrics.tool_calls == 0
    assert c_output.metrics.tool_calls == 0
    assert a_output.metrics.retrieved_tokens == 0
    assert c_output.metrics.retrieved_tokens == 0
    assert not (tmp_path / "retrieval").exists()


def test_coder_inherits_visible_planner_evidence(tmp_path, project_root):
    # Planner does search, gets evidence. Coder should see it in prompt.
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, DIFF, REVIEW),
    )
    session.generate_initial_patch()
    # Coder prompt is at provider.requests[2] (0=Planner search, 1=Planner plan, 2=Coder diff)
    coder_prompt = provider.requests[2].user_prompt
    assert "<EVIDENCE_DATA>[" in coder_prompt
    assert "E000001" in coder_prompt


def test_coder_inheritance_rejects_cross_run_task_phase_evidence(tmp_path, project_root):
    from experiments.strategies.models import EvidenceItem
    from dataclasses import replace
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (PLAN, DIFF, REVIEW),
    )
    # Add cross-run/task/phase items to ledger
    items = list(session.evidence_ledger.items)
    items.append(EvidenceItem("E999991", "other-run", "T01", "Planner", "initial", "keyword_search", "student_system/API_SPEC.md", "chunk-1", "hash", "text", 10))
    items.append(EvidenceItem("E999992", "run-e", "other-task", "Planner", "initial", "keyword_search", "student_system/API_SPEC.md", "chunk-1", "hash", "text", 10))
    items.append(EvidenceItem("E999993", "run-e", "T01", "Planner", "repair_1", "keyword_search", "student_system/API_SPEC.md", "chunk-1", "hash", "text", 10))
    session.evidence_ledger = replace(session.evidence_ledger, items=tuple(items))
    session.generate_initial_patch()
    coder_prompt = provider.requests[1].user_prompt
    assert "E999991" not in coder_prompt
    assert "E999992" not in coder_prompt
    assert "E999993" not in coder_prompt


def test_coder_can_view_planner_evidence_without_inheriting_authorization(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, DIFF, REVIEW),
    )
    session.generate_initial_patch()
    coder_auths = [
        auth for auth in session.evidence_ledger.search_authorizations
        if auth.role == "Coder"
    ]
    assert not coder_auths


def test_planner_authorization_does_not_authorize_coder_chunk_read(tmp_path, project_root):
    from experiments.strategies.parsers import StrategyResponseError
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_chunk = '{"action":"retrieve","chunk_id":"ACTUAL_PLANNER_CHUNK_ID","file_path":"student_system/API_SPEC.md","tool":"chunk_read"}'
    session_ref = []
    session, provider, _store, log_path = _build_dynamic(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_chunk),
        session_ref,
    )
    with pytest.raises(StrategyResponseError, match="chunk_read is not authorized for this scope"):
        session.generate_initial_patch()


def test_coder_own_search_authorizes_coder_chunk_read(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    coder_chunk = '{"action":"retrieve","chunk_id":"ACTUAL_CODER_CHUNK_ID","file_path":"student_system/API_SPEC.md","tool":"chunk_read"}'
    session_ref = []
    session, provider, _store, log_path = _build_dynamic(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_search, coder_chunk, DIFF, REVIEW),
        session_ref,
    )
    session.generate_initial_patch()
    assert len(provider.requests) == 6
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_coder_same_role_phase_duplicate_search_uses_cache_without_budget_decrement(tmp_path, project_root):
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (PLAN, coder_search, coder_search, DIFF, REVIEW),
    )
    output = session.generate_initial_patch()
    assert output.metrics.tool_calls == 1
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_coder_query_matching_planner_does_not_cross_role_cache(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, search_q, DIFF, REVIEW),
    )
    output = session.generate_initial_patch()
    assert output.metrics.tool_calls == 2
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2


def test_coder_three_distinct_searches_allowed(tmp_path, project_root):
    c1 = '{"action":"retrieve","query":"q1","tool":"keyword_search","top_k":1}'
    c2 = '{"action":"retrieve","query":"q2","tool":"keyword_search","top_k":1}'
    c3 = '{"action":"retrieve","query":"q3","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (PLAN, c1, c2, c3, DIFF, REVIEW),
    )
    output = session.generate_initial_patch()
    assert output.patch == DIFF
    assert output.metrics.tool_calls == 3
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_coder_fourth_distinct_search_fails_before_backend(tmp_path, project_root):
    c1 = '{"action":"retrieve","query":"q1","tool":"keyword_search","top_k":1}'
    c2 = '{"action":"retrieve","query":"q2","tool":"keyword_search","top_k":1}'
    c3 = '{"action":"retrieve","query":"q3","tool":"keyword_search","top_k":1}'
    c4 = '{"action":"retrieve","query":"q4","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (PLAN, c1, c2, c3, c4),
    )
    with pytest.raises(RetrievalBudgetExceededError, match="Coder/initial retrieval budget exhausted"):
        session.generate_initial_patch()
    assert len(provider.requests) == 5
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_reviewer_only_gets_coder_provenance_evidence(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_search, DIFF, REVIEW),
    )
    session.generate_initial_patch()
    assert "E000001" not in session._coder_evidence_ids
    assert "E000002" in session._coder_evidence_ids


def test_reviewer_rejects_planner_evidence_id(tmp_path, project_root):
    from experiments.strategies.parsers import StrategyResponseError
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    bad_reviewer = '{"issues":[{"category":"correctness","evidence_chunk_ids":["E000001"],"message":"bad"}],"verdict":"fail"}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_search, DIFF, bad_reviewer),
    )
    with pytest.raises(StrategyResponseError, match="Reviewer cited unauthorized evidence"):
        session.generate_initial_patch()


def test_repair_round_does_not_gain_planner_evidence_implicitly(tmp_path, project_root):
    from experiments.strategies.models import SanitizedPublicFeedback
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    coder_search = '{"action":"retrieve","query":"student","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, coder_search, DIFF, REVIEW, DIFF),
    )
    session.generate_initial_patch()
    feedback = SanitizedPublicFeedback(1, "fail", "hash")
    session.generate_repair_patch(feedback, DIFF)
    repair_prompt = provider.requests[-1].user_prompt
    assert "E000001" not in repair_prompt
    assert "E000002" in repair_prompt


def test_retrieval_requests_not_printed_to_stdout_or_stderr(tmp_path, project_root, capsys):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate SECRET_SENTINEL","tool":"keyword_search","top_k":1}'
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, PLAN, DIFF, REVIEW),
    )
    session.generate_initial_patch()
    captured = capsys.readouterr()
    assert "RAW RETRIEVAL REQUEST" not in captured.out
    assert "RAW RETRIEVAL REQUEST" not in captured.err
    assert "SECRET_SENTINEL" not in captured.out
    assert "SECRET_SENTINEL" not in captured.err


def test_frozen_hashes_unchanged(project_root):
    expected_hashes = {
        "results/raw/gates/m7d_smoke_20260611T123000Z.json": "a891b54c245f0de54650ff65693d08e11dce5f2850fd233f387c2c9e76ff6b1a",
        "results/raw/m7d_smoke_20260611T123000Z.jsonl": "74b931d1d78b3e1be152d65885f3143cd655326af23d53c58289c795aba8256c",
        "results/raw/m7e_full_20260611T210000Z.jsonl": "c15e8da518b4e8bb2997ebd3954e0524cfd8f5750a3735673d237784b9aa2638",
        "results/raw/m7e_full_20260611T230000Z.jsonl": "d2a725332d37e0a9f98d95de14f7af6b961b72d0bad6a6dc4c8f21f879d2dfa7",
        "results/raw/m7e_full_20260612T010000Z.jsonl": "67dbf397a63f29f9262d7c2c4f38873e2f4140fef1a3629a58fb25717cf3d30a",
        "results/raw/m7e_full_20260612T020000Z.jsonl": "327d75250233cd4f401d1d944a301186a66a741288789e289bda5d7c22d9f456",
        "results/raw/m7e_full_20260612T030000Z.jsonl": "548f7c7de796c0462be727249e09ebebf43e97694b3cc9649049434ced797664",
    }

    for relative_path, expected_hash in expected_hashes.items():
        artifact_path = project_root / relative_path
        assert artifact_path.is_file(), f"missing frozen artifact: {relative_path}"
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == expected_hash


def test_retrieved_queries_are_accumulated_and_injected_in_session(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, DIFF, REVIEW),
    )
    session.generate_initial_patch()

    assert "<RETRIEVED_QUERIES>" not in provider.requests[0].user_prompt
    assert "<RETRIEVED_QUERIES>" in provider.requests[1].user_prompt
    assert "calculate_pass_rate" in provider.requests[1].user_prompt
    assert "You MUST perform retrieval using this format at least once" in provider.requests[1].user_prompt
    assert "<RETRIEVED_QUERIES>" not in provider.requests[2].user_prompt


def test_coder_prompt_relaxes_when_inherited_planner_evidence_is_visible(tmp_path, project_root):
    search_q = '{"action":"retrieve","query":"grades","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_q, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    coder_prompt = provider.requests[2].user_prompt
    assert "You MUST perform retrieval using this format at least once" not in coder_prompt
    assert "You have already performed retrieval. If you have sufficient information" in coder_prompt


def test_cache_hit_loop_adds_forward_progress_note_to_next_turn(tmp_path, project_root):
    search_dup = '{"action":"retrieve","query":"calculate_pass_rate","tool":"keyword_search","top_k":1}'
    session, provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (search_dup, search_dup, PLAN, DIFF, REVIEW),
    )

    session.generate_initial_patch()

    assert "already satisfied by visible evidence" in provider.requests[2].user_prompt


def test_strategy_e_invalid_coder_response_preserves_raw_response_and_role(tmp_path, project_root):
    invalid_coder = "I think the fix is simple: update the function accordingly."
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (SEARCH, PLAN, invalid_coder),
    )

    with pytest.raises(StrategyResponseError, match="Coder returned invalid response") as exc_info:
        session.generate_initial_patch()

    assert getattr(exc_info.value, "raw_response", None) == invalid_coder
    assert getattr(exc_info.value, "role", None) == "Coder"


def test_strategy_e_invalid_retrieval_request_preserves_raw_response_and_role(tmp_path, project_root):
    invalid_retrieval = '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":"oops"}'
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (invalid_retrieval,),
    )

    with pytest.raises(StrategyResponseError, match="top_k must be an integer from 1 to 3") as exc_info:
        session.generate_initial_patch()

    assert getattr(exc_info.value, "raw_response", None) == invalid_retrieval
    assert getattr(exc_info.value, "role", None) == "Planner"


def test_strategy_e_coder_accepts_single_fenced_diff_with_leading_text(tmp_path, project_root):
    fenced_patch = "note before\n```diff\n" + DIFF + "\n```"
    session, _provider, _store, _log_path = _build(
        tmp_path,
        project_root,
        (SEARCH, PLAN, fenced_patch, REVIEW),
    )

    output = session.generate_initial_patch()

    assert output.patch.startswith("--- ")
    assert "\n+++ " in output.patch
    assert "\n@@ " in output.patch
    assert "```" not in output.patch
    assert output.metrics.tool_calls == 1

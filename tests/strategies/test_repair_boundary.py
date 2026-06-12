import hashlib
from pathlib import Path

import pytest

from experiments.providers.fake import FakeProvider, ScriptedOutcome, ScriptedProvider
from experiments.providers.models import (
    ModelParameters,
    ProviderFinishReasonError,
    Usage,
)
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade
from experiments.strategies.arag_multi_agent import ARAGMultiAgentStrategySession
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.models import ModelVisibleTask, SanitizedPublicFeedback, StarterFile
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


def _feedback(index):
    text = f"public failure {index}"
    return SanitizedPublicFeedback(index, text, hashlib.sha256(text.encode()).hexdigest())


def test_strategy_constructor_rejects_full_task_mapping(tmp_path):
    provider = FakeProvider(responses=(DIFF,))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run", task_id="T01", strategy="A", model="m", provider_id="provider", seed=1)
    with pytest.raises(TypeError):
        SingleLLMStrategySession(
            run_id="run",
            task={"task_id": "T01", "required_evidence": ["secret"]},
            provider=provider,
            parameters=ModelParameters("m", 0, 1, 10, 1, 1),
            artifact_writer=writer,
        )


def test_strategy_e_exact_maximum_schedule_is_fourteen(tmp_path, project_root):
    facade = RetrievalFacade()
    store = facade.build_store(
        spec=RetrievalTaskSpec("T01", ("student_system/API_SPEC.md",)),
        repo_root=project_root,
        strategy="E",
    )
    log_root = tmp_path / "logs"
    log_writer = RetrievalLogWriter(approved_log_root=log_root, log_file_path=log_root / "retrieval.jsonl")
    s1 = '{"action":"retrieve","query":"q1","tool":"keyword_search","top_k":1}'
    s2 = '{"action":"retrieve","query":"q2","tool":"keyword_search","top_k":1}'
    s3 = '{"action":"retrieve","query":"q3","tool":"keyword_search","top_k":1}'
    s4 = '{"action":"retrieve","query":"q4","tool":"keyword_search","top_k":1}'
    s5 = '{"action":"retrieve","query":"q5","tool":"keyword_search","top_k":1}'
    s6 = '{"action":"retrieve","query":"q6","tool":"keyword_search","top_k":1}'
    s7 = '{"action":"retrieve","query":"q7","tool":"keyword_search","top_k":1}'
    s8 = '{"action":"retrieve","query":"q8","tool":"keyword_search","top_k":1}'
    s9 = '{"action":"retrieve","query":"q9","tool":"keyword_search","top_k":1}'
    responses = (
        s1, s2, PLAN,
        s3, s4, DIFF,
        s5, REVIEW,
        s6, s7, DIFF,
        s8, s9, DIFF,
    )
    provider = FakeProvider(responses=responses, usage=Usage(1, 1, 2, "provider"))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-e14", task_id="T01", strategy="E", model="m", provider_id="provider", seed=1)
    session = ARAGMultiAgentStrategySession(
        run_id="run-e14",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0, 1, 10, 1, 1),
        artifact_writer=writer,
        store=store,
        retrieval_facade=facade,
        log_writer=log_writer,
    )

    initial = session.generate_initial_patch()
    repair1 = session.generate_repair_patch(_feedback(1), initial.patch)
    repair2 = session.generate_repair_patch(_feedback(2), repair1.patch)
    finalization = session.finalize()

    assert repair2.metrics.model_call_count == 14
    assert repair2.metrics.tool_calls == 9
    assert len(provider.requests) == 14
    assert finalization.artifact_path == "run-e14"


def test_terminal_finish_reason_failure_rolls_back_staged_bundle(tmp_path):
    provider = ScriptedProvider((ScriptedOutcome.response(DIFF, finish_reason="length"),))
    writer = ArtifactBundleWriter(tmp_path / "artifacts", run_id="run-fail", task_id="T01", strategy="A", model="m", provider_id="provider", seed=1)
    session = SingleLLMStrategySession(
        run_id="run-fail",
        task=_task(),
        provider=provider,
        parameters=ModelParameters("m", 0, 1, 10, 1, 1),
        artifact_writer=writer,
    )

    with pytest.raises(ProviderFinishReasonError) as exc_info:
        session.generate_initial_patch()
    assert not (tmp_path / "artifacts/run-fail").exists()
    assert exc_info.value.failure_audit is not None

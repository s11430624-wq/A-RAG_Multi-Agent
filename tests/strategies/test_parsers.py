import json

import pytest

from experiments.providers.models import ProviderFinishReasonError
from experiments.strategies.models import EvidenceLedger, SearchAuthorization
from experiments.strategies.parsers import (
    InvalidPatchError,
    PatchResponseParser,
    PlannerResponseParser,
    ResponseEnvelopeClassifier,
    RetrievalRequestParser,
    ReviewerResponseParser,
    StrategyResponseError,
)

DIFF = "--- a/student_system/src/main.py\n+++ b/student_system/src/main.py\n@@ -1 +1 @@\n-old\n+new\n"


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_request", "unknown"])
def test_finish_reason_fails_before_classification_even_for_valid_looking_text(reason):
    with pytest.raises(ProviderFinishReasonError):
        ResponseEnvelopeClassifier.classify(
            expected_role="Coder",
            response_text=DIFF,
            finish_reason=reason,
        )


def test_classifier_distinguishes_retrieval_json_role_json_and_diff():
    retrieval = '{"action":"retrieve","query":"x","tool":"keyword_search","top_k":1}'
    planner = '{"files_to_modify":["student_system/src/main.py"],"implementation_steps":["x"],"risks":[]}'

    assert ResponseEnvelopeClassifier.classify(expected_role="Planner", response_text=retrieval, finish_reason="stop").kind == "retrieval_request"
    assert ResponseEnvelopeClassifier.classify(expected_role="Planner", response_text=planner, finish_reason="stop").kind == "final_output"
    assert ResponseEnvelopeClassifier.classify(expected_role="Coder", response_text=DIFF, finish_reason="stop").kind == "final_output"


@pytest.mark.parametrize(
    "text",
    [
        "```diff\n" + DIFF + "```",
        DIFF + "\ncomment",
        '{"action":"retrieve","tool":"keyword_search","query":"x","top_k":1}\nexplain',
        "prefix " + DIFF,
    ],
)
def test_classifier_rejects_mixed_or_markdown_envelopes(text):
    result = ResponseEnvelopeClassifier.classify(expected_role="Coder", response_text=text, finish_reason="stop")
    assert result.kind == "invalid"


def test_patch_parser_accepts_only_pure_unified_diff():
    assert PatchResponseParser.parse(DIFF) == DIFF
    with pytest.raises(InvalidPatchError):
        PatchResponseParser.parse("--- a/x\n+++ b/x\n")


def test_planner_parser_requires_exact_fields_and_allowlisted_files():
    valid = json.dumps(
        {
            "implementation_steps": ["change it"],
            "risks": [],
            "files_to_modify": ["student_system/src/main.py"],
        }
    )
    parsed = PlannerResponseParser.parse(valid, allowed_files=("student_system/src/main.py",))
    assert parsed.implementation_steps == ("change it",)

    with pytest.raises(StrategyResponseError):
        PlannerResponseParser.parse(valid[:-1] + ',"extra":1}', allowed_files=("student_system/src/main.py",))


def test_reviewer_parser_enforces_pass_fail_and_evidence_scope():
    assert ReviewerResponseParser.parse('{"issues":[],"verdict":"pass"}', allowed_evidence_ids=()).verdict == "PASS"
    invalid = '{"issues":[{"category":"correctness","message":"bad","evidence_chunk_ids":[]}],"verdict":"pass"}'
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse(invalid, allowed_evidence_ids=())
    forged = '{"issues":[{"category":"correctness","message":"bad","evidence_chunk_ids":["E999999"]}],"verdict":"fail"}'
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse(forged, allowed_evidence_ids=("E000001",))


def test_retrieval_parser_enforces_types_budget_shape_and_phase_authorization():
    ledger = EvidenceLedger(
        run_id="run-1",
        task_id="T01",
        next_sequence=1,
        items=(),
        search_authorizations=(
            SearchAuthorization("run-1", "T01", "Coder", "initial", "student_system/API_SPEC.md", "chunk-1"),
        ),
    )
    search = RetrievalRequestParser.parse(
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":3}',
        ledger=ledger,
        run_id="run-1",
        task_id="T01",
        role="Coder",
        phase="initial",
    )
    assert search.top_k == 3
    chunk = RetrievalRequestParser.parse(
        '{"action":"retrieve","chunk_id":"chunk-1","file_path":"student_system/API_SPEC.md","tool":"chunk_read"}',
        ledger=ledger,
        run_id="run-1",
        task_id="T01",
        role="Coder",
        phase="initial",
    )
    assert chunk.chunk_id == "chunk-1"
    for bad in (
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":true}',
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":4}',
        '{"action":"retrieve","chunk_id":"chunk-1","file_path":"student_system/API_SPEC.md","tool":"chunk_read","extra":1}',
    ):
        with pytest.raises(StrategyResponseError):
            RetrievalRequestParser.parse(
                bad,
                ledger=ledger,
                run_id="run-1",
                task_id="T01",
                role="Coder",
                phase="repair_1",
            )

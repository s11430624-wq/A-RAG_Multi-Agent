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
    assert PatchResponseParser.parse("```diff\n" + DIFF + "```").startswith("--- a/student_system/src/main.py")
    with pytest.raises(InvalidPatchError):
        PatchResponseParser.parse("--- a/x\n+++ b/x\n")


def test_patch_parser_accepts_single_fenced_diff_with_extra_text():
    parsed = PatchResponseParser.parse("note\n```diff\n" + DIFF + "```\nthanks")
    assert parsed.startswith("--- a/student_system/src/main.py")
    assert "```" not in parsed


def test_classifier_accepts_single_fenced_diff_with_extra_text():
    result = ResponseEnvelopeClassifier.classify(
        expected_role="Coder",
        response_text="note\n```diff\n" + DIFF + "```\nthanks",
        finish_reason="stop",
    )
    assert result.kind == "final_output"


def test_patch_parser_accepts_git_diff_prolog_for_multi_file_patch():
    patch = (
        "diff --git a/student_system/src/utils.py b/student_system/src/utils.py\n"
        "--- a/student_system/src/utils.py\n"
        "+++ b/student_system/src/utils.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/student_system/src/student.py b/student_system/src/student.py\n"
        "--- a/student_system/src/student.py\n"
        "+++ b/student_system/src/student.py\n"
        "@@ -1 +1 @@\n"
        "-x\n"
        "+y\n"
    )

    parsed = PatchResponseParser.parse(patch)
    assert "diff --git" not in parsed
    assert parsed.startswith("--- a/student_system/src/utils.py")
    assert "--- a/student_system/src/student.py" in parsed


def test_patch_parser_accepts_bare_diff_prefix_before_multi_file_patch():
    patch = (
        "diff\n"
        "--- student_system/src/utils.py\n"
        "+++ student_system/src/utils.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "--- student_system/src/student.py\n"
        "+++ student_system/src/student.py\n"
        "@@ -1 +1 @@\n"
        "-x\n"
        "+y\n"
    )

    parsed = PatchResponseParser.parse(patch)
    assert not parsed.startswith("diff")
    assert parsed.startswith("--- student_system/src/utils.py")


def test_patch_parser_normalizes_model_hunk_line_counts():
    patch = (
        "--- student_system/src/grade.py\n"
        "+++ student_system/src/grade.py\n"
        "@@ -2,1 +2,1 @@\n"
        " old\n"
        "+new\n"
    )

    assert PatchResponseParser.parse(patch) == (
        "--- student_system/src/grade.py\n"
        "+++ student_system/src/grade.py\n"
        "@@ -2,1 +2,2 @@\n"
        " old\n"
        "+new\n"
    )


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
    search_from_string = RetrievalRequestParser.parse(
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":"3"}',
        ledger=ledger,
        run_id="run-1",
        task_id="T01",
        role="Coder",
        phase="initial",
    )
    assert search_from_string.top_k == 3
    search_from_float_string = RetrievalRequestParser.parse(
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":"3.0"}',
        ledger=ledger,
        run_id="run-1",
        task_id="T01",
        role="Coder",
        phase="initial",
    )
    assert search_from_float_string.top_k == 3
    search_clamped = RetrievalRequestParser.parse(
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":5}',
        ledger=ledger,
        run_id="run-1",
        task_id="T01",
        role="Coder",
        phase="initial",
    )
    assert search_clamped.top_k == 3
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
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":"3.5"}',
        '{"action":"retrieve","query":"api","tool":"keyword_search","top_k":0}',
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

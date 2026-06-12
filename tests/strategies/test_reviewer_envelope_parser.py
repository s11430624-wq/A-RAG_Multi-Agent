import pytest
from experiments.strategies.parsers import ReviewerResponseParser, StrategyResponseError

def test_accept_valid_cases():
    # 1. Accept {"verdict":"PASS","issues":[]}
    res = ReviewerResponseParser.parse('{"verdict":"PASS","issues":[]}', allowed_evidence_ids=())
    assert res.verdict == "PASS" or res.verdict == "pass" # Check case-insensitive output norm

    # 2. Accept {"verdict":"FAIL","issues":["bug"]} with a valid structure
    res2 = ReviewerResponseParser.parse(
        '{"verdict":"FAIL","issues":[{"category":"correctness","message":"bug","evidence_chunk_ids":[]}]}', 
        allowed_evidence_ids=()
    )
    assert res2.verdict == "FAIL" or res2.verdict == "fail"

    # 3. Accept fenced JSON with only whitespace outside
    fenced = '```json\n{"verdict":"PASS","issues":[]}\n```'
    res3 = ReviewerResponseParser.parse(fenced, allowed_evidence_ids=())
    assert res3.verdict == "PASS" or res3.verdict == "pass"

    # 4. Accept lowercase "pass" normalized to PASS
    res4 = ReviewerResponseParser.parse('{"verdict":"pass","issues":[]}', allowed_evidence_ids=())
    assert res4.verdict == "PASS"

    # 5. Accept mixed case "Fail" normalized to FAIL
    res5 = ReviewerResponseParser.parse(
        '{"verdict":"Fail","issues":[{"category":"correctness","message":"bug","evidence_chunk_ids":[]}]}', 
        allowed_evidence_ids=()
    )
    assert res5.verdict == "FAIL"


def test_reject_extra_keys_thoughts():
    # 6. Reject extra key thoughts
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS","issues":[],"thoughts":"looks good"}', allowed_evidence_ids=())


def test_reject_extra_keys_explanation():
    # 7. Reject extra key explanation
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS","issues":[],"explanation":"..."}', allowed_evidence_ids=())


def test_reject_text_before_json():
    # 8. Reject text before JSON
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('Here is the JSON:\n{"verdict":"PASS","issues":[]}', allowed_evidence_ids=())


def test_reject_text_after_json():
    # 9. Reject text after JSON
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS","issues":[]}\nThanks', allowed_evidence_ids=())


def test_reject_multiple_json_objects():
    # 10. Reject multiple JSON objects
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS","issues":[]} {"verdict":"FAIL","issues":[]}', allowed_evidence_ids=())


def test_reject_missing_verdict():
    # 11. Reject missing verdict
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"issues":[]}', allowed_evidence_ids=())


def test_reject_missing_issues():
    # 12. Reject missing issues
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS"}', allowed_evidence_ids=())


def test_reject_issues_not_list():
    # 13. Reject issues not list
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"PASS","issues":"none"}', allowed_evidence_ids=())


def test_reject_invalid_verdict_value():
    # 14. Reject invalid verdict (e.g. MAYBE)
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('{"verdict":"MAYBE","issues":[]}', allowed_evidence_ids=())


def test_reject_empty_response():
    # 15. Reject empty response
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('', allowed_evidence_ids=())


def test_reject_malformed_fenced_json_with_trailing_text():
    # 16. Malformed fenced JSON with trailing text outside fence
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse('```json\n{"verdict":"PASS","issues":[]}\n```\nSome trailing text', allowed_evidence_ids=())


def test_reject_multiple_fenced_blocks():
    # 17. Multiple fenced blocks
    multiple_fenced = '```json\n{"verdict":"PASS","issues":[]}\n```\n```json\n{"verdict":"FAIL","issues":[]}\n```'
    with pytest.raises(StrategyResponseError):
        ReviewerResponseParser.parse(multiple_fenced, allowed_evidence_ids=())

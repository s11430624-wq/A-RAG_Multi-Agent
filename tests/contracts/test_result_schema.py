import os
import json
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# 取得 Schema 的絕對路徑
SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../contracts/result.schema.json")
)

@pytest.fixture
def result_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def validator(result_schema):
    Draft202012Validator.check_schema(result_schema)
    return Draft202012Validator(result_schema)

@pytest.fixture
def valid_result_data():
    return {
      "run_id": "run_01_t01_rep1",
      "task_id": "T01",
      "strategy": "E",
      "repetition": 1,
      "model": "GPT5.4",
      "seed": 42,
      "valid_run": True,
      "pass1_public": False,
      "pass1_hidden": False,
      "pass1_public_tests_passed": 2,
      "pass1_hidden_tests_passed": 0,
      "final_public": True,
      "final_hidden": True,
      "public_tests_passed": 5,
      "public_tests_total": 5,
      "hidden_tests_passed": 3,
      "hidden_tests_total": 3,
      "repair_rounds": 1,
      "patch_apply_failures": 0,
      "api_correct": None,
      "hallucinated_api": None,
      "requirement_score": None,
      "quality_score": None,
      "tool_calls": 4,
      "retrieved_tokens": 1250,
      "retrieval_success": True,
      "input_tokens": 12000,
      "output_tokens": 1500,
      "estimated_cost": 0.045,
      "latency_seconds": 25.5,
      "model_latency_seconds": 18.2,
      "test_latency_seconds": 4.1,
      "infra_error": False,
      "error_type": "none",
      "stop_reason": "public_pass",
      "manual_review_status": "pending",
      "artifact_path": "results/raw/T01/run_01_t01_rep1_artifact.py"
    }

def test_valid_result(validator, valid_result_data):
    """測試一個完整的合規正例，應該順利通過驗證。"""
    validator.validate(valid_result_data)

def test_valid_result_estimated_cost_null(validator, valid_result_data):
    """測試 estimated_cost 為 null (None) 時應該順利通過驗證。"""
    valid_result_data["estimated_cost"] = None
    validator.validate(valid_result_data)

def test_missing_required_fields(validator, valid_result_data):
    """測試缺少必填欄位時必須驗證失敗。"""
    del valid_result_data["run_id"]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_result_data)
    assert "run_id" in str(exc_info.value)

def test_invalid_task_id_pattern(validator, valid_result_data):
    """測試 task_id 不合規時必須失敗。"""
    valid_result_data["task_id"] = "T001"
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_invalid_strategy_enum(validator, valid_result_data):
    """測試 strategy 不是 A/C/E 時必須失敗。"""
    valid_result_data["strategy"] = "B"
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_invalid_error_type_enum(validator, valid_result_data):
    """測試 error_type 填入無效枚舉值時必須失敗。"""
    valid_result_data["error_type"] = "invalid_timeout_error"
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_invalid_stop_reason_enum(validator, valid_result_data):
    """測試 stop_reason 填入無效枚舉值時必須失敗。"""
    valid_result_data["stop_reason"] = "completed"
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_invalid_manual_review_status_enum(validator, valid_result_data):
    """測試 manual_review_status 填入無效枚舉值時必須失敗。"""
    valid_result_data["manual_review_status"] = "approved"
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_requirement_score_out_of_range(validator, valid_result_data):
    """測試 requirement_score 超出 0-2 範圍時必須失敗。"""
    valid_result_data["manual_review_status"] = "reviewed"
    valid_result_data["api_correct"] = 1
    valid_result_data["hallucinated_api"] = 0
    valid_result_data["quality_score"] = 5
    valid_result_data["requirement_score"] = 3
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_quality_score_out_of_range(validator, valid_result_data):
    """測試 quality_score 超出 1-5 範圍時必須失敗。"""
    valid_result_data["manual_review_status"] = "reviewed"
    valid_result_data["api_correct"] = 1
    valid_result_data["hallucinated_api"] = 0
    valid_result_data["requirement_score"] = 2
    
    valid_result_data["quality_score"] = 0
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)
        
    valid_result_data["quality_score"] = 6
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_additional_properties_forbidden(validator, valid_result_data):
    """測試當包含額外未知欄位時必須失敗。"""
    valid_result_data["unknown_data"] = 123
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_result_data)
    assert "unknown_data" in str(exc_info.value)

def test_repair_rounds_greater_than_two_fails(validator, valid_result_data):
    """測試 repair_rounds 大於 2 時必須失敗。"""
    valid_result_data["repair_rounds"] = 3
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_manual_review_pending_with_all_null(validator, valid_result_data):
    """測試 manual_review_status 為 pending 且四個人工評分欄位皆為 null (None) 時，應順利通過。"""
    valid_result_data["manual_review_status"] = "pending"
    valid_result_data["api_correct"] = None
    valid_result_data["hallucinated_api"] = None
    valid_result_data["requirement_score"] = None
    valid_result_data["quality_score"] = None
    validator.validate(valid_result_data)

def test_manual_review_pending_with_any_integer(validator, valid_result_data):
    """測試 manual_review_status 為 pending 時，若任一人工評分欄位為整數，則必須失敗。"""
    fields = ["api_correct", "hallucinated_api", "requirement_score", "quality_score"]
    default_vals = {"api_correct": 1, "hallucinated_api": 0, "requirement_score": 2, "quality_score": 5}
    for field in fields:
        data = valid_result_data.copy()
        data["manual_review_status"] = "pending"
        for f in fields:
            data[f] = None
        data[field] = default_vals[field]
        with pytest.raises(ValidationError):
            validator.validate(data)

def test_manual_review_reviewed_with_valid_integers(validator, valid_result_data):
    """測試 manual_review_status 為 reviewed 且四個人工評分欄位皆為合法整數時，應順利通過。"""
    valid_result_data["manual_review_status"] = "reviewed"
    valid_result_data["api_correct"] = 1
    valid_result_data["hallucinated_api"] = 0
    valid_result_data["requirement_score"] = 2
    valid_result_data["quality_score"] = 5
    validator.validate(valid_result_data)

def test_manual_review_disputed_with_valid_integers(validator, valid_result_data):
    """測試 manual_review_status 為 disputed 且四個人工評分欄位皆為合法整數時，應順利通過。"""
    valid_result_data["manual_review_status"] = "disputed"
    valid_result_data["api_correct"] = 1
    valid_result_data["hallucinated_api"] = 0
    valid_result_data["requirement_score"] = 2
    valid_result_data["quality_score"] = 5
    validator.validate(valid_result_data)

def test_manual_review_reviewed_or_disputed_with_any_null(validator, valid_result_data):
    """測試 manual_review_status 為 reviewed 或 disputed 時，若任一人工評分欄位為 null (None)，則必須失敗。"""
    fields = ["api_correct", "hallucinated_api", "requirement_score", "quality_score"]
    for status in ["reviewed", "disputed"]:
        for field in fields:
            data = valid_result_data.copy()
            data["manual_review_status"] = status
            data["api_correct"] = 1
            data["hallucinated_api"] = 0
            data["requirement_score"] = 2
            data["quality_score"] = 5
            data[field] = None
            with pytest.raises(ValidationError):
                validator.validate(data)

def test_manual_review_missing_any_field(validator, valid_result_data):
    """測試不論 review status 為何，缺少任一人工評分欄位皆必須失敗。"""
    fields = ["api_correct", "hallucinated_api", "requirement_score", "quality_score"]
    for status in ["pending", "reviewed"]:
        for field in fields:
            data = valid_result_data.copy()
            data["manual_review_status"] = status
            if status == "reviewed":
                data["api_correct"] = 1
                data["hallucinated_api"] = 0
                data["requirement_score"] = 2
                data["quality_score"] = 5
            else:
                data["api_correct"] = None
                data["hallucinated_api"] = None
                data["requirement_score"] = None
                data["quality_score"] = None
            del data[field]
            with pytest.raises(ValidationError):
                validator.validate(data)

def test_api_correct_out_of_range(validator, valid_result_data):
    """測試 api_correct 超出 [0, 1] 範圍或為非法整數時必須失敗。"""
    valid_result_data["manual_review_status"] = "reviewed"
    valid_result_data["api_correct"] = 2
    valid_result_data["hallucinated_api"] = 0
    valid_result_data["requirement_score"] = 2
    valid_result_data["quality_score"] = 5
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

def test_hallucinated_api_out_of_range(validator, valid_result_data):
    """測試 hallucinated_api 超出 [0, 1] 範圍或為非法整數時必須失敗。"""
    valid_result_data["manual_review_status"] = "reviewed"
    valid_result_data["api_correct"] = 1
    valid_result_data["hallucinated_api"] = 2
    valid_result_data["requirement_score"] = 2
    valid_result_data["quality_score"] = 5
    with pytest.raises(ValidationError):
        validator.validate(valid_result_data)

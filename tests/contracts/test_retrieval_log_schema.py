import os
import json
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# 取得 Schema 的絕對路徑
SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../contracts/retrieval-log.schema.json")
)

@pytest.fixture
def log_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def validator(log_schema):
    Draft202012Validator.check_schema(log_schema)
    return Draft202012Validator(log_schema)

@pytest.fixture
def valid_log_data():
    return {
      "run_id": "run_01_t01_rep1",
      "task_id": "T01",
      "strategy": "E",
      "agent_role": "Planner",
      "tool_name": "keyword_search",
      "query": "calculate_pass_rate",
      "returned_files": ["student_system/API_SPEC.md"],
      "returned_chunk_ids": ["student_system/API_SPEC.md#chunk_12"],
      "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "excerpt": "def calculate_pass_rate(course_id): calculates ...",
      "timestamp": "2026-06-11T12:00:00Z",
      "token_count": 120
    }

def test_valid_log(validator, valid_log_data):
    """測試一個完整的合規正例，應該順利通過驗證。"""
    validator.validate(valid_log_data)

def test_missing_required_fields(validator, valid_log_data):
    """測試缺少必填欄位時必須驗證失敗。"""
    del valid_log_data["tool_name"]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_log_data)
    assert "tool_name" in str(exc_info.value)

def test_invalid_task_id_pattern(validator, valid_log_data):
    """測試 task_id 不合規時必須失敗。"""
    valid_log_data["task_id"] = "T3"
    with pytest.raises(ValidationError):
        validator.validate(valid_log_data)

def test_invalid_tool_name_enum(validator, valid_log_data):
    """測試 tool_name 填入非法列舉值時必須失敗。"""
    valid_log_data["tool_name"] = "unsupported_search_tool"
    with pytest.raises(ValidationError):
        validator.validate(valid_log_data)

def test_invalid_types(validator, valid_log_data):
    """測試當欄位型別不合規時必須失敗。"""
    valid_log_data["token_count"] = "120"  # 應該是整數，而非字串
    with pytest.raises(ValidationError):
        validator.validate(valid_log_data)

def test_additional_properties_forbidden(validator, valid_log_data):
    """測試當包含額外未知欄位時必須失敗。"""
    valid_log_data["extra_log_field"] = "unexpected"
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_log_data)
    assert "extra_log_field" in str(exc_info.value)

import os
import json
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# 取得 Schema 的絕對路徑
SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../contracts/task.schema.json")
)

@pytest.fixture
def task_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def validator(task_schema):
    Draft202012Validator.check_schema(task_schema)
    return Draft202012Validator(task_schema)

@pytest.fixture
def valid_task_data():
    return {
      "task_id": "T01",
      "title": "Calculate pass rate",
      "task_type": "code_generation",
      "difficulty": "easy",
      "tags": ["grade", "statistics"],
      "task_description": "Create a function to calculate course pass rate.",
      "starter_files": ["student_system/src/grade.py"],
      "files_to_modify": ["student_system/src/grade.py"],
      "allowed_corpus": ["student_system/API_SPEC.md", "student_system/STYLE_GUIDE.md"],
      "required_evidence": ["student_system/API_SPEC.md"],
      "public_test_paths": ["student_system/tests/test_grade.py"],
      "hidden_test_id": "hidden_test_t01",
      "expected_behavior": [
        "Returns a float between 0.0 and 1.0.",
        "Raises ValueError when course_id does not exist."
      ],
      "forbidden_behaviors": ["Do not hardcode return value"],
      "grading": {
        "required_api_symbols": ["get_course_students", "utils.validate_score"],
        "forbidden_api_symbols": ["math.prod"],
        "requirement_checks": ["Must handle empty courses correctly", "Must round to 4 decimal places"]
      },
      "limits": {
        "max_repair_rounds": 2,
        "public_test_timeout_seconds": 30,
        "hidden_test_timeout_seconds": 30
      },
      "public_feedback_policy": {
        "include_stdout": True,
        "include_stderr": True,
        "include_traceback": False,
        "max_chars": 2048
      }
    }

def test_valid_task(validator, valid_task_data):
    """測試一個完整的合規正例，應該順利通過驗證。"""
    validator.validate(valid_task_data)

def test_missing_required_fields(validator, valid_task_data):
    """測試缺少必填欄位時必須驗證失敗。"""
    del valid_task_data["task_id"]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_task_data)
    assert "task_id" in str(exc_info.value)

def test_invalid_task_id_pattern(validator, valid_task_data):
    """測試 task_id 不符合 ^T[0-9]{2}$ 格式時必須失敗。"""
    valid_task_data["task_id"] = "T1"  # 格式應為 T01, 非 T1
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)
    
    valid_task_data["task_id"] = "A01"
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)

def test_invalid_enums(validator, valid_task_data):
    """測試當 task_type, difficulty 填入非法列舉值時必須失敗。"""
    # 測試 task_type
    bad_type = valid_task_data.copy()
    bad_type["task_type"] = "Invalid Type"
    with pytest.raises(ValidationError):
        validator.validate(bad_type)

    # 測試 difficulty
    bad_diff = valid_task_data.copy()
    bad_diff["difficulty"] = "very_hard"
    with pytest.raises(ValidationError):
        validator.validate(bad_diff)

def test_invalid_types(validator, valid_task_data):
    """測試當欄位型別不符時必須失敗。"""
    valid_task_data["tags"] = "grade"  # 應該是陣列，而非字串
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)

def test_additional_properties_forbidden(validator, valid_task_data):
    """測試當包含額外未知欄位時必須失敗。"""
    valid_task_data["unknown_field"] = "some_value"
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_task_data)
    assert "unknown_field" in str(exc_info.value)

def test_expected_behavior_empty_array_fails(validator, valid_task_data):
    """測試 expected_behavior 為空陣列時必須失敗。"""
    valid_task_data["expected_behavior"] = []
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)

def test_limits_max_repair_rounds_out_of_bounds(validator, valid_task_data):
    """測試 limits.max_repair_rounds 超出 0-2 範圍時必須失敗。"""
    valid_task_data["limits"]["max_repair_rounds"] = 3
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)

    valid_task_data["limits"]["max_repair_rounds"] = -1
    with pytest.raises(ValidationError):
        validator.validate(valid_task_data)

def test_grading_weights_forbidden_by_additional_properties(validator, valid_task_data):
    """測試若額外在 grading 中加入已遭移除的權重屬性（如 public_tests_weight）時必須失敗。"""
    valid_task_data["grading"]["public_tests_weight"] = 0.4
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(valid_task_data)
    assert "public_tests_weight" in str(exc_info.value)

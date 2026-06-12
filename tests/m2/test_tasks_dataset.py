import os
import json
import pytest
from jsonschema import Draft202012Validator

def test_tasks_schema_validation():
    schema_path = os.path.abspath("contracts/task.schema.json")
    tasks_path = os.path.abspath("experiments/tasks.json")
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
        
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    
    for task in tasks:
        # Validate schema
        validator.validate(task)
        
        # Verify required_evidence is subset of allowed_corpus
        allowed = set(task["allowed_corpus"])
        required = set(task["required_evidence"])
        assert required.issubset(allowed), f"Task {task['task_id']}: required_evidence {required} must be a subset of allowed_corpus {allowed}"
        
        # Verify all paths are repo-root-relative
        for path_field in ["starter_files", "files_to_modify", "allowed_corpus", "required_evidence", "public_test_paths"]:
            for path in task[path_field]:
                assert path.startswith("student_system/"), f"Task {task['task_id']}: Path '{path}' in field '{path_field}' must be repo-root-relative (starting with 'student_system/')"
                assert not os.path.isabs(path), f"Task {task['task_id']}: Path '{path}' must not be absolute"

        # Verify no hidden test path leakage in hidden_test_id
        assert "evaluation" not in task["hidden_test_id"].lower(), f"Task {task['task_id']}: hidden_test_id must not leak evaluation paths"
        assert "hidden_tests" not in task["hidden_test_id"].lower(), f"Task {task['task_id']}: hidden_test_id must not leak hidden tests paths"

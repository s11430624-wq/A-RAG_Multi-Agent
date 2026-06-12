import copy
import pytest


def test_preview_bulk_score_update_preserves_order():
    from student_system.src import grade

    preview = grade.preview_bulk_score_update(
        [
            {"student_id": "S001", "course_id": "C001", "score": 88},
            {"student_id": "S002", "course_id": "C002", "score": 72},
        ]
    )
    assert [item["student_id"] for item in preview["valid_updates"]] == ["S001", "S002"]


def test_preview_bulk_score_update_does_not_mutate_storage():
    from student_system.src import grade

    before = copy.deepcopy(grade._GRADES)
    grade.preview_bulk_score_update(
        [
            {"student_id": "S001", "course_id": "C001", "score": 88},
            {"student_id": "S002", "course_id": "C002", "score": 72},
        ]
    )
    assert grade._GRADES == before


def test_preview_bulk_score_update_collects_invalid_without_short_circuit():
    from student_system.src import grade

    preview = grade.preview_bulk_score_update(
        [
            {"student_id": "S001", "course_id": "C999", "score": 88},
            {"student_id": "S999", "course_id": "C001", "score": 88},
        ]
    )
    assert preview["summary"] == {"total": 2, "valid": 0, "invalid": 2}


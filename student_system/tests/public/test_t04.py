import pytest


def test_preview_bulk_score_update_exists():
    from student_system.src import grade

    assert hasattr(grade, "preview_bulk_score_update"), "preview_bulk_score_update does not exist"


def test_preview_bulk_score_update_mixed_results():
    from student_system.src import grade

    preview = grade.preview_bulk_score_update(
        [
            {"student_id": "S001", "course_id": "C001", "score": 88},
            {"student_id": "S001", "course_id": "C999", "score": 88},
            {"student_id": "S002", "course_id": "C002", "score": True},
        ]
    )
    assert preview["summary"] == {"total": 3, "valid": 1, "invalid": 2}
    assert preview["valid_updates"][0]["normalized_score"] == 88
    assert preview["valid_updates"][0]["gpa"] == 3.5
    assert preview["invalid_updates"][0]["index"] == 1
    assert preview["invalid_updates"][1]["index"] == 2


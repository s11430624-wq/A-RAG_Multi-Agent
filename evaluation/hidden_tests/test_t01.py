import pytest


def test_get_course_leaderboard_empty_course():
    from student_system.src import course

    assert course.get_course_leaderboard("C003") == []


def test_get_course_leaderboard_invalid_course():
    from student_system.src import course

    with pytest.raises(ValueError):
        course.get_course_leaderboard("C999")


def test_get_course_leaderboard_tie_break(monkeypatch):
    from student_system.src import course

    monkeypatch.setattr(
        "student_system.src.grade.get_grades_by_course",
        lambda course_id: [
            {"student_id": "S002", "course_id": course_id, "score": 80, "gpa": 0.0},
            {"student_id": "S001", "course_id": course_id, "score": 80, "gpa": 0.0},
        ],
    )
    result = course.get_course_leaderboard("C001")
    assert [item["student_id"] for item in result] == ["S001", "S002"]


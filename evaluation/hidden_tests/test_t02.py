import pytest


def test_get_student_transcript_summary_invalid_student():
    from student_system.src import student

    with pytest.raises(ValueError):
        student.get_student_transcript_summary("S999")


def test_get_student_transcript_summary_empty_grades(monkeypatch):
    from student_system.src import student

    monkeypatch.setattr("student_system.src.grade.get_grades_by_student", lambda student_id: [])
    summary = student.get_student_transcript_summary("S001")
    assert summary["total_courses"] == 0
    assert summary["total_credits"] == 0
    assert summary["passed_courses"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["average_gpa"] == 0.0
    assert summary["courses"] == []


def test_get_student_transcript_summary_course_order():
    from student_system.src import student

    summary = student.get_student_transcript_summary("S001")
    assert [item["course_id"] for item in summary["courses"]] == sorted(
        item["course_id"] for item in summary["courses"]
    )


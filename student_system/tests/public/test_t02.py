import pytest


def test_get_student_transcript_summary_exists():
    from student_system.src import student

    assert hasattr(student, "get_student_transcript_summary"), "get_student_transcript_summary does not exist"


def test_get_student_transcript_summary_normal():
    from student_system.src import student

    summary = student.get_student_transcript_summary("S001")
    assert summary["student_id"] == "S001"
    assert summary["name"] == "Alice"
    assert summary["total_courses"] == 2
    assert summary["total_credits"] == 7
    assert summary["passed_courses"] == 2
    assert summary["pass_rate"] == 1.0
    assert summary["average_gpa"] == 3.75
    assert [item["course_id"] for item in summary["courses"]] == ["C001", "C002"]


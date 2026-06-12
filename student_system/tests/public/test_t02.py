import pytest

def test_get_student_course_summary_exists():
    from student_system.src import student
    assert hasattr(student, "get_student_course_summary"), "get_student_course_summary does not exist"

def test_get_student_course_summary_normal():
    from student_system.src import student
    summary = student.get_student_course_summary("S001")
    assert summary["student_id"] == "S001"
    assert len(summary["courses"]) > 0
    c_ids = [c["course_id"] for c in summary["courses"]]
    assert "C001" in c_ids

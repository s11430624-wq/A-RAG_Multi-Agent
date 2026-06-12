import pytest


def test_summarize_grade_records_empty():
    from student_system.src import utils

    assert utils.summarize_grade_records([]) == {
        "total_courses": 0,
        "passed_courses": 0,
        "failed_courses": 0,
        "pass_rate": 0.0,
        "average_gpa": 0.0,
    }


def test_get_course_pass_stats_invalid_course():
    from student_system.src import course

    with pytest.raises(ValueError):
        course.get_course_pass_stats("C999")


def test_get_course_pass_stats_empty_course():
    from student_system.src import course

    stats = course.get_course_pass_stats("C003")
    assert stats["course_id"] == "C003"
    assert stats["total_courses"] == 0
    assert stats["passed_courses"] == 0
    assert stats["failed_courses"] == 0
    assert stats["pass_rate"] == 0.0
    assert stats["average_gpa"] == 0.0

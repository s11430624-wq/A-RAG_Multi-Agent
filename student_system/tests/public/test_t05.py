import pytest


def test_get_course_pass_stats_exists():
    from student_system.src import course

    assert hasattr(course, "get_course_pass_stats"), "get_course_pass_stats does not exist"


def test_get_course_pass_stats_normal():
    from student_system.src import course

    stats = course.get_course_pass_stats("C002")
    assert stats["course_id"] == "C002"
    assert stats["title"] == "Physics"
    assert stats["credits"] == 4
    assert stats["total_courses"] == 2
    assert stats["passed_courses"] == 2
    assert stats["failed_courses"] == 0
    assert stats["pass_rate"] == 1.0
    assert stats["average_gpa"] == 3.0

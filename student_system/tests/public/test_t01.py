import pytest


def test_get_course_leaderboard_exists():
    from student_system.src import course

    assert hasattr(course, "get_course_leaderboard"), "get_course_leaderboard does not exist"


def test_get_course_leaderboard_normal_course():
    from student_system.src import course

    leaderboard = course.get_course_leaderboard("C001")
    assert [item["student_id"] for item in leaderboard] == ["S001", "S002"]
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["score"] == 85
    assert leaderboard[0]["gpa"] == 3.5


import pytest


def test_get_honor_roll_students_exists():
    from student_system.src import student

    assert hasattr(student, "get_honor_roll_students"), "get_honor_roll_students does not exist"


def test_get_honor_roll_students_default_threshold():
    from student_system.src import student

    result = student.get_honor_roll_students()
    assert result == [
        {
            "student_id": "S001",
            "name": "Alice",
            "average_gpa": 3.75,
            "total_courses": 2,
        }
    ]


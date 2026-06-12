import pytest


def test_get_honor_roll_students_invalid_threshold():
    from student_system.src import student

    with pytest.raises(ValueError):
        student.get_honor_roll_students(True)
    with pytest.raises(ValueError):
        student.get_honor_roll_students(4.1)


def test_get_honor_roll_students_higher_threshold():
    from student_system.src import student

    assert student.get_honor_roll_students(3.8) == []


def test_get_honor_roll_students_sorted(monkeypatch):
    from student_system.src import student

    original = student.get_honor_roll_students(0.0)
    assert original == sorted(
        original,
        key=lambda item: (-item["average_gpa"], item["student_id"]),
    )


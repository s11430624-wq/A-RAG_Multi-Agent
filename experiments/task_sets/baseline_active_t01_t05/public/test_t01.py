import pytest

def test_calculate_pass_rate_exists():
    from student_system.src import grade
    assert hasattr(grade, "calculate_pass_rate"), "calculate_pass_rate does not exist"

def test_calculate_pass_rate_normal():
    from student_system.src import grade
    rate = grade.calculate_pass_rate("C001")
    assert rate == 0.5, f"Expected 0.5, got {rate}"

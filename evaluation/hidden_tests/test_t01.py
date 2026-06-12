import pytest

def test_calculate_pass_rate_empty_course():
    from student_system.src import grade
    # C003 is empty course
    assert grade.calculate_pass_rate("C003") == 0.0

def test_calculate_pass_rate_invalid_course():
    from student_system.src import grade
    with pytest.raises(ValueError):
        grade.calculate_pass_rate("C999")

def test_calculate_pass_rate_bounds():
    from student_system.src import grade
    # Verify exact round to 4 decimal places
    # If grades are score 85 (pass) and 55 (fail) -> pass rate 0.5000
    assert grade.calculate_pass_rate("C001") == 0.5

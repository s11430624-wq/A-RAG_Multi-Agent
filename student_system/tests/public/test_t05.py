import pytest

def test_validate_score_exists():
    from student_system.src import utils
    assert hasattr(utils, "validate_score"), "validate_score does not exist in utils"

def test_validate_score_behavior():
    from student_system.src.utils import validate_score
    # Legal score should silently pass
    validate_score(50)
    
    # Illegal score should raise ValueError
    with pytest.raises(ValueError):
        validate_score(105)
    with pytest.raises(ValueError):
        validate_score(-5)
    with pytest.raises(ValueError):
        validate_score("90")
    with pytest.raises(ValueError):
        validate_score(True)

def test_validate_score_integrated():
    from student_system.src import student, grade
    with pytest.raises(ValueError):
        student.update_student_score("S001", 150)
    with pytest.raises(ValueError):
        student.update_student_score("S001", "90")
    with pytest.raises(ValueError):
        grade.add_grade("S001", "C001", -10)
    with pytest.raises(ValueError):
        grade.add_grade("S001", "C001", "90")

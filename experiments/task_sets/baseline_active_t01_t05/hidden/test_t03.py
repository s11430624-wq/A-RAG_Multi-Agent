import pytest

def test_score_to_gpa_bounds_mapping():
    from student_system.src import grade
    
    # 90-100 -> 4.0
    assert grade.score_to_gpa(100) == 4.0
    assert grade.score_to_gpa(90) == 4.0
    
    # 85-89  -> 3.5
    assert grade.score_to_gpa(89) == 3.5
    assert grade.score_to_gpa(85) == 3.5
    
    # 80-84  -> 3.0
    assert grade.score_to_gpa(84) == 3.0
    assert grade.score_to_gpa(80) == 3.0
    
    # 75-79  -> 2.5
    assert grade.score_to_gpa(79) == 2.5
    assert grade.score_to_gpa(75) == 2.5
    
    # 70-74  -> 2.0
    assert grade.score_to_gpa(74) == 2.0
    assert grade.score_to_gpa(70) == 2.0
    
    # 60-69  -> 1.0
    assert grade.score_to_gpa(69) == 1.0
    assert grade.score_to_gpa(60) == 1.0
    
    # < 60   -> 0.0
    assert grade.score_to_gpa(59.9) == 0.0
    assert grade.score_to_gpa(0) == 0.0

def test_score_to_gpa_errors():
    from student_system.src import grade
    with pytest.raises(ValueError):
        grade.score_to_gpa(-1)
    with pytest.raises(ValueError):
        grade.score_to_gpa(101)
    with pytest.raises(ValueError):
        grade.score_to_gpa("90")
    with pytest.raises(ValueError):
        grade.score_to_gpa(True)

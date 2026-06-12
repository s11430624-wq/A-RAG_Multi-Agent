import pytest
from student_system.src import grade

def test_score_to_gpa_normal():
    assert grade.score_to_gpa(90) == 4.0
    assert grade.score_to_gpa(55) == 0.0

def test_score_to_gpa_defect_85():
    gpa = grade.score_to_gpa(85)
    assert gpa == 3.5, f"85 mapped to {gpa} (expected 3.5)"

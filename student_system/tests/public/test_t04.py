import pytest
from student_system.src import utils

def test_is_valid_score_normal():
    assert utils.is_valid_score(85) is True

def test_is_valid_score_boundaries():
    assert utils.is_valid_score(0) is True, "0 returned False"
    assert utils.is_valid_score(100) is True, "100 returned False"

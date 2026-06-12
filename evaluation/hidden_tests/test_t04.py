import pytest

def test_is_valid_score_extreme_boundaries():
    from student_system.src import utils
    assert utils.is_valid_score(0) is True
    assert utils.is_valid_score(100) is True
    assert utils.is_valid_score(0.0) is True
    assert utils.is_valid_score(100.0) is True

def test_is_valid_score_invalid_types():
    from student_system.src import utils
    # Boolean type should return False
    assert utils.is_valid_score(True) is False
    assert utils.is_valid_score(False) is False
    
    # None and container types
    assert utils.is_valid_score(None) is False
    assert utils.is_valid_score([50]) is False
    assert utils.is_valid_score("80") is False
    
    # Out of bounds
    assert utils.is_valid_score(-0.1) is False
    assert utils.is_valid_score(100.1) is False

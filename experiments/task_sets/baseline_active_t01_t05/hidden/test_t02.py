import pytest
from unittest.mock import patch

def test_get_student_course_summary_invalid_student():
    from student_system.src import student
    with pytest.raises(ValueError):
        student.get_student_course_summary("S999")

def test_get_student_course_summary_api_usage():
    from student_system.src import student, grade, course
    
    # Mock the APIs and make sure they are called
    with patch("student_system.src.grade.get_grades_by_student", return_value=[]) as mock_get_grades, \
         patch("student_system.src.student.get_student_by_id", return_value={"student_id": "S001", "name": "Alice"}) as mock_get_student:
        
        summary = student.get_student_course_summary("S001")
        assert summary["student_id"] == "S001"
        assert summary["courses"] == []
        mock_get_grades.assert_called_once_with("S001")
        mock_get_student.assert_called_once_with("S001")

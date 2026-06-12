_STUDENTS = {
    "S001": {"student_id": "S001", "name": "Alice"},
    "S002": {"student_id": "S002", "name": "Bob"}
}

def get_student_by_id(student_id: str) -> dict:
    if student_id not in _STUDENTS:
        raise ValueError("Student not found")
    return _STUDENTS[student_id].copy()

def get_all_students() -> list[dict]:
    return [s.copy() for s in _STUDENTS.values()]

def update_student_score(student_id: str, score: int | float) -> None:
    # Hardcoded check to be removed in T05 refactoring
    if score < 0 or score > 100:
        raise ValueError("Invalid Score")
    get_student_by_id(student_id)

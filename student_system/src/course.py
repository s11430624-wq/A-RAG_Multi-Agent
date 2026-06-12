_COURSES = {
    "C001": {"course_id": "C001", "title": "Mathematics", "credits": 3},
    "C002": {"course_id": "C002", "title": "Physics", "credits": 4},
    "C003": {"course_id": "C003", "title": "Empty Course", "credits": 2}
}

_ENROLLMENT = {
    "C001": ["S001", "S002"],
    "C002": ["S001", "S002"],
    "C003": []
}

def get_course_by_id(course_id: str) -> dict:
    if course_id not in _COURSES:
        raise ValueError("Course not found")
    return _COURSES[course_id].copy()

def get_students_by_course(course_id: str) -> list[dict]:
    from student_system.src.student import get_student_by_id
    if course_id not in _COURSES:
        raise ValueError("Course not found")
    return [get_student_by_id(sid) for sid in _ENROLLMENT[course_id]]

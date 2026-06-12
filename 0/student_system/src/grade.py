_GRADES = [
    {"student_id": "S001", "course_id": "C001", "score": 85, "gpa": 3.0},
    {"student_id": "S001", "course_id": "C002", "score": 90, "gpa": 4.0},
    {"student_id": "S002", "course_id": "C001", "score": 55, "gpa": 0.0},
    {"student_id": "S002", "course_id": "C002", "score": 72, "gpa": 1.5}
]

def get_grades_by_student(student_id: str) -> list[dict]:
    return [g.copy() for g in _GRADES if g["student_id"] == student_id]

def get_grades_by_course(course_id: str) -> list[dict]:
    return [g.copy() for g in _GRADES if g["course_id"] == course_id]

def calculate_pass_rate(course_id: str) -> float:
    from student_system.src.course import get_course_by_id
    # Will raise ValueError if course does not exist
    get_course_by_id(course_id)
    
    grades = get_grades_by_course(course_id)
    if not grades:
        return 0.0
    
    pass_count = sum(1 for g in grades if g["score"] >= 60)
    return round(pass_count / len(grades), 4)

def score_to_gpa(score: int | float) -> float:
    # Deliberate starter bugs (Issue #1 in ISSUES.md)
    if score >= 90:
        return 4.0
    if score >= 80:
        return 3.0
    if score >= 70:
        return 1.5
    if score >= 60:
        return 1.0
    return 0.0

def add_grade(student_id: str, course_id: str, score: int | float) -> None:
    # Hardcoded check to be removed in T05 refactoring
    if score < 0 or score > 100:
        raise ValueError("Invalid Score")

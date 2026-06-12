import os
import ast
import pytest

def check_ast_for_validate_score(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
        
    local_names = {"validate_score"}
    
    # Analyze imports to find what name validate_score is imported as
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and ("utils" in node.module):
                for alias in node.names:
                    if alias.name == "validate_score":
                        local_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "utils" in alias.name:
                    local_names.add(alias.asname or alias.name)
                    
    has_call = False
    has_hardcoded_compare = False
    
    for node in ast.walk(tree):
        # 1. Detect validate_score call
        if isinstance(node, ast.Call):
            # name call like: validate_score(score)
            if isinstance(node.func, ast.Name) and node.func.id in local_names:
                has_call = True
            # attribute call like: utils.validate_score(score)
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in local_names:
                    if node.func.attr == "validate_score":
                        has_call = True
                        
        # 2. Detect hardcoded comparisons like score < 0 or score > 100
        if isinstance(node, ast.Compare):
            # Verify if comparing with 0 or 100
            has_score_var = False
            if isinstance(node.left, ast.Name) and node.left.id == "score":
                has_score_var = True
            for comp in node.comparators:
                if isinstance(comp, ast.Name) and comp.id == "score":
                    has_score_var = True
                
                # Check for numerical constants 0 or 100
                is_constant = False
                val = None
                if isinstance(comp, ast.Constant):
                    is_constant = True
                    val = comp.value
                elif isinstance(comp, ast.Num):
                    is_constant = True
                    val = comp.n
                    
                if is_constant and val in (0, 100) and (has_score_var or isinstance(node.left, (ast.Constant, ast.Num))):
                    # Also check operator type
                    for op in node.ops:
                        if isinstance(op, (ast.Lt, ast.Gt, ast.LtE, ast.GtE)):
                            has_hardcoded_compare = True

    return has_call, has_hardcoded_compare

def test_ast_refactoring_student_and_grade():
    student_path = os.path.abspath("student_system/src/student.py")
    grade_path = os.path.abspath("student_system/src/grade.py")
    
    # 1. Verify student.py
    s_call, s_compare = check_ast_for_validate_score(student_path)
    assert s_call is True, "student.py does not call validate_score"
    assert s_compare is False, "student.py still contains hardcoded score comparisons"
    
    # 2. Verify grade.py
    g_call, g_compare = check_ast_for_validate_score(grade_path)
    assert g_call is True, "grade.py does not call validate_score"
    assert g_compare is False, "grade.py still contains hardcoded score comparisons"

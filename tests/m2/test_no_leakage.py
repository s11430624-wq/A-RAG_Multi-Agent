import os
import json

def test_no_leakage_checks():
    # 1. Verify no temp_sandbox_T* exists in repo root
    for item in os.listdir("."):
        if item.startswith("temp_sandbox_T") and os.path.isdir(item):
            raise AssertionError(f"Residual directory found in repo root: '{item}'")

    # 2. Verify no cache or pyc files exist in student_system, evaluation, tests/m2, tests/contracts
    targets = ["student_system", "evaluation", "tests/m2", "tests/contracts"]
    for target in targets:
        if not os.path.exists(target):
            continue
        for root, dirs, files in os.walk(target):
            for d in dirs:
                assert d not in ("__pycache__", ".pytest_cache"), f"Residual cache dir '{d}' found in '{root}'"
            for f in files:
                assert not f.endswith(".pyc"), f"Residual compiled file '{f}' found in '{root}'"

    # 3. Scan student_system text files recursive for leakage words
    forbidden_words = ["hidden_tests", "reference_patches", "evaluation/"]
    
    # Text-only file extensions
    allowed_extensions = (".md", ".json", ".py", ".txt", ".yaml", ".yml")
    
    for root, dirs, files in os.walk("student_system"):
        for file in files:
            # Skip non-text files based on extension to avoid binary reading
            if not file.lower().endswith(allowed_extensions):
                continue
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for word in forbidden_words:
                assert word not in content, f"Leakage detected: word '{word}' found in file '{filepath}'"
                
    # Scan experiments/tasks.json
    tasks_path = os.path.abspath("experiments/tasks.json")
    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks_content = f.read()
    for word in forbidden_words:
        assert word not in tasks_content, f"Leakage detected: word '{word}' found in tasks.json"
        
    # Scan SNAPSHOT.json
    snapshot_path = os.path.abspath("student_system/SNAPSHOT.json")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_content = f.read()
    for word in forbidden_words:
        assert word not in snapshot_content, f"Leakage detected: word '{word}' found in SNAPSHOT.json"

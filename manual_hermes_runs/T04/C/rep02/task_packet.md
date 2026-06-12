# Task Packet T04: Correct is_valid_score boundaries

這份題目包可以直接提供給 Hermes agent。

## 使用規則

- 不可以使用 hidden tests。
- 不可以使用 reference patches。
- 不可以看其他 strategy 或其他 repetition 的結果。
- 只能修改 files_to_modify 列出的檔案。
- public test source 不直接提供；由操作員執行 public test 後回饋結果。
- 如果是 Strategy A 或 C，不可以使用 RAG。
- 如果是 Strategy E，只能使用本題對應的 manual_rag_corpus 資料夾。

## Workspace Policy

Repository root:

```text
C:/上課檔案/報告/A-RAG_Multi-Agent
```

This task may only modify:

- student_system/src/utils.py

Forbidden paths:

```text
evaluation/hidden_tests/
evaluation/reference_patches/
results/
workspaces/
.git/
__pycache__/
.pytest_cache/
```

Strategy A and C must not read manual_rag_corpus/.
Strategy E may read only manual_rag_corpus/T04/.

## Task Metadata

- task_id: T04
- title: Correct is_valid_score boundaries
- task_type: bug_fix
- difficulty: easy
- tags: type-check, boundaries

## Task Description

```text
Fix the boundaries and type handling in is_valid_score(score) inside utils.py. The boundaries 0 and 100 must return True, and any non-numeric types or booleans (True/False) must return False instead of raising exceptions.
```

## Files To Modify

- student_system/src/utils.py

## Starter Files Included Below

- student_system/src/utils.py

## Public Test Command

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m pytest student_system/tests/public/test_t04.py -q
```

## Expected Behavior

- 0 and 100 are validated as True.
- String inputs, list inputs, None, or boolean inputs return False.

## Forbidden Behaviors


## Grading Hints From Public Task Metadata

### Required API Symbols
- is_valid_score

### Forbidden API Symbols
- None

### Requirement Checks
- Returns True for 0 and 100
- Returns False for strings, arrays or None without crashing
- Returns False for boolean values True/False

## Strategy E RAG Corpus

Use only this folder for Strategy E: manual_rag_corpus/T04/

Allowed source paths represented in that folder:
- student_system/API_SPEC.md
- student_system/STYLE_GUIDE.md
- student_system/ISSUES.md

## Starter Code

### student_system/src/utils.py

```python
def is_valid_score(score: object) -> bool:
    # Deliberate starter bugs (Issue #2 in ISSUES.md)
    if score > 0 and score < 100:
        return True
    return False
```


This directory is a reversible backup of the original active `T01-T05` bundle
before the 2026-06-13 challenge-set swap.

Contents:

- `tasks.json`: the original active task definitions
- `public/`: the original public tests
- `hidden/`: the original hidden tests
- `reference_patches/`: the original evaluator reference patches

To restore the baseline active set, copy these files back to:

- `experiments/tasks.json`
- `student_system/tests/public/`
- `evaluation/hidden_tests/`
- `evaluation/reference_patches/`

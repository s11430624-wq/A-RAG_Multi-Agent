# M7-E.27 Pilot15 Result Table

## Scope

This table consolidates the `15` successful records for the `pilot15` phase centered on `m7e_full_20260612T060000Z`, plus the preserved failed retry evidence for `T01 / E / rep01`.

## Summary

- Successful records used for the pilot15 dataset: `15`
- Preserved failed retry evidence: `1`
- Successful public passes: `15 / 15`
- Successful hidden passes: `15 / 15`

## Successful 15

| Source | Task | Strategy | Rep | Public | Hidden | Stop Reason | Run ID | Record File |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pilot | T01 | A | 1 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__A__rep01__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| pilot | T01 | A | 2 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__A__rep02__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| pilot | T01 | A | 3 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__A__rep03__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| pilot | T01 | C | 1 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__C__rep01__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| pilot | T01 | C | 2 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__C__rep02__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| pilot | T01 | C | 3 | pass | pass | `public_pass` | `m7e_full_20260612T060000Z__T01__C__rep03__seed42` | `results/raw/m7e_full_20260612T060000Z.jsonl` |
| retry | T01 | E | 1 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_02__T01__E__rep01__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_02.jsonl` |
| retry | T01 | E | 2 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_03__T01__E__rep02__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_03.jsonl` |
| retry | T01 | E | 3 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_04__T01__E__rep03__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_04.jsonl` |
| retry | T02 | A | 1 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_05__T02__A__rep01__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_05.jsonl` |
| retry | T02 | A | 2 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_06__T02__A__rep02__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_06.jsonl` |
| retry | T02 | A | 3 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_07__T02__A__rep03__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_07.jsonl` |
| retry | T02 | C | 1 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_08__T02__C__rep01__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_08.jsonl` |
| retry | T02 | C | 2 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_09__T02__C__rep02__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_09.jsonl` |
| retry | T02 | C | 3 | pass | pass | `public_pass` | `m7e_retry_20260612T060000Z_10__T02__C__rep03__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_10.jsonl` |

## Preserved Failed Retry Evidence

| Task | Strategy | Rep | Public | Hidden | Stop Reason | Run ID | Record File |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | E | 1 | fail | fail | `infra_error` | `m7e_retry_20260612T060000Z_01__T01__E__rep01__seed42` | `results/raw/retries/m7e_retry_20260612T060000Z_01.jsonl` |

## Notes

- The successful pilot15 dataset is the `15` rows in the "Successful 15" table.
- `m7e_retry_20260612T060000Z_01` is retained as failure evidence and is not counted inside the final `15`.

# Flaky test report

**Runs analysed:** 5 (2 on main, 3 from pull requests) · **Tests tracked:** 22 · **Flaky:** 0 (🔴 0 critical, 🟠 0 high, 🟡 0 medium, ⚪ 0 low) · **Consistently failing:** 0

## This run

main (merge of #9) · commit `dcfdd75` · Bump flaky test detector to 4d866f2 (#9)

All 22 tests passed.

## Flaky tests

No flaky tests detected: no test has both passed and failed on the same code.

## Trends

```mermaid
xychart-beta
    title "First-attempt pass rate (%), last 5 runs"
    x-axis "Run" [1, 2, 3, 4, 5]
    y-axis "Pass rate" 0 --> 100
    line [100.0, 100.0, 100.0, 100.0, 100.0]
```

```mermaid
xychart-beta
    title "Flaky failures per run, last 5 runs"
    x-axis "Run" [1, 2, 3, 4, 5]
    y-axis "Flaky failures" 0 --> 1
    bar [0, 0, 0, 0, 0]
```

```mermaid
xychart-beta
    title "Line coverage (%), last 5 runs"
    x-axis "Run" [1, 2, 3, 4, 5]
    y-axis "Coverage" 0 --> 100
    line [89.82, 89.82, 89.82, 89.82, 89.82]
```

<details><summary>Run key</summary>

| Run | Commit | Where | Date |
| --- | --- | --- | --- |
| 1 | `909826c` | PR #8 | 2026-10-22 |
| 2 | `62115d0` | PR #8 | 2026-10-22 |
| 3 | `cc5389e` | main (merge of #8) | 2026-10-22 |
| 4 | `6850eda` | PR #9 | 2026-10-22 |
| 5 | `dcfdd75` | main (merge of #9) | 2026-10-22 |

</details>

## Coverage

**Total:** 89.82% of 275 statements (+0.00 vs main at `cc5389e`)

## Graph data

- `runs.csv`: one row per run: pass rate, failures, flaky failures, coverage, diff coverage
- `runs.json`: same as runs.csv, as JSON
- `test_outcomes.csv`: every test attempt in every run (long format, for heatmaps)
- `flaky_tests.json`: flaky and failing tests with stats, onset and per-run timeline
- `coverage_files.csv`: per-file coverage for the latest run with coverage
- `coverage_gaps.json`: files below threshold, never-executed files, uncovered changed lines

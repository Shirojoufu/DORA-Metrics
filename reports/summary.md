# Flaky test report

**Runs analysed:** 3 (1 on main, 2 from pull requests) · **Tests tracked:** 22 · **Flaky:** 0 (🔴 0 critical, 🟠 0 high, 🟡 0 medium, ⚪ 0 low) · **Consistently failing:** 0

## This run

main (merge of #8) · commit `cc5389e` · Add flaky test detection and per-test coverage to CI (#8)

All 22 tests passed.

## Flaky tests

No flaky tests detected: no test has both passed and failed on the same code.

## Trends

```mermaid
xychart-beta
    title "First-attempt pass rate (%), last 3 runs"
    x-axis ["909826c", "62115d0", "cc5389e"]
    y-axis "Pass rate" 0 --> 100
    line [100.0, 100.0, 100.0]
```

```mermaid
xychart-beta
    title "Flaky failures per run, last 3 runs"
    x-axis ["909826c", "62115d0", "cc5389e"]
    y-axis "Flaky failures" 0 --> 1
    bar [0, 0, 0]
```

```mermaid
xychart-beta
    title "Line coverage (%), last 3 runs"
    x-axis ["909826c", "62115d0", "cc5389e"]
    y-axis "Coverage" 0 --> 100
    line [89.82, 89.82, 89.82]
```

## Coverage

**Total:** 89.82% of 275 statements

## Graph data

- `runs.csv`: one row per run: pass rate, failures, flaky failures, coverage, diff coverage
- `runs.json`: same as runs.csv, as JSON
- `test_outcomes.csv`: every test attempt in every run (long format, for heatmaps)
- `flaky_tests.json`: flaky and failing tests with stats, onset and per-run timeline
- `coverage_files.csv`: per-file coverage for the latest run with coverage
- `coverage_gaps.json`: files below threshold, never-executed files, uncovered changed lines

# dora-metrics

CLI that reads a GitHub repo's Deployments and merged PRs, calculates the four
DORA metrics, and charts them in Grafana. Part of a portfolio for a platform /
developer-experience role (Pliant): project 3 of 4. Projects 1 and 2 are the
companion repo `Shirojoufu/Service-Template` (golden-path service template plus
admission webhook).

## Layout

- `src/dora_metrics/metrics.py`: **the only place metrics are defined.** Pure
  functions, no I/O. Change a definition here, update `tests/test_metrics.py`
  and the definitions table in README.md together.
- `src/dora_metrics/github.py`: REST client. Uses the newest *finished*
  deployment status (success/failure/error) because GitHub later marks old
  successes `inactive`. Stops paging once past the time window.
- `src/dora_metrics/store.py`: Postgres upserts. Stores per-event rows
  (lead_times, recoveries) so dashboard SQL only aggregates.
- `src/dora_metrics/cli.py`: `dora owner/name [--environment] [--days] [--db]`.
  `--db` defaults to `$DORA_DATABASE_URL`, else the compose database; only that
  built-in default may fail quietly (report still prints, exit 0).
- `grafana/build_dashboard.py` generates `grafana/dashboards/dora.json`. Never
  hand-edit the JSON; CI fails if they differ.
- `compose.yaml`: Postgres 18.6 + Grafana 13.2.4, dashboard provisioned.

## Commands

```
uv run pytest                      # Postgres test skipped without a DB
docker compose up -d
DORA_TEST_DATABASE_URL=postgresql://dora:dora@localhost:5432/dora uv run pytest
uv run ruff check && uv run ruff format --check
uv run python grafana/build_dashboard.py
```

## Environment notes

- Windows, Git Bash and PowerShell. In Git Bash, prefix `docker run -v` with
  `MSYS_NO_PATHCONV=1` or container paths get mangled.
- `gh auth login` is done; the tool picks up its token (5,000 requests/hour).
  Anonymous is 60/hour.
- Git commits use the GitHub noreply email (pushes with the personal email are
  blocked by GitHub).

## Status (2026-10-21)

Built and tested: 20 tests (8 metrics, 4 client against a fake API, 7 CLI, 1
Postgres integration), every Grafana panel verified against known data via Grafana's
API, CI with a Postgres service container, actionlint clean.

Done: first push (CI green); Service-Template records Deployments and this
tool reports on it.

Next:
1. Run against a real repo with deployment history (e.g. `vercel/next.js`;
   the environment filter ignores case), fill the dashboard, and add real
   output and a screenshot to the README. One PR, docs only.
2. Then one deeper item, one PR each: change failure rate from incidents
   (reverts, `incident` label) not just failed deploys; a GitHub Action that
   writes the report to the job summary; DORA performance bands; listing real
   environment names when none match; GraphQL to cut per-deployment and per-PR
   requests; incremental runs; `--format json`; PyPI for `uvx`; type checking.
3. Optional project 4: a flaky-test detector. Parse test results across CI
   runs, flag flaky tests, and post a summary comment on PRs, optionally with an
   AI-written summary of failures.

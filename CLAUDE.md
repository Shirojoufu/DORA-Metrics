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
- `src/dora_metrics/cli.py`: `dora owner/name [--environment] [--days] [--db]
  [--no-save] [--format text|markdown]`. `--db` defaults to
  `$DORA_DATABASE_URL`, else the compose database; only that built-in default
  may fail quietly (report still prints, exit 0). With markdown, stdout is only
  the report.
- `action.yml`: composite GitHub Action; runs the CLI with `--format markdown
  --no-save` into the job summary. Released as `v1` and `v1.0.1`.
- `.github/workflows/dora-report.yml`: weekly run of the action against
  Service-Template (`production`, `policy-webhook`).
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

Project complete. 22 tests (8 metrics, 4 client against a fake API, 9 CLI, 1
Postgres integration); every Grafana panel verified against known data via
Grafana's API; CI with a Postgres service container; actionlint clean.

Shipped: one-command CLI; README example from `vercel/next.js`
(`release-canary`: its `Production` env has almost no deployments) with a
dashboard screenshot in `docs/dashboard.png`; GitHub Action, verified on
GitHub against Service-Template; Prior art section (Four Keys, DevLake,
Middleware). Licences checked: all compatible with MIT (psycopg is LGPL as a
dependency; Grafana is AGPL but used unmodified).

Ideas if picked up again, one PR each: change failure rate from incidents
(reverts, `incident` label) not just failed deploys; DORA performance bands;
listing real environment names when none match; GraphQL to cut the
per-deployment and per-PR requests (~1,300 for next.js); incremental runs;
`--format json`; PyPI for `uvx`; type checking.

Next portfolio project (4): a flaky-test detector. Parse test results across
CI runs, flag flaky tests, and post a summary comment on PRs, optionally with
an AI-written summary of failures.

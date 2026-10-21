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
- `src/dora_metrics/cli.py`: `dora --repo owner/name [--environment] [--days] [--db]`.
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
- No `gh` login yet; anonymous GitHub API limit is 60 requests/hour. Set
  `GITHUB_TOKEN` for real runs.
- Git commits use the GitHub noreply email (pushes with the personal email are
  blocked by GitHub).

## Status (2026-10-21)

Built and tested: 12 tests (8 metrics, 3 client against a fake API, 1 Postgres
integration), every Grafana panel verified against known data via Grafana's
API, CI with a Postgres service container, actionlint clean.

Next:
1. First commit and push to a new public GitHub repo (user does the push).
2. With a GitHub token, run against a real repo with deployment history (e.g.
   `vercel/next.js`, environment `Production`), fill the dashboard, and add real
   output and a screenshot to the README.
3. Service-Template branch `record-deployments` makes its CI record GitHub
   Deployments (`production` for the app, `policy-webhook` for the webhook).
   Once merged, this tool can report on Service-Template itself.
4. Optional project 4: a flaky-test detector. Parse test results across CI
   runs, flag flaky tests, and post a summary comment on PRs, optionally with an
   AI-written summary of failures.

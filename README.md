# dora-metrics

> A command-line tool that reads a GitHub repo's deployments and pull requests,
> calculates the four DORA metrics, and charts them in Grafana.

## What it measures

| Metric | Definition |
|---|---|
| **Deployment frequency** | Successful deployments to an environment, per week |
| **Lead time for changes** | From a merged PR's first commit to the first successful deployment that finished after the merge |
| **Change failure rate** | Deployments that ended in `failure` or `error`, divided by all finished deployments |
| **Recovery time** | From a failed deployment to the next successful one in the same environment. A run of consecutive failures counts once, from the first failure ("failed deployment recovery time" in DORA's 2023 definitions). |

All four come from the GitHub [Deployments API](https://docs.github.com/en/rest/deployments/deployments)
plus merged pull requests. The definitions live in one place,
[src/dora_metrics/metrics.py](src/dora_metrics/metrics.py), as pure functions
with their own tests. Everything else only fetches, stores or charts.

## Example: vercel/next.js

Next.js publishes a canary release to npm most days, and each publish is
recorded as a GitHub Deployment to `release-canary`. For a library, a release
is the deployment, so lead time here runs from a merged PR's first commit to
the canary that ships it. (Its `Production` environment only had 3
deployments in this window.)

```
$ uv run dora vercel/next.js --environment release-canary
DORA metrics for vercel/next.js (release-canary), last 90 days

  Deployment frequency   124 deploys (9.6/week)
  Lead time for changes  30.2h (median)
  Change failure rate    2% (2 of 126)
  Recovery time          10.1h (median)

  Week of      Deploys  Failed   CFR    Lead  Recovery
  2026-07-20         3       0    0%   27.3h         -
  2026-07-27         8       1   11%   28.4h         -
  2026-08-03        10       1    9%   28.5h     10.1h
  2026-08-10        12       0    0%   30.8h         -
  ...
  2026-10-12         9       0    0%   25.9h         -
  2026-10-19         4       0    0%   45.2h         -

Saved to localhost:5432/dora
```

![DORA dashboard in Grafana for vercel/next.js release-canary](docs/dashboard.png)

In short: about 1.4 releases a day, 2 of 126 failed, and each failure was
followed by a successful canary 14.0h and 6.1h later. The run took about 10
minutes and roughly 1,300 API requests, mostly one per merged PR (1,166 of
them) to find its first commit.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```
uv sync
docker compose up -d
uv run dora owner/name
```

That prints the report and saves it to the compose database. Open
<http://localhost:3000> to see it charted: the DORA dashboard is the home page,
with a dropdown per repo and environment. Run the command again at any time. It
upserts, so overlapping windows don't duplicate anything.

Without Docker it still works: the report prints, plus a note that nothing was
saved.

### Options

| Option | Default | |
|---|---|---|
| `owner/name` | required | The repo (`--repo owner/name` also works) |
| `--environment` | `production` | Deployment environment to measure |
| `--days` | `90` | How far back to look |
| `--db` | `$DORA_DATABASE_URL`, else the compose database | Postgres URL. If you set one, failing to save is an error. |

To set `DORA_DATABASE_URL`: `export DORA_DATABASE_URL=...` in bash, or
`$env:DORA_DATABASE_URL = "..."` in PowerShell.

### Authentication

The tool uses `GITHUB_TOKEN` if set, otherwise the GitHub CLI's token if you've
run `gh auth login`. Without either it falls back to GitHub's anonymous limit of
60 requests an hour, which is only enough for small repos. Each deployment costs
one extra request (its statuses) and each merged PR one more (its commits).

## Recording deployments

The metrics need a repo to create GitHub Deployments. The simplest way in GitHub
Actions is to give the job that deploys an `environment`. GitHub then records a
Deployment, and its success or failure, every time the job runs:

```yaml
jobs:
  deploy:
    runs-on: ubuntu-24.04
    environment: production
    steps:
      - ...
```

Many hosting integrations (Vercel, Netlify, Heroku) record Deployments too.

## Design

```mermaid
flowchart LR
    gh[(GitHub API)] -->|deployments, statuses,<br/>merged PRs, commits| client[github.py]
    client --> metrics["metrics.py<br/>(pure functions)"]
    metrics --> cli["dora CLI<br/>prints a report"]
    metrics --> store[store.py] --> pg[(Postgres)] --> grafana[Grafana]
```

- **Metrics are calculated once, in Python.** Postgres stores each lead time,
  recovery and weekly summary as rows, and the dashboard's SQL only aggregates
  them. A definition can't drift between the CLI and the chart.
- **Dashboard as code.** [grafana/build_dashboard.py](grafana/build_dashboard.py)
  generates the dashboard JSON so the SQL stays readable. CI fails if the
  committed JSON doesn't match the generator.
- **GitHub marks old successes `inactive`.** When a newer deployment succeeds,
  earlier ones get a later `inactive` status. The client uses the newest
  *finished* status (`success`, `failure` or `error`), otherwise most past
  successes would disappear.
- **Paging stops early.** GitHub returns newest first, so the client stops as
  soon as it passes the start of the window instead of reading the whole
  history.

## Known simplifications

- **PRs are matched to deployments by time, not by commit.** A PR counts as
  shipped by the first successful deployment that finished after its merge.
  This is right for a repo that deploys `main`, but would be wrong for one that
  deploys from release branches or holds changes back.
- **Change failure rate counts failed deployments, not production incidents.**
  A deployment that succeeded but broke something isn't counted. Linking
  incidents (for example, issues with an `incident` label) would close that gap.
- **"First commit" uses the commit's author date.** Rebasing keeps the original
  author date, so lead time includes time a branch spent waiting before its PR
  was opened. That's the usual DORA reading ("commit to production"), but it's
  longer than "PR opened to production".

## Development

```
uv run pytest            # unit tests; Postgres test skipped
docker compose up -d postgres
DORA_TEST_DATABASE_URL=postgresql://dora:dora@localhost:5432/dora uv run pytest
uv run ruff check && uv run ruff format --check
```

These are bash. In PowerShell, set the variable on its own line first
(`$env:DORA_TEST_DATABASE_URL = "postgresql://dora:dora@localhost:5432/dora"`)
and run the two ruff commands separately.

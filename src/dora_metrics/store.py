"""Write metric data to Postgres for Grafana to chart.

The metrics are calculated in Python (metrics.py) and stored here per event,
so the dashboard's SQL only aggregates and never re-defines a metric.
"""

from __future__ import annotations

from datetime import date, timedelta

import psycopg

from .metrics import Summary, lead_times, recoveries
from .models import Deployment, PullRequest

SCHEMA = """
create table if not exists deployments (
    repo text not null,
    environment text not null,
    id bigint not null,
    sha text not null,
    created_at timestamptz not null,
    finished_at timestamptz not null,
    state text not null,
    primary key (repo, id)
);

-- One row per merged PR and environment: the same PR reaches different
-- environments at different times.
create table if not exists lead_times (
    repo text not null,
    environment text not null,
    pr_number int not null,
    first_commit_at timestamptz not null,
    merged_at timestamptz not null,
    deployment_id bigint,           -- null until the PR has shipped
    deployed_at timestamptz,
    lead_time_hours double precision,
    primary key (repo, environment, pr_number)
);

create table if not exists recoveries (
    repo text not null,
    environment text not null,
    failed_deployment_id bigint not null,
    recovered_by_id bigint not null,
    recovered_at timestamptz not null,
    recovery_hours double precision not null,
    primary key (repo, failed_deployment_id)
);

create table if not exists weekly_metrics (
    repo text not null,
    environment text not null,
    week date not null,
    deployments int not null,
    failed int not null,
    change_failure_rate double precision,
    median_lead_time_hours double precision,
    median_recovery_hours double precision,
    primary key (repo, environment, week)
);
"""


def _hours(duration: timedelta) -> float:
    return duration.total_seconds() / 3600


def _hours_or_none(duration: timedelta | None) -> float | None:
    return None if duration is None else _hours(duration)


def save(
    database_url: str,
    repo: str,
    environment: str,
    prs: list[PullRequest],
    deployments: list[Deployment],
    weeks: dict[date, Summary],
) -> None:
    """Upsert everything, so re-running over an overlapping window is safe."""
    shipped = {lt.pr.number: lt for lt in lead_times(prs, deployments)}
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        cur.executemany(
            """
            insert into deployments values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (repo, id) do update set
                state = excluded.state, finished_at = excluded.finished_at
            """,
            [
                (repo, environment, d.id, d.sha, d.created_at, d.finished_at, d.state)
                for d in deployments
            ],
        )
        lead_rows = []
        for pr in prs:
            lt = shipped.get(pr.number)
            lead_rows.append(
                (
                    repo,
                    environment,
                    pr.number,
                    pr.first_commit_at,
                    pr.merged_at,
                    lt.deployment.id if lt else None,
                    lt.deployment.finished_at if lt else None,
                    _hours(lt.duration) if lt else None,
                )
            )
        cur.executemany(
            """
            insert into lead_times values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (repo, environment, pr_number) do update set
                deployment_id = excluded.deployment_id,
                deployed_at = excluded.deployed_at,
                lead_time_hours = excluded.lead_time_hours
            """,
            lead_rows,
        )
        cur.executemany(
            """
            insert into recoveries values (%s, %s, %s, %s, %s, %s)
            on conflict (repo, failed_deployment_id) do nothing
            """,
            [
                (
                    repo,
                    environment,
                    r.failed.id,
                    r.recovered_by.id,
                    r.recovered_by.finished_at,
                    _hours(r.duration),
                )
                for r in recoveries(deployments)
            ],
        )
        cur.executemany(
            """
            insert into weekly_metrics values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (repo, environment, week) do update set
                deployments = excluded.deployments,
                failed = excluded.failed,
                change_failure_rate = excluded.change_failure_rate,
                median_lead_time_hours = excluded.median_lead_time_hours,
                median_recovery_hours = excluded.median_recovery_hours
            """,
            [
                (
                    repo,
                    environment,
                    week,
                    s.deployments,
                    s.failed,
                    s.change_failure_rate,
                    _hours_or_none(s.median_lead_time),
                    _hours_or_none(s.median_recovery_time),
                )
                for week, s in weeks.items()
            ],
        )

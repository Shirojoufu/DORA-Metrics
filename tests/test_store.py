"""Postgres integration test. Skipped unless DORA_TEST_DATABASE_URL is set:

docker compose up -d postgres
DORA_TEST_DATABASE_URL=postgresql://dora:dora@localhost:5432/dora uv run pytest
"""

import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from dora_metrics.metrics import weekly
from dora_metrics.models import Deployment, PullRequest
from dora_metrics.store import save

DB = os.environ.get("DORA_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="DORA_TEST_DATABASE_URL not set")

REPO, ENV = "test/store", "production"
T0 = datetime(2026, 10, 19, 9, tzinfo=UTC)  # a Monday


def deploy(id_, hours, state="success"):
    finished = T0 + timedelta(hours=hours)
    return Deployment(id_, f"sha{id_}", ENV, finished - timedelta(minutes=5), state, finished)


@pytest.fixture
def conn():
    with psycopg.connect(DB, autocommit=True) as c:
        yield c
        for table in ("deployments", "lead_times", "recoveries", "weekly_metrics"):
            c.execute(f"delete from {table} where repo = %s", (REPO,))


def test_save_stores_each_metric_and_is_safe_to_rerun(conn):
    deploys = [deploy(1, 0, "failure"), deploy(2, 3), deploy(3, 30)]
    prs = [
        PullRequest(10, merged_at=T0 + timedelta(hours=1), first_commit_at=T0 - timedelta(hours=5)),
        PullRequest(11, merged_at=T0 + timedelta(hours=40), first_commit_at=T0),  # not shipped
    ]

    for _ in range(2):  # a second run over the same window must not fail or duplicate
        save(DB, REPO, ENV, prs, deploys, weekly(prs, deploys))

    def rows(sql):
        return conn.execute(sql, (REPO,)).fetchall()

    assert rows("select id, state from deployments where repo = %s order by id") == [
        (1, "failure"),
        (2, "success"),
        (3, "success"),
    ]
    assert rows(
        "select pr_number, deployment_id, lead_time_hours from lead_times "
        "where repo = %s order by pr_number"
    ) == [(10, 2, 8.0), (11, None, None)]
    assert rows(
        "select failed_deployment_id, recovered_by_id, recovery_hours from recoveries "
        "where repo = %s"
    ) == [(1, 2, 3.0)]
    assert rows(
        "select week, deployments, failed, change_failure_rate from weekly_metrics where repo = %s"
    ) == [(T0.date(), 2, 1, pytest.approx(1 / 3))]

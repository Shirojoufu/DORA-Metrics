from datetime import UTC, date, datetime, timedelta

from dora_metrics.metrics import (
    change_failure_rate,
    lead_times,
    recoveries,
    summarise,
    week_start,
    weekly,
)
from dora_metrics.models import Deployment, PullRequest


def at(day: int, hour: int = 0) -> datetime:
    # October 2026: the 19th is a Monday
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def deploy(id: int, finished: datetime, state: str = "success") -> Deployment:
    return Deployment(
        id, f"sha{id}", "production", finished - timedelta(minutes=5), state, finished
    )


def pr(number: int, first_commit: datetime, merged: datetime) -> PullRequest:
    return PullRequest(number, merged, first_commit)


def test_lead_time_runs_from_first_commit_to_next_successful_deploy():
    deploys = [deploy(1, at(20, 9)), deploy(2, at(20, 15), "failure"), deploy(3, at(21, 10))]
    prs = [pr(7, first_commit=at(19, 10), merged=at(20, 12))]

    [lt] = lead_times(prs, deploys)

    # Skips the deploy before the merge and the failed one after it
    assert lt.deployment.id == 3
    assert lt.duration == at(21, 10) - at(19, 10)


def test_unshipped_prs_have_no_lead_time():
    deploys = [deploy(1, at(20, 9))]
    prs = [pr(7, at(20, 10), merged=at(20, 11))]

    assert lead_times(prs, deploys) == []


def test_run_of_failures_counts_as_one_recovery_from_the_first_failure():
    deploys = [
        deploy(1, at(20, 9)),
        deploy(2, at(20, 10), "failure"),
        deploy(3, at(20, 11), "error"),
        deploy(4, at(20, 14)),
        deploy(5, at(21, 9), "failure"),
    ]

    [rec] = recoveries(deploys)

    assert (rec.failed.id, rec.recovered_by.id) == (2, 4)
    assert rec.duration == timedelta(hours=4)


def test_change_failure_rate():
    deploys = [
        deploy(1, at(20)),
        deploy(2, at(21), "failure"),
        deploy(3, at(22)),
        deploy(4, at(23)),
    ]

    assert change_failure_rate(deploys) == 0.25
    assert change_failure_rate([]) is None


def test_order_of_input_does_not_matter():
    deploys = [deploy(3, at(20, 14)), deploy(1, at(20, 9), "failure"), deploy(2, at(20, 11))]

    [rec] = recoveries(deploys)

    assert rec.recovered_by.id == 2


def test_summary_with_no_data():
    s = summarise([], [])

    assert (s.deployments, s.failed, s.change_failure_rate) == (0, 0, None)
    assert s.median_lead_time is None and s.median_recovery_time is None


def test_week_start_is_monday():
    assert week_start(at(19)) == date(2026, 10, 19)
    assert week_start(at(25, 23)) == date(2026, 10, 19)
    assert week_start(at(26)) == date(2026, 10, 26)


def test_weekly_counts_a_change_in_the_week_it_shipped():
    deploys = [deploy(1, at(23, 9), "failure"), deploy(2, at(27, 9))]
    # merged in week 1, shipped by the deploy in week 2
    prs = [pr(7, first_commit=at(22), merged=at(23, 12))]

    weeks = weekly(prs, deploys)

    first, second = weeks[date(2026, 10, 19)], weeks[date(2026, 10, 26)]
    assert (first.deployments, first.failed, first.change_failure_rate) == (0, 1, 1.0)
    assert first.median_lead_time is None
    assert second.deployments == 1
    assert second.median_lead_time == at(27, 9) - at(22)
    # recovered in week 2, from a failure in week 1
    assert second.median_recovery_time == at(27, 9) - at(23, 9)

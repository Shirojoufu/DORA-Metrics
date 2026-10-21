"""DORA metric calculations.

Pure functions over Deployment and PullRequest records, with no I/O, so the
definitions can be tested against fixed data. Definitions:

- Deployment frequency: successful deployments per week.
- Lead time for changes: from a merged PR's first commit to the first
  successful deployment that finished at or after the merge.
- Change failure rate: failed deployments / finished deployments.
- Recovery time: from a failed deployment to the next successful one. A run
  of consecutive failures counts once, from the first failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median

from .models import Deployment, PullRequest


@dataclass(frozen=True)
class LeadTime:
    pr: PullRequest
    deployment: Deployment
    duration: timedelta


@dataclass(frozen=True)
class Recovery:
    failed: Deployment
    recovered_by: Deployment
    duration: timedelta


@dataclass(frozen=True)
class Summary:
    deployments: int
    failed: int
    change_failure_rate: float | None
    median_lead_time: timedelta | None
    median_recovery_time: timedelta | None


def _by_finish(deployments: list[Deployment]) -> list[Deployment]:
    return sorted(deployments, key=lambda d: d.finished_at)


def lead_times(prs: list[PullRequest], deployments: list[Deployment]) -> list[LeadTime]:
    """Pair each merged PR with the first successful deployment after its merge.

    PRs merged after the last successful deployment haven't shipped yet and
    are left out.
    """
    successes = [d for d in _by_finish(deployments) if d.succeeded]
    result = []
    for pr in prs:
        shipped_by = next((d for d in successes if d.finished_at >= pr.merged_at), None)
        if shipped_by is not None:
            result.append(LeadTime(pr, shipped_by, shipped_by.finished_at - pr.first_commit_at))
    return result


def recoveries(deployments: list[Deployment]) -> list[Recovery]:
    """Time from each failure (or run of failures) to the next success."""
    result = []
    first_failure: Deployment | None = None
    for d in _by_finish(deployments):
        if not d.succeeded:
            first_failure = first_failure or d
        elif first_failure is not None:
            result.append(Recovery(first_failure, d, d.finished_at - first_failure.finished_at))
            first_failure = None
    return result


def change_failure_rate(deployments: list[Deployment]) -> float | None:
    if not deployments:
        return None
    return sum(not d.succeeded for d in deployments) / len(deployments)


def _median(durations: list[timedelta]) -> timedelta | None:
    return median(durations) if durations else None


def summarise(prs: list[PullRequest], deployments: list[Deployment]) -> Summary:
    return Summary(
        deployments=sum(d.succeeded for d in deployments),
        failed=sum(not d.succeeded for d in deployments),
        change_failure_rate=change_failure_rate(deployments),
        median_lead_time=_median([lt.duration for lt in lead_times(prs, deployments)]),
        median_recovery_time=_median([r.duration for r in recoveries(deployments)]),
    )


def week_start(moment: datetime) -> date:
    """Monday of the ISO week containing `moment`."""
    day = moment.date()
    return day - timedelta(days=day.weekday())


def weekly(prs: list[PullRequest], deployments: list[Deployment]) -> dict[date, Summary]:
    """One Summary per week that had any deployment activity.

    Each metric is attributed to the week its outcome landed: a deployment by
    when it finished, a lead time by its deployment, a recovery by the
    deployment that fixed it. Lead times and recoveries are worked out across
    the whole period first, so a change merged one week and shipped the next
    is still counted.
    """
    all_lead_times = lead_times(prs, deployments)
    all_recoveries = recoveries(deployments)

    weeks = sorted({week_start(d.finished_at) for d in deployments})
    result = {}
    for week in weeks:
        in_week = [d for d in deployments if week_start(d.finished_at) == week]
        week_lead = [
            lt.duration for lt in all_lead_times if week_start(lt.deployment.finished_at) == week
        ]
        week_rec = [
            r.duration for r in all_recoveries if week_start(r.recovered_by.finished_at) == week
        ]
        result[week] = Summary(
            deployments=sum(d.succeeded for d in in_week),
            failed=sum(not d.succeeded for d in in_week),
            change_failure_rate=change_failure_rate(in_week),
            median_lead_time=_median(week_lead),
            median_recovery_time=_median(week_rec),
        )
    return result

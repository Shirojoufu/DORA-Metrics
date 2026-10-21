"""Command-line entry point: `dora --repo owner/name`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx

from .github import GitHub, find_token
from .metrics import Summary, summarise, weekly


def _duration(d: timedelta | None) -> str:
    if d is None:
        return "-"
    hours = d.total_seconds() / 3600
    if hours < 1:
        return f"{round(hours * 60)}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def _rate(r: float | None) -> str:
    return "-" if r is None else f"{r:.0%}"


def _print_report(repo: str, env: str, days: int, overall: Summary, weeks) -> None:
    per_week = overall.deployments / (days / 7)
    print(f"DORA metrics for {repo} ({env}), last {days} days\n")
    print(f"  Deployment frequency   {overall.deployments} deploys ({per_week:.1f}/week)")
    print(f"  Lead time for changes  {_duration(overall.median_lead_time)} (median)")
    print(
        f"  Change failure rate    {_rate(overall.change_failure_rate)} "
        f"({overall.failed} of {overall.deployments + overall.failed})"
    )
    print(f"  Recovery time          {_duration(overall.median_recovery_time)} (median)")
    if weeks:
        print(
            f"\n  {'Week of':<12}{'Deploys':>8}{'Failed':>8}{'CFR':>6}{'Lead':>8}{'Recovery':>10}"
        )
        for week, s in weeks.items():
            print(
                f"  {week.isoformat():<12}{s.deployments:>8}{s.failed:>8}"
                f"{_rate(s.change_failure_rate):>6}{_duration(s.median_lead_time):>8}"
                f"{_duration(s.median_recovery_time):>10}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dora",
        description="Calculate DORA metrics from a GitHub repo's deployments and pull requests.",
    )
    parser.add_argument(
        "--repo", required=True, help="owner/name, e.g. Shirojoufu/Service-Template"
    )
    parser.add_argument(
        "--environment", default="production", help="deployment environment (default: production)"
    )
    parser.add_argument("--days", type=int, default=90, help="how far back to look (default: 90)")
    parser.add_argument(
        "--db",
        default=os.environ.get("DORA_DATABASE_URL"),
        help="Postgres URL to save results for Grafana (default: $DORA_DATABASE_URL)",
    )
    args = parser.parse_args(argv)

    token = find_token()
    if token is None:
        print(
            "No GitHub token found (GITHUB_TOKEN or `gh auth login`); "
            "using the anonymous limit of 60 requests/hour.",
            file=sys.stderr,
        )

    since = datetime.now(UTC) - timedelta(days=args.days)
    try:
        with GitHub(token) as gh:
            branch = gh.default_branch(args.repo)
            deployments = gh.deployments(args.repo, args.environment, since)
            prs = gh.merged_pull_requests(args.repo, branch, since)
    except httpx.HTTPStatusError as e:
        print(f"GitHub API error: {e.response.status_code} {e.request.url}", file=sys.stderr)
        if e.response.status_code in (403, 429):
            print("You've probably hit the rate limit; set GITHUB_TOKEN.", file=sys.stderr)
        return 1

    weeks = weekly(prs, deployments)
    _print_report(args.repo, args.environment, args.days, summarise(prs, deployments), weeks)
    if not deployments:
        sys.stdout.flush()  # keep the hint below the report
        print(
            f"\nNo finished deployments to '{args.environment}' found. Does this repo use "
            "GitHub Deployments, and is that the right environment name?",
            file=sys.stderr,
        )

    if args.db:
        from .store import save

        save(args.db, args.repo, args.environment, prs, deployments, weeks)
        print(f"\nSaved to {args.db.split('@')[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

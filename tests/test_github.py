"""GitHub client tests against a fake API (httpx.MockTransport), no network."""

from datetime import UTC, datetime

import httpx

from dora_metrics.github import GitHub

SINCE = datetime(2026, 10, 1, tzinfo=UTC)
REPO = "acme/shop"


def fake_api(routes: dict[str, httpx.Response]) -> GitHub:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path + (
            f"?page={request.url.params['page']}" if "page" in request.url.params else ""
        )
        seen.append(key)
        return routes[key]

    client = GitHub(token="t", transport=httpx.MockTransport(handler))
    client.seen = seen
    return client


def test_deployment_outcome_ignores_later_inactive_status():
    gh = fake_api(
        {
            f"/repos/{REPO}/deployments": httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "sha": "abc",
                        "environment": "production",
                        "created_at": "2026-10-05T10:00:00Z",
                    }
                ],
            ),
            # newest first: superseded by a later deploy, but it did succeed
            f"/repos/{REPO}/deployments/1/statuses": httpx.Response(
                200,
                json=[
                    {"state": "inactive", "created_at": "2026-10-06T09:00:00Z"},
                    {"state": "success", "created_at": "2026-10-05T10:04:00Z"},
                    {"state": "in_progress", "created_at": "2026-10-05T10:01:00Z"},
                ],
            ),
        }
    )

    [d] = gh.deployments(REPO, "production", SINCE)

    assert d.state == "success"
    assert d.finished_at == datetime(2026, 10, 5, 10, 4, tzinfo=UTC)


def test_unfinished_deployments_are_skipped_and_paging_stops_at_since():
    gh = fake_api(
        {
            f"/repos/{REPO}/deployments": httpx.Response(
                200,
                json=[
                    {
                        "id": 2,
                        "sha": "b",
                        "environment": "production",
                        "created_at": "2026-10-09T10:00:00Z",
                    },
                ],
                headers={
                    "Link": f'<https://api.github.com/repos/{REPO}/deployments?page=2>; rel="next"'
                },
            ),
            f"/repos/{REPO}/deployments?page=2": httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "sha": "a",
                        "environment": "production",
                        "created_at": "2026-09-20T10:00:00Z",
                    },
                ],
                headers={
                    "Link": f'<https://api.github.com/repos/{REPO}/deployments?page=3>; rel="next"'
                },
            ),
            f"/repos/{REPO}/deployments/2/statuses": httpx.Response(
                200, json=[{"state": "in_progress", "created_at": "2026-10-09T10:01:00Z"}]
            ),
        }
    )

    assert gh.deployments(REPO, "production", SINCE) == []
    # followed page 2, found a deploy older than SINCE, and never asked for page 3
    # or for the statuses of the old deploy
    assert f"/repos/{REPO}/deployments?page=3" not in gh.seen
    assert f"/repos/{REPO}/deployments/1/statuses" not in gh.seen


def test_merged_pull_requests_skip_unmerged_and_use_earliest_commit():
    gh = fake_api(
        {
            f"/repos/{REPO}/pulls": httpx.Response(
                200,
                json=[
                    {"number": 3, "merged_at": None, "updated_at": "2026-10-08T00:00:00Z"},
                    {
                        "number": 2,
                        "merged_at": "2026-10-07T12:00:00Z",
                        "updated_at": "2026-10-07T12:00:00Z",
                    },
                    {
                        "number": 1,
                        "merged_at": "2026-09-01T00:00:00Z",
                        "updated_at": "2026-09-02T00:00:00Z",
                    },
                ],
            ),
            f"/repos/{REPO}/pulls/2/commits": httpx.Response(
                200,
                json=[
                    {"commit": {"author": {"date": "2026-10-06T09:00:00Z"}}},
                    {"commit": {"author": {"date": "2026-10-04T15:30:00Z"}}},
                ],
            ),
        }
    )

    [pr] = gh.merged_pull_requests(REPO, "main", SINCE)

    assert pr.number == 2
    assert pr.first_commit_at == datetime(2026, 10, 4, 15, 30, tzinfo=UTC)

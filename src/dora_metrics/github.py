"""Read deployments and merged pull requests from the GitHub REST API."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from datetime import datetime

import httpx

from .models import Deployment, PullRequest

# A deployment's statuses are newest first. Successful deployments are later
# marked "inactive" when a newer one succeeds, so the outcome is the newest
# status that is one of these, not simply the newest status.
FINAL_STATES = {"success", "failure", "error"}


def _parse(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


def find_token() -> str | None:
    """GITHUB_TOKEN if set, otherwise the GitHub CLI's token, if logged in."""
    if token := os.environ.get("GITHUB_TOKEN"):
        return token
    if shutil.which("gh"):
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


class GitHub:
    def __init__(
        self,
        token: str | None,
        base_url: str = "https://api.github.com",
        transport: httpx.BaseTransport | None = None,
    ):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(
            base_url=base_url, headers=headers, transport=transport, timeout=30
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GitHub:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _pages(self, path: str, params: dict) -> Iterator[dict]:
        """Yield items across all pages, following the Link header."""
        response = self._http.get(path, params={"per_page": 100, **params})
        while True:
            response.raise_for_status()
            yield from response.json()
            next_url = response.links.get("next", {}).get("url")
            if not next_url:
                return
            response = self._http.get(next_url)

    def default_branch(self, repo: str) -> str:
        response = self._http.get(f"/repos/{repo}")
        response.raise_for_status()
        return response.json()["default_branch"]

    def deployments(self, repo: str, environment: str, since: datetime) -> list[Deployment]:
        """Finished deployments to `environment` created on or after `since`."""
        result = []
        for item in self._pages(f"/repos/{repo}/deployments", {"environment": environment}):
            created_at = _parse(item["created_at"])
            if created_at < since:
                break  # newest first, so everything after this is older
            final = self._final_status(repo, item["id"])
            if final is None:
                continue  # still queued or in progress
            result.append(
                Deployment(
                    id=item["id"],
                    sha=item["sha"],
                    environment=item["environment"],
                    created_at=created_at,
                    state=final["state"],
                    finished_at=_parse(final["created_at"]),
                )
            )
        return result

    def _final_status(self, repo: str, deployment_id: int) -> dict | None:
        path = f"/repos/{repo}/deployments/{deployment_id}/statuses"
        for status in self._pages(path, {}):
            if status["state"] in FINAL_STATES:
                return status
        return None

    def merged_pull_requests(self, repo: str, base: str, since: datetime) -> list[PullRequest]:
        """PRs merged into `base` on or after `since`."""
        result = []
        params = {"state": "closed", "base": base, "sort": "updated", "direction": "desc"}
        for item in self._pages(f"/repos/{repo}/pulls", params):
            if _parse(item["updated_at"]) < since:
                break  # sorted by last update, newest first
            if not item["merged_at"] or _parse(item["merged_at"]) < since:
                continue  # closed without merging, or merged earlier
            result.append(
                PullRequest(
                    number=item["number"],
                    merged_at=_parse(item["merged_at"]),
                    first_commit_at=self._first_commit_at(repo, item["number"]),
                )
            )
        return result

    def _first_commit_at(self, repo: str, number: int) -> datetime:
        commits = self._pages(f"/repos/{repo}/pulls/{number}/commits", {})
        return min(_parse(c["commit"]["author"]["date"]) for c in commits)

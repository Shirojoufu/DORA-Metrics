"""The two kinds of event the DORA metrics are calculated from."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Deployment:
    id: int
    sha: str
    environment: str
    created_at: datetime
    # Final outcome: "success", "failure" or "error". Deployments still in
    # progress are left out before they get here.
    state: str
    # When that final status was set, i.e. when the change reached (or
    # failed to reach) the environment.
    finished_at: datetime

    @property
    def succeeded(self) -> bool:
        return self.state == "success"


@dataclass(frozen=True)
class PullRequest:
    number: int
    merged_at: datetime
    # Earliest commit in the PR: where the "commit to production" clock starts.
    first_commit_at: datetime

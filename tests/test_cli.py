"""CLI tests: a fake GitHub client and a fake save, so no network or database."""

import psycopg
import pytest

from dora_metrics import cli, store
from dora_metrics.cli import LOCAL_DATABASE_URL, main
from dora_metrics.github import RepoNotFound


class FakeGitHub:
    missing = False

    def __init__(self, token):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def default_branch(self, repo):
        if self.missing:
            raise RepoNotFound(repo)
        return "main"

    def deployments(self, repo, environment, since):
        return []

    def merged_pull_requests(self, repo, base, since):
        return []


class FakeSave:
    def __init__(self):
        self.urls = []
        self.fail = False

    def __call__(self, db, *_):
        self.urls.append(db)
        if self.fail:
            raise psycopg.OperationalError("connection refused")


@pytest.fixture
def save(monkeypatch):
    fake = FakeSave()
    monkeypatch.setattr(cli, "GitHub", FakeGitHub)
    monkeypatch.setattr(cli, "find_token", lambda: "t")
    monkeypatch.setattr(store, "save", fake)
    monkeypatch.delenv("DORA_DATABASE_URL", raising=False)
    return fake


def test_repo_as_argument_saves_to_compose_database(save, capsys):
    assert main(["acme/shop"]) == 0

    assert save.urls == [LOCAL_DATABASE_URL]
    assert "DORA metrics for acme/shop" in capsys.readouterr().out


def test_repo_option_still_works(save):
    assert main(["--repo", "acme/shop"]) == 0
    assert save.urls == [LOCAL_DATABASE_URL]


def test_no_repo_is_a_usage_error(save):
    with pytest.raises(SystemExit) as exit_:
        main([])
    assert exit_.value.code == 2


def test_default_database_down_still_prints_report(save, capsys):
    save.fail = True

    assert main(["acme/shop"]) == 0

    out, err = capsys.readouterr()
    assert "DORA metrics for acme/shop" in out
    assert "Not saved" in err


@pytest.mark.parametrize("source", ["option", "env"])
def test_chosen_database_down_is_an_error(save, monkeypatch, capsys, source):
    url = "postgresql://u:p@db.example:5432/dora"
    argv = ["acme/shop"]
    if source == "option":
        argv += ["--db", url]
    else:
        monkeypatch.setenv("DORA_DATABASE_URL", url)
    save.fail = True

    assert main(argv) == 1

    assert save.urls == [url]
    assert "Couldn't save to db.example:5432/dora" in capsys.readouterr().err


def test_missing_repo_explains_itself(save, monkeypatch, capsys):
    monkeypatch.setattr(FakeGitHub, "missing", True)

    assert main(["acme/nope"]) == 1

    assert "Repository acme/nope not found" in capsys.readouterr().err
    assert save.urls == []

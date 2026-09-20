from __future__ import annotations

import json
from io import BytesIO

import pytest

from jevtriage.github import GitHubError, apply_labels, fetch_pull_request, label_for


def test_label_names() -> None:
    assert label_for("ready") == "jev:ready"
    assert label_for("needs_review") == "jev:needs-review"
    assert label_for("risky") == "jev:risky"
    with pytest.raises(GitHubError):
        label_for("unknown")


class FakeResponse:
    def __init__(self, status: int, body: str, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeOpener:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[object] = []

    def __call__(self, request: object, timeout: int = 30) -> FakeResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected GitHub request")
        return self.responses.pop(0)


def test_fetch_pull_request(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = FakeOpener(
        [
            FakeResponse(
                200,
                json.dumps(
                    {
                        "title": "Fix typo",
                        "body": "nits",
                        "additions": 1,
                        "deletions": 0,
                        "changed_files": 1,
                    }
                ),
            ),
            FakeResponse(200, "diff --git a/README.md b/README.md\n"),
            FakeResponse(
                200,
                json.dumps(
                    [{"filename": "README.md", "status": "modified", "additions": 1, "deletions": 0, "changes": 1}]
                ),
            ),
        ]
    )
    pr = fetch_pull_request("acme/widgets", 7, token="t", opener=opener)
    assert pr["title"] == "Fix typo"
    assert pr["diff"].startswith("diff --git")
    assert pr["files"][0]["filename"] == "README.md"
    assert pr["stats"]["changed_files"] == 1


def test_apply_labels_replaces_stale_jev_label() -> None:
    opener = FakeOpener(
        [
            FakeResponse(200, json.dumps({"name": "jev:ready"})),
            FakeResponse(200, json.dumps({"name": "jev:needs-review"})),
            FakeResponse(200, json.dumps({"name": "jev:risky"})),
            FakeResponse(200, json.dumps([{"name": "jev:ready"}, {"name": "docs"}])),
            FakeResponse(200, ""),
            FakeResponse(200, json.dumps([{"name": "jev:risky"}])),
        ]
    )
    label = apply_labels("acme/widgets", 7, "risky", token="t", opener=opener)
    assert label == "jev:risky"
    methods = [getattr(req, "method", None) or req.get_method() for req in opener.requests]
    assert "DELETE" in methods
    assert "POST" in methods


def test_fetch_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(GitHubError, match="GITHUB_TOKEN"):
        fetch_pull_request("acme/widgets", 1, token=None)

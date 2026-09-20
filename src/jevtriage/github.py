"""Optional GitHub PR fetch and jev:* labels. Uses GITHUB_TOKEN only."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

LABELS = {
    "ready": "jev:ready",
    "needs_review": "jev:needs-review",
    "risky": "jev:risky",
}
LABEL_COLORS = {
    "jev:ready": "0E8A16",
    "jev:needs-review": "FBCA04",
    "jev:risky": "B60205",
}
API_VERSION = "2022-11-28"


class GitHubError(RuntimeError):
    """GitHub API or `gh` failure."""


def label_for(verdict: str) -> str:
    try:
        return LABELS[verdict]
    except KeyError as exc:
        raise GitHubError(f"no label mapping for verdict {verdict!r}") from exc


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def github_request(
    method: str,
    url: str,
    *,
    token: str,
    accept: str = "application/vnd.github+json",
    body: dict[str, Any] | None = None,
    opener: Any = None,
) -> tuple[int, str, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", accept)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", API_VERSION)
    request.add_header("User-Agent", "jevtriage")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            headers = {k.lower(): v for k, v in response.headers.items()}
            return int(response.status), raw, headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GitHubError(f"GitHub {method} {url} failed: {exc.code} {detail[:300]}") from exc


def fetch_pull_request(
    repo: str,
    number: int,
    *,
    token: str | None = None,
    opener: Any = None,
) -> dict[str, Any]:
    auth = token if token is not None else _token()
    if not auth:
        raise GitHubError("GITHUB_TOKEN (or GH_TOKEN) is required to fetch a pull request")
    owner, _, name = repo.partition("/")
    if not owner or not name:
        raise GitHubError(f"repository must be owner/name, got {repo!r}")
    base = f"https://api.github.com/repos/{owner}/{name}/pulls/{number}"
    _, pr_raw, _ = github_request("GET", base, token=auth, opener=opener)
    pr = json.loads(pr_raw)
    try:
        _, diff, _ = github_request(
            "GET",
            base,
            token=auth,
            accept="application/vnd.github.diff",
            opener=opener,
        )
    except GitHubError:
        diff = ""
    files: list[dict[str, Any]] = []
    page = 1
    while page <= 3:
        files_url = f"{base}/files?per_page=100&page={page}"
        _, files_raw, _ = github_request("GET", files_url, token=auth, opener=opener)
        batch = json.loads(files_raw)
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            files.append(
                {
                    "filename": item.get("filename"),
                    "status": item.get("status"),
                    "additions": item.get("additions"),
                    "deletions": item.get("deletions"),
                    "changes": item.get("changes"),
                }
            )
        if len(batch) < 100:
            break
        page += 1
    return {
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "diff": diff,
        "files": files,
        "stats": {
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "changed_files": pr.get("changed_files"),
        },
    }


def ensure_label(
    repo: str,
    name: str,
    *,
    token: str,
    opener: Any = None,
) -> None:
    owner, _, repo_name = repo.partition("/")
    encoded = urllib.parse.quote(name)
    url = f"https://api.github.com/repos/{owner}/{repo_name}/labels/{encoded}"
    try:
        github_request("GET", url, token=token, opener=opener)
        return
    except GitHubError:
        pass
    create = f"https://api.github.com/repos/{owner}/{repo_name}/labels"
    github_request(
        "POST",
        create,
        token=token,
        opener=opener,
        body={
            "name": name,
            "color": LABEL_COLORS.get(name, "ededed"),
            "description": f"jevtriage verdict ({name})",
        },
    )


def apply_labels(
    repo: str,
    number: int,
    verdict: str,
    *,
    token: str | None = None,
    opener: Any = None,
) -> str:
    auth = token if token is not None else _token()
    if not auth:
        raise GitHubError("GITHUB_TOKEN (or GH_TOKEN) is required to apply labels")
    label = label_for(verdict)
    owner, _, repo_name = repo.partition("/")
    if not owner or not repo_name:
        raise GitHubError(f"repository must be owner/name, got {repo!r}")
    for name in LABELS.values():
        try:
            ensure_label(repo, name, token=auth, opener=opener)
        except GitHubError:
            continue
    issue_url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{number}/labels"
    _, current_raw, _ = github_request("GET", issue_url, token=auth, opener=opener)
    current = {item.get("name") for item in json.loads(current_raw) if isinstance(item, dict)}
    stale = [name for name in LABELS.values() if name in current and name != label]
    for name in stale:
        encoded = urllib.parse.quote(name)
        delete_url = (
            f"https://api.github.com/repos/{owner}/{repo_name}/issues/{number}/labels/{encoded}"
        )
        try:
            github_request("DELETE", delete_url, token=auth, opener=opener)
        except GitHubError:
            continue
    if label not in current:
        github_request("POST", issue_url, token=auth, opener=opener, body={"labels": [label]})
    return label

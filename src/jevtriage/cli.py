"""jevtriage CLI — triage a pull request with TypeSafe Jev."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from jevtriage import __version__
from jevtriage.answers import AnswerError, TriageResult, adapt_response
from jevtriage.client import AUTH_ENV, MODEL_ENV, ApiError, ConfigError, JevClient, resolve_model
from jevtriage.gate import DEFAULT_MIN_CONFIDENCE, EXIT_RISKY_OR_ERROR, gate_exit
from jevtriage.github import GitHubError, apply_labels, fetch_pull_request
from jevtriage.pinning import ModelIdentityError, UnpinnedModelError
from jevtriage.state import DEFAULT_MAX_DIFF_CHARS, build_state


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _load_json_mapping(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ConfigError(f"{path} must contain a JSON object")
    return dict(payload)


def load_replay(path: str, *, case: str | None = None) -> dict[str, Any]:
    """Load a single SystemOneResponse or a jevcheck-style keyed replay."""
    payload = _load_json_mapping(path)
    if "answers" in payload and "model" in payload:
        return payload
    if case:
        if case not in payload:
            raise ConfigError(f"replay {path} has no case {case!r}")
        item = payload[case]
        if not isinstance(item, Mapping):
            raise ConfigError(f"replay case {case!r} must be a JSON object")
        return dict(item)
    if len(payload) == 1:
        only = next(iter(payload.values()))
        if isinstance(only, Mapping) and "answers" in only:
            return dict(only)
    raise ConfigError(
        f"replay {path} is keyed by case id; pass --case (one of {sorted(payload)})"
    )


def write_github_output(path: str, result: TriageResult) -> None:
    dest = Path(path)
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(f"verdict={result.verdict}\n")
        handle.write(f"confidence={result.confidence}\n")
        handle.write(f"model={result.model}\n")


def _emit(result: TriageResult, *, stdout: TextIO, stderr: TextIO) -> None:
    json.dump(result.as_dict(), stdout)
    stdout.write("\n")
    stderr.write(
        f"jevtriage: {result.verdict}  confidence={result.confidence:.3f}  "
        f"model={result.model}\n"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevtriage",
        description=(
            "Triage a pull request with TypeSafe Jev (ready / needs_review / risky)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"jevtriage {__version__}")
    parser.add_argument("--title", default="", help="Pull request title")
    parser.add_argument("--body", default="", help="Pull request body")
    parser.add_argument(
        "--diff",
        dest="diff_path",
        default="",
        help="Unified diff file, or - for stdin",
    )
    parser.add_argument(
        "--files-json",
        default="",
        help="Optional JSON array of file rows (filename, additions, deletions)",
    )
    parser.add_argument("--stats-json", default="", help="Optional JSON object of diff stats")
    parser.add_argument("--pr", type=int, default=0, help="Pull request number to fetch")
    parser.add_argument(
        "--repo",
        default="",
        help="owner/name (defaults to GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--model",
        default="",
        help=f"Pinned Jev model (else {MODEL_ENV}). Rejects latest/preview.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help=f"Minimum official ChoiceAnswer.confidence for exit 0 (default {DEFAULT_MIN_CONFIDENCE})",
    )
    parser.add_argument(
        "--max-diff-chars",
        type=int,
        default=DEFAULT_MAX_DIFF_CHARS,
        help=f"Unified diff cap (default {DEFAULT_MAX_DIFF_CHARS})",
    )
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="Opt in to floating latest/preview aliases (not for production)",
    )
    parser.add_argument(
        "--apply-labels",
        action="store_true",
        help="Apply jev:ready / jev:needs-review / jev:risky when GITHUB_TOKEN is set",
    )
    parser.add_argument(
        "--answers",
        default="",
        help="Replay a recorded System One JSON (skips the live TypeSafe call)",
    )
    parser.add_argument("--case", default="", help="Case id when --answers is a keyed replay")
    return parser


def _gather_state(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    title = args.title
    body = args.body
    diff = _read_text(args.diff_path) if args.diff_path else ""
    files = json.loads(Path(args.files_json).read_text(encoding="utf-8")) if args.files_json else None
    stats = _load_json_mapping(args.stats_json) if args.stats_json else None
    pr_number = args.pr
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")

    if (not title or not diff) and pr_number:
        if not repo:
            raise ConfigError("--repo or GITHUB_REPOSITORY is required with --pr")
        fetched = fetch_pull_request(repo, pr_number)
        title = title or fetched["title"]
        body = body or fetched["body"]
        diff = diff or fetched["diff"]
        files = files or fetched.get("files")
        stats = stats or fetched.get("stats")

    if not title and not args.answers:
        raise ConfigError("provide --title (and --diff), or --pr, or --answers")

    state = build_state(
        title=title or "(replay)",
        body=body,
        diff=diff,
        files=files if isinstance(files, list) else None,
        stats=stats if isinstance(stats, Mapping) else None,
        max_diff_chars=args.max_diff_chars,
    )
    return state, pr_number


def run(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    stderr = sys.stderr
    stdout = sys.stdout

    try:
        if args.min_confidence < 0.0 or args.min_confidence > 1.0:
            raise ConfigError("--min-confidence must be in [0, 1]")
        model = resolve_model(args.model or None, allow_unpinned=args.allow_unpinned)
        state, pr_number = _gather_state(args)

        if args.answers:
            raw = load_replay(args.answers, case=args.case or None)
            result = adapt_response(
                raw,
                truncated=bool(state.get("diff_truncated") or state.get("jevtriage_notes")),
            )
            from jevtriage.pinning import require_response_identity

            require_response_identity(result.model, model, allow_unpinned=args.allow_unpinned)
        else:
            if not os.environ.get(AUTH_ENV):
                raise ConfigError(f"{AUTH_ENV} is required for live calls (or pass --answers)")
            client = JevClient(model, allow_unpinned=args.allow_unpinned)
            result = client.system_one(state, model=model)

        _emit(result, stdout=stdout, stderr=stderr)
        output_path = os.environ.get("GITHUB_OUTPUT")
        if output_path:
            write_github_output(output_path, result)

        if args.apply_labels:
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
            if token and repo and pr_number:
                try:
                    label = apply_labels(repo, pr_number, result.verdict, token=token)
                    stderr.write(f"jevtriage: applied label {label}\n")
                except GitHubError as exc:
                    stderr.write(f"jevtriage: label apply failed (verdict unchanged): {exc}\n")
            else:
                stderr.write(
                    "jevtriage: --apply-labels ignored "
                    "(need GITHUB_TOKEN, --repo / GITHUB_REPOSITORY, and --pr)\n"
                )

        return gate_exit(
            result.verdict, result.confidence, min_confidence=args.min_confidence
        )
    except (ConfigError, UnpinnedModelError, ModelIdentityError, AnswerError) as exc:
        stderr.write(f"jevtriage: config error: {exc}\n")
        json.dump({"error": str(exc)}, stdout)
        stdout.write("\n")
        return EXIT_RISKY_OR_ERROR
    except (ApiError, GitHubError) as exc:
        stderr.write(f"jevtriage: error: {exc}\n")
        json.dump({"error": str(exc)}, stdout)
        stdout.write("\n")
        return EXIT_RISKY_OR_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())

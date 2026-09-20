"""Build the System One `state` object from PR title, body, and diff.

`state` may be a string or a JSON object (official SDK). We send an object
so truncation metadata stays structured. Diff is capped; when over the cap
we keep a prefix plus a clear note, and attach a file list + stats when
available.
"""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_MAX_DIFF_CHARS = 32_000
DEFAULT_MAX_BODY_CHARS = 8_000
DEFAULT_MAX_TITLE_CHARS = 500
DEFAULT_MAX_FILES = 80

TRUNCATION_NOTE = (
    "\n\n[jevtriage: truncated to {kept} of {original} characters; "
    "later content omitted]\n"
)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool, int]:
    """Return `(text, truncated, original_len)` with a visible truncation note.

    The cap applies to the kept prefix of the original text. The note is
    appended after that prefix so it is never dropped when the cap is small.
    """
    original = len(text)
    if original <= max_chars:
        return text, False, original
    kept = max(0, max_chars)
    note = TRUNCATION_NOTE.format(kept=kept, original=original)
    return text[:kept] + note, True, original


def build_state(
    *,
    title: str,
    body: str = "",
    diff: str = "",
    files: list[Mapping[str, Any]] | None = None,
    stats: Mapping[str, Any] | None = None,
    max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
    max_title_chars: int = DEFAULT_MAX_TITLE_CHARS,
    max_files: int = DEFAULT_MAX_FILES,
) -> dict[str, Any]:
    title_text, title_truncated, title_original = truncate_text(title, max_title_chars)
    body_text, body_truncated, body_original = truncate_text(body or "", max_body_chars)

    state: dict[str, Any] = {
        "title": title_text,
        "body": body_text,
    }
    notes: list[str] = []

    if title_truncated:
        notes.append(f"title truncated ({title_original} chars)")
    if body_truncated:
        notes.append(f"body truncated ({body_original} chars)")

    if diff:
        diff_text, diff_truncated, diff_original = truncate_text(diff, max_diff_chars)
        state["diff"] = diff_text
        state["diff_truncated"] = diff_truncated
        state["diff_original_chars"] = diff_original
        if diff_truncated:
            notes.append(
                f"unified diff truncated to {max_diff_chars} of {diff_original} characters"
            )
    else:
        state["diff"] = ""
        state["diff_truncated"] = False
        state["diff_original_chars"] = 0
        if files or stats:
            notes.append("unified diff omitted; using file list and stats")

    if files:
        file_list = [dict(item) for item in files[:max_files]]
        state["files"] = file_list
        if len(files) > max_files:
            state["files_truncated"] = True
            state["files_original_count"] = len(files)
            notes.append(f"file list truncated to {max_files} of {len(files)} files")
        else:
            state["files_truncated"] = False
    if stats:
        state["stats"] = dict(stats)

    if notes:
        state["jevtriage_notes"] = notes
    return state

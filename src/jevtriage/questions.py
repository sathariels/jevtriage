"""Verified System One choice used as the triage gate.

Official `Choice` fields only: `instructions` and required `criteria`
(`Mapping[str, desc | None]`). Exactly three criteria — do not add more.
"""

from __future__ import annotations

from typing import Any

TRIAGE_QUESTION_NAME = "triage"

TRIAGE_INSTRUCTIONS = (
    "Triage this pull request for merge readiness. Choose exactly one label. "
    "Use the pull request title, body, and the provided diff (or file list "
    "and stats when the diff is truncated or omitted)."
)

TRIAGE_CRITERIA: dict[str, str] = {
    "ready": (
        "Looks safe to merge with normal review depth. The change is focused, "
        "has low blast radius, and is not security-sensitive or destructive."
    ),
    "needs_review": (
        "Needs human eyes. Risk is unclear, or the change is large, "
        "ambiguous, or hard to assess from the provided context."
    ),
    "risky": (
        "Elevated risk. Security-sensitive, destructive, or high blast radius."
    ),
}

VERDICTS = frozenset(TRIAGE_CRITERIA)


def triage_questions() -> dict[str, Any]:
    """Return the official SDK `Choice` object keyed as System One expects."""
    from typesafe_sdk import Choice

    return {
        TRIAGE_QUESTION_NAME: Choice(
            instructions=TRIAGE_INSTRUCTIONS,
            criteria=dict(TRIAGE_CRITERIA),
        )
    }


def triage_question_wire() -> dict[str, Any]:
    """JSON-serializable question matching the official Choice schema."""
    return {
        "type": "choice",
        "instructions": TRIAGE_INSTRUCTIONS,
        "criteria": dict(TRIAGE_CRITERIA),
    }

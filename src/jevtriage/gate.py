"""Map a triage ChoiceAnswer onto process exit codes.

Exit codes (documented in README):

* ``0`` — ``ready`` and official ``confidence`` ≥ threshold
* ``1`` — ``needs_review``, or any verdict whose ``confidence`` is below threshold
* ``2`` — ``risky``, or an API / config / identity error (see CLI)

``risky`` with low confidence is still ``2`` (elevated risk wins).
A ``ready`` or ``needs_review`` answer below the threshold is ``1``
(human eyes; fail closed).
"""

from __future__ import annotations

EXIT_READY = 0
EXIT_NEEDS_REVIEW = 1
EXIT_RISKY_OR_ERROR = 2

DEFAULT_MIN_CONFIDENCE = 0.8


def gate_exit(verdict: str, confidence: float, *, min_confidence: float) -> int:
    if verdict == "risky":
        return EXIT_RISKY_OR_ERROR
    if confidence < min_confidence:
        return EXIT_NEEDS_REVIEW
    if verdict == "ready":
        return EXIT_READY
    if verdict == "needs_review":
        return EXIT_NEEDS_REVIEW
    return EXIT_RISKY_OR_ERROR

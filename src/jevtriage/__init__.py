"""jevtriage — PR triage gate using TypeSafe Jev (System One)."""

from __future__ import annotations

from jevtriage.gate import EXIT_NEEDS_REVIEW, EXIT_READY, EXIT_RISKY_OR_ERROR, gate_exit
from jevtriage.questions import TRIAGE_CRITERIA, TRIAGE_QUESTION_NAME

__version__ = "0.1.0"

__all__ = [
    "EXIT_NEEDS_REVIEW",
    "EXIT_READY",
    "EXIT_RISKY_OR_ERROR",
    "TRIAGE_CRITERIA",
    "TRIAGE_QUESTION_NAME",
    "__version__",
    "gate_exit",
]

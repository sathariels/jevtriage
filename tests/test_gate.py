from __future__ import annotations

from jevtriage.gate import EXIT_NEEDS_REVIEW, EXIT_READY, EXIT_RISKY_OR_ERROR, gate_exit


def test_ready_at_or_above_threshold() -> None:
    assert gate_exit("ready", 0.8, min_confidence=0.8) == EXIT_READY
    assert gate_exit("ready", 0.94, min_confidence=0.8) == EXIT_READY


def test_ready_below_threshold_is_needs_review() -> None:
    assert gate_exit("ready", 0.79, min_confidence=0.8) == EXIT_NEEDS_REVIEW


def test_needs_review() -> None:
    assert gate_exit("needs_review", 0.99, min_confidence=0.8) == EXIT_NEEDS_REVIEW
    assert gate_exit("needs_review", 0.1, min_confidence=0.8) == EXIT_NEEDS_REVIEW


def test_risky_wins_even_with_low_confidence() -> None:
    assert gate_exit("risky", 0.99, min_confidence=0.8) == EXIT_RISKY_OR_ERROR
    assert gate_exit("risky", 0.1, min_confidence=0.8) == EXIT_RISKY_OR_ERROR


def test_unknown_verdict_is_error() -> None:
    assert gate_exit("unknown", 0.99, min_confidence=0.8) == EXIT_RISKY_OR_ERROR

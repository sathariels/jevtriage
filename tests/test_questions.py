from __future__ import annotations

from jevtriage.questions import (
    TRIAGE_CRITERIA,
    TRIAGE_INSTRUCTIONS,
    TRIAGE_QUESTION_NAME,
    VERDICTS,
    triage_question_wire,
)


def test_exactly_three_criteria() -> None:
    assert TRIAGE_QUESTION_NAME == "triage"
    assert set(TRIAGE_CRITERIA) == {"ready", "needs_review", "risky"}
    assert set(VERDICTS) == set(TRIAGE_CRITERIA)
    assert len(TRIAGE_CRITERIA) == 3
    wire = triage_question_wire()
    assert wire["type"] == "choice"
    assert wire["instructions"] == TRIAGE_INSTRUCTIONS
    assert set(wire["criteria"]) == {"ready", "needs_review", "risky"}
    assert "confidence" not in wire

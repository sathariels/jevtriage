from __future__ import annotations

import pytest

from jevtriage.answers import AnswerError, adapt_choice_answer, adapt_response


READY = {
    "type": "choice",
    "choice": "ready",
    "confidence": 0.94,
    "probabilities": {"ready": 0.94, "needs_review": 0.04, "risky": 0.02},
}


def test_adapt_official_choice() -> None:
    verdict, confidence, probs = adapt_choice_answer(READY)
    assert verdict == "ready"
    assert confidence == 0.94
    assert probs["ready"] == 0.94


def test_rejects_missing_official_fields() -> None:
    with pytest.raises(AnswerError, match="confidence"):
        adapt_choice_answer({"choice": "ready"})
    with pytest.raises(AnswerError, match="probabilities"):
        adapt_choice_answer({"choice": "ready", "confidence": 0.9})


def test_rejects_unknown_choice_and_bad_probs() -> None:
    with pytest.raises(AnswerError, match="not one of"):
        adapt_choice_answer({"choice": "merge-it", "confidence": 0.9, "probabilities": {"merge-it": 1.0}})
    with pytest.raises(AnswerError, match="sum"):
        adapt_choice_answer(
            {"choice": "ready", "confidence": 0.9, "probabilities": {"ready": 0.5, "risky": 0.1}}
        )


def test_adapt_response_and_choices_helper() -> None:
    raw = {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 4, "output_tokens": 2},
        "answers": {"triage": READY},
    }
    result = adapt_response(raw, truncated=True)
    assert result.verdict == "ready"
    assert result.model == "jev-1.13.0"
    assert result.usage.input_tokens == 4
    assert result.truncated is True

    class _Resp:
        model = "jev-1.13.0"
        usage = {"input_tokens": None, "output_tokens": None}
        answers = {}
        choices = {"triage": READY}

    helper = adapt_response(_Resp())
    assert helper.verdict == "ready"


def test_adapt_response_requires_triage() -> None:
    with pytest.raises(AnswerError, match="triage"):
        adapt_response({"model": "jev-1.13.0", "answers": {"other": READY}})
    with pytest.raises(AnswerError, match="model"):
        adapt_response({"answers": {"triage": READY}})

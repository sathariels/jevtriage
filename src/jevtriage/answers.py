"""Adapt official System One ChoiceAnswer fields only.

Verified ChoiceAnswer: `choice`, `confidence` in [0, 1], `probabilities`.
Verified response: `model`, `usage`, `answers`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from jevtriage.questions import TRIAGE_QUESTION_NAME, VERDICTS

PROBABILITY_SUM_TOLERANCE = 1e-6


class AnswerError(ValueError):
    """Raised when a response is missing required official Choice fields."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class TriageResult:
    verdict: str
    confidence: float
    probabilities: dict[str, float]
    model: str
    usage: Usage
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "probabilities": dict(self.probabilities),
            "model": self.model,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
            },
            "truncated": self.truncated,
        }


def _to_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if hasattr(raw, "model_dump"):
        dumped = raw.model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    skip = {"model_config", "model_fields", "model_computed_fields"}
    if hasattr(raw, "__dict__"):
        dumped = {k: v for k, v in vars(raw).items() if not k.startswith("_") and k not in skip}
        if dumped:
            return dumped
    public = {
        name: getattr(raw, name)
        for name in (
            "choice",
            "confidence",
            "probabilities",
            "type",
            "model",
            "usage",
            "answers",
            "input_tokens",
            "output_tokens",
        )
        if hasattr(raw, name)
    }
    if public:
        return public
    raise TypeError(f"cannot adapt {type(raw).__name__} to a mapping")


def _finite_unit_interval(value: Any, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AnswerError(f"{what} must be a finite number") from exc
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise AnswerError(f"{what} must be a finite number in [0, 1]")
    return number


def _probabilities(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping) or not raw:
        raise AnswerError("choice probabilities must be a nonempty mapping")
    cleaned: dict[str, float] = {}
    for key, item in raw.items():
        try:
            number = float(item)
        except (TypeError, ValueError) as exc:
            raise AnswerError(f"probability {key!r} must be a finite number") from exc
        if not math.isfinite(number) or number < 0.0:
            raise AnswerError(f"probability {key!r} must be a finite number >= 0")
        cleaned[str(key)] = number
    total = math.fsum(cleaned.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise AnswerError(
            f"choice probabilities must sum to 1 ± {PROBABILITY_SUM_TOLERANCE}; got {total}"
        )
    return cleaned


def adapt_choice_answer(raw: Any) -> tuple[str, float, dict[str, float]]:
    data = _to_mapping(raw)
    if "choice" not in data or "confidence" not in data:
        raise AnswerError("ChoiceAnswer requires official fields choice and confidence")
    verdict = str(data["choice"]).strip()
    if verdict not in VERDICTS:
        raise AnswerError(
            f"choice {verdict!r} is not one of {sorted(VERDICTS)}"
        )
    confidence = _finite_unit_interval(data["confidence"], "choice confidence")
    if "probabilities" not in data:
        raise AnswerError("ChoiceAnswer requires official field probabilities")
    probabilities = _probabilities(data["probabilities"])
    return verdict, confidence, probabilities


def adapt_usage(raw: Any) -> Usage:
    if raw is None:
        return Usage()
    data = _to_mapping(raw) if not isinstance(raw, Usage) else {
        "input_tokens": raw.input_tokens,
        "output_tokens": raw.output_tokens,
    }
    input_tokens = data.get("input_tokens")
    output_tokens = data.get("output_tokens")
    return Usage(
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
    )


def _answers_from_response(data: Mapping[str, Any], raw: Any) -> Mapping[str, Any]:
    answers = data.get("answers")
    if isinstance(answers, Mapping) and answers:
        return answers
    choices = None
    if hasattr(raw, "choices"):
        choices = getattr(raw, "choices")
    elif "choices" in data:
        choices = data["choices"]
    if isinstance(choices, Mapping) and choices:
        return choices
    raise AnswerError("response is missing answers (or choices helper)")


def adapt_response(raw: Any, *, truncated: bool = False) -> TriageResult:
    data = _to_mapping(raw)
    model = data.get("model")
    if not isinstance(model, str) or not model.strip():
        raise AnswerError("response.model must be a nonempty string")
    answers = _answers_from_response(data, raw)
    if TRIAGE_QUESTION_NAME not in answers:
        raise AnswerError(f"response.answers is missing {TRIAGE_QUESTION_NAME!r}")
    verdict, confidence, probabilities = adapt_choice_answer(answers[TRIAGE_QUESTION_NAME])
    return TriageResult(
        verdict=verdict,
        confidence=confidence,
        probabilities=probabilities,
        model=model.strip(),
        usage=adapt_usage(data.get("usage")),
        truncated=truncated,
    )

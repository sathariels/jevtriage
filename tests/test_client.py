from __future__ import annotations

from types import SimpleNamespace

import pytest

from jevtriage.client import ApiError, ConfigError, JevClient, resolve_model
from jevtriage.questions import TRIAGE_CRITERIA, TRIAGE_QUESTION_NAME, VERDICTS


class FakeSdk:
    def __init__(self, raw: object | None = None, *, error: Exception | None = None) -> None:
        self.raw = raw
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.closed = False

    def system_one(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.raw

    def close(self) -> None:
        self.closed = True


def _ready_response(model: str = "jev-1.13.0") -> dict[str, object]:
    return {
        "model": model,
        "usage": {"input_tokens": 10, "output_tokens": 3},
        "answers": {
            "triage": {
                "type": "choice",
                "choice": "ready",
                "confidence": 0.91,
                "probabilities": {"ready": 0.91, "needs_review": 0.06, "risky": 0.03},
            }
        },
    }


def test_system_one_sends_official_choice_and_pin() -> None:
    sdk = FakeSdk(_ready_response())
    client = JevClient("jev-1.13.0", api_key="test-key", sdk_client=sdk)
    result = client.system_one({"title": "Fix typo", "body": "", "diff": "x"})
    assert result.verdict == "ready"
    assert result.confidence == 0.91
    assert result.model == "jev-1.13.0"
    call = sdk.calls[0]
    assert call["model"] == "jev-1.13.0"
    questions = call["questions"]
    assert isinstance(questions, dict)
    assert TRIAGE_QUESTION_NAME in questions
    choice = questions[TRIAGE_QUESTION_NAME]
    assert getattr(choice, "type", "choice") == "choice" or type(choice).__name__ == "Choice"
    criteria = getattr(choice, "criteria")
    assert set(criteria) == set(VERDICTS)
    assert set(criteria) == set(TRIAGE_CRITERIA)


def test_identity_mismatch_is_api_error() -> None:
    sdk = FakeSdk(_ready_response("jev-other"))
    client = JevClient("jev-1.13.0", api_key="test-key", sdk_client=sdk)
    with pytest.raises(ApiError, match="does not match"):
        client.system_one({"title": "x"})


def test_sdk_exception_is_api_error() -> None:
    sdk = FakeSdk(error=RuntimeError("boom"))
    client = JevClient("jev-1.13.0", api_key="test-key", sdk_client=sdk)
    with pytest.raises(ApiError, match="system_one failed"):
        client.system_one({"title": "x"})


def test_missing_key_without_injected_client() -> None:
    client = JevClient("jev-1.13.0", api_key="")
    with pytest.raises(ConfigError, match="TYPESAFE_API_KEY"):
        client._open_sdk("jev-1.13.0")


def test_resolve_model_env_and_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TYPESAFE_DEFAULT_MODEL", raising=False)
    with pytest.raises(ConfigError, match="model pin required"):
        resolve_model(None)
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "jev-1.13.0")
    assert resolve_model(None) == "jev-1.13.0"
    assert resolve_model("jev-1.14.0") == "jev-1.14.0"
    with pytest.raises(Exception, match="unpinned"):
        resolve_model("jev-latest")


def test_namespace_response() -> None:
    sdk = FakeSdk(
        SimpleNamespace(
            model="jev-1.13.0",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            answers={
                "triage": SimpleNamespace(
                    choice="needs_review",
                    confidence=0.82,
                    probabilities={"ready": 0.1, "needs_review": 0.82, "risky": 0.08},
                )
            },
        )
    )
    result = JevClient("jev-1.13.0", api_key="k", sdk_client=sdk).system_one({"title": "x"})
    assert result.verdict == "needs_review"

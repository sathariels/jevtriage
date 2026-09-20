from __future__ import annotations

import json
from pathlib import Path

import pytest

from jevtriage.cli import load_replay, main, write_github_output
from jevtriage.client import JevClient
from jevtriage.answers import adapt_response

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_load_single_and_keyed_replay() -> None:
    single = load_replay(str(FIXTURES / "replay-single-ready.json"))
    assert single["answers"]["triage"]["choice"] == "ready"
    keyed = load_replay(str(FIXTURES / "replay-ready.json"), case="auth-bypass")
    assert keyed["answers"]["triage"]["choice"] == "risky"
    with pytest.raises(Exception, match="--case"):
        load_replay(str(FIXTURES / "replay-ready.json"))


def test_cli_replay_ready(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-single-ready.json"),
            "--model",
            "jev-1.13.0",
            "--title",
            "Fix typo in README",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "ready"
    assert payload["confidence"] == 0.94
    assert payload["model"] == "jev-1.13.0"
    assert set(payload["probabilities"]) == {"ready", "needs_review", "risky"}


def test_cli_replay_needs_review() -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-ready.json"),
            "--case",
            "large-ambiguous",
            "--model",
            "jev-1.13.0",
        ]
    )
    assert code == 1


def test_cli_replay_risky() -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-ready.json"),
            "--case",
            "auth-bypass",
            "--model",
            "jev-1.13.0",
        ]
    )
    assert code == 2


def test_cli_ready_below_threshold() -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-single-ready.json"),
            "--model",
            "jev-1.13.0",
            "--min-confidence",
            "0.99",
        ]
    )
    assert code == 1


def test_cli_rejects_unpinned(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-single-ready.json"),
            "--model",
            "jev-latest",
        ]
    )
    assert code == 2
    err = capsys.readouterr()
    assert "unpinned" in err.err.lower() or "unpinned" in err.out.lower()


def test_cli_missing_key_for_live(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "jev-1.13.0")
    code = main(["--title", "Fix typo", "--diff", "/dev/null"])
    assert code == 2
    assert "TYPESAFE_API_KEY" in capsys.readouterr().err


def test_cli_writes_github_output(tmp_path: Path) -> None:
    result = adapt_response(
        json.loads((FIXTURES / "replay-single-ready.json").read_text(encoding="utf-8"))
    )
    dest = tmp_path / "output"
    write_github_output(str(dest), result)
    text = dest.read_text(encoding="utf-8")
    assert "verdict=ready\n" in text
    assert "confidence=0.94\n" in text
    assert "model=jev-1.13.0\n" in text


def test_cli_github_output_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "github_output"
    dest.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(dest))
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-single-ready.json"),
            "--model",
            "jev-1.13.0",
        ]
    )
    assert code == 0
    assert "verdict=ready" in dest.read_text(encoding="utf-8")


def test_cli_identity_mismatch() -> None:
    code = main(
        [
            "--answers",
            str(FIXTURES / "replay-single-ready.json"),
            "--model",
            "jev-9.9.9",
        ]
    )
    assert code == 2


def test_mocked_live_path(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeSdk:
        def system_one(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["model"] == "jev-1.13.0"
            return json.loads((FIXTURES / "replay-single-ready.json").read_text(encoding="utf-8"))

        def close(self) -> None:
            return None

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr(JevClient, "_open_sdk", lambda self, model: FakeSdk())
    code = main(["--title", "Fix typo", "--model", "jev-1.13.0"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "ready"

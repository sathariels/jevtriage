from __future__ import annotations

import json
from pathlib import Path

from jevtriage.answers import adapt_response
from jevtriage.cli import load_replay
from jevtriage.gate import gate_exit
from jevtriage.questions import TRIAGE_CRITERIA, TRIAGE_INSTRUCTIONS, TRIAGE_QUESTION_NAME

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "fixtures" / "pr-triage.contract.json").read_text(encoding="utf-8"))
REPLAY = json.loads((ROOT / "fixtures" / "replay-ready.json").read_text(encoding="utf-8"))


def test_contract_is_jevcheck_shaped() -> None:
    assert CONTRACT["version"] == "0.1"
    assert CONTRACT["baseline_model"] == "jev-1.13.0"
    ids = [case["id"] for case in CONTRACT["cases"]]
    assert ids == ["docs-typo", "large-ambiguous", "auth-bypass"]
    for case in CONTRACT["cases"]:
        question = case["questions"][TRIAGE_QUESTION_NAME]
        assert question["type"] == "choice"
        assert question["instructions"] == TRIAGE_INSTRUCTIONS
        assert set(question["criteria"]) == set(TRIAGE_CRITERIA)
        assert set(case["expect"][TRIAGE_QUESTION_NAME]) >= {"choice", "min_confidence"}


def test_replay_matches_contract_expectations() -> None:
    expected_exit = {"ready": 0, "needs_review": 1, "risky": 2}
    for case in CONTRACT["cases"]:
        raw = load_replay(str(ROOT / "fixtures" / "replay-ready.json"), case=case["id"])
        result = adapt_response(raw)
        expect = case["expect"][TRIAGE_QUESTION_NAME]
        assert result.verdict == expect["choice"]
        assert result.confidence >= expect["min_confidence"]
        assert result.model == CONTRACT["baseline_model"]
        assert gate_exit(result.verdict, result.confidence, min_confidence=0.8) == expected_exit[result.verdict]
        assert case["id"] in REPLAY

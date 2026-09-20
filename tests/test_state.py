from __future__ import annotations

from jevtriage.state import build_state, truncate_text


def test_short_text_is_not_truncated() -> None:
    text, truncated, original = truncate_text("hello", 32)
    assert text == "hello"
    assert truncated is False
    assert original == 5


def test_long_text_includes_note() -> None:
    text, truncated, original = truncate_text("x" * 80, 40)
    assert truncated is True
    assert original == 80
    assert "truncated to 40 of 80" in text
    assert text.startswith("x")


def test_build_state_keeps_small_diff() -> None:
    state = build_state(title="Fix typo", body="nits", diff="diff --git a/a b/a\n")
    assert state["title"] == "Fix typo"
    assert state["diff_truncated"] is False
    assert state["diff"].startswith("diff --git")
    assert "jevtriage_notes" not in state


def test_build_state_truncates_diff_and_keeps_stats() -> None:
    state = build_state(
        title="Big change",
        body="see diff",
        diff="+" * 200,
        files=[{"filename": "a.py", "additions": 1, "deletions": 0}],
        stats={"additions": 200, "deletions": 0, "changed_files": 1},
        max_diff_chars=80,
    )
    assert state["diff_truncated"] is True
    assert state["diff_original_chars"] == 200
    assert "truncated" in state["diff"]
    assert state["files"][0]["filename"] == "a.py"
    assert state["stats"]["changed_files"] == 1
    assert any("unified diff truncated" in note for note in state["jevtriage_notes"])


def test_omitted_diff_uses_file_list_note() -> None:
    state = build_state(
        title="Refactor",
        files=[{"filename": "a.py"}],
        stats={"changed_files": 1},
    )
    assert state["diff"] == ""
    assert "unified diff omitted" in state["jevtriage_notes"][0]


def test_file_list_truncated() -> None:
    files = [{"filename": f"f{i}.py"} for i in range(10)]
    state = build_state(title="many", files=files, max_files=3)
    assert len(state["files"]) == 3
    assert state["files_truncated"] is True
    assert state["files_original_count"] == 10

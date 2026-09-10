"""Detecting a run that never happened."""

from __future__ import annotations

from flightrec.models import Cassette, RunMeta, Span, ToolCall

from whetstone.capture import _refusal_text

REFUSAL = "You've hit your session limit · resets 10:40am (America/Los_Angeles)"


def synthetic_turn(text: str) -> Span:
    return Span(
        id=1,
        kind="llm",
        name="claude-code.turn.1",
        model="<synthetic>",
        response={"content": [{"type": "text", "text": text}], "role": "assistant"},
    )


def test_a_usage_limit_refusal_is_recognised() -> None:
    """The exact shape sixteen of this project's v2 runs came back in."""
    cassette = Cassette(
        meta=RunMeta(name="r", labels={"is_error": "true", "num_turns": "1"}),
        spans=[synthetic_turn(REFUSAL)],
    )
    detected = _refusal_text(cassette)
    assert detected is not None
    assert "session limit" in detected


def test_a_real_run_is_not_mistaken_for_a_refusal() -> None:
    cassette = Cassette(
        meta=RunMeta(name="r", labels={"is_error": "false"}),
        spans=[
            Span(id=1, kind="llm", name="turn", model="claude-opus-5"),
            Span(id=2, kind="tool", name="Read", tool=ToolCall(name="Read", arguments={})),
        ],
    )
    assert _refusal_text(cassette) is None


def test_a_failed_run_that_used_tools_is_not_a_refusal() -> None:
    """An error flag alone is not enough; the agent may have worked and failed."""
    cassette = Cassette(
        meta=RunMeta(name="r", labels={"is_error": "true"}),
        spans=[
            Span(id=1, kind="llm", name="turn", model="claude-opus-5"),
            Span(id=2, kind="tool", name="Bash", tool=ToolCall(name="Bash", arguments={})),
        ],
    )
    assert _refusal_text(cassette) is None

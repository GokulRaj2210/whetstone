"""The report's job is to make its own limits visible.

A results table that only lists what reached significance turns a null
experiment into a positive one, and the omission is invisible to the reader.
These tests pin the parts that stop that happening.
"""

from __future__ import annotations

import io
import random

from rich.console import Console

from whetstone.analyze import analyze
from whetstone.report import console_report, markdown_report
from whetstone.results import RunRecord
from whetstone.spec import Experiment

SPEC = {
    "name": "t",
    "arms": [{"name": "control", "skill": None}, {"name": "treat", "skill": "s"}],
    "metrics": [
        {"name": "reads", "family": "primary", "direction": "higher_is_better", "rationale": "r"},
        {"name": "flat", "family": "primary", "rationale": "r"},
        {"name": "tokens", "rationale": "r"},
    ],
}


def build(effect: float = 0.0, n: int = 12) -> object:
    spec = Experiment.from_dict(SPEC)
    rng = random.Random(1)
    records = []
    for index in range(n):
        base = rng.uniform(1, 10)
        for arm, shift in (("control", 0.0), ("treat", effect)):
            records.append(
                RunRecord(
                    task=f"t{index}",
                    arm=arm,
                    repeat=0,
                    spec_digest=spec.digest,
                    task_success=True,
                    duration_s=1.0,
                    metrics={
                        "reads": base + shift,
                        "flat": base + rng.gauss(0, 3),
                        "tokens": base * 100,
                    },
                )
            )
    return analyze(spec, records)


def render(analysis: object) -> str:
    buffer = io.StringIO()
    console_report(analysis, Console(file=buffer, width=140, no_color=True))
    return buffer.getvalue()


def test_every_declared_metric_gets_a_row_even_when_flat() -> None:
    """Listing only the movers is how an experiment gets over-claimed."""
    text = render(build(effect=3.0))
    for metric in ("reads", "flat", "tokens"):
        assert metric in text


def test_an_unresolved_metric_is_not_reported_as_no_effect() -> None:
    """ "We found nothing" and "we could not have seen it" are different claims."""
    text = render(build(effect=0.0))
    assert "Nothing resolved" in text
    assert "power" in text
    assert "MDE" in text


def test_exploratory_metrics_are_labelled_as_such() -> None:
    text = render(build(effect=3.0))
    assert "exploratory" in text
    assert "not evidence for a claim" in text


def test_behaviour_and_outcome_are_kept_apart() -> None:
    """The sentence that stops a reader turning a tool-use delta into a quality claim."""
    # Asserted on a short fragment: rich wraps at the console width, and a
    # long substring check would pass locally and fail on a narrower CI terminal.
    text = render(build(effect=3.0))
    assert "Behaviour and outcome are separate claims" in text
    assert "task_success" in text


def test_the_spec_digest_is_always_printed() -> None:
    """Without it a reader cannot check the metrics were declared in advance."""
    analysis = build(effect=1.0)
    assert analysis.experiment.digest in render(analysis)
    assert analysis.experiment.digest in markdown_report(analysis)


def test_the_markdown_table_has_a_row_per_metric() -> None:
    markdown = markdown_report(build(effect=2.0))
    body = [line for line in markdown.splitlines() if line.startswith("| ")]
    assert len(body) == 1 + 3, "a header plus one row per declared metric"


def test_a_resolved_primary_metric_is_marked_in_markdown() -> None:
    markdown = markdown_report(build(effect=5.0))
    assert "**" in markdown, "a resolved effect should stand out in the table"


def test_an_identical_primary_metric_is_called_out_as_a_ceiling_effect() -> None:
    """The most dangerous row in the table gets a sentence of its own.

    Identical arms read as "no effect" and almost always mean "this metric had
    no room to move". Reporting the first when it is the second is how a
    badly-calibrated task suite turns into a finding about the skill.
    """
    spec = Experiment.from_dict(SPEC)
    records = [
        RunRecord(
            task=f"t{index}",
            arm=arm,
            repeat=0,
            spec_digest=spec.digest,
            task_success=True,
            duration_s=1.0,
            metrics={"reads": 1.0, "flat": 1.0, "tokens": 1.0},
        )
        for index in range(8)
        for arm in ("control", "treat")
    ]
    text = render(analyze(spec, records))
    assert "identical in every pair" in text
    assert "no room to move" in text

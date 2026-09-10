"""The pre-registration, which is what makes the rest of the numbers mean anything."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from whetstone.spec import Experiment, SpecError

MINIMAL = """
name: demo
arms:
  - name: control
    skill: null
  - name: treatment
    skill: deep-work
metrics:
  task_success:
    kind: binary
    family: primary
    rationale: the outcome
  total_tokens:
    rationale: the cost
"""


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "experiment.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_a_minimal_experiment_loads(tmp_path: Path) -> None:
    spec = Experiment.load(write(tmp_path, MINIMAL))
    assert spec.baseline.name == "control"
    assert spec.treatment.skill == "deep-work"
    assert [m.name for m in spec.primary] == ["task_success"]


def test_the_digest_is_stable_across_formatting(tmp_path: Path) -> None:
    """Reformatting the YAML must not look like a different experiment.

    Otherwise the digest cries wolf on a whitespace change and people stop
    reading it, which defeats the entire mechanism.
    """
    first = Experiment.load(write(tmp_path, MINIMAL))
    reflowed = "# a comment that changes nothing\n" + MINIMAL.replace(
        "metrics:", "\n\nmetrics:"
    ).replace("name: demo", 'name: "demo"')
    second = Experiment.load(write(tmp_path, reflowed))
    assert first.digest == second.digest


def test_the_digest_changes_when_a_metric_changes(tmp_path: Path) -> None:
    """The half that matters: a silent change to what is measured cannot happen."""
    first = Experiment.load(write(tmp_path, MINIMAL))
    altered = MINIMAL.replace("direction: lower_is_better", "").replace(
        "  total_tokens:\n    rationale: the cost",
        "  total_tokens:\n    rationale: the cost\n  tool_calls:\n    rationale: added later",
    )
    second = Experiment.load(write(tmp_path, altered))
    assert first.digest != second.digest


def test_scoring_an_undeclared_metric_is_refused(tmp_path: Path) -> None:
    """The core refusal. Picking metrics after seeing results is the whole hazard."""
    spec = Experiment.load(write(tmp_path, MINIMAL))
    with pytest.raises(SpecError, match="not pre-registered"):
        spec.metric("something_that_moved")


def test_a_metric_without_a_rationale_is_refused(tmp_path: Path) -> None:
    """A metric nobody can justify in advance was added to raise the odds."""
    body = MINIMAL.replace("  total_tokens:\n    rationale: the cost", "  total_tokens: {}")
    with pytest.raises(SpecError, match="rationale"):
        Experiment.load(write(tmp_path, body))


def test_the_control_arm_may_not_carry_a_skill(tmp_path: Path) -> None:
    """Order is load-bearing: every delta is treatment minus baseline."""
    body = MINIMAL.replace("  - name: control\n    skill: null", "  - name: control\n    skill: x")
    with pytest.raises(SpecError, match="must have no skill"):
        Experiment.load(write(tmp_path, body))


def test_an_experiment_needs_a_primary_metric(tmp_path: Path) -> None:
    body = MINIMAL.replace("    family: primary\n", "")
    with pytest.raises(SpecError, match="primary"):
        Experiment.load(write(tmp_path, body))


def test_too_many_primary_metrics_are_refused(tmp_path: Path) -> None:
    """Correcting across a large family costs more power than n can afford."""
    extra = "".join(f"  m{i}:\n    family: primary\n    rationale: r\n" for i in range(5))
    with pytest.raises(SpecError, match="too many"):
        Experiment.load(write(tmp_path, MINIMAL + extra))


def test_duplicate_metrics_are_refused(tmp_path: Path) -> None:
    spec = {
        "name": "d",
        "arms": [{"name": "c"}, {"name": "t", "skill": "s"}],
        "metrics": [
            {"name": "a", "rationale": "r", "family": "primary"},
            {"name": "a", "rationale": "r"},
        ],
    }
    with pytest.raises(SpecError, match="declared twice"):
        Experiment.from_dict(spec)


def test_exactly_two_arms_are_required(tmp_path: Path) -> None:
    body = MINIMAL.replace("  - name: treatment\n    skill: deep-work\n", "")
    with pytest.raises(SpecError, match="two arms"):
        Experiment.load(write(tmp_path, body))


def test_the_shipped_experiments_are_valid() -> None:
    """The specs this project's own results come from must load and differ."""
    root = Path(__file__).resolve().parent.parent / "experiments"
    deep = Experiment.load(root / "deep-work.yaml")
    placebo = Experiment.load(root / "placebo.yaml")
    assert deep.digest != placebo.digest, "the control experiment must be a distinct declaration"
    assert deep.treatment.skill == "deep-work"
    assert placebo.treatment.skill == "placebo"
    assert {m.name for m in deep.primary} == {m.name for m in placebo.primary}, (
        "the placebo must test the same primary metrics or it is not a control"
    )


def test_adding_a_metric_does_not_invalidate_existing_runs(tmp_path: Path) -> None:
    """The split that lets a measurement bug be fixed rather than buried.

    A metric shapes the analysis; the arms and repeats shape the evidence. Under
    one hash, correcting a bad metric would invalidate the very records the bug
    was found in -- which rewards leaving it alone.
    """
    before = Experiment.load(write(tmp_path, MINIMAL))
    after = Experiment.load(
        write(tmp_path, MINIMAL + "  added:\n    rationale: found later\n")
    )
    assert before.run_digest == after.run_digest, "the runs were not affected"
    assert before.digest != after.digest, "but the analysis was, and it must show"


def test_changing_an_arm_does_invalidate_existing_runs(tmp_path: Path) -> None:
    """The other half: a different intervention is different evidence."""
    before = Experiment.load(write(tmp_path, MINIMAL))
    after = Experiment.load(
        write(tmp_path, MINIMAL.replace("skill: deep-work", "skill: something-else"))
    )
    assert before.run_digest != after.run_digest

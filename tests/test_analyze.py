"""Pairing, analysis, and the harness's own negative control.

The most important test in this file is
`test_the_harness_finds_nothing_in_a_null_experiment`. A tool that detects
effects in noise is worse than no tool, because it produces confident writeups
of things that did not happen. Everything else here is scaffolding for that one.
"""

from __future__ import annotations

import random

import pytest

from whetstone.analyze import analyze
from whetstone.results import RunRecord, pair_by_task
from whetstone.spec import Experiment, SpecError
from whetstone.stats import Verdict

SPEC = {
    "name": "t",
    "repeats": 2,
    "arms": [{"name": "control", "skill": None}, {"name": "treat", "skill": "s"}],
    "metrics": [
        {"name": "task_success", "kind": "binary", "family": "primary", "rationale": "r"},
        {"name": "reads", "family": "primary", "direction": "higher_is_better", "rationale": "r"},
        {"name": "tokens", "rationale": "r"},
    ],
}


def record(task: str, arm: str, repeat: int, **metrics: float) -> RunRecord:
    success = bool(metrics.pop("task_success", 0.0))
    return RunRecord(
        task=task,
        arm=arm,
        repeat=repeat,
        spec_digest=Experiment.from_dict(SPEC).digest,
        task_success=success,
        duration_s=1.0,
        metrics=dict(metrics),
    )


# --- pairing ---------------------------------------------------------------


def test_repeats_are_averaged_into_one_value_per_task() -> None:
    """Repeats reduce noise; they must not inflate n.

    Treating each repeat as its own observation would multiply the apparent
    sample size and manufacture significance out of variance the paired design
    exists to cancel.
    """
    records = [
        record("a", "control", 0, reads=2.0),
        record("a", "control", 1, reads=4.0),
        record("a", "treat", 0, reads=6.0),
        record("a", "treat", 1, reads=8.0),
    ]
    tasks, left, right = pair_by_task(
        records, baseline="control", treatment="treat", metric="reads"
    )
    assert tasks == ["a"]
    assert left == [3.0]
    assert right == [7.0]


def test_a_task_present_in_only_one_arm_is_dropped() -> None:
    """An unpaired task would silently become an unpaired comparison."""
    records = [record("a", "control", 0, reads=1.0), record("b", "treat", 0, reads=9.0)]
    tasks, left, right = pair_by_task(
        records, baseline="control", treatment="treat", metric="reads"
    )
    assert tasks == []
    assert left == right == []


# --- the negative control --------------------------------------------------


def test_the_harness_finds_nothing_in_a_null_experiment() -> None:
    """Both arms drawn from the same process must not resolve anything.

    This is the harness's own control, and it is run without a model on purpose:
    a false positive here would be indistinguishable from a real finding in the
    published table.
    """
    rng = random.Random(4)
    records = []
    for index in range(14):
        task = f"task{index}"
        # Task difficulty varies a lot; the arms do not differ at all.
        difficulty = rng.uniform(1, 20)
        for arm in ("control", "treat"):
            for repeat in range(2):
                records.append(
                    record(
                        task,
                        arm,
                        repeat,
                        reads=difficulty + rng.gauss(0, 2),
                        tokens=difficulty * 1000 + rng.gauss(0, 500),
                        task_success=float(rng.random() < 0.6),
                    )
                )

    analysis = analyze(Experiment.from_dict(SPEC), records)
    assert analysis.n_pairs == 14
    assert not analysis.resolved, (
        "the harness resolved an effect in an experiment with no effect: "
        + ", ".join(f"{e.metric} p={e.p_adjusted:.3f}" for e in analysis.resolved)
    )


def test_a_planted_effect_is_found() -> None:
    """The other half: a harness that finds nothing ever is equally useless."""
    rng = random.Random(9)
    records = []
    for index in range(14):
        task = f"task{index}"
        difficulty = rng.uniform(1, 20)
        for repeat in range(2):
            records.append(record(task, "control", repeat, reads=difficulty, tokens=1.0))
            records.append(record(task, "treat", repeat, reads=difficulty + 5.0, tokens=1.0))
    analysis = analyze(Experiment.from_dict(SPEC), records)
    reads = next(e for e in analysis.estimates if e.metric == "reads")
    assert reads.verdict is Verdict.RESOLVED
    assert reads.difference == pytest.approx(5.0)


# --- the refusal -----------------------------------------------------------


def test_only_declared_metrics_are_scored() -> None:
    """A metric that is not in the spec cannot be reported, however tempting."""
    spec = Experiment.from_dict(SPEC)
    records = [record("a", "control", 0, reads=1.0), record("a", "treat", 0, reads=2.0)]
    analysis = analyze(spec, records)
    assert {e.metric for e in analysis.estimates} == set(spec.metric_names)
    with pytest.raises(SpecError, match="not pre-registered"):
        spec.metric("reads_but_only_the_good_ones")


def test_exploratory_metrics_are_excluded_from_the_correction() -> None:
    """Folding them in would cost the primary metrics the power they were given."""
    spec = Experiment.from_dict(SPEC)
    rng = random.Random(2)
    records = []
    for index in range(12):
        task = f"t{index}"
        base = rng.uniform(1, 10)
        records.append(record(task, "control", 0, reads=base, tokens=base))
        records.append(record(task, "treat", 0, reads=base + 4, tokens=base + 4))
    analysis = analyze(spec, records)
    tokens = next(e for e in analysis.estimates if e.metric == "tokens")
    reads = next(e for e in analysis.estimates if e.metric == "reads")
    assert tokens.p_adjusted == tokens.p_value, "exploratory metrics keep their raw p"
    assert reads.p_adjusted >= reads.p_value, "primary metrics are corrected"


def test_a_mixed_set_of_spec_digests_is_flagged() -> None:
    """Records from a different declaration must not be silently pooled."""
    spec = Experiment.from_dict(SPEC)
    stale = record("a", "control", 0, reads=1.0)
    stale.spec_digest = "000000000000"
    analysis = analyze(spec, [stale, record("a", "treat", 0, reads=2.0)])
    assert not analysis.digest_matches


def test_a_run_that_never_executed_is_excluded_not_scored_as_a_failure() -> None:
    """The distinction that saved this project's v2 experiment from a false result.

    Sixteen of thirty v2 runs were session-limit refusals. Recorded as ordinary
    failures they made the table read "the skill makes things worse"; excluded,
    the tasks simply drop out of the pairing. A run that never started is not
    evidence about the intervention.
    """
    spec = Experiment.from_dict(SPEC)
    good = [
        record("a", "control", 0, reads=1.0, task_success=1.0),
        record("a", "treat", 0, reads=2.0, task_success=1.0),
    ]
    refused = []
    for arm in ("control", "treat"):
        r = record("b", arm, 0, reads=0.0, task_success=0.0)
        r.executed = False
        r.error = "the agent never ran: session limit"
        refused.append(r)

    analysis = analyze(spec, [*good, *refused])
    assert analysis.unexecuted_runs == 2
    assert analysis.paired_tasks == ("a",), "task b never ran, so it is not a pair"
    success = next(e for e in analysis.estimates if e.metric == "task_success")
    assert success.baseline_mean == 1.0, "the refusals must not drag the rate down"


def test_a_timeout_is_kept_because_the_agent_did_run() -> None:
    """The other side of the same line.

    A run that started and ran out of clock is evidence -- the skill may be what
    made it slow -- so it stays in.
    """
    spec = Experiment.from_dict(SPEC)
    good = record("a", "control", 0, reads=1.0, task_success=1.0)
    slow = record("a", "treat", 0, reads=9.0, task_success=0.0)
    slow.error = "timed out after 600s"
    analysis = analyze(spec, [good, slow])
    assert analysis.unexecuted_runs == 0
    assert analysis.failed_runs == 1
    assert analysis.paired_tasks == ("a",)


def test_errored_runs_are_counted_not_discarded() -> None:
    """A run that timed out is data. Dropping it would bias toward the arm that
    finished, which is exactly the arm the skill might be slowing down."""
    good = record("a", "control", 0, reads=1.0)
    bad = record("a", "treat", 0, reads=0.0)
    bad.error = "timed out after 600s"
    analysis = analyze(Experiment.from_dict(SPEC), [good, bad])
    assert analysis.failed_runs == 1
    assert analysis.n_pairs == 1

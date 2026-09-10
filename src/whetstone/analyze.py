"""Turn recorded runs into pre-registered estimates.

Thin on purpose: the statistics live in :mod:`whetstone.stats` and the pairing
lives in :mod:`whetstone.results`. What this module contributes is the *refusal*
-- it will only score metrics the experiment declared, and it checks that the
records it is scoring came from the spec it is scoring them under.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from whetstone import results as results_mod
from whetstone.results import RunRecord
from whetstone.spec import Experiment, SpecError
from whetstone.stats import Estimate, adjust_family, estimate_binary, estimate_continuous


@dataclass(frozen=True, slots=True)
class Analysis:
    """Every declared metric's estimate, plus what the data could not support."""

    experiment: Experiment
    estimates: tuple[Estimate, ...]
    #: Tasks that appeared in both arms and so contributed a pair.
    paired_tasks: tuple[str, ...]
    #: Records that recorded an error, kept in the denominator and flagged here.
    failed_runs: int
    #: Spec digests found among the records. More than one is a mixed set.
    digests: tuple[str, ...]

    @property
    def n_pairs(self) -> int:
        return len(self.paired_tasks)

    @property
    def resolved(self) -> list[Estimate]:
        return [e for e in self.estimates if e.resolved]

    @property
    def digest_matches(self) -> bool:
        """Were these records produced by this experiment's *run* definition?

        Checked against `run_digest`, not `digest`: adding a metric changes the
        analysis, not the evidence. See Experiment.run_digest.
        """
        return self.digests == (self.experiment.run_digest,)


def analyze(experiment: Experiment, records: Sequence[RunRecord]) -> Analysis:
    """Score every pre-registered metric, then correct across the family."""
    if not records:
        raise SpecError("no runs to analyse")

    baseline = experiment.baseline.name
    treatment = experiment.treatment.name
    estimates: list[Estimate] = []
    paired: tuple[str, ...] = ()

    for metric in experiment.metrics:
        tasks, left, right = results_mod.pair_by_task(
            records, baseline=baseline, treatment=treatment, metric=metric.name
        )
        paired = tuple(tasks)
        if metric.is_binary:
            # Repeats are averaged into a rate per task, so a 0/1 metric is only
            # genuinely binary at repeats=1. Above that, thresholding at the
            # majority keeps McNemar applicable and keeps the question the same
            # one the metric asks: did this task's runs mostly do the thing.
            estimates.append(
                estimate_binary(
                    metric.name,
                    [value >= 0.5 for value in left],
                    [value >= 0.5 for value in right],
                    alpha=experiment.alpha,
                )
            )
        else:
            estimates.append(estimate_continuous(metric.name, left, right, alpha=experiment.alpha))

    # Holm runs over the primary family only. Exploratory metrics keep their
    # raw p-values and are labelled non-confirmatory in the report; folding them
    # into the correction would cost the primary metrics the power they were
    # declared to have.
    primary_names = {m.name for m in experiment.primary}
    corrected = {
        e.metric: e
        for e in adjust_family(
            [e for e in estimates if e.metric in primary_names], alpha=experiment.alpha
        )
    }
    final = tuple(corrected.get(e.metric, e) for e in estimates)

    return Analysis(
        experiment=experiment,
        estimates=final,
        paired_tasks=paired,
        failed_runs=sum(1 for record in records if record.error),
        digests=tuple(sorted(results_mod.digests(records))),
    )


__all__ = ["Analysis", "analyze"]

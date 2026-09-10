"""Paired statistics for very small samples, with no dependencies.

Every number this project publishes comes from here, which is why it imports
nothing. The argument of the whole project is that the measurement is
*checkable*; a reader who has to trust scipy's defaults to audit a claim cannot
check it, and a reader who can read 200 lines of stdlib can.

The design constraints are unusual and worth stating, because they rule out most
of what a statistics textbook would suggest:

**n is tiny.** A run costs real model time, so an experiment is ten to twenty
tasks, not ten thousand. Anything relying on asymptotic normality is out.

**Observations are paired.** The same task is run under both arms, so the pairing
carries most of the information -- task difficulty varies far more than the
intervention does. Throwing that away by comparing two independent means would
bury any real effect under between-task variance.

**Many metrics are tested at once.** Eight metrics at alpha=0.05 gives roughly a
one-in-three chance of a false winner. Reporting them uncorrected would
manufacture exactly the result the experimenter wants to see, which is why
:func:`holm_bonferroni` is not optional here.

**A null result has to mean something.** "No significant difference" is
uninformative unless you also say what you could have detected. Hence
:func:`minimum_detectable_effect` on every metric, resolved or not.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

#: Two-sided by default: a skill can plausibly make a metric worse, and a
#: one-sided test would hide exactly the outcome most worth knowing.
DEFAULT_ALPHA = 0.05

#: Conventional power target, used only to express the minimum detectable
#: effect. Nothing is gated on it.
DEFAULT_POWER = 0.80

#: Enough that the interval is stable to the third decimal; cheap at this n.
DEFAULT_RESAMPLES = 10_000

#: Fixed so a report is reproducible from the same inputs. A bootstrap that
#: moves between runs invites re-rolling until the answer is nice.
DEFAULT_SEED = 20260910


class Verdict(StrEnum):
    """What the data supports, after correcting for multiplicity."""

    #: The corrected interval excludes zero: the effect is real at this n.
    RESOLVED = "resolved"
    #: The interval includes zero. Not "no effect" -- see `mde`.
    UNRESOLVED = "unresolved"
    #: Every pair is identical, so there is nothing to resample.
    IDENTICAL = "identical"
    #: Fewer pairs than any inference could use.
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class Estimate:
    """One metric's answer, with everything needed to argue about it."""

    metric: str
    n_pairs: int
    baseline_mean: float
    treatment_mean: float
    difference: float
    ci_low: float
    ci_high: float
    p_value: float
    #: `p_value` after Holm-Bonferroni across the metric family. Set by
    #: :func:`adjust_family`; equal to `p_value` until then.
    p_adjusted: float
    #: The smallest true difference this experiment could have resolved.
    mde: float
    verdict: Verdict
    #: Which test produced `p_value`, so the reader can check it applies.
    test: str

    @property
    def relative(self) -> float:
        """Difference as a fraction of the baseline mean, or 0 when undefined."""
        return self.difference / self.baseline_mean if self.baseline_mean else 0.0

    @property
    def resolved(self) -> bool:
        return self.verdict is Verdict.RESOLVED


# ---------------------------------------------------------------------------
# the bootstrap
# ---------------------------------------------------------------------------


def paired_bootstrap(
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float, float, float]:
    """Percentile bootstrap CI and p-value for the paired mean difference.

    Returns ``(difference, ci_low, ci_high, p_value)``.

    **Pairs are resampled, not observations.** Drawing the two arms
    independently would destroy the pairing that makes this design work: task 7
    being hard affects both arms, and the difference is what cancels it out.

    The p-value is the standard bootstrap inversion -- twice the smaller tail
    mass on either side of zero. It agrees with the interval by construction,
    so a reader never has to reconcile a significant p against an interval that
    covers zero.

    A percentile interval rather than BCa: at n=12 the bias-correction and
    acceleration terms are themselves estimated from twelve points, and the
    apparent precision would be false.
    """
    if len(baseline) != len(treatment):
        raise ValueError(f"unpaired inputs: {len(baseline)} vs {len(treatment)}")
    differences = [t - b for b, t in zip(baseline, treatment, strict=True)]
    n = len(differences)
    if n == 0:
        return 0.0, 0.0, 0.0, 1.0

    observed = statistics.fmean(differences)
    if all(d == differences[0] for d in differences):
        # No spread: every resample is the same number, so an interval would be
        # a point and a p-value would be meaningless.
        return observed, observed, observed, 0.0 if observed else 1.0

    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        means.append(statistics.fmean(rng.choices(differences, k=n)))
    means.sort()

    low = _quantile(means, alpha / 2)
    high = _quantile(means, 1 - alpha / 2)

    # Inversion: the mass on the far side of zero, doubled for two-sidedness.
    # `+1` in numerator and denominator is the standard finite-resample
    # correction -- it stops the p-value from ever being exactly zero, which it
    # cannot honestly be from a finite number of draws.
    below = sum(1 for m in means if m <= 0)
    above = resamples - below
    p_value = min(1.0, 2.0 * (min(below, above) + 1) / (resamples + 1))
    return observed, low, high, p_value


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated quantile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


# ---------------------------------------------------------------------------
# binary outcomes
# ---------------------------------------------------------------------------


def mcnemar_exact(only_baseline: int, only_treatment: int) -> float:
    """Exact two-sided McNemar p-value from the discordant counts.

    For a paired binary outcome -- did the agent run the tests, did the fix
    work -- the pairs where both arms agree carry no information about the
    intervention. Only the discordant ones do, and under the null each is a fair
    coin. So this is an exact binomial test on ``b`` successes out of ``b + c``,
    with no chi-square approximation: at these counts the approximation is
    simply wrong, and the exact computation is a sum of `math.comb` terms.
    """
    total = only_baseline + only_treatment
    if total == 0:
        return 1.0  # the arms never disagreed; there is nothing to test
    smaller = min(only_baseline, only_treatment)
    tail = sum(math.comb(total, k) for k in range(smaller + 1)) / float(2**total)
    return min(1.0, 2.0 * tail)


def discordant_counts(baseline: Sequence[bool], treatment: Sequence[bool]) -> tuple[int, int]:
    """``(only_baseline, only_treatment)`` -- the pairs where the arms disagreed."""
    if len(baseline) != len(treatment):
        raise ValueError(f"unpaired inputs: {len(baseline)} vs {len(treatment)}")
    only_baseline = sum(1 for b, t in zip(baseline, treatment, strict=True) if b and not t)
    only_treatment = sum(1 for b, t in zip(baseline, treatment, strict=True) if t and not b)
    return only_baseline, only_treatment


# ---------------------------------------------------------------------------
# multiplicity
# ---------------------------------------------------------------------------


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjustment, returned in the input order.

    Testing eight metrics at 0.05 and reporting the raw p-values gives about a
    34% chance of at least one false positive -- which, for an experimenter
    hoping their skill works, is not a small problem.

    Holm rather than plain Bonferroni because it is uniformly more powerful and
    just as assumption-free: it controls the family-wise error rate without
    requiring the tests to be independent, which these are not (a skill that
    makes the agent read more also makes it spend more tokens).

    The running maximum enforces monotonicity, so a metric can never end up with
    a smaller adjusted p-value than one that was more significant to begin with.
    """
    indexed = sorted(enumerate(p_values), key=lambda pair: pair[1])
    total = len(p_values)
    adjusted = [0.0] * total
    running = 0.0
    for rank, (original_index, p) in enumerate(indexed):
        running = max(running, min(1.0, (total - rank) * p))
        adjusted[original_index] = running
    return adjusted


# ---------------------------------------------------------------------------
# what we could have seen
# ---------------------------------------------------------------------------


def minimum_detectable_effect(
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> float:
    """The smallest true difference this many pairs could reliably have found.

    Reported on every metric, and it is the reason an unresolved result here is
    still worth printing. "No significant difference" alone is uninformative:
    it conflates "the intervention does nothing" with "we ran twelve tasks". The
    MDE separates them -- an unresolved metric with an MDE of 0.3 files really is
    evidence of a small effect, while one with an MDE of 9 files is evidence of
    nothing at all.

    Standard paired formula, using the observed spread of the differences as the
    estimate of the true one. It is therefore an estimate, not a guarantee, and
    at n below about six it is a rough one.
    """
    differences = [t - b for b, t in zip(baseline, treatment, strict=True)]
    n = len(differences)
    if n < 2:
        return math.inf
    spread = statistics.stdev(differences)
    if spread == 0:
        # Every pair moved by exactly the same amount, so there is no variance
        # to estimate a detectable effect *from*. Undefined, not zero -- and the
        # distinction matters, because returning 0.0 would print as "this
        # experiment could have detected any effect at all", which is precisely
        # backwards when the reason for zero variance is that a metric was
        # pinned at its ceiling or floor in both arms.
        return math.inf
    normal = statistics.NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    return float((z_alpha + z_power) * spread / math.sqrt(n))


# ---------------------------------------------------------------------------
# putting it together
# ---------------------------------------------------------------------------


def min_pairs_for_binary(alpha: float = DEFAULT_ALPHA) -> int:
    """Fewest paired tasks that could *ever* resolve a binary metric.

    An exact two-sided McNemar test on `n` discordant pairs bottoms out at
    ``2 / 2**n`` -- the case where every single pair flipped the same way. Below
    the `n` where that reaches `alpha`, no result is achievable: a clean sweep
    of every task still reports "unresolved", and the experiment cannot answer
    its own question however it comes out.

    At the conventional alpha this is **6**. Five tasks flipping five times out
    of five gives p = 0.0625, which is the single most commonly over-read number
    in small-sample work.

    Worth knowing before spending an hour of model time rather than after, which
    is why `whet check` refuses to stay quiet about it.
    """
    pairs = 1
    while 2.0 ** (1 - pairs) > alpha and pairs < 64:
        pairs += 1
    return pairs


def estimate_continuous(
    metric: str,
    baseline: Sequence[float],
    treatment: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Full paired estimate for a continuous metric."""
    n = len(baseline)
    if n < 2:
        return _degenerate(metric, baseline, treatment, Verdict.INSUFFICIENT, "paired-bootstrap")

    difference, low, high, p_value = paired_bootstrap(
        baseline, treatment, resamples=resamples, alpha=alpha, seed=seed
    )
    if low == high:
        verdict = Verdict.IDENTICAL if difference == 0 else Verdict.RESOLVED
    else:
        verdict = Verdict.RESOLVED if (low > 0) == (high > 0) else Verdict.UNRESOLVED

    return Estimate(
        metric=metric,
        n_pairs=n,
        baseline_mean=statistics.fmean(baseline),
        treatment_mean=statistics.fmean(treatment),
        difference=difference,
        ci_low=low,
        ci_high=high,
        p_value=p_value,
        p_adjusted=p_value,
        mde=minimum_detectable_effect(baseline, treatment, alpha=alpha),
        verdict=verdict,
        test="paired-bootstrap",
    )


def estimate_binary(
    metric: str,
    baseline: Sequence[bool],
    treatment: Sequence[bool],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = DEFAULT_SEED,
) -> Estimate:
    """Full paired estimate for a binary metric.

    The p-value comes from the exact McNemar test; the interval comes from the
    same bootstrap used for continuous metrics, applied to the 0/1 values. Two
    different machineries because each is the right tool: McNemar is exact where
    the bootstrap would be lumpy at these counts, and the bootstrap gives an
    interval where McNemar gives none.
    """
    n = len(baseline)
    numeric_baseline = [float(v) for v in baseline]
    numeric_treatment = [float(v) for v in treatment]
    if n < 2:
        return _degenerate(
            metric, numeric_baseline, numeric_treatment, Verdict.INSUFFICIENT, "mcnemar-exact"
        )

    only_baseline, only_treatment = discordant_counts(baseline, treatment)
    p_value = mcnemar_exact(only_baseline, only_treatment)
    difference, low, high, _ = paired_bootstrap(
        numeric_baseline, numeric_treatment, resamples=resamples, alpha=alpha, seed=seed
    )

    if only_baseline == only_treatment == 0:
        verdict = Verdict.IDENTICAL
    else:
        verdict = Verdict.RESOLVED if p_value <= alpha else Verdict.UNRESOLVED

    return Estimate(
        metric=metric,
        n_pairs=n,
        baseline_mean=statistics.fmean(numeric_baseline),
        treatment_mean=statistics.fmean(numeric_treatment),
        difference=difference,
        ci_low=low,
        ci_high=high,
        p_value=p_value,
        p_adjusted=p_value,
        mde=minimum_detectable_effect(numeric_baseline, numeric_treatment, alpha=alpha),
        verdict=verdict,
        test="mcnemar-exact",
    )


def adjust_family(estimates: Sequence[Estimate], *, alpha: float = DEFAULT_ALPHA) -> list[Estimate]:
    """Apply Holm-Bonferroni across a family and re-decide every verdict.

    Called once, over all metrics in the pre-registered spec -- including the
    ones that came out flat. Correcting only the interesting-looking subset is
    the same error as not correcting at all, dressed up.
    """
    testable = [e for e in estimates if e.verdict not in (Verdict.INSUFFICIENT,)]
    adjusted = holm_bonferroni([e.p_value for e in testable])
    by_metric = dict(zip((e.metric for e in testable), adjusted, strict=True))

    out: list[Estimate] = []
    for estimate in estimates:
        if estimate.metric not in by_metric:
            out.append(estimate)
            continue
        p_adjusted = by_metric[estimate.metric]
        verdict = estimate.verdict
        if verdict is Verdict.RESOLVED and p_adjusted > alpha:
            # Survived on its own and did not survive the family. This is the
            # correction doing its job, and the demotion is the whole point.
            verdict = Verdict.UNRESOLVED
        out.append(
            Estimate(
                metric=estimate.metric,
                n_pairs=estimate.n_pairs,
                baseline_mean=estimate.baseline_mean,
                treatment_mean=estimate.treatment_mean,
                difference=estimate.difference,
                ci_low=estimate.ci_low,
                ci_high=estimate.ci_high,
                p_value=estimate.p_value,
                p_adjusted=p_adjusted,
                mde=estimate.mde,
                verdict=verdict,
                test=estimate.test,
            )
        )
    return out


def _degenerate(
    metric: str,
    baseline: Sequence[float],
    treatment: Sequence[float],
    verdict: Verdict,
    test: str,
) -> Estimate:
    mean_baseline = statistics.fmean(baseline) if baseline else 0.0
    mean_treatment = statistics.fmean(treatment) if treatment else 0.0
    return Estimate(
        metric=metric,
        n_pairs=len(baseline),
        baseline_mean=mean_baseline,
        treatment_mean=mean_treatment,
        difference=mean_treatment - mean_baseline,
        ci_low=0.0,
        ci_high=0.0,
        p_value=1.0,
        p_adjusted=1.0,
        mde=math.inf,
        verdict=verdict,
        test=test,
    )


__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_POWER",
    "DEFAULT_RESAMPLES",
    "DEFAULT_SEED",
    "Estimate",
    "Verdict",
    "adjust_family",
    "discordant_counts",
    "estimate_binary",
    "estimate_continuous",
    "holm_bonferroni",
    "mcnemar_exact",
    "min_pairs_for_binary",
    "minimum_detectable_effect",
    "paired_bootstrap",
]

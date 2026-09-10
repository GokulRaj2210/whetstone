"""Known-answer tests for the statistics.

Every published number comes from this module, so it is tested against values
computed by hand or by a textbook formula rather than against its own output.
A statistics module that only agrees with itself is a random number generator
with good manners.
"""

from __future__ import annotations

import math
import random
import statistics

import pytest

from whetstone.stats import (
    Verdict,
    adjust_family,
    discordant_counts,
    estimate_binary,
    estimate_continuous,
    holm_bonferroni,
    mcnemar_exact,
    minimum_detectable_effect,
    paired_bootstrap,
)

# --- McNemar: computed by hand from the binomial ---------------------------


@pytest.mark.parametrize(
    ("only_baseline", "only_treatment", "expected"),
    [
        # No disagreement at all: nothing to test, p must be exactly 1.
        (0, 0, 1.0),
        # b=0, c=1: 2 * C(1,0)/2^1 = 2 * 0.5 = 1.0
        (0, 1, 1.0),
        # b=0, c=5: 2 * C(5,0)/2^5 = 2/32 = 0.0625 -- the classic result that
        # five-for-five is *not* significant at 0.05 two-sided.
        (0, 5, 0.0625),
        # b=0, c=6: 2 * 1/64 = 0.03125, the first count that clears 0.05.
        (0, 6, 0.03125),
        # b=2, c=9: 2 * (C(11,0)+C(11,1)+C(11,2))/2^11 = 2*67/2048
        (2, 9, 2 * 67 / 2048),
        # Symmetric in its arguments.
        (9, 2, 2 * 67 / 2048),
    ],
)
def test_mcnemar_matches_the_binomial_by_hand(
    only_baseline: int, only_treatment: int, expected: float
) -> None:
    assert mcnemar_exact(only_baseline, only_treatment) == pytest.approx(expected)


def test_five_for_five_does_not_clear_significance() -> None:
    """The result most likely to be mis-reported, pinned deliberately.

    A skill that flips five of five tasks looks overwhelming and is not: the
    two-sided exact p is 0.0625. Anyone eyeballing "5/5!" would claim an effect
    the data does not support.
    """
    assert mcnemar_exact(0, 5) > 0.05
    assert mcnemar_exact(0, 6) < 0.05


def test_discordant_counts_ignore_the_agreeing_pairs() -> None:
    baseline = [True, True, False, False, True]
    treatment = [True, False, True, False, False]
    assert discordant_counts(baseline, treatment) == (2, 1)


# --- Holm-Bonferroni: worked example ---------------------------------------


def test_holm_matches_a_worked_example() -> None:
    """Sorted p x (n - rank), made monotone, clamped at 1."""
    assert holm_bonferroni([0.001, 0.02, 0.04, 0.5]) == pytest.approx([0.004, 0.06, 0.08, 0.5])


def test_holm_returns_results_in_the_input_order() -> None:
    """Order matters: these line up with a metric list downstream."""
    assert holm_bonferroni([0.5, 0.001]) == pytest.approx([0.5, 0.002])


def test_holm_is_monotone() -> None:
    """A more significant metric can never end up with a larger adjusted p."""
    raw = [0.01, 0.011, 0.012, 0.013, 0.9]
    adjusted = holm_bonferroni(raw)
    ordered = [adjusted[i] for i in sorted(range(len(raw)), key=lambda i: raw[i])]
    assert ordered == sorted(ordered)


def test_holm_never_exceeds_one() -> None:
    assert all(p <= 1.0 for p in holm_bonferroni([0.4, 0.5, 0.6, 0.7]))


def test_holm_is_less_conservative_than_plain_bonferroni() -> None:
    """The reason to prefer it: same guarantee, more power."""
    raw = [0.01, 0.02, 0.03]
    assert holm_bonferroni(raw)[2] < min(1.0, len(raw) * raw[2])


# --- the bootstrap ---------------------------------------------------------


def test_the_bootstrap_recovers_a_planted_effect() -> None:
    rng = random.Random(7)
    baseline = [rng.uniform(5, 15) for _ in range(14)]
    treatment = [b - 3.0 + rng.uniform(-0.5, 0.5) for b in baseline]

    difference, low, high, p_value = paired_bootstrap(baseline, treatment)
    assert difference == pytest.approx(-3.0, abs=0.3)
    assert low < -3.0 < high, "the interval must cover the truth"
    assert high < 0, "and must exclude zero, since the effect is real"
    assert p_value < 0.01


def test_the_bootstrap_finds_nothing_when_there_is_nothing() -> None:
    """The property that makes a null result trustworthy.

    Two arms drawn from the same distribution must not produce a resolved
    verdict. A harness that finds effects in noise is worse than no harness.
    """
    rng = random.Random(11)
    baseline = [rng.gauss(10, 2) for _ in range(14)]
    treatment = [rng.gauss(10, 2) for _ in range(14)]

    _, low, high, p_value = paired_bootstrap(baseline, treatment)
    assert low < 0 < high, "the interval must cover zero"
    assert p_value > 0.05


def test_the_interval_and_the_p_value_never_disagree() -> None:
    """They come from the same resamples, so they must agree by construction.

    A significant p alongside an interval covering zero is the single most
    common way a statistics report loses a reader's trust.
    """
    rng = random.Random(3)
    for _ in range(25):
        n = rng.randint(4, 15)
        baseline = [rng.gauss(10, 3) for _ in range(n)]
        shift = rng.choice([0.0, 0.5, 2.0, -2.0])
        treatment = [b + shift + rng.gauss(0, 1) for b in baseline]
        _, low, high, p_value = paired_bootstrap(baseline, treatment)
        excludes_zero = (low > 0) == (high > 0)
        assert excludes_zero == (p_value <= 0.05), (low, high, p_value)


def test_pairing_is_preserved_by_the_resampling() -> None:
    """Resampling the arms independently would destroy the design.

    Here between-task variance is enormous and the effect is small and constant.
    A paired analysis sees the effect easily; an unpaired one would drown in it.
    """
    baseline = [10.0, 100.0, 1000.0, 10.0, 100.0, 1000.0, 55.0, 550.0]
    treatment = [b + 1.0 for b in baseline]
    difference, low, high, p_value = paired_bootstrap(baseline, treatment)
    assert difference == pytest.approx(1.0)
    assert low == high == pytest.approx(1.0), "a constant shift has no spread"
    assert p_value < 0.05


def test_identical_arms_are_reported_as_identical_not_significant() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    estimate = estimate_continuous("flat", values, list(values))
    assert estimate.verdict is Verdict.IDENTICAL
    assert estimate.difference == 0.0


# --- minimum detectable effect ---------------------------------------------


def test_mde_matches_the_paired_formula() -> None:
    """(z_alpha + z_power) * sd / sqrt(n), computed independently here."""
    baseline = [10.0, 12.0, 14.0, 11.0, 13.0, 9.0]
    treatment = [11.0, 14.0, 15.0, 11.5, 16.0, 10.0]
    differences = [t - b for b, t in zip(baseline, treatment, strict=True)]

    normal = statistics.NormalDist()
    expected = (
        (normal.inv_cdf(0.975) + normal.inv_cdf(0.80))
        * statistics.stdev(differences)
        / math.sqrt(len(differences))
    )
    assert minimum_detectable_effect(baseline, treatment) == pytest.approx(expected)


def test_mde_shrinks_as_pairs_are_added() -> None:
    """The claim the MDE column makes: more tasks resolve smaller effects."""
    rng = random.Random(5)
    small = [rng.gauss(0, 1) for _ in range(6)]
    large = small + [rng.gauss(0, 1) for _ in range(60)]
    mde_small = minimum_detectable_effect([0.0] * len(small), small)
    mde_large = minimum_detectable_effect([0.0] * len(large), large)
    assert mde_large < mde_small


def test_a_single_pair_admits_no_inference() -> None:
    assert minimum_detectable_effect([1.0], [2.0]) == math.inf
    assert estimate_continuous("lonely", [1.0], [2.0]).verdict is Verdict.INSUFFICIENT


# --- the family ------------------------------------------------------------


def test_a_lone_winner_can_be_demoted_by_its_family() -> None:
    """The correction doing the job it exists for.

    A metric significant on its own, tested alongside seven flat ones, is
    exactly the false positive multiplicity produces -- and it must not survive.
    """
    rng = random.Random(13)
    estimates = [
        estimate_continuous(
            "lucky",
            [rng.gauss(10, 1) for _ in range(12)],
            [rng.gauss(10, 1) - 1.2 for _ in range(12)],
        )
    ]
    for i in range(7):
        flat = [rng.gauss(10, 3) for _ in range(12)]
        estimates.append(estimate_continuous(f"flat{i}", flat, [v + rng.gauss(0, 3) for v in flat]))

    before = {e.metric: e.verdict for e in estimates}
    after = {e.metric: e.verdict for e in adjust_family(estimates)}
    assert before["lucky"] is Verdict.RESOLVED
    assert all(after[e.metric] is not Verdict.RESOLVED or e.p_value < 0.006 for e in estimates)


def test_a_real_effect_survives_the_family() -> None:
    """Correction must not be so blunt that nothing can ever pass."""
    rng = random.Random(17)
    baseline = [rng.uniform(5, 15) for _ in range(16)]
    strong = estimate_continuous("real", baseline, [b - 4.0 for b in baseline])
    others = [
        estimate_continuous(f"flat{i}", baseline, [b + rng.gauss(0, 2) for b in baseline])
        for i in range(6)
    ]
    adjusted = {e.metric: e for e in adjust_family([strong, *others])}
    assert adjusted["real"].verdict is Verdict.RESOLVED
    assert adjusted["real"].p_adjusted <= 0.05


def test_adjustment_covers_every_metric_including_the_flat_ones() -> None:
    """Correcting only the interesting subset is the same error, dressed up."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    estimates = [
        estimate_continuous("moved", values, [v - 2 for v in values]),
        estimate_continuous("flat", values, list(values)),
    ]
    adjusted = adjust_family(estimates)
    assert len(adjusted) == 2
    assert {e.metric for e in adjusted} == {"moved", "flat"}


# --- binary end to end -----------------------------------------------------


def test_binary_estimate_reports_rates_and_an_exact_p() -> None:
    baseline = [False] * 10 + [True] * 2
    treatment = [True] * 9 + [False] * 3
    estimate = estimate_binary("ran_tests", baseline, treatment)

    assert estimate.baseline_mean == pytest.approx(2 / 12)
    assert estimate.treatment_mean == pytest.approx(9 / 12)
    assert estimate.p_value == pytest.approx(2 * 67 / 2048)
    assert estimate.test == "mcnemar-exact"
    # 2 -> 9 of 12 looks overwhelming and does not clear 0.05 two-sided.
    assert estimate.verdict is Verdict.UNRESOLVED


def test_a_clean_binary_sweep_does_resolve() -> None:
    baseline = [False] * 12
    treatment = [True] * 12
    estimate = estimate_binary("ran_tests", baseline, treatment)
    assert estimate.verdict is Verdict.RESOLVED
    assert estimate.p_value < 0.001


def test_zero_variance_makes_the_mde_undefined_not_zero() -> None:
    """The bug this project's own results found.

    When every pair moves by exactly the same amount there is no variance to
    estimate power from. Returning 0.0 would print as "this experiment could
    have detected any effect", which is exactly backwards when the reason for
    the zero is that a metric sat at its ceiling in both arms.
    """
    identical = [1.0, 1.0, 1.0, 1.0]
    assert minimum_detectable_effect(identical, identical) == math.inf

    constant_shift = [2.0, 2.0, 2.0, 2.0]
    assert minimum_detectable_effect(identical, constant_shift) == math.inf

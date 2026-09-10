"""The pre-registered experiment: what will be measured, decided before running.

This is the smallest part of the project and the one that makes the rest
trustworthy. Everything else here is machinery for producing numbers; this is
the machinery that stops the numbers from being chosen after the fact.

The failure it prevents is not fraud, it is enthusiasm. Run an experiment, look
at twelve metrics, notice that three moved, and write up those three -- and the
write-up is worthless, because the selection happened after the data was seen.
Doing that accidentally requires no bad faith at all, only hope.

So the spec is declared first, hashed, and the hash is stamped into every result
file. `whet analyze` refuses to score a metric the spec does not name, and
`whet report` prints the hash next to the table. Changing the spec after a run
produces a different hash and a visibly different experiment -- which is allowed,
as long as it is not silent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

#: Metrics whose values are 0/1 and are tested with the exact McNemar test.
KIND_BINARY = "binary"
KIND_CONTINUOUS = "continuous"

#: Confirmatory metrics. Multiplicity is corrected *within this family only*,
#: which is the standard design for a reason: correcting across every metric
#: anyone might want to look at costs so much power that a real effect cannot
#: be found at achievable n, while correcting across none manufactures winners.
#: Keep it to three or four, and declare them before running.
FAMILY_PRIMARY = "primary"
#: Everything else. Reported in full, uncorrected, and labelled as
#: hypothesis-generating rather than confirmatory -- an exploratory metric that
#: moves is a reason to design the next experiment, not a result.
FAMILY_EXPLORATORY = "exploratory"


class SpecError(ValueError):
    """The experiment definition is malformed or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One pre-registered metric."""

    name: str
    kind: str = KIND_CONTINUOUS
    #: Which way is good. Used only for presentation -- the statistics are
    #: two-sided regardless, because a skill that makes a metric worse is the
    #: finding most worth not hiding.
    direction: str = "lower_is_better"
    #: Free text: why this metric is in the spec at all. Required, because a
    #: metric nobody can justify in one sentence is a metric that was added to
    #: increase the chance that something moved.
    rationale: str = ""
    #: `primary` metrics are confirmatory and share a Holm correction.
    #: `exploratory` ones are reported uncorrected and cannot support a claim.
    family: str = FAMILY_EXPLORATORY

    @property
    def is_primary(self) -> bool:
        return self.family == FAMILY_PRIMARY

    @property
    def is_binary(self) -> bool:
        return self.kind == KIND_BINARY

    def improved(self, difference: float) -> bool:
        """Did a treatment-minus-baseline difference move in the good direction?"""
        return difference < 0 if self.direction == "lower_is_better" else difference > 0


@dataclass(frozen=True, slots=True)
class Arm:
    """One experimental condition."""

    name: str
    #: The skill directory to make available, or None for the control arm.
    skill: str | None = None
    #: Extra text appended to every prompt in this arm. Normally empty; it
    #: exists so a prompt-only intervention can be compared against a skill.
    prompt_suffix: str = ""


@dataclass(frozen=True, slots=True)
class Experiment:
    """A pre-registered experiment definition, plus the hash that pins it."""

    name: str
    arms: tuple[Arm, ...]
    metrics: tuple[MetricSpec, ...]
    repeats: int = 3
    alpha: float = 0.05
    timeout_s: int = 600
    source_path: Path | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    # -- identity ----------------------------------------------------------

    @property
    def digest(self) -> str:
        """Stable sha256 over the whole declaration, metrics included.

        Canonical means sorted keys and no whitespace, so reformatting the YAML
        does not change the hash while changing a metric does. Twelve hex
        characters is plenty to spot a mismatch and short enough to print in a
        table header.
        """
        return _hash(self.to_dict())

    @property
    def run_digest(self) -> str:
        """Hash of only the parts that determine what the *runs* were.

        Arms, prompts, repeats, timeout -- everything that shaped the data.
        Deliberately excludes the metric list, because metrics shape the
        *analysis* and a recorded run is evidence regardless of what is later
        computed from it.

        The distinction is not academic. This project's own experiment shipped
        with `test_run_after_edit` as a primary metric; reading the transcripts
        afterwards showed it measured "ran a test runner" while claiming to
        measure "verified the change", and the control arm had been verifying
        with inline scripts all along. Fixing that needed a new metric over the
        *same* runs. Under a single digest, correcting a measurement error would
        have invalidated the evidence it was corrected from -- which would push
        anyone who found such a bug toward quietly not fixing it.

        So a changed `run_digest` invalidates records; a changed `digest` alone
        is reported, and the added metric is exploratory because it was chosen
        after the data was seen.
        """
        shape = {k: v for k, v in self.to_dict().items() if k != "metrics"}
        return _hash(shape)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "alpha": self.alpha,
            "repeats": self.repeats,
            "timeout_s": self.timeout_s,
            "arms": [
                {"name": a.name, "skill": a.skill, "prompt_suffix": a.prompt_suffix}
                for a in self.arms
            ],
            "metrics": [
                {
                    "name": m.name,
                    "kind": m.kind,
                    "direction": m.direction,
                    "rationale": m.rationale,
                    "family": m.family,
                }
                for m in self.metrics
            ],
        }

    # -- access ------------------------------------------------------------

    @property
    def baseline(self) -> Arm:
        return self.arms[0]

    @property
    def treatment(self) -> Arm:
        return self.arms[1]

    @property
    def metric_names(self) -> list[str]:
        return [m.name for m in self.metrics]

    @property
    def primary(self) -> tuple[MetricSpec, ...]:
        return tuple(m for m in self.metrics if m.is_primary)

    def metric(self, name: str) -> MetricSpec:
        for candidate in self.metrics:
            if candidate.name == name:
                return candidate
        raise SpecError(
            f"metric {name!r} is not pre-registered in {self.name!r}. "
            f"Declared: {', '.join(self.metric_names)}. "
            "Add it to the spec and re-run -- scoring a metric chosen after the "
            "results were seen is how a null result becomes a positive one."
        )

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, path: Path | str) -> Experiment:
        source = Path(path)
        try:
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise SpecError(f"could not read experiment {source}: {exc}") from exc
        return cls.from_dict(raw, source_path=source)

    @classmethod
    def from_dict(cls, raw: Any, *, source_path: Path | None = None) -> Experiment:
        if not isinstance(raw, dict):
            raise SpecError("an experiment must be a mapping")

        arms = tuple(_parse_arm(entry) for entry in raw.get("arms") or ())
        if len(arms) != 2:
            raise SpecError(
                f"exactly two arms are required (baseline first, treatment second); got {len(arms)}"
            )
        if arms[0].skill is not None:
            raise SpecError(
                f"the first arm is the control and must have no skill; {arms[0].name!r} has "
                f"{arms[0].skill!r}. Order matters: every difference is reported as "
                "treatment minus baseline."
            )

        metrics = tuple(_parse_metric(entry) for entry in _as_items(raw.get("metrics")))
        if not metrics:
            raise SpecError("an experiment with no declared metrics measures nothing")
        seen: set[str] = set()
        for metric in metrics:
            if metric.name in seen:
                raise SpecError(f"metric {metric.name!r} is declared twice")
            seen.add(metric.name)
            if metric.kind not in (KIND_BINARY, KIND_CONTINUOUS):
                raise SpecError(f"metric {metric.name!r} has unknown kind {metric.kind!r}")
            if metric.family not in (FAMILY_PRIMARY, FAMILY_EXPLORATORY):
                raise SpecError(f"metric {metric.name!r} has unknown family {metric.family!r}")
            if not metric.rationale:
                raise SpecError(
                    f"metric {metric.name!r} has no `rationale`. Every declared metric needs a "
                    "one-line reason it is being tested; a metric nobody can justify in advance "
                    "is one added to raise the odds that something moved."
                )

        primary = [m for m in metrics if m.is_primary]
        if not primary:
            raise SpecError(
                "no metric is declared `family: primary`. An experiment needs at least one "
                "confirmatory metric; if everything is exploratory, nothing can be concluded."
            )
        if len(primary) > 4:
            raise SpecError(
                f"{len(primary)} primary metrics is too many to correct across at feasible n. "
                "Pick the three or four the experiment is actually about and make the rest "
                "exploratory."
            )

        repeats = int(raw.get("repeats", 3))
        if repeats < 1:
            raise SpecError("`repeats` must be at least 1")

        return cls(
            name=str(raw.get("name") or (source_path.stem if source_path else "experiment")),
            arms=arms,
            metrics=metrics,
            repeats=repeats,
            alpha=float(raw.get("alpha", 0.05)),
            timeout_s=int(raw.get("timeout_s", 600)),
            source_path=source_path,
            raw=raw,
        )


def _hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _parse_arm(entry: Any) -> Arm:
    if not isinstance(entry, dict):
        raise SpecError(f"an arm must be a mapping, got {entry!r}")
    name = entry.get("name")
    if not name:
        raise SpecError(f"an arm needs a `name`: {entry!r}")
    skill = entry.get("skill")
    return Arm(
        name=str(name),
        skill=str(skill) if skill else None,
        prompt_suffix=str(entry.get("prompt_suffix") or ""),
    )


def _as_items(value: Any) -> list[dict[str, Any]]:
    """Accept both the mapping and the list form of `metrics:`."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [{"name": name, **(body or {})} for name, body in value.items()]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    raise SpecError(f"`metrics` must be a mapping or a list, got {type(value).__name__}")


def _parse_metric(entry: dict[str, Any]) -> MetricSpec:
    name = entry.get("name")
    if not name:
        raise SpecError(f"a metric needs a `name`: {entry!r}")
    return MetricSpec(
        name=str(name),
        kind=str(entry.get("kind", KIND_CONTINUOUS)),
        direction=str(entry.get("direction", "lower_is_better")),
        rationale=str(entry.get("rationale") or ""),
        family=str(entry.get("family", FAMILY_EXPLORATORY)),
    )


__all__ = [
    "FAMILY_EXPLORATORY",
    "FAMILY_PRIMARY",
    "KIND_BINARY",
    "KIND_CONTINUOUS",
    "Arm",
    "Experiment",
    "MetricSpec",
    "SpecError",
]

"""What one run produced, and how a set of runs is stored.

Kept apart from :mod:`whetstone.capture` so that analysis and reporting never
import the subprocess machinery. Re-analysing committed results has to work on a
machine with no `claude` binary, no API key and no network -- that is what makes
the CI check meaningful and the numbers reproducible by someone else.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

#: One JSON object per line, so a partial run is still readable and an
#: interrupted experiment loses one row rather than the file.
RESULTS_FILE = "runs.jsonl"


@dataclass(slots=True)
class RunRecord:
    """A single (task, arm, repeat) observation."""

    task: str
    arm: str
    repeat: int
    #: The pre-registered spec's digest, copied here so a result can never be
    #: silently re-interpreted under a different spec than it was run for.
    spec_digest: str
    #: Did the hidden test pass afterwards. The only quality claim made.
    task_success: bool
    #: Wall clock for the agent's run, not counting verification.
    duration_s: float
    #: Behavioural metrics from `extract`, plus cost metrics from flightrec.
    metrics: dict[str, float] = field(default_factory=dict)
    #: Files the agent wrote to, for eyeballing a suspicious result.
    touched: list[str] = field(default_factory=list)
    #: Where the ingested cassette lives, relative to the results directory.
    cassette: str = ""
    #: Set when the run itself failed (timeout, crash, refusal). The record is
    #: still written either way -- see `executed` for what may be analysed.
    error: str | None = None
    #: Did the agent actually get to work on the task?
    #:
    #: The distinction this draws is load-bearing. A run that *ran and timed
    #: out* is evidence about the intervention -- the skill may be what made it
    #: slow -- and belongs in the analysis. A run that never started, because
    #: the session hit its usage limit and the CLI returned a one-line refusal,
    #: is evidence about nothing.
    #:
    #: Conflating them is not a small error. Sixteen of this project's own v2
    #: runs were refusals, and every one was recorded as `task_success: false`,
    #: which is indistinguishable from the agent trying and failing. The
    #: experiment read as "the skill makes things worse".
    executed: bool = True

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.task, self.arm, self.repeat)

    def value(self, metric: str) -> float:
        if metric == "task_success":
            return float(self.task_success)
        if metric == "duration_s":
            return self.duration_s
        return self.metrics.get(metric, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RunRecord:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})


def append(directory: Path | str, record: RunRecord) -> None:
    """Append one record, flushing immediately.

    Written as it happens rather than at the end. An experiment is an hour of
    model time; losing it to a crash in the last task would be its own kind of
    result, and not a useful one.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    with (path / RESULTS_FILE).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def load(directory: Path | str) -> list[RunRecord]:
    """Every record under ``directory``, skipping blank and unreadable lines."""
    path = Path(directory) / RESULTS_FILE
    if not path.exists():
        return []
    return list(_iter_records(path))


def _iter_records(path: Path) -> Iterator[RunRecord]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield RunRecord.from_dict(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue


def digests(records: Iterable[RunRecord]) -> set[str]:
    """Every spec digest present. More than one means mixed experiments."""
    return {record.spec_digest for record in records}


def pair_by_task(
    records: Sequence[RunRecord], *, baseline: str, treatment: str, metric: str
) -> tuple[list[str], list[float], list[float]]:
    """Fold repeats into one value per (task, arm) and return aligned vectors.

    The unit of the paired design is the **task**, not the run: repeats exist to
    average out the sampler, not to inflate n. Treating each repeat as an
    independent observation would trip the pairing and, by multiplying the
    apparent sample size, manufacture significance out of variance that the
    design was built to cancel.

    A task missing from either arm is dropped, and the caller is told which
    tasks survived so the report can say how many pairs it actually had. Runs
    that never executed are dropped first, for the same reason -- and because a
    task whose runs were all refusals then disappears from the pairing entirely
    rather than contributing a fabricated pair of failures.
    """
    grouped: dict[tuple[str, str], list[float]] = {}
    for record in records:
        if record.arm not in (baseline, treatment):
            continue
        if not record.executed:
            continue  # never ran; not evidence either way
        grouped.setdefault((record.task, record.arm), []).append(record.value(metric))

    tasks = sorted({task for task, _ in grouped})
    kept: list[str] = []
    baseline_values: list[float] = []
    treatment_values: list[float] = []
    for task in tasks:
        left = grouped.get((task, baseline))
        right = grouped.get((task, treatment))
        if not left or not right:
            continue
        kept.append(task)
        baseline_values.append(sum(left) / len(left))
        treatment_values.append(sum(right) / len(right))
    return kept, baseline_values, treatment_values


__all__ = ["RESULTS_FILE", "RunRecord", "append", "digests", "load", "pair_by_task"]

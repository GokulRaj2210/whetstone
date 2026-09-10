#!/usr/bin/env python
"""Fail if the README's results table has drifted from the committed records.

A results table in a README is a copy. Copies rot: a re-run changes the numbers,
someone updates the prose and not the table, and the document quietly starts
claiming something the data does not support. Since the whole argument of this
project is that its numbers are checkable, the check is automated and runs in CI.

Compares the digest and every metric row. Regenerate with:

    uv run whet report experiments/deep-work.yaml --results runs --md results.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from whetstone import results as results_mod
from whetstone.analyze import analyze
from whetstone.spec import Experiment

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def main() -> int:
    experiment = Experiment.load(ROOT / "experiments" / "deep-work.yaml")
    records = results_mod.load(ROOT / "runs")
    if not records:
        print("no committed runs to check against", file=sys.stderr)
        return 1
    analysis = analyze(experiment, records)
    readme = README.read_text(encoding="utf-8")

    problems: list[str] = []
    if experiment.digest not in readme:
        problems.append(
            f"the README does not mention the spec digest {experiment.digest}; "
            "either the experiment changed or the table is stale"
        )

    for estimate in analysis.estimates:
        row = _row_for(readme, estimate.metric)
        if row is None:
            problems.append(f"`{estimate.metric}` is declared but has no row in the README")
            continue
        for label, value in (
            ("control", estimate.baseline_mean),
            ("skill", estimate.treatment_mean),
        ):
            if f"{value:.2f}" not in row:
                problems.append(
                    f"`{estimate.metric}`: README row does not contain the {label} mean "
                    f"{value:.2f}\n    row: {row.strip()}"
                )

    if problems:
        print("README results table is out of date:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nRegenerate with:\n"
            "  uv run whet report experiments/deep-work.yaml --results runs --md results.md",
            file=sys.stderr,
        )
        return 1

    print(f"README matches {len(analysis.estimates)} metric rows at spec {experiment.digest}")
    return 0


def _row_for(readme: str, metric: str) -> str | None:
    pattern = re.compile(rf"^\|\s*[`_]{re.escape(metric)}[`_]\s*\|.*$", re.MULTILINE)
    match = pattern.search(readme)
    return match.group(0) if match else None


if __name__ == "__main__":
    sys.exit(main())

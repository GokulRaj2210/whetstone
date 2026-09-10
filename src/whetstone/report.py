"""Render an analysis so that its limits are as visible as its findings.

The design rule for everything here: **an unresolved metric gets a row too.**
Reports that list only what reached significance are how a null experiment turns
into a positive one, and the omission is invisible to the reader. So every
pre-registered metric appears, resolved or not, with the minimum detectable
effect beside it so "we found nothing" can be read as either "there is little
here" or "we could not have seen it" -- which are very different claims.

Two other things are printed that a friendlier report would leave out: the spec
digest, so a reader can check the metrics were declared before the run, and the
count of runs that errored, so a suspiciously clean result can be interrogated.
"""

from __future__ import annotations

import math

from rich.console import Console
from rich.table import Table

from whetstone.analyze import Analysis
from whetstone.stats import Estimate, Verdict

_GLYPH = {
    Verdict.RESOLVED: "[green]resolved[/green]",
    Verdict.UNRESOLVED: "[yellow]unresolved[/yellow]",
    Verdict.IDENTICAL: "[dim]identical[/dim]",
    Verdict.INSUFFICIENT: "[dim]too few[/dim]",
}


def console_report(analysis: Analysis, console: Console) -> None:
    experiment = analysis.experiment
    console.print()
    console.print(
        f"[bold]{experiment.name}[/bold]  "
        f"spec {experiment.digest}  "
        f"{analysis.n_pairs} paired task(s)  "
        f"{experiment.repeats} repeat(s) per arm  "
        f"alpha {experiment.alpha}"
    )
    console.print(
        f"  {experiment.baseline.name} (control) vs "
        f"[bold]{experiment.treatment.name}[/bold] "
        f"(skill: {experiment.treatment.skill or 'none'})"
    )

    if not analysis.digest_matches:
        console.print(
            f"  [red]spec mismatch[/red]: records carry {', '.join(analysis.digests)} but this "
            f"spec is {experiment.digest}. These runs were made under a different declaration."
        )
    if analysis.failed_runs:
        console.print(
            f"  [yellow]{analysis.failed_runs} run(s) errored or timed out[/yellow] "
            "(kept in the results, not discarded)"
        )

    table = Table(box=None, pad_edge=False)
    table.add_column("metric", no_wrap=True, min_width=28)
    table.add_column("control", justify="right")
    table.add_column("+skill", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("95% CI", justify="right", no_wrap=True)
    table.add_column("p (adj)", justify="right")
    table.add_column("MDE", justify="right")
    table.add_column("verdict", no_wrap=True)

    for estimate in analysis.estimates:
        metric = experiment.metric(estimate.metric)
        direction = "[green]" if metric.improved(estimate.difference) else "[red]"
        delta = f"{direction}{estimate.difference:+.2f}[/]" if estimate.difference else "0.00"
        label = estimate.metric if metric.is_primary else f"[dim]{estimate.metric}[/dim]"
        table.add_row(
            label,
            f"{estimate.baseline_mean:.2f}",
            f"{estimate.treatment_mean:.2f}",
            delta,
            f"[{estimate.ci_low:+.2f}, {estimate.ci_high:+.2f}]",
            f"{estimate.p_adjusted:.3f}",
            _mde(estimate),
            _GLYPH[estimate.verdict] if metric.is_primary else "[dim]exploratory[/dim]",
        )
    console.print()
    console.print(table)
    console.print()
    for line in _caveats(analysis):
        console.print(f"  {line}")
    console.print()


def markdown_report(analysis: Analysis) -> str:
    """The same table, for a README or a PR comment."""
    experiment = analysis.experiment
    lines = [
        f"### {experiment.name}",
        "",
        f"Pre-registered spec `{experiment.digest}` · {analysis.n_pairs} paired tasks · "
        f"{experiment.repeats} repeats per arm · two-sided, alpha {experiment.alpha}, "
        "Holm-corrected across the metric family.",
        "",
        "| Metric | Control | +Skill | Delta | 95% CI | p (adj) | MDE | Verdict |",
        "|---|--:|--:|--:|:--:|--:|--:|---|",
    ]
    for estimate in analysis.estimates:
        metric = experiment.metric(estimate.metric)
        primary = metric.is_primary
        arrow = "**" if estimate.resolved and primary else ""
        verdict = estimate.verdict.value if primary else "exploratory"
        lines.append(
            f"| {'`' + estimate.metric + '`' if primary else '_' + estimate.metric + '_'} | "
            f"{estimate.baseline_mean:.2f} | "
            f"{estimate.treatment_mean:.2f} | {arrow}{estimate.difference:+.2f}{arrow} | "
            f"[{estimate.ci_low:+.2f}, {estimate.ci_high:+.2f}] | "
            f"{estimate.p_adjusted:.3f} | {_mde(estimate, plain=True)} | "
            f"{verdict} |"
        )
    lines.extend(["", *(f"- {line}" for line in _caveats(analysis, plain=True))])
    return "\n".join(lines)


def _mde(estimate: Estimate, *, plain: bool = False) -> str:
    if math.isinf(estimate.mde):
        return "—"
    return f"{estimate.mde:.2f}" if plain else f"[dim]{estimate.mde:.2f}[/dim]"


def _caveats(analysis: Analysis, *, plain: bool = False) -> list[str]:
    """The sentences that stop a reader over-claiming. Always printed."""
    primary = {m.name for m in analysis.experiment.primary}
    resolved = [e for e in analysis.resolved if e.metric in primary]
    unresolved = [
        e for e in analysis.estimates if e.verdict is Verdict.UNRESOLVED and e.metric in primary
    ]
    out: list[str] = []

    if resolved:
        names = ", ".join(f"`{e.metric}`" for e in resolved)
        out.append(f"Resolved at n={analysis.n_pairs}: {names}.")
    else:
        out.append(
            f"Nothing resolved at n={analysis.n_pairs}. That is a statement about this "
            "experiment's power as much as about the skill -- read the MDE column."
        )
    if unresolved:
        worst = max(unresolved, key=lambda e: e.mde if math.isfinite(e.mde) else 0.0)
        if math.isfinite(worst.mde):
            out.append(
                f"Unresolved metrics are not null results: `{worst.metric}` could only have "
                f"resolved a difference of {worst.mde:.2f} or larger at this sample size."
            )
    degenerate = [
        e for e in analysis.estimates if e.metric in primary and e.verdict is Verdict.IDENTICAL
    ]
    for estimate in degenerate:
        # The most dangerous row in the table: identical arms look like "no
        # effect" and usually mean "this metric could not have shown one".
        out.append(
            f"`{estimate.metric}` was **identical in every pair** "
            f"({estimate.baseline_mean:.2f} in both arms). That is a property of the task "
            "suite, not a finding about the skill: a metric pinned at its ceiling or floor "
            "has no room to move and no variance to estimate power from."
        )

    out.append(
        "Behaviour and outcome are separate claims. A metric moving means the agent "
        "worked differently; only `task_success` speaks to whether the code was right."
    )
    out.append(
        f"Italic/dim rows are exploratory: reported uncorrected, and not evidence for a "
        f"claim. Only the {len(primary)} primary metric(s) share the Holm correction."
    )
    if not plain:
        out.append("[dim]MDE = smallest true difference this many pairs could resolve.[/dim]")
    return out


__all__ = ["console_report", "markdown_report"]

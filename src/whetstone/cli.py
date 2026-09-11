"""`whet` -- run a skill A/B experiment, and analyse one that has already run.

Three commands, split along the line that matters: `run` spends model time,
`analyze` and `report` do not. Anyone can re-derive the published numbers from
the committed records without a `claude` binary, an API key, or a network.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from whetstone import results as results_mod
from whetstone.analyze import analyze
from whetstone.capture import Runner, available
from whetstone.report import console_report, markdown_report
from whetstone.spec import Experiment, SpecError
from whetstone.stats import min_pairs_for_binary
from whetstone.tasks import TaskError, discover

app = typer.Typer(add_completion=False, help=__doc__)
# A fixed width when stdout is not a terminal: the results table is the
# deliverable, and letting it wrap to 80 columns in a redirected log or a CI
# transcript makes the numbers unreadable exactly where they get quoted from.
console = Console(width=None if sys.stdout.isatty() else 132)
errors = Console(stderr=True, soft_wrap=True)

ExperimentArg = Annotated[Path, typer.Argument(help="The pre-registered experiment YAML.")]
ResultsOpt = Annotated[Path, typer.Option("--results", "-r", help="Directory of recorded runs.")]


@app.command()
def run(
    experiment: ExperimentArg,
    tasks: Annotated[Path, typer.Option("--tasks", "-t", help="Task fixtures.")] = Path("tasks"),
    results: ResultsOpt = Path("runs"),
    skills: Annotated[Path, typer.Option("--skills", help="Skill directory.")] = Path("skills"),
    repeats: Annotated[int | None, typer.Option("--repeats", "-k", help="Override spec.")] = None,
    only: Annotated[str | None, typer.Option("--only", help="Run one task by name.")] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Skip (task, arm, repeat) triples that already ran."),
    ] = False,
    keep: Annotated[bool, typer.Option("--keep", help="Keep working directories.")] = False,
) -> None:
    """Execute the experiment. This is the command that costs model time."""
    spec = _load(experiment)
    if not available():
        errors.print("[red]`claude` is not on PATH.[/red] `whet run` needs it; `analyze` does not.")
        raise typer.Exit(2)

    try:
        suite = discover(tasks)
    except TaskError as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    if only:
        suite = [task for task in suite if task.name == only]
        if not suite:
            errors.print(f"[red]no task named {only!r}[/red]")
            raise typer.Exit(2)

    k = repeats or spec.repeats

    # Resume, because an experiment is an hour or more of model time and the
    # ways it dies are mundane: a usage limit, a laptop lid, a dropped network.
    # Losing the completed half to restart the failed half is the kind of cost
    # that quietly discourages re-running an experiment at all.
    done: set[tuple[str, str, int]] = set()
    if resume:
        done = {
            record.key
            for record in results_mod.load(results)
            if record.executed and not record.error
        }
        if done:
            console.print(f"[dim]resuming: {len(done)} completed run(s) already on disk[/dim]")

    planned = [
        (task, arm, repeat)
        for task in suite
        for repeat in range(k)
        for arm in spec.arms
        if (task.name, arm.name, repeat) not in done
    ]
    total = len(planned)
    console.print(
        f"[bold]{spec.name}[/bold] spec {spec.digest} · {len(suite)} task(s) x "
        f"{len(spec.arms)} arm(s) x {k} repeat(s) = [bold]{total}[/bold] agent run(s)"
    )

    runner = Runner(
        experiment=spec,
        skills_root=skills,
        results_dir=results,
        cassettes_dir=results / "cassettes",
        keep_workdirs=keep,
    )
    # `planned` interleaves the arms within each repeat rather than running them
    # in blocks, so a drift in model behaviour over the hour lands on both arms
    # equally instead of on whichever one ran last.
    refused = 0
    for index, (task, arm, repeat) in enumerate(planned, start=1):
        console.print(f"  [{index}/{total}] {task.name} · {arm.name} · repeat {repeat}", end=" ")
        record = runner.run_one(task, arm, repeat)
        results_mod.append(results, record)
        if not record.executed:
            refused += 1
            console.print(f"→ [red]did not run[/red] {record.error}")
            if refused >= 3:
                # Three refusals in a row is a wall, not a blip. Continuing
                # would fill the results file with non-runs and -- before this
                # was detected -- scored every one of them as a failed task.
                console.print(
                    "\n[red]stopping[/red]: three consecutive runs were refused before "
                    "starting. Nothing further will execute. Re-run with [bold]--resume[/bold] "
                    "once the limit clears; completed runs are already on disk."
                )
                break
            continue
        refused = 0
        verdict = "[green]pass[/green]" if record.task_success else "[red]fail[/red]"
        note = f" [yellow]{record.error}[/yellow]" if record.error else ""
        console.print(f"→ {verdict} ({record.duration_s:.0f}s){note}")

    console.print(f"\nwrote to {results / results_mod.RESULTS_FILE}")
    _analyze_and_print(spec, results, markdown=None)


@app.command()
def report(
    experiment: ExperimentArg,
    results: ResultsOpt = Path("runs"),
    markdown: Annotated[Path | None, typer.Option("--md", help="Also write Markdown.")] = None,
) -> None:
    """Analyse recorded runs. No model, no key, no network."""
    _analyze_and_print(_load(experiment), results, markdown=markdown)


@app.command()
def calibrate(
    experiment: ExperimentArg,
    tasks: Annotated[Path, typer.Option("--tasks", "-t")] = Path("tasks"),
    results: ResultsOpt = Path("runs-calibration"),
    repeats: Annotated[int, typer.Option("--repeats", "-k")] = 3,
    low: Annotated[float, typer.Option("--low", help="Lower edge of the useful band.")] = 0.3,
    high: Annotated[float, typer.Option("--high", help="Upper edge.")] = 0.7,
) -> None:
    """Run the CONTROL arm only, and report which tasks can show a difference.

    The step both of this project's own experiments needed and neither had.

    A task the baseline always passes cannot show an improvement; a task it
    always fails cannot either. v1 discovered this the expensive way -- every
    one of its tasks was passed by both arms or failed by both, so the outcome
    metric was structurally incapable of moving, and it took a full experiment
    to find out.

    Calibration is cheap because it runs one arm. Keep the tasks whose baseline
    success falls inside the band, and an experiment built on them can at least
    answer its own question.
    """
    spec = _load(experiment)
    if not available():
        errors.print("[red]`claude` is not on PATH.[/red]")
        raise typer.Exit(2)
    try:
        suite = discover(tasks)
    except TaskError as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    control = spec.baseline
    runner = Runner(
        experiment=spec,
        skills_root=Path("skills"),
        results_dir=results,
        cassettes_dir=results / "cassettes",
    )
    console.print(
        f"calibrating {len(suite)} task(s) x {repeats} control run(s) = "
        f"[bold]{len(suite) * repeats}[/bold] runs (one arm only)"
    )

    outcomes: dict[str, list[bool]] = {}
    refused = 0
    for task in suite:
        for repeat in range(repeats):
            record = runner.run_one(task, control, repeat)
            results_mod.append(results, record)
            if not record.executed:
                refused += 1
                if refused >= 3:
                    console.print("[red]stopping[/red]: three consecutive refusals.")
                    break
                continue
            refused = 0
            outcomes.setdefault(task.name, []).append(record.task_success)
        else:
            continue
        break

    table = Table(box=None, pad_edge=False)
    table.add_column("task", no_wrap=True, min_width=24)
    table.add_column("baseline", justify="right")
    table.add_column("verdict")
    usable = 0
    for task in suite:
        got = outcomes.get(task.name)
        if not got:
            table.add_row(task.name, "—", "[dim]not run[/dim]")
            continue
        rate = sum(got) / len(got)
        if rate > high:
            verdict = "[yellow]too easy[/yellow] — no room to improve"
        elif rate < low:
            verdict = "[yellow]too hard[/yellow] — no room to improve"
        else:
            verdict = "[green]usable[/green]"
            usable += 1
        table.add_row(task.name, f"{sum(got)}/{len(got)}", verdict)
    console.print()
    console.print(table)
    console.print(
        f"\n[bold]{usable}[/bold] of {len(suite)} task(s) inside the {low:.0%}-{high:.0%} band."
    )
    floor = min_pairs_for_binary(spec.alpha)
    if usable < floor:
        console.print(
            f"[red]not enough[/red]: a binary primary metric needs at least {floor} usable "
            "tasks before any result is achievable. Write harder or easier tasks rather than "
            "running an experiment that cannot answer its question."
        )


@app.command()
def remeasure(
    results: ResultsOpt = Path("runs"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report, do not write.")] = False,
    restamp: Annotated[
        Path | None,
        typer.Option("--restamp", help="Re-stamp records with this experiment's run digest."),
    ] = None,
) -> None:
    """Recompute behavioural metrics from the stored cassettes.

    The reason the cassettes are committed. A metric definition can be wrong --
    ours was: `test_run_after_edit` looked only for test *runners*, and missed
    that the control arm was verifying its work with throwaway
    `python3 -c "from money import ..."` scripts. Fixing that would normally
    mean re-running the whole experiment at hours of model time. Instead the
    transcripts are on disk, so the fix is re-derived from the same evidence.

    Only metrics that are a function of the transcript are touched.
    `task_success`, `duration_s` and `error` are observations from the run
    itself and are carried through untouched.
    """
    from flightrec.cassette import store

    from whetstone.capture import _refusal_text
    from whetstone.extract import observe

    records = results_mod.load(results)
    if not records:
        errors.print(f"[red]no runs found in {results}[/red]")
        raise typer.Exit(2)

    stamp: str | None = None
    if restamp is not None:
        # Only ever the *run* digest, and only from a spec whose arms and
        # repeats are the ones these records were produced under -- which the
        # operator is asserting by passing the flag. It exists because splitting
        # the digest in two left already-recorded runs carrying the old
        # combined hash; without it they would read as evidence from a different
        # experiment forever.
        stamp = _load(restamp).run_digest
        console.print(f"re-stamping {len(records)} record(s) with run digest [bold]{stamp}[/bold]")

    changed = 0
    missing = 0
    for record in records:
        if stamp is not None:
            record.spec_digest = stamp
        path = results / record.cassette if record.cassette else None
        if path is None or not path.exists():
            missing += 1
            continue
        cassette = store.load(path)

        # Re-derive whether the agent ran at all, not just what it did. Records
        # written before refusal detection existed carry `executed: true` and a
        # fabricated `task_success: false`; this is what corrects them.
        refusal = _refusal_text(cassette)
        behaviour = observe(cassette)
        fresh = behaviour.as_metrics()

        if refusal is not None and record.executed:
            record.executed = False
            record.error = f"the agent never ran: {refusal}"
            record.task_success = False
            changed += 1
        elif any(record.metrics.get(k) != v for k, v in fresh.items()):
            changed += 1

        record.metrics.update(fresh)
        record.touched = behaviour.touched_paths

    refused = sum(1 for r in records if not r.executed)
    console.print(
        f"{len(records)} record(s) · {changed} changed"
        + (f" · [red]{refused} never executed[/red]" if refused else "")
        + (f" · [yellow]{missing} cassette(s) missing[/yellow]" if missing else "")
    )
    if dry_run:
        return

    target = results / results_mod.RESULTS_FILE
    target.write_text("", encoding="utf-8")
    for record in records:
        results_mod.append(results, record)
    console.print(f"rewrote {target}")


@app.command()
def check(
    experiment: ExperimentArg,
    tasks_dir: Annotated[Path, typer.Option("--tasks", "-t")] = Path("tasks"),
) -> None:
    """Validate an experiment and print its digest, before spending anything."""
    spec = _load(experiment)
    console.print(f"[green]valid[/green] · {spec.name} · spec [bold]{spec.digest}[/bold]")
    console.print(
        f"  {spec.baseline.name} (control) vs {spec.treatment.name} "
        f"(skill: {spec.treatment.skill or 'none'})"
    )
    for metric in spec.metrics:
        console.print(f"  [dim]{metric.kind:10}[/dim] {metric.name:32} {metric.rationale}")

    # The check worth doing before an hour of model time rather than after.
    binary = [m for m in spec.primary if m.is_binary]
    if binary:
        floor = min_pairs_for_binary(spec.alpha)
        try:
            available = len(discover(tasks_dir))
        except TaskError:
            available = 0
        names = ", ".join(m.name for m in binary)
        if available and available < floor:
            console.print(
                f"\n[red]underpowered[/red]: {available} task(s) cannot resolve a binary "
                f"metric ({names}) at alpha {spec.alpha}. An exact two-sided McNemar test "
                f"bottoms out at 2/2^n, so it needs at least [bold]{floor}[/bold] paired "
                "tasks even if every one of them flips. Add tasks, or expect an unresolvable "
                "experiment."
            )
        elif available:
            console.print(
                f"\n[green]powered[/green]: {available} tasks vs a floor of {floor} for the "
                f"binary primary metric(s) ({names})."
            )


def _load(path: Path) -> Experiment:
    try:
        return Experiment.load(path)
    except SpecError as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc


def _analyze_and_print(spec: Experiment, results: Path, *, markdown: Path | None) -> None:
    records = results_mod.load(results)
    if not records:
        errors.print(f"[red]no runs found in {results}[/red]")
        raise typer.Exit(2)
    try:
        analysis = analyze(spec, records)
    except SpecError as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    console_report(analysis, console)
    if markdown:
        markdown.write_text(markdown_report(analysis) + "\n", encoding="utf-8")
        console.print(f"wrote {markdown}")
    if not analysis.digest_matches:
        raise typer.Exit(1)


def main() -> int:  # pragma: no cover
    app()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

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

from whetstone import results as results_mod
from whetstone.analyze import analyze
from whetstone.capture import Runner, available
from whetstone.report import console_report, markdown_report
from whetstone.spec import Experiment, SpecError
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
    total = len(suite) * len(spec.arms) * k
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
    done = 0
    for task in suite:
        for repeat in range(k):
            # Arms are interleaved per repeat rather than run in blocks, so a
            # drift in model behaviour over the hour lands on both arms equally
            # instead of on whichever one ran last.
            for arm in spec.arms:
                done += 1
                console.print(
                    f"  [{done}/{total}] {task.name} · {arm.name} · repeat {repeat}", end=" "
                )
                record = runner.run_one(task, arm, repeat)
                results_mod.append(results, record)
                verdict = "[green]pass[/green]" if record.task_success else "[red]fail[/red]"
                note = f" [yellow]{record.error}[/yellow]" if record.error else ""
                console.print(f"→ {verdict} ({record.duration_s:.0f}s){note}")

    console.print(f"\nwrote {total} record(s) to {results / results_mod.RESULTS_FILE}")
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
        behaviour = observe(store.load(path))
        fresh = behaviour.as_metrics()
        if any(record.metrics.get(k) != v for k, v in fresh.items()):
            changed += 1
        record.metrics.update(fresh)
        record.touched = behaviour.touched_paths

    console.print(
        f"{len(records)} record(s) · {changed} changed"
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
def check(experiment: ExperimentArg) -> None:
    """Validate an experiment and print its digest, before spending anything."""
    spec = _load(experiment)
    console.print(f"[green]valid[/green] · {spec.name} · spec [bold]{spec.digest}[/bold]")
    console.print(
        f"  {spec.baseline.name} (control) vs {spec.treatment.name} "
        f"(skill: {spec.treatment.skill or 'none'})"
    )
    for metric in spec.metrics:
        console.print(f"  [dim]{metric.kind:10}[/dim] {metric.name:32} {metric.rationale}")


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

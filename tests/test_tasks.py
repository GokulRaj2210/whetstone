"""Every task must actually be broken, and must be fixable.

A fixture whose hidden tests already pass measures nothing -- both arms score
100% and the outcome metric is dead weight. A fixture that cannot be fixed
measures nothing either, and worse, it looks like a finding: both arms score 0%
and it reads as "the skill did not help".

So both properties are asserted here, against a hand-written reference fix for
every task. These tests run in CI with no model involved.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from whetstone.tasks import discover

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks"
FIXES_ROOT = Path(__file__).resolve().parent / "reference_fixes"


def _run_hidden_tests(task, workdir: Path) -> bool:
    for source in task.verify_dir.iterdir():
        shutil.copy2(source, workdir / source.name)
    # A timeout, because a broken fixture can hang rather than fail -- an
    # earlier trap task's bug was an infinite loop, and the suite that was
    # supposed to catch bad fixtures instead hung on one.
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=workdir,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


def task_names() -> list[str]:
    return [task.name for task in discover(TASKS_ROOT)]


@pytest.mark.parametrize("name", task_names())
def test_the_task_starts_broken(name: str, tmp_path: Path) -> None:
    """The hidden tests must fail on the pristine repo.

    If they pass, the task is not a task: every arm succeeds and the outcome
    metric silently stops discriminating.
    """
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    workdir = task.stage(tmp_path)
    assert not _run_hidden_tests(task, workdir), (
        f"{name} passes its own hidden tests before anything is changed"
    )


@pytest.mark.parametrize("name", task_names())
def test_the_task_is_fixable(name: str, tmp_path: Path) -> None:
    """A hand-written reference fix must make the hidden tests pass.

    This is what stops an unfair fixture from masquerading as a null result: a
    task no correct change could satisfy would show both arms failing and read
    as evidence about the skill.
    """
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    fix = FIXES_ROOT / name
    assert fix.is_dir(), f"{name} has no reference fix in {FIXES_ROOT}"

    workdir = task.stage(tmp_path)
    for source in fix.iterdir():
        shutil.copy2(source, workdir / source.name)
    assert _run_hidden_tests(task, workdir), (
        f"the reference fix for {name} does not satisfy its own hidden tests"
    )


@pytest.mark.parametrize("name", [n for n in task_names() if n.startswith("trap-")])
def test_a_trap_tasks_visible_suite_starts_green(name: str, tmp_path: Path) -> None:
    """A regression trap only works if the suite it protects is already passing.

    These tasks exist to test one specific mechanism: the skill runs the
    project's test suite where the control runs an inline snippet. The trap is a
    naive fix that silences the reported symptom and breaks a *visible*,
    currently-passing test. If the suite were already red, breaking it further
    would be invisible and the task would measure nothing.
    """
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    workdir = task.stage(tmp_path)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, (
        f"{name}'s visible suite is not green before the fix:\n{completed.stdout[-800:]}"
    )


@pytest.mark.parametrize("name", [n for n in task_names() if n.startswith("trap-")])
def test_a_trap_task_ships_a_visible_suite(name: str) -> None:
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    visible = list(task.repo.glob("test_*.py"))
    assert visible, f"{name} has no visible test file, so there is nothing to break"


def test_every_task_declares_what_it_is() -> None:
    """`describes` feeds the README table, so a blank one is a silent gap."""
    for task in discover(TASKS_ROOT):
        assert task.describes, f"{task.name} has no `describes`"
        assert task.prompt.strip(), f"{task.name} has no prompt"


NAIVE_ROOT = Path(__file__).resolve().parent / "naive_fixes"


def _apply(fix_root: Path, name: str, workdir: Path) -> bool:
    fix = fix_root / name
    if not fix.is_dir():
        return False
    for source in fix.iterdir():
        shutil.copy2(source, workdir / source.name)
    return True


def _visible_suite_passes(workdir: Path) -> bool:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=workdir,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


@pytest.mark.parametrize("name", [n for n in task_names() if n.startswith("trap-")])
def test_the_naive_fix_is_caught_by_running_the_suite(name: str, tmp_path: Path) -> None:
    """The mechanism the trap tasks exist to test, verified without a model.

    The experiment's finding was that the skill's real effect is running the
    project's test suite where the control runs an inline snippet checking only
    the reported case. A task can only detect that if the plausible hurried fix
    *passes the reported symptom and fails the visible suite*.

    So: apply the naive fix, and assert the visible suite goes red. If it stays
    green, the task cannot distinguish the arms and it is measuring something
    else -- which is exactly the mistake the first round of tasks made.
    """
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    workdir = task.stage(tmp_path)
    assert _apply(NAIVE_ROOT, name, workdir), f"{name} has no naive fix to check against"
    assert not _visible_suite_passes(workdir), (
        f"{name}: the naive fix leaves the visible suite green, so running it would not "
        "catch the mistake and the task cannot separate the arms"
    )


@pytest.mark.parametrize("name", [n for n in task_names() if n.startswith("trap-")])
def test_the_reference_fix_keeps_the_suite_green(name: str, tmp_path: Path) -> None:
    """The other half: a correct fix must not break the visible suite either."""
    task = next(t for t in discover(TASKS_ROOT) if t.name == name)
    workdir = task.stage(tmp_path)
    assert _apply(FIXES_ROOT, name, workdir)
    assert _visible_suite_passes(workdir)


def test_a_hidden_test_may_not_demand_more_than_the_prompt_asks() -> None:
    """A fixture must be satisfiable by a competent reading of its own prompt.

    `masking-bug` was deleted for failing this. Its prompt reported that
    trailing spaces were accepted; the agent fixed exactly that, correctly, and
    the hidden test then failed it for not also adding a minimum-length check
    nobody had mentioned. The task scored 0/2 in calibration and would have read
    as a hard task the skill could not help with, when it was simply unfair.

    There is no automatic check for this -- fairness is a judgement about
    whether the prompt implies the contract. What is asserted here is the
    weaker, checkable thing: every task ships a reference fix, and that fix is
    the *documented* correct behaviour rather than a guess at the hidden test.
    """
    for task in discover(TASKS_ROOT):
        fix = FIXES_ROOT / task.name
        assert fix.is_dir(), (
            f"{task.name} has no reference fix. Writing one is what surfaces a hidden test "
            "that demands more than the prompt asks for."
        )

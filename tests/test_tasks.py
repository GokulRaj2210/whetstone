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
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
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


def test_every_task_declares_what_it_is() -> None:
    """`describes` feeds the README table, so a blank one is a silent gap."""
    for task in discover(TASKS_ROOT):
        assert task.describes, f"{task.name} has no `describes`"
        assert task.prompt.strip(), f"{task.name} has no prompt"

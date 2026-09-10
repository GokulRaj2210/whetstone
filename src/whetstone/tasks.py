"""Task fixtures: a starting repo, a prompt, and a test the agent never sees.

The hidden test is the single most important design decision in the project.

The obvious way to score "did the skill improve the code" is to have a model
grade the diff. That is worthless here: the grader shares the experimenter's
prior, the rubric is written by the person hoping for an effect, and the whole
thing is unfalsifiable. So instead every task ships a test that lives outside
the working directory, is copied in only after the agent has finished, and
either passes or does not.

That gives one honest binary outcome -- `task_success` -- and it is the only
quality claim this project makes. Everything else it measures is *behaviour*,
which is interesting but is not the same thing, and the report keeps the two
apart on purpose.

Layout of a task::

    tasks/off-by-one/
      task.yaml       prompt, verify command, timeout
      repo/           copied into a fresh workdir; this is all the agent sees
      verify/         copied in *after* the run, then `verify` is executed
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: Where a task's hidden tests are staged. Named so that an agent listing the
#: directory during a run sees nothing suggestive -- it is not there yet.
VERIFY_DIR = "verify"
REPO_DIR = "repo"
TASK_FILE = "task.yaml"


class TaskError(ValueError):
    """A task fixture is malformed."""


@dataclass(frozen=True, slots=True)
class Task:
    """One unit of the paired design: the same task runs in both arms."""

    name: str
    prompt: str
    #: Shell command run after the hidden tests are staged. Exit 0 means the
    #: agent's change actually worked.
    verify: str = "python -m pytest -q"
    #: Per-run wall clock ceiling. A run that hits it is recorded as a failure
    #: rather than discarded, because "the skill made it time out" is a result.
    timeout_s: int | None = None
    #: One line on what is actually broken. For the README table, and to make a
    #: reviewer able to judge whether the suite is fair.
    describes: str = ""
    directory: Path = Path()

    @property
    def repo(self) -> Path:
        return self.directory / REPO_DIR

    @property
    def verify_dir(self) -> Path:
        return self.directory / VERIFY_DIR

    def stage(self, workdir: Path) -> Path:
        """Copy the starting repo into a fresh working directory."""
        target = workdir / self.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.repo, target)
        return target

    def check(self, workdir: Path, *, timeout_s: int = 120) -> bool:
        """Stage the hidden tests into ``workdir`` and run them.

        Copied in only now, so nothing the agent read could have contained them.
        A task whose tests were visible would measure the agent's ability to
        read a test file, which is not the question.
        """
        for source in self.verify_dir.iterdir():
            destination = workdir / source.name
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
        try:
            completed = subprocess.run(
                self.verify,
                shell=True,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return False
        return completed.returncode == 0

    @classmethod
    def load(cls, directory: Path | str) -> Task:
        path = Path(directory)
        definition = path / TASK_FILE
        if not definition.exists():
            raise TaskError(f"{path} has no {TASK_FILE}")
        try:
            raw: Any = yaml.safe_load(definition.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise TaskError(f"could not read {definition}: {exc}") from exc
        if not isinstance(raw, dict):
            raise TaskError(f"{definition} must contain a mapping")

        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            raise TaskError(f"{definition} has no `prompt`")
        if not (path / REPO_DIR).is_dir():
            raise TaskError(f"{path} has no {REPO_DIR}/ directory")
        if not (path / VERIFY_DIR).is_dir():
            raise TaskError(
                f"{path} has no {VERIFY_DIR}/ directory. Every task needs a hidden test: "
                "without one the only outcome measure left is a judgement call."
            )

        timeout = raw.get("timeout_s")
        return cls(
            name=str(raw.get("name") or path.name),
            prompt=prompt,
            verify=str(raw.get("verify") or "python -m pytest -q"),
            timeout_s=int(timeout) if timeout else None,
            describes=str(raw.get("describes") or ""),
            directory=path,
        )


def discover(root: Path | str) -> list[Task]:
    """Every task under ``root``, in a stable order.

    Sorted by name so a report's rows do not shuffle between runs -- a table
    that reorders itself is a table nobody can diff.
    """
    return sorted(_iter_tasks(Path(root)), key=lambda task: task.name)


def _iter_tasks(root: Path) -> Iterator[Task]:
    if not root.is_dir():
        raise TaskError(f"{root} is not a directory")
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / TASK_FILE).exists():
            yield Task.load(entry)


__all__ = ["REPO_DIR", "VERIFY_DIR", "Task", "TaskError", "discover"]

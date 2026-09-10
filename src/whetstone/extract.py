"""Behavioural metrics: what the agent actually did, read off the tool spans.

The point of the whole project is that "the skill helped" has to cash out as
something observable. These are the observables. Each one is a mechanical
consequence of one of the skill's gates, chosen so that a reader can object to
the *definition* rather than having to trust a judgement call:

    gate                      metric it must move
    ----------------------    ------------------------------------------
    read before you edit      files_read_before_first_edit
    get a signal first        test_run_before_edit, test_run_after_edit
    prune your context        repeat_reads, total_tokens
    do not go shallow         files_touched, task_success

Deliberately *not* here: anything resembling a quality score. There is no LLM
judge and no rubric, because a judge that shares the experimenter's hopes is not
evidence. The quality signal in this project is `task_success` -- a hidden test,
not in the agent's context, that either passes afterwards or does not.

`flightrec` already computes the cost-side metrics (tokens, cost, duration, tool
counts). This module adds only what is specific to *how the work was done*.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from flightrec.models import Cassette, Span

#: Tools that change a file. Anything here counts as "editing" for the purpose
#: of the before/after split that most of these metrics turn on.
EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

#: Tools that only look. `Task`/`Agent` are excluded on purpose: a subagent's
#: reads are not this agent's context, and counting them would credit the skill
#: for work it delegated.
READ_TOOLS = frozenset({"Read", "NotebookRead"})

#: Tools that search rather than read in full. Kept separate because "grepped
#: the file" is precisely the shallow behaviour the skill is meant to replace.
SEARCH_TOOLS = frozenset({"Grep", "Glob"})

#: A command counts as running tests if its *executable* is one of these, or if
#: it is a runner invoked through a package manager. Matching on the whole
#: string would count `cat pytest.ini`, and matching on a bare substring would
#: count `git commit -m "add pytest"`.
_TEST_EXECUTABLES = frozenset({"pytest", "py.test", "tox", "nox", "unittest", "go", "cargo"})
_TEST_SUBCOMMANDS = {
    "go": {"test"},
    "cargo": {"test"},
    "npm": {"test", "t"},
    "yarn": {"test"},
    "pnpm": {"test"},
    "uv": {"run"},
    "poetry": {"run"},
    "make": {"test", "check"},
    "python": {"-m"},
    "python3": {"-m"},
}
_TEST_MODULES = frozenset({"pytest", "unittest", "nose2"})

#: Interpreters that execute a program given inline on the command line.
#: `python3 -c "from money import round_money; print(round_money(0.29))"` is not
#: a test-suite run, but it is unmistakably the agent checking its own work --
#: and treating it as "did not verify" would have been simply wrong. This
#: distinction was not anticipated; it was found by reading what the control arm
#: actually ran. See `verified_after_edit`.
_INLINE_FLAGS = {
    "python": "-c",
    "python3": "-c",
    "node": "-e",
    "ruby": "-e",
    "perl": "-e",
    "php": "-r",
}


@dataclass(slots=True)
class Behaviour:
    """One run's observable behaviour. Every field is a metric or supports one."""

    #: Reads that happened before the first edit. The direct signature of
    #: "understand before you change".
    files_read_before_first_edit: float = 0.0
    #: Searches before the first edit, tracked separately: grepping is not reading.
    searches_before_first_edit: float = 0.0
    #: Did a test command run *before* the first edit -- i.e. was there a signal
    #: to work against, rather than a guess to verify afterwards.
    test_run_before_edit: bool = False
    #: Did a test command run after the last edit.
    test_run_after_edit: bool = False
    #: Did the agent check its work *at all* after the last edit -- the test
    #: suite, or an inline script exercising the changed code. Strictly weaker
    #: than `test_run_after_edit` and strictly more honest: an agent that runs
    #: `python3 -c "from money import round_money; print(...)"` has verified
    #: something, whatever one thinks of the method.
    verified_after_edit: bool = False
    #: Distinct files written to.
    files_touched: float = 0.0
    #: Reads of a file already read earlier. Context that had to be re-fetched
    #: because the first copy was buried -- the attention-residue analogue.
    repeat_reads: float = 0.0
    #: Tool calls whose subject never appears again. Exploration that went
    #: nowhere and stayed in the window anyway.
    dead_end_tool_calls: float = 0.0
    #: Total tool calls, and the edit/read split, for context.
    tool_calls: float = 0.0
    edits: float = 0.0
    #: Files the run touched, kept for the task verifier and for debugging.
    touched_paths: list[str] = field(default_factory=list)

    def as_metrics(self) -> dict[str, float]:
        """The numeric view, which is what the statistics consume."""
        return {
            "files_read_before_first_edit": self.files_read_before_first_edit,
            "searches_before_first_edit": self.searches_before_first_edit,
            "test_run_before_edit": float(self.test_run_before_edit),
            "test_run_after_edit": float(self.test_run_after_edit),
            "verified_after_edit": float(self.verified_after_edit),
            "files_touched": self.files_touched,
            "repeat_reads": self.repeat_reads,
            "dead_end_tool_calls": self.dead_end_tool_calls,
            "tool_calls": self.tool_calls,
            "edits": self.edits,
        }


#: Metrics from this module that are 0/1 and must be tested with McNemar rather
#: than a bootstrap on means.
BINARY_METRICS = frozenset(
    {"test_run_before_edit", "test_run_after_edit", "verified_after_edit", "task_success"}
)


def observe(cassette: Cassette) -> Behaviour:
    """Read one run's behaviour off its tool spans."""
    tools = [span for span in cassette.tool_calls if span.tool]
    first_edit = _first_edit_index(tools)

    behaviour = Behaviour(tool_calls=float(len(tools)))
    seen_paths: set[str] = set()
    touched: list[str] = []

    for index, span in enumerate(tools):
        assert span.tool is not None
        name = span.tool.name
        path = _path_of(span)

        if name in EDIT_TOOLS:
            behaviour.edits += 1
            if path and path not in touched:
                touched.append(path)
        elif name in READ_TOOLS:
            if path:
                if path in seen_paths:
                    behaviour.repeat_reads += 1
                seen_paths.add(path)
            if first_edit is None or index < first_edit:
                behaviour.files_read_before_first_edit += 1
        elif name in SEARCH_TOOLS and (first_edit is None or index < first_edit):
            behaviour.searches_before_first_edit += 1

    behaviour.touched_paths = touched
    behaviour.files_touched = float(len(touched))
    last_edit = _last_edit_index(tools)
    behaviour.test_run_before_edit = _ran_tests(tools, before=first_edit)
    behaviour.test_run_after_edit = _ran_tests(tools, after=last_edit)
    behaviour.verified_after_edit = behaviour.test_run_after_edit or _ran_inline_check(
        tools, after=last_edit
    )
    behaviour.dead_end_tool_calls = float(_count_dead_ends(tools))
    return behaviour


# ---------------------------------------------------------------------------
# the pieces
# ---------------------------------------------------------------------------


def _first_edit_index(tools: Sequence[Span]) -> int | None:
    for index, span in enumerate(tools):
        if span.tool and span.tool.name in EDIT_TOOLS:
            return index
    return None


def _last_edit_index(tools: Sequence[Span]) -> int | None:
    for index in range(len(tools) - 1, -1, -1):
        span = tools[index]
        if span.tool and span.tool.name in EDIT_TOOLS:
            return index
    return None


def _path_of(span: Span) -> str | None:
    if not span.tool:
        return None
    arguments = span.tool.arguments or {}
    for key in ("file_path", "notebook_path", "path", "filePath"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _ran_tests(
    tools: Sequence[Span], *, before: int | None = None, after: int | None = None
) -> bool:
    """Was a test command run in the given window.

    ``before=None`` with ``after=None`` means "anywhere". A window bound that is
    None because there was no edit means the window is the whole run, which is
    the right reading: if nothing was edited, every test run is both before and
    after the (nonexistent) edit.
    """
    for index, span in enumerate(tools):
        if before is not None and index >= before:
            continue
        if after is not None and index <= after:
            continue
        if (
            span.tool
            and span.tool.name == "Bash"
            and is_test_command(str((span.tool.arguments or {}).get("command", "")))
        ):
            return True
    return False


def _ran_inline_check(tools: Sequence[Span], *, after: int | None) -> bool:
    """Did the agent execute the changed code inline after editing?"""
    for index, span in enumerate(tools):
        if after is not None and index <= after:
            continue
        if (
            span.tool
            and span.tool.name == "Bash"
            and is_inline_check(str((span.tool.arguments or {}).get("command", "")))
        ):
            return True
    return False


def is_inline_check(command: str) -> bool:
    """Does this command run a program given on the command line?

    Requires an `import` or `require` in the inline source, so that
    `python3 -c "print(1)"` -- which exercises nothing in the repo -- does not
    count. Erring toward counting is deliberate: over-crediting the *control*
    arm shrinks the measured effect, which is the safe direction to be wrong in.
    """
    for part in _split_commands(command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        if not words:
            continue
        executable = words[0].rsplit("/", 1)[-1]
        flag = _INLINE_FLAGS.get(executable)
        if flag and flag in words[1:]:
            source = " ".join(words[1:])
            if "import" in source or "require" in source:
                return True
    return False


def is_test_command(command: str) -> bool:
    """Does this shell command run a test suite?

    Matched on the executable and its first arguments rather than by substring.
    `grep pytest setup.cfg` is not a test run, and `git commit -m "fix pytest"`
    very much is not -- both of which a substring check would happily count, in
    the direction that flatters the skill.

    Compound commands are split, so `cd sub && pytest` is caught.
    """
    for part in _split_commands(command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        if _is_test_invocation(words):
            return True
    return False


def _split_commands(command: str) -> Iterable[str]:
    return (piece.strip() for piece in re.split(r"&&|\|\||;|\|", command) if piece.strip())


def _is_test_invocation(words: list[str]) -> bool:
    while words and ("=" in words[0] and not words[0].startswith("-")):
        words = words[1:]  # leading VAR=value assignments
    if not words:
        return False
    executable = words[0].rsplit("/", 1)[-1]
    rest = words[1:]

    if executable in {"python", "python3"} and rest[:1] == ["-m"]:
        return len(rest) > 1 and rest[1] in _TEST_MODULES
    if executable in _TEST_SUBCOMMANDS:
        allowed = _TEST_SUBCOMMANDS[executable]
        if not rest:
            return False
        if rest[0] not in allowed:
            return False
        if executable in {"uv", "poetry"}:
            # `uv run pytest` is a test run; `uv run python app.py` is not.
            return _is_test_invocation(rest[1:])
        if executable in {"python", "python3"}:
            return len(rest) > 1 and rest[1] in _TEST_MODULES
        return True
    return executable in _TEST_EXECUTABLES and executable not in _TEST_SUBCOMMANDS


def _count_dead_ends(tools: Sequence[Span]) -> int:
    """Tool calls whose subject is never mentioned again.

    The operational stand-in for attention residue: context that was fetched,
    never used, and never left. A read is a dead end when the file's name never
    appears in any later tool argument and the file is never edited; a failed
    tool call is a dead end unless something later refers to what it touched.

    This is a heuristic and is documented as one -- it under-counts exploration
    that is referenced only in prose the model never repeats. It is still worth
    having, because the alternative is not measuring the thing at all.
    """
    dead = 0
    for index, span in enumerate(tools):
        if not span.tool:
            continue
        subject = _path_of(span) or _query_of(span)
        if not subject:
            continue
        needle = subject.rsplit("/", 1)[-1]
        if not needle:
            continue
        later = tools[index + 1 :]
        if any(needle in _text_of(other) for other in later):
            continue
        if span.tool.name in EDIT_TOOLS:
            continue  # an edit is the point of the run, never a dead end
        dead += 1
    return dead


def _query_of(span: Span) -> str | None:
    if not span.tool:
        return None
    value = (span.tool.arguments or {}).get("pattern")
    return value if isinstance(value, str) else None


def _text_of(span: Span) -> str:
    if not span.tool:
        return ""
    return _stringify(span.tool.arguments)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_stringify(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_stringify(v) for v in value)
    return str(value)


__all__ = [
    "BINARY_METRICS",
    "EDIT_TOOLS",
    "READ_TOOLS",
    "SEARCH_TOOLS",
    "Behaviour",
    "is_inline_check",
    "is_test_command",
    "observe",
]

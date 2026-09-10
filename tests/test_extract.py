"""Behaviour extraction: what counts as reading, editing and verifying.

Every one of these definitions could be drawn more loosely in a way that
flatters the skill -- counting a grep as a read, counting `git commit -m "fix
pytest"` as a test run. The tests pin the strict reading.
"""

from __future__ import annotations

from flightrec.models import Cassette, RunMeta, Span, ToolCall

from whetstone.extract import is_test_command, observe


def tool(name: str, index: int, **arguments: object) -> Span:
    return Span(
        id=index,
        kind="tool",
        name=name,
        start_ms=index,
        tool=ToolCall(name=name, arguments=dict(arguments)),
    )


def cassette(*spans: Span) -> Cassette:
    return Cassette(meta=RunMeta(name="t"), spans=list(spans))


# --- the before/after split ------------------------------------------------


def test_reads_after_the_first_edit_do_not_count() -> None:
    """The claim is "read before you change", not "read a lot"."""
    behaviour = observe(
        cassette(
            tool("Read", 0, file_path="a.py"),
            tool("Edit", 1, file_path="a.py"),
            tool("Read", 2, file_path="b.py"),
            tool("Read", 3, file_path="c.py"),
        )
    )
    assert behaviour.files_read_before_first_edit == 1


def test_a_grep_is_not_a_read() -> None:
    """Grep-and-patch is the failure being measured; it must not score as reading."""
    behaviour = observe(cassette(tool("Grep", 0, pattern="foo"), tool("Edit", 1, file_path="a.py")))
    assert behaviour.files_read_before_first_edit == 0
    assert behaviour.searches_before_first_edit == 1


def test_a_run_with_no_edit_counts_every_read() -> None:
    """No edit means the whole run is "before the edit"; nothing is lost."""
    behaviour = observe(
        cassette(tool("Read", 0, file_path="a.py"), tool("Read", 1, file_path="b.py"))
    )
    assert behaviour.files_read_before_first_edit == 2
    assert behaviour.files_touched == 0


# --- verification ----------------------------------------------------------


def test_a_test_run_after_the_last_edit_is_detected() -> None:
    behaviour = observe(
        cassette(
            tool("Edit", 0, file_path="a.py"),
            tool("Bash", 1, command="python -m pytest -q"),
        )
    )
    assert behaviour.test_run_after_edit
    assert not behaviour.test_run_before_edit


def test_a_test_run_before_the_edit_is_a_different_metric() -> None:
    behaviour = observe(
        cassette(
            tool("Bash", 0, command="pytest -q tests/test_a.py"),
            tool("Edit", 1, file_path="a.py"),
        )
    )
    assert behaviour.test_run_before_edit
    assert not behaviour.test_run_after_edit


def test_a_test_run_between_two_edits_is_not_after_the_last_one() -> None:
    """Verification has to follow the final change, or it verified something else."""
    behaviour = observe(
        cassette(
            tool("Edit", 0, file_path="a.py"),
            tool("Bash", 1, command="pytest"),
            tool("Edit", 2, file_path="b.py"),
        )
    )
    assert not behaviour.test_run_after_edit


def test_a_non_test_bash_call_does_not_count() -> None:
    behaviour = observe(
        cassette(tool("Edit", 0, file_path="a.py"), tool("Bash", 1, command="git diff"))
    )
    assert not behaviour.test_run_after_edit


# --- the command classifier ------------------------------------------------


def test_commands_that_merely_mention_a_runner_are_not_test_runs() -> None:
    """Every one of these would inflate the metric under a substring match."""
    for command in (
        'git commit -m "fix pytest failure"',
        "grep pytest setup.cfg",
        "cat pytest.ini",
        "echo 'run pytest next'",
        "uv run python app.py",
        "python -m http.server",
        "npm run build",
    ):
        assert not is_test_command(command), command


def test_real_test_invocations_are_recognised() -> None:
    for command in (
        "pytest",
        "pytest -q tests/",
        "python -m pytest",
        "python3 -m unittest discover",
        "uv run pytest -x",
        "cd sub && pytest",
        "npm test",
        "go test ./...",
        "cargo test",
        "make check",
        "CI=1 pytest -q",
    ):
        assert is_test_command(command), command


# --- context metrics -------------------------------------------------------


def test_re_reading_a_file_is_counted() -> None:
    behaviour = observe(
        cassette(
            tool("Read", 0, file_path="a.py"),
            tool("Read", 1, file_path="b.py"),
            tool("Read", 2, file_path="a.py"),
        )
    )
    assert behaviour.repeat_reads == 1


def test_an_edit_is_never_a_dead_end() -> None:
    """Editing is the point of the run, however little follows it."""
    behaviour = observe(cassette(tool("Edit", 0, file_path="a.py")))
    assert behaviour.dead_end_tool_calls == 0


def test_a_read_never_referred_to_again_is_a_dead_end() -> None:
    behaviour = observe(
        cassette(
            tool("Read", 0, file_path="wrong_lead.py"),
            tool("Read", 1, file_path="a.py"),
            tool("Edit", 2, file_path="a.py"),
        )
    )
    assert behaviour.dead_end_tool_calls == 1


def test_distinct_edited_files_are_counted_once_each() -> None:
    behaviour = observe(
        cassette(
            tool("Edit", 0, file_path="a.py"),
            tool("Edit", 1, file_path="a.py"),
            tool("Write", 2, file_path="b.py"),
        )
    )
    assert behaviour.files_touched == 2
    assert behaviour.edits == 3
    assert behaviour.touched_paths == ["a.py", "b.py"]

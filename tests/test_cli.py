"""The CLI, and the boundary that matters: analysis never needs a model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

typer_testing = pytest.importorskip("typer.testing")
from whetstone.cli import app  # noqa: E402

runner = typer_testing.CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def test_check_validates_and_prints_the_digest() -> None:
    result = runner.invoke(app, ["check", str(ROOT / "experiments" / "deep-work.yaml")])
    assert result.exit_code == 0
    assert "valid" in result.output
    assert "deep-work-v1" in result.output


def test_check_refuses_a_spec_with_no_primary_metric(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "name: b\narms:\n  - name: c\n  - name: t\n    skill: s\n"
        "metrics:\n  a:\n    rationale: r\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", str(path)])
    assert result.exit_code == 2
    assert "primary" in result.output


def test_report_works_without_a_model_present(tmp_path: Path) -> None:
    """The load-bearing property for reproducibility.

    `whet report` must run on a machine with no `claude` binary, no key and no
    network -- otherwise nobody can check the published numbers.
    """
    spec_path = ROOT / "experiments" / "deep-work.yaml"
    from whetstone.spec import Experiment

    # Records carry the *run* digest; the full digest also covers metrics.
    digest = Experiment.load(spec_path).run_digest
    results = tmp_path / "runs"
    results.mkdir()
    rows = []
    for index in range(6):
        for arm in ("control", "deep-work"):
            rows.append(
                {
                    "task": f"t{index}",
                    "arm": arm,
                    "repeat": 0,
                    "spec_digest": digest,
                    "task_success": arm == "deep-work",
                    "duration_s": 1.0,
                    "metrics": {"files_read_before_first_edit": 2.0 if arm == "control" else 5.0},
                    "touched": [],
                    "cassette": "",
                    "error": None,
                }
            )
    (results / "runs.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["report", str(spec_path), "--results", str(results)])
    assert result.exit_code == 0
    assert "files_read_before_first_edit" in result.output
    assert Experiment.load(spec_path).digest in result.output


def test_report_fails_loudly_on_an_empty_results_directory(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["report", str(ROOT / "experiments" / "deep-work.yaml"), "--results", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "no runs found" in result.output

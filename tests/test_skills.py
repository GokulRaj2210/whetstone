"""The skills are the product, and their format is load-bearing.

A `SKILL.md` with malformed frontmatter is not discovered at all -- it fails
silently and the treatment arm quietly becomes a second control, which would
look exactly like "the skill had no effect". These tests are cheap insurance
against publishing that.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_ROOT.iterdir() if (p / "SKILL.md").exists())


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no YAML frontmatter"
    _, raw, body = text.split("---\n", 2)
    return yaml.safe_load(raw), body


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_frontmatter_has_the_required_fields(skill: Path) -> None:
    meta, _ = frontmatter(skill / "SKILL.md")
    assert meta.get("name") == skill.name, "the declared name must match the directory"
    assert meta.get("description"), "a skill with no description is never triggered"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_the_description_names_when_to_use_it(skill: Path) -> None:
    """The description is the only part always in context; it does the triggering."""
    meta, _ = frontmatter(skill / "SKILL.md")
    description = meta["description"].lower()
    assert "when" in description or "use" in description, (
        "the description must say when the skill applies, or nothing will invoke it"
    )
    assert len(description) > 80, "a one-clause description is too vague to trigger on"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_the_body_stays_within_the_context_budget(skill: Path) -> None:
    """Guidance nobody reads costs the same tokens as guidance that works.

    The official skill-development guidance targets 1,500-2,000 words and caps
    at 3,000; past that, detail belongs in `references/` where it is loaded only
    when needed.
    """
    _, body = frontmatter(skill / "SKILL.md")
    words = len(body.split())
    assert 150 < words < 3000, f"{skill.name} body is {words} words"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_referenced_files_exist_and_are_addressable(skill: Path) -> None:
    """A companion file must exist *and* be reachable without searching for it.

    Naming one by bare relative path is what caused this project's largest
    measurement artifact: the agent could not resolve `references/x.md`, and
    `Glob` does not return paths under a dot-directory, so it spent ~3.5 tool
    calls per run hunting the filesystem -- inflating every cost metric and 83%
    of the one metric that moved the wrong way.
    """
    _, body = frontmatter(skill / "SKILL.md")
    for token in body.split("`"):
        if token.endswith(".md") and "references/" in token:
            assert token.startswith("${CLAUDE_SKILL_DIR}/"), (
                f"{skill.name} names {token!r} by relative path; the agent cannot resolve "
                "that and will search for it. Use ${CLAUDE_SKILL_DIR}/."
            )
            relative = token.removeprefix("${CLAUDE_SKILL_DIR}/")
            assert (skill / relative).exists(), f"{skill.name} references missing {relative}"


def test_the_deep_work_skill_gates_rather_than_exhorts() -> None:
    """The design commitment, asserted so it cannot drift back into vibes.

    Telling a model to focus is asking it to feel something. Every gate has to
    be a thing to do or not do, observable in a transcript afterwards.
    """
    _, body = frontmatter(SKILLS_ROOT / "deep-work" / "SKILL.md")
    lowered = body.lower()

    # The commitment is stated in the skill itself, so drift is visible.
    assert "none of them asks you to feel focused" in lowered

    # Each gate must survive as a checkable instruction.
    for gate in ("do not call edit", "run it", "ledger", "stop and say so"):
        assert gate in lowered, f"the {gate!r} gate has gone missing"

    # Motivational phrasing, matched as an instruction rather than as a word:
    # the skill is allowed to *mention* concentration in order to disclaim it.
    for exhortation in (
        "focus deeply",
        "stay focused",
        "be mindful",
        "take your time",
        "think carefully",
        "work slowly",
    ):
        assert exhortation not in lowered, f"{exhortation!r} is motivation, not a gate"


def test_the_placebo_adds_no_guidance() -> None:
    """If the control arm starts advising things, it stops being a control."""
    _, body = frontmatter(SKILLS_ROOT / "placebo" / "SKILL.md")
    assert "control, not advice" in body
    for gate in ("read the file", "run the test", "ledger"):
        assert gate not in body.lower(), f"the placebo is advising {gate!r}"


def test_the_placebo_is_a_comparable_size() -> None:
    """A control that is a tenth the length also controls for length, badly."""
    _, deep = frontmatter(SKILLS_ROOT / "deep-work" / "SKILL.md")
    _, placebo = frontmatter(SKILLS_ROOT / "placebo" / "SKILL.md")
    ratio = len(placebo.split()) / len(deep.split())
    assert 0.15 < ratio < 1.5, f"placebo is {ratio:.0%} of the treatment's length"

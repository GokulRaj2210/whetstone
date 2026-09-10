"""Run the agent, once per (task, arm, repeat), and record what happened.

The only module that spends model time, and the only one that needs the `claude`
binary. Everything downstream works from the records it writes, which is what
lets the published numbers be re-derived by someone who cannot run the agent.

**The confound this module is careful about.** A skill is normally reached by
asking for it, so the treatment arm's prompt differs from the control's by the
few words that invoke it. That difference is part of the intervention as users
actually experience it -- but it is *also* an uncontrolled prompt change, and
attributing its effect to the skill's contents would be wrong.

The design answer is not to hide it but to declare it (`Arm.prompt_suffix`, in
the pre-registered spec) and to run a placebo arm: an empty skill, invoked by an
equivalent suffix. Whatever the placebo moves is the cost of *invoking a skill*;
only the remainder belongs to this skill's contents. See `experiments/placebo.yaml`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from flightrec.cassette import store
from flightrec.evals import metrics as flightrec_metrics
from flightrec.models import Cassette
from flightrec.sources import claude_code

from whetstone.extract import observe
from whetstone.results import RunRecord
from whetstone.spec import Arm, Experiment
from whetstone.tasks import Task

#: Tools the agent is allowed. Fixed across arms -- varying them would confound
#: the comparison with a capability change, and the skill is meant to alter how
#: the tools are used, not which exist.
ALLOWED_TOOLS = "Read,Write,Edit,Bash,Grep,Glob"

#: The CLI answers a refused request with a single synthetic turn and no tools.
#: Detected rather than inferred from emptiness alone, because a legitimately
#: trivial run could also make no tool calls.
_REFUSAL_MODEL = "<synthetic>"

#: Metrics taken from flightrec rather than recomputed here.
COST_METRICS = (
    "total_tokens",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cost_usd",
    "llm_calls",
    "tool_error_count",
)


class CaptureError(RuntimeError):
    """The agent could not be run at all -- a setup problem, not a result."""


@dataclass(slots=True)
class Runner:
    """Executes one experiment against one set of tasks."""

    experiment: Experiment
    skills_root: Path
    results_dir: Path
    #: Where cassettes are written. Committed, so CI can re-analyse them.
    cassettes_dir: Path
    claude_bin: str = "claude"
    keep_workdirs: bool = False

    def run_one(self, task: Task, arm: Arm, repeat: int) -> RunRecord:
        """One observation: stage, run, verify, ingest."""
        started = time.perf_counter()
        workroot = Path(tempfile.mkdtemp(prefix=f"whet-{arm.name}-"))
        error: str | None = None
        try:
            workdir = task.stage(workroot)
            self._install_skill(workdir, arm)
            prompt = task.prompt + (f"\n\n{arm.prompt_suffix}" if arm.prompt_suffix else "")

            stream = workdir / ".whetstone-run.jsonl"
            timeout = task.timeout_s or self.experiment.timeout_s
            try:
                self._invoke(workdir, prompt, stream, timeout)
            except subprocess.TimeoutExpired:
                # A timeout is data. The skill making the agent slower until it
                # runs out of clock is exactly the kind of result that should
                # survive to the report rather than being retried away.
                error = f"timed out after {timeout}s"

            duration = time.perf_counter() - started
            name = f"{self.experiment.name}-{task.name}-{arm.name}-{repeat}"
            record = RunRecord(
                task=task.name,
                arm=arm.name,
                repeat=repeat,
                spec_digest=self.experiment.run_digest,
                task_success=False,
                duration_s=duration,
                error=error,
            )

            if stream.exists() and stream.stat().st_size:
                self._ingest(stream, name, record)
            stream.unlink(missing_ok=True)
            self._cleanup_skill(workdir)

            record.task_success = task.check(workdir)
            return record
        finally:
            if not self.keep_workdirs:
                shutil.rmtree(workroot, ignore_errors=True)

    # -- the pieces --------------------------------------------------------

    def _invoke(self, workdir: Path, prompt: str, stream: Path, timeout: int) -> None:
        command = [
            self.claude_bin,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--allowedTools",
            ALLOWED_TOOLS,
        ]
        with stream.open("w", encoding="utf-8") as handle, open("/dev/null") as devnull:
            subprocess.run(
                command,
                cwd=workdir,
                stdout=handle,
                stderr=subprocess.DEVNULL,
                stdin=devnull,
                timeout=timeout,
                check=False,
            )

    def _ingest(self, stream: Path, name: str, record: RunRecord) -> None:
        """Turn the event stream into a cassette and read the metrics off it."""
        try:
            cassette = claude_code.load_file(stream, name=name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            record.error = f"{record.error + '; ' if record.error else ''}ingest failed: {exc}"
            return

        path = store.save(cassette, root=self.cassettes_dir)
        record.cassette = str(Path(path).relative_to(self.cassettes_dir.parent))

        refusal = _refusal_text(cassette)
        if refusal is not None:
            record.executed = False
            record.error = f"the agent never ran: {refusal}"
            return

        behaviour = observe(cassette)
        record.metrics.update(behaviour.as_metrics())
        record.touched = behaviour.touched_paths
        collected = flightrec_metrics.collect(cassette)
        record.metrics.update({k: v for k, v in collected.items() if k in COST_METRICS})

    def _install_skill(self, workdir: Path, arm: Arm) -> None:
        """Make the arm's skill discoverable inside the working directory.

        Project-local at `.claude/skills/<name>/`, which is how a real user
        would ship one with a repo. Installing it globally would leak the
        treatment into the control arm.
        """
        if arm.skill is None:
            return
        source = self.skills_root / arm.skill
        if not source.is_dir():
            raise CaptureError(
                f"arm {arm.name!r} names skill {arm.skill!r}, but {source} does not exist"
            )
        shutil.copytree(source, workdir / ".claude" / "skills" / arm.skill)

    def _cleanup_skill(self, workdir: Path) -> None:
        """Remove the skill before verification.

        Otherwise `.claude/` would be present when the hidden tests run, and a
        task whose verifier walks the tree would see files that differ between
        arms. Small, but it is exactly the sort of asymmetry that quietly
        becomes the effect you measured.
        """
        shutil.rmtree(workdir / ".claude", ignore_errors=True)


def _refusal_text(cassette: Cassette) -> str | None:
    """The message, when the CLI declined to run at all.

    A usage-limit refusal comes back as one synthetic assistant turn carrying
    the explanation, `is_error` set on the result, and no tool calls. That is
    not a failed attempt at the task and must never be scored as one.
    """
    if cassette.tool_calls:
        return None
    if str(cassette.meta.labels.get("is_error", "")).lower() != "true":
        return None
    for span in cassette.llm_calls:
        if span.model == _REFUSAL_MODEL and span.response:
            for block in span.response.get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    return str(block.get("text", "")).strip()[:200]
    return "no tool calls and the result was flagged as an error"


def available(claude_bin: str = "claude") -> bool:
    """Is the agent runnable here? Analysis never needs this to be true."""
    return shutil.which(claude_bin) is not None


__all__ = ["ALLOWED_TOOLS", "COST_METRICS", "CaptureError", "Runner", "available"]

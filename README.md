# whetstone

**Does that skill actually do anything?**

Claude Code skills are shipped on faith. A `SKILL.md` is a markdown file, and the
usual evidence that one helps is that it reads like it should. whetstone runs a
paired A/B experiment against real tasks, with the metrics declared before the
first run, and tells you what the data supports — including, often, *not much*.

It ships with a subject as well as a tool: **`deep-work`**, a skill that replaces
guess-and-patch with four mechanical gates. The results below are that skill
measured by this harness, published whichever way they came out.

```bash
uv run whet check  experiments/deep-work.yaml     # validate + print the spec digest
uv run whet run    experiments/deep-work.yaml     # the part that costs model time
uv run whet report experiments/deep-work.yaml     # no model, no key, no network
```

---

## <a name="results"></a>Results

### What the experiment found

**The skill reliably produces a regression test where the control produced
none, and that is attributable to what it says rather than to the act of
invoking it. It did not make the agent verify its work — both arms already did,
and it changed the method. Whether any of this yields better code is not
something this experiment could answer, and on the single task that could have
discriminated, it did not help.**

Both of those qualifications were discovered *after* the first writeup, by
reading the transcripts instead of the summary table. They are the most useful
thing here.

Pre-registered spec `52346e509177` · 8 paired tasks · 3 repeats per arm · two-sided, alpha 0.05, Holm-corrected across the metric family.

| Metric | Control | +Skill | Delta | 95% CI | p (adj) | MDE | Verdict |
|---|--:|--:|--:|:--:|--:|--:|---|
| `task_success` | 0.88 | 0.88 | +0.00 | [+0.00, +0.00] | 1.000 | — | identical |
| `test_run_after_edit` | 0.00 | 1.00 | **+1.00** | [+1.00, +1.00] | 0.016 | — | resolved |
| `files_read_before_first_edit` | 1.88 | 2.92 | **+1.04** | [+1.00, +1.12] | 0.001 | 0.12 | resolved |
| _verified_after_edit_ | 1.00 | 1.00 | +0.00 | [+0.00, +0.00] | 1.000 | — | exploratory |
| _test_run_before_edit_ | 0.00 | 0.00 | +0.00 | [+0.00, +0.00] | 1.000 | — | exploratory |
| _repeat_reads_ | 0.00 | 0.00 | +0.00 | [+0.00, +0.00] | 1.000 | — | exploratory |
| _dead_end_tool_calls_ | 0.54 | 1.79 | +1.25 | [+1.08, +1.46] | 0.000 | 0.29 | exploratory |
| _searches_before_first_edit_ | 0.38 | 1.17 | +0.79 | [+0.46, +1.12] | 0.000 | 0.53 | exploratory |
| _files_touched_ | 1.33 | 2.33 | +1.00 | [+1.00, +1.00] | 0.000 | 0.00 | exploratory |
| _total_tokens_ | 211424.38 | 649692.75 | +438268.38 | [+369138.50, +511439.08] | 0.000 | 108671.05 | exploratory |
| _tool_calls_ | 6.38 | 15.12 | +8.75 | [+7.92, +9.67] | 0.000 | 1.35 | exploratory |
| _duration_s_ | 40.07 | 108.60 | +68.53 | [+55.11, +82.83] | 0.000 | 21.22 | exploratory |

- Resolved at n=8: `test_run_after_edit`, `files_read_before_first_edit`.
- `task_success` was **identical in every pair** (0.88 in both arms). That is a property of the task suite, not a finding about the skill: a metric pinned at its ceiling or floor has no room to move and no variance to estimate power from.
- Behaviour and outcome are separate claims. A metric moving means the agent worked differently; only `task_success` speaks to whether the code was right.
- Italic/dim rows are exploratory: reported uncorrected, and not evidence for a claim. Only the 3 primary metric(s) share the Holm correction.

#### The correction that matters most

The first version of this README opened with a much better headline: *"control
edited the code and never ran anything."* The metric said so — `test_run_after_edit`
was 0/24 in the control arm and 22/24 with the skill.

It was wrong. Reading what the control arm actually executed:

```
python3 -c "
from money import round_money
from receipt import receipt_total
print(receipt_total([0.145, 0.145]))"
```

The control arm was verifying its work the whole time, with throwaway inline
scripts. `test_run_after_edit` measured *"ran a test runner"* while claiming to
measure *"checked the change"*, and I read the number rather than the behaviour.
Corrected:

| | ran the test suite | verified by any means |
|---|--:|--:|
| control | **0 / 24** | **23 / 24** |
| deep-work | **22 / 24** | **23 / 24** |

So the real finding is narrower and more interesting than the one I nearly
published: **the skill did not change *whether* the agent verified, it changed
*how*** — from an ad-hoc snippet exercising the one case in the bug report, to
running the project's suite, which also covers the cases the report did not
mention. That is plausibly worth something. It is not "the agent finally started
checking its work."

Two pieces of the design earned their keep here:

- **The cassettes are committed**, so correcting a measurement error cost one
  `whet remeasure` instead of another two hours of model time. The metric was
  re-derived from the same evidence.
- **The digest is split in two.** Adding a metric changes what is computed, not
  what happened, so `run_digest` (arms, prompts, repeats) validates the records
  while the full digest tracks the analysis. Under a single hash, fixing a
  measurement bug would have invalidated the very evidence it was found in —
  which quietly rewards not fixing it.

`verified_after_edit` is **exploratory**, for one reason only: it was chosen
after the data was seen. A metric picked with hindsight cannot confirm anything,
however well motivated it is.

#### The clearest thing it did

`files_touched` went 1.33 -> 2.33, which read at first like the fix being
scattered across more files. It is the opposite:

| across 24 runs | source files edited | test files written |
|---|--:|--:|
| control | 32 | **0** |
| deep-work | 32 | **24** |

The source edits are identical in number. The entire increase is **a regression
test, written in 24 of 24 runs**, with the suite run afterwards in 22 of them.
The control arm wrote a test zero times.

That is the narrow, defensible claim this experiment supports: the skill
converts throwaway verification into a committed regression test - one that
covers the cases the bug report did not mention - at roughly 3x the tokens.
Whether that trade is worth making depends entirely on whether you wanted the
test.

#### The pointed negative

`strip-order` is the one task whose contract exists only in a docstring
(`"""...trim, lowercase, drop punctuation"""`) while the prompt mentions only
trailing commas. It is precisely the case Gate 1 - read the file in full before
editing - was written for.

It failed **0/3 in both arms.** The skill's extra reading did not translate into
catching the wider contract. One task is not much evidence, but it is the only
task in the suite that could have discriminated, and it did not.

#### What did resolve

`files_read_before_first_edit` moved 1.88 → 2.92 (p=0.001) — about "read one
more file, usually the caller, before touching anything". `test_run_after_edit`
resolved too, but as established above it should be read as a change of method,
not the appearance of a habit.

#### What could not be answered

`task_success` was **identical in every single pair.** Seven of eight tasks
passed 3/3 in both arms; `strip-order` failed 0/3 in both. There is no task
where the arms differed, so the metric had no room to move.

That is a **fixture calibration failure**, and reporting it as "the skill does
not improve correctness" would be exactly the over-claim this project exists to
prevent. A discriminating suite needs tasks the baseline fails *sometimes*; mine
were either too easy (both arms 100%) or too hard (both arms 0%). The next
version needs the baseline sitting around 40–70%.

It also exposed a bug in the harness. It first printed `MDE 0.00` on that row,
which reads as "this experiment could have detected any effect" when the truth
is the reverse: zero variance means there was nothing to estimate power *from*.
The MDE is now undefined in that case, and an identical primary metric gets a
sentence of its own in every report. ([test](tests/test_stats.py))

#### What it cost

| | control | deep-work | |
|---|--:|--:|--:|
| tokens | 211,424 | 649,693 | **3.1x** |
| wall clock | 40s | 109s | **2.7x** |
| tool calls | 6.4 | 15.1 | 2.4x |
| files touched | 1.3 | 2.3 | 1.8x |

Tripling the token cost of every task to move from an inline check to a suite
run is a real trade, and on a one-line fix it is plainly not worth it.

#### The cost is partly the harness's fault

One exploratory metric moved the *wrong* way: `dead_end_tool_calls` went 0.54 →
1.79. Gate 3 asks the agent to prune its context, and by this measure it
explored more blind alleys instead.

Before writing that up as "Gate 3 does not work", I went and read what those
calls were. **23% of every tool call in the treatment arm touched `.claude`** —
3.5 calls per run spent hunting around the filesystem for the skill itself,
including in my home directory:

```
ls /Users/gokul_raj/.claude/skills/ 2>/dev/null; find /Users/gokul_raj/.claude ...
```

The skill is installed project-local at `<workdir>/.claude/skills/`, and the
agent went looking for it anyway. Those searches are exploration that never gets
referenced again, so the metric counted every one of them. Excluding them:

| `dead_end_tool_calls` | control | deep-work | delta |
|---|--:|--:|--:|
| as measured | 0.54 | 1.79 | **+1.25** |
| excluding skill-hunting | 0.54 | 0.75 | +0.21 |

So **83% of the apparent regression is an artifact of how this harness installs
skills**, not of anything the skill does. The same artifact inflates
`tool_calls`, `total_tokens` and `duration_s` by an unknown but non-trivial
amount, which means the 3.1x token figure above is an **upper bound** on the
skill's real cost.

That is a harness bug, not a result, and fixing it is the first item for v2. It
is left in the published numbers rather than quietly subtracted, because the
committed transcripts are what make it findable at all — and a table that had
been silently corrected would be one nobody could check.

---

## The `deep-work` skill

The framing hazard first, because it is the reason most skills like this do
nothing: **deep work and flow are theories of human cognition.** Attention
residue, willpower depletion, the challenge–skill channel — those describe a
brain. A model does not get distracted or tired, and telling one to "focus
deeply" is asking it to feel something. That evaporates under measurement.

What survives translation is not the motivation but the **taxonomy**. Each of
these names a real failure with a mechanical signature in a transcript:

| Newport / Csikszentmihalyi | The agent failure | Gate | Signature |
|---|---|---|---|
| Attention residue | Context fills with exploration that led nowhere | 3 | `repeat_reads`, `dead_end_tool_calls` |
| Shallow work | Grep the symbol, patch the line, never read the callers | 1 | `files_read_before_first_edit` |
| Fragmentation | Edits made, nothing run, report says "should work" | 2, 4 | `test_run_after_edit` |
| Clear goals *(flow precondition)* | Underspecified task → thrashing | 1 | the one-sentence statement |
| Immediate feedback *(flow precondition)* | Never runs anything; works blind | 2 | `test_run_before_edit` |
| Challenge–skill balance | Task too big for one pass → sprawling half-change | 4 | `files_touched` |

So the skill never exhorts. It gates:

1. **Read before you edit** — not until you have read the file in full, found its
   callers, and can finish the sentence *"in `<file>`, `<symbol>` currently does
   X; it should do Y, because Z."*
2. **Get a failing signal first** — find or write the covering test, run it,
   confirm it fails *for the reason you expect*, then edit. Never report a
   change as done on the strength of having written it.
3. **Keep a KEEP/DROP ledger** — after each burst of exploration, compress it to
   four lines and cite those instead of re-reading.
4. **Stop rather than go shallow** — explicit stop conditions: fixing at the call
   site rather than the cause, inferring an unread API, "done" meaning "it
   compiles".

Install it into any project:

```bash
cp -r skills/deep-work /your/project/.claude/skills/
```

---

## How the measurement works

### The outcome is a hidden test, not a judge

The obvious way to score "did the skill improve the code" is to have a model
grade the diff. That is worthless here: the grader shares the experimenter's
prior, the rubric is written by whoever wants an effect, and nothing about it is
falsifiable.

Instead every task ships a test that lives **outside** the working directory and
is copied in only after the agent has finished. It passes or it does not. That
one binary — `task_success` — is the only claim this project makes about code
quality; everything else it measures is *behaviour*, and the report keeps the two
apart on purpose.

The tasks are built so a shallow fix can pass the reported symptom and still
fail. Most put the cause in a shared helper and mention only one of its two
callers:

| Task | What is broken |
|---|---|
| `shared-rounding` | Truncation in a money helper; the report names the receipt, the invoice shares it |
| `int-division` | `//` in a shared mean; the dashboard is mentioned, billing is not |
| `strip-order` | Punctuation left by a shared normaliser; only the CSV path is reported |
| `stale-cache` | Cache never invalidated; `rename_user` is reported, `delete_user` shares the bug |
| `mutable-default` | Mutable default argument; the obvious fix is at the call site |
| `swallowed-error` | `except Exception: return {}` against a documented contract to raise |
| `range-boundary` | Off-by-one against a contract stated only in the docstring |
| `retry-count` | One retry too many; visible only by counting calls |

Two tests in CI keep the suite honest: every task must **fail** its hidden tests
on the pristine repo, and a hand-written reference fix must **pass** them. A task
that is already passing measures nothing; a task nothing could satisfy looks like
evidence against the skill.

### The metrics are declared before the run

`experiments/deep-work.yaml` names every metric, its direction, and a one-line
rationale, and is hashed. `whet report` refuses to score a metric the spec does
not declare, and every metric needs a rationale — one nobody can justify in a
sentence is one added to raise the odds that *something* moved.

The hazard here is not fraud, it is enthusiasm. Run an experiment, look at
eleven metrics, notice three moved, write up those three. That requires no bad
faith at all, only hope, and the resulting number is meaningless.

There are **two** hashes, and the reason is in the results above. `run_digest`
covers the arms, prompts and repeats — everything that shaped the evidence — and
is stamped into every record; a mismatch means the records came from a different
experiment and the report fails. The full `digest` also covers the metric list,
and a change to it is reported rather than fatal.

Collapsing them into one hash sounds tidier and is worse: correcting a metric
that turned out to measure the wrong thing would invalidate the records the bug
was discovered in. A design that punishes fixing a measurement error is a design
that produces uncorrected measurement errors.

### Three primary metrics, everything else exploratory

Testing eleven metrics at α=0.05 gives roughly a 43% chance of at least one
false winner. Correcting across all eleven costs so much power that a real effect
cannot be found at feasible n.

So the spec declares a **primary family** of three — `task_success`,
`test_run_after_edit`, `files_read_before_first_edit` — which share a
Holm–Bonferroni correction and are the only metrics that can support a claim.
The other eight are reported in full, uncorrected, and labelled exploratory. An
exploratory metric that moves is a reason to design the next experiment.

### The statistics, and why they are 200 lines of stdlib

`src/whetstone/stats.py` imports nothing. The argument of this project is that
its numbers are checkable, and a reader who must trust scipy's defaults cannot
check them.

- **Paired, by task.** The same task runs in both arms and the difference is
  taken per task. Task difficulty varies far more than the intervention does;
  comparing two independent means would bury any real effect under it.
- **Percentile bootstrap**, resampling *pairs* rather than observations, 10,000
  times, with a fixed seed so a report is reproducible from the same inputs.
  Not BCa: at n=8 the bias-correction terms are themselves estimated from eight
  points, and the extra precision would be false.
- **Exact McNemar** for binary metrics — a binomial test on the discordant
  pairs. At these counts a chi-square approximation is simply wrong. It is also
  chastening: five tasks flipped out of five is *p = 0.0625*, and does not clear
  significance however overwhelming "5/5" looks.
- **The p-value is the bootstrap inversion of the interval**, so a significant p
  can never sit beside an interval covering zero.
- **Minimum detectable effect on every row.** "No significant difference"
  conflates *the intervention does nothing* with *we ran eight tasks*. The MDE
  separates them.

Repeats are averaged into one value per task rather than counted as independent
observations. Treating each repeat as its own data point would multiply the
apparent sample size and manufacture significance from the very variance the
paired design exists to cancel.

### The placebo arm

A skill is normally reached by asking for it, so the treatment prompt differs
from the control by the words that invoke it. That is part of the intervention
as users meet it — and it is also an uncontrolled prompt change. Without a
control for it, "the skill made the agent read more" might just mean "being told
to load a skill made the agent take the task more seriously".

`experiments/placebo.yaml` runs a skill of the same shape and roughly the same
length that instructs nothing, under an equivalent suffix. Whatever it moves is
the cost of *invoking a skill at all*; only the remainder belongs to `deep-work`'s
contents.

| Metric | placebo (invocation only) | deep-work (invocation + content) |
|---|---|---|
| `test_run_after_edit` | **+0.00**, identical | **+1.00**, resolved |
| `files_read_before_first_edit` | +0.38, unresolved (p=0.136) | **+1.04**, resolved (p=0.001) |
| `total_tokens` | +82% | +207% |
| `tool_calls` | +68% | +137% |

The switch to running the test suite is **entirely** attributable to the skill's
contents — invoking an empty skill produced exactly zero test-suite runs, same as
the bare control. The reading effect is mostly content too, though the placebo
moves in the same direction and this experiment cannot rule out a small
invocation component.

The cost is a different story: **roughly a third of `deep-work`'s token overhead
is the price of invoking any skill at all**, not of anything this one says.

One caveat, stated because it would otherwise flatter the comparison: the
placebo ran at k=1 against the main experiment's k=3, so its control arm is a
noisier sample of the same condition (`task_success` 0.75 vs 0.88, tokens 122k vs
211k). The within-experiment contrasts above are paired and sound; the
cross-experiment absolute numbers are not directly comparable.

The harness has its own negative control too, and it needs no model: a synthetic
experiment where both arms are drawn from the same process must resolve nothing.
A tool that finds effects in noise is worse than no tool. ([test](tests/test_analyze.py))

---

## Reproducing this

Every run is committed as a `flightrec` cassette under `runs/`, so the analysis
re-derives from disk with no model, no API key and no network:

```bash
uv run whet report experiments/deep-work.yaml --results runs
```

CI does exactly that on every push, and `scripts/check_report.py` fails the
build if the table above has drifted from what the records actually say. A
results table in a README is a copy, and copies rot.

Built on [agent-flight-recorder](https://github.com/GokulRaj2210/agent-flight-recorder),
which handles capture, cassette storage, redaction and cost accounting.

## What this does not do

- **It cannot tell you a skill is useless**, only that this experiment could not
  resolve an effect of a given size. Read the MDE column.
- **n is small.** Eight tasks is eight pairs. Agent runs cost real time, and the
  honest response is to report the resulting limits rather than to pretend n was
  larger.
- **The tasks are small and Python.** A fix that requires understanding a large
  unfamiliar codebase is the case where reading first should matter most, and it
  is exactly the case not represented here.
- **`dead_end_tool_calls` is a heuristic.** It counts tool calls whose subject
  never appears again, which under-counts exploration referenced only in prose.
  It is measured anyway, as an exploratory metric, because the alternative is not
  measuring context pollution at all.
- **One model, one version.** Results are for the Claude Code build they were run
  on; a skill's effect is not obviously stable across model versions.
- **The harness inflates its own cost metrics.** The treatment arm spends ~3.5
  tool calls per run locating the skill (see above). Until that is fixed, every
  cost figure for a treatment arm is an upper bound.

## License

MIT.

---
name: deep-work
description: This skill should be used when the user asks to fix a bug, implement a feature, refactor, or otherwise change code in an existing repository. It replaces guess-and-patch with four gates - read before editing, get a failing signal first, keep a KEEP/DROP ledger of what exploration found, and stop rather than go shallow.
allowed-tools: [Read, Grep, Glob, Bash, Edit, Write]
---

# Deep Work

Four gates. Each is a thing to **do or not do**, checkable from the transcript
afterwards. None of them asks you to feel focused, concentrate harder, or enter
any particular state — those are not available to you and pretending otherwise
would just add words to the context.

The gates exist because the failure modes they block are the common ones: the
patch applied to a file whose callers were never read, the fix declared done
without ever being run, the twentieth tool call re-reading something already in
the window, and the symptom silenced at the call site while the cause stays.

---

## Gate 1 — Read before you edit

**Do not call Edit or Write until all three are true.**

1. You have read the file you are about to change, in full. Not a grep hit, not
   a 40-line window around a match — the whole file. A grep tells you a name
   occurs; it does not tell you what else in the file depends on the thing you
   are about to change.
2. You have found its callers and read enough of each to know what they expect.
   `Grep` for the symbol name across the repo. If there are none, say so — a
   function nothing calls is a different problem than the one you were given.
3. You can state the change in one sentence, of the form *"in `<file>`,
   `<symbol>` currently does X; it should do Y, because Z."* Write that sentence
   out before editing. If you cannot finish it, you do not yet know what to
   change, and the next tool call is another read rather than an edit.

**The exception, and it is narrow:** creating a genuinely new file that nothing
imports yet. Then there is nothing to read and no callers to find. Say that
explicitly rather than skipping the gate silently.

## Gate 2 — Get a failing signal first

The two preconditions for flow that survive translation from humans to agents
are a clear goal and immediate feedback. This gate is the feedback one, and it
is the highest-value gate in this file.

**Before editing:**

1. Find the test that covers the behaviour you are about to change. `Grep` the
   test directory for the symbol, the filename, or the behaviour's name.
2. If one exists, **run it first.** You need to know whether it currently
   passes. A test that already passes is not covering the bug you were sent to
   fix, and editing against it tells you nothing.
3. If none exists, write the smallest failing test that captures the bug, and
   run it to confirm it fails **for the reason you expect**. A test that fails
   with `ImportError` is not yet evidence of anything.
4. Only now edit.

**After editing:** run that same test again, plus the narrowest suite that
contains it. If you changed something with wide reach, run the full suite.

**Never report a change as done on the strength of having written it.** "It
should work now" is not a result. If you could not run anything — no test
runner, no way to execute the code — say precisely that, and say what you would
have run. An unverified change presented as a finished one is the single most
expensive thing you can hand back, because it looks identical to a working one.

## Gate 3 — Keep a KEEP/DROP ledger

Every file you read stays in the context window whether or not it turned out to
matter. Twenty tool calls in, most of what you can see is exploration that led
nowhere, and the useful two facts are buried in it.

**After each burst of exploration — roughly every 3–5 reads or searches — write
a short ledger before continuing:**

```
KEEP  store.py:open() — takes the lock at line 88; this is the deadlock
KEEP  config.py — TIMEOUT defaults to 0, which means "never" here
DROP  migrations/ — wrong lead, the schema is not involved
DROP  test_store.py — covers a different code path
```

Then reason from the ledger, not from a re-scan. When you need one of those
facts again, cite the ledger line instead of re-reading the file.

**If you find yourself reading a file you have already read, stop and write the
ledger instead.** The re-read is the symptom; the missing ledger is the cause.

## Gate 4 — Stop rather than go shallow

Stop and say so, rather than proceeding, when any of these is true:

- **The fix you are about to make is at the call site, not the cause.** Guarding
  one caller against a bad return value leaves the bad return value there, and
  the next caller finds it. Say where the cause is and what fixing it would take.
- **You are inferring an API you have not read.** If you are about to call a
  method because the name sounds right, read it first, or say you could not
  find it. A plausible method name that does not exist fails at runtime, not now.
- **The test you would need does not exist and you cannot write it.** Say what
  makes it impossible — no fixture, no way to reach the state, a network
  dependency. That is useful information; a change made anyway is not.
- **"Done" would mean "it type-checks."** Compiling is not working.

Stopping is a real answer, and a short accurate report of what blocks you beats
a confident wrong change every time. When you do stop, say what you learned,
what you tried, and what the next step would be.

---

## The shape of a session under these gates

```
research   read the file, read the callers, grep the tests    (Gate 1)
           write the one-sentence statement of the change
signal     run the covering test, watch it fail correctly     (Gate 2)
ledger     KEEP/DROP what the reading turned up               (Gate 3)
implement  the smallest edit that makes the test pass
verify     run the test, then the suite around it             (Gate 2)
report     what changed, what you ran, what you did not check
```

Not a ritual to perform for its own sake. If a task is one line in one file with
an obvious test, the whole thing is four tool calls and the gates barely bind.
They bind when the task is unclear — which is exactly when the temptation to
start editing is strongest.

## Related

Two reference files sit beside this one, and **you do not need them to follow
the gates above** — the gates are self-contained. Read them only if the user
asks why a gate exists, and only if you already know where they are.

Do not go looking for them. Measured across 39 runs of this skill, searching for
its own files cost ~3.2 tool calls per run — a quarter of all tool use — because
project-local skills live under a dot-directory that `Glob` does not return and
`${CLAUDE_SKILL_DIR}` is not substituted for them. Every one of those calls is
context spent on nothing, which is the exact failure Gate 3 exists to prevent.

- `references/failure-modes.md` — the failure each gate blocks.
- `references/verification.md` — finding the right test in an unfamiliar repo.

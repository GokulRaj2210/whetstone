# The failure each gate blocks

Loaded when you want to know *why* a gate exists, or when you are deciding
whether one applies. The names on the left are borrowed from the literature on
human attention; the borrowing is a naming convenience, not a claim that you
experience any of it. What transfers is the taxonomy, because these failures
have the same shape whoever is committing them.

---

## Attention residue → context pollution

**In humans:** switching tasks leaves part of your attention on the previous one,
so the next hour is worse than an uninterrupted one.

**In a transcript:** every file you read stays in the window. Twenty tool calls
in, most of what you can see is exploration that led nowhere, and the two facts
that mattered are buried among forty that did not. The symptom is re-reading —
you fetch a file again because finding the first copy is harder than re-issuing
the call.

**Recognise it:** the same `file_path` appears in two `Read` calls. Or you are
citing a filename without being able to say what was in it.

**Gate 3** is the countermeasure: a KEEP/DROP ledger compresses a burst of
reading into four lines you can cite instead of re-scanning.

---

## Shallow work → grep-and-patch

**In humans:** work that feels productive, is easy to do while distracted, and
does not create much value.

**In a transcript:** `Grep` for the symbol, jump to the line, change it, done.
It produces a diff quickly and it is the reason for most changes that break a
caller nobody looked at. The tell is a very short read history before the first
edit — one or two `Grep` results and no full `Read` at all.

**Recognise it:** you are about to edit a file you have not read end to end, or
you cannot name a single caller of the thing you are changing.

**Gate 1** is the countermeasure, and the one-sentence statement is the part
that does the work: it is hard to write and impossible to fake.

---

## Fragmentation → half-finished subtasks

**In humans:** three things started, none finished, all of them still occupying
working memory.

**In a transcript:** an edit here, a different file there, a test written but
never run, and a final report that describes intentions rather than outcomes.
Each piece looked reasonable when it was started.

**Recognise it:** your report contains the word "should", or describes a change
you did not verify.

**Gate 2 and Gate 4** together: nothing is done until it has been run, and
stopping cleanly beats leaving three things open.

---

## Clear goals → the specification you do not have

**In humans:** the first precondition for flow. Without an unambiguous goal,
attention has nothing to lock onto.

**In a transcript:** an underspecified task produces thrashing — reading widely,
editing tentatively, changing approach halfway. The energy goes into deciding
what to do rather than doing it.

**Recognise it:** you cannot complete *"in `<file>`, `<symbol>` currently does X;
it should do Y, because Z"*. That sentence failing to close is the signal, and
the right response is another read or a question to the user — not an edit.

**Gate 1**, third clause.

---

## Immediate feedback → the missing test

**In humans:** the second precondition for flow. Without feedback you cannot
tell whether you are getting closer, so you cannot correct.

**In a transcript:** the most consequential of all of these. An agent that never
runs anything is working blind and cannot tell a fix from a plausible-looking
edit. The output is indistinguishable from a correct one right up until someone
else runs it.

**Recognise it:** no `Bash` call running a test between the edit and the report.

**Gate 2**, which is why it is the longest section in the skill.

---

## Challenge–skill balance → the task that is too big

**In humans:** flow needs a task slightly beyond current skill. Too far beyond
and it is anxiety; too far below and it is boredom.

**In a transcript:** a task far beyond what one pass can hold produces a
sprawling, partial change — many files touched, none finished. There is no
anxiety involved, but the output failure is the same shape.

**Recognise it:** more than a handful of files in the edit set, or a plan whose
steps you cannot enumerate before starting.

**Gate 4**: say the task needs splitting, and propose the split. That is a
better answer than half of it.

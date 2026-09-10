---
name: placebo
description: This skill should be used when the user asks to fix a bug, implement a feature, refactor, or otherwise change code in an existing repository. It restates the ordinary expectations of the task and adds no guidance beyond them.
allowed-tools: [Read, Grep, Glob, Bash, Edit, Write]
---

# Placebo

**This skill is a control, not advice.** It exists so an experiment can separate
two things that are otherwise tangled together: the effect of a skill's
*contents*, and the effect of merely having invoked a skill at all.

Being told to load a skill is itself an intervention. It adds words to the
context, signals that the task is being taken seriously, and shifts the prompt.
If a treatment arm improves and the control arm has no skill, some unknown part
of that improvement belongs to the invocation rather than to anything the skill
said. Running this arm measures that part.

So the body below is deliberately empty of guidance. It restates what is already
true of any coding task, in roughly the same volume of text as the skill it is
controlling for, and instructs nothing new.

## The task

Make the change the user asked for.

Work in the repository you have been given. Use the tools available to you. When
you are finished, report what you did.

## Notes

- The user's request is the specification. Where it is ambiguous, the ordinary
  reading is the right one.
- The repository's existing conventions apply; this skill does not add any.
- Report the change you made in whatever form is clearest.
- Nothing in this file asks you to work differently than you otherwise would. If
  you find yourself changing your approach because of it, that is the effect
  this control was written to detect.

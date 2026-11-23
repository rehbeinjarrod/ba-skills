---
name: define-feature
description: Defines one feature in depth: each job it does as a draft flow, its branches, and three questions a turn, each with a recommended answer. Use when the person names a feature to define, go through or question, asks for its flow or picture, or answers its questions. What a feature covers is ask-records.
---

First read [references/rules.md](references/rules.md).

A reply starts at step 6.

"Picture": run `python3 <skill folder>/scripts/ba.py bundle handover <the Feature's ID>`, reply with each `mermaid` block of the brief it wrote, unchanged, and end the turn.

## 1. Read the records

Run `python3 <skill folder>/scripts/ba.py check --shape all`, then read `work.md`. A feature named with no Feature record gets a draft one, its `Intent` the person's words.

Done when: you hold the shapes, the Feature, its requirements and its Flows.

## 2. Write the jobs

A job is one named person, in one situation, wanting one result. Find the feature's in its `Intent` and requirements.

Each job with no Flow gets a draft:

- `Trigger` is the situation, `Overview` the job in one sentence, `Source` its requirement's.
- Its steps are what a person or team does or receives, the first and last at least.
- Where a requirement says "if", "unless" or a limit, the step before is a decision: a `Go to` line with its `(when ...)` for each way it can go.

A new branch of a job that has a Flow goes into that Flow: a `Go to` in from the step it follows, and one back.

Done when: the Feature's `Flow` line names a Flow of two steps or more for every job.

## 3. Find the gaps

Take the first three:

1. a Flow whose last step is no one's result
2. a decision's `Go to` with no condition
3. a condition with no Requirement stating its rule
4. a rule with no example on one side of its condition
5. nothing on how well the feature must work: read [references/cards/probe-quality-needs.md](references/cards/probe-quality-needs.md)

On "it depends", or a job passing between people, read [references/cards/walk-a-process.md](references/cards/walk-a-process.md). On two conditions on one step, read [references/cards/untangle-the-rules.md](references/cards/untangle-the-rules.md).

Write each as a Question: `About` names the Flow or Requirement, `Working answer` is your recommended answer, `Owner` the Work's business analyst, by name.

Done when: at most three new Questions are in `work.md`, each with those lines.

## 4. Check

Run `python3 <skill folder>/scripts/ba.py check --fix` and do each fix it states under `work.md`.

Done when: none is left.

## 5. Reply

Reply with this, filled from `work.md`, and end the turn.

```
**<feature name>**: <its intent>

**<flow name>**: <who> wants <what>, when <the trigger>
1. <step> (<who does it>)
2. <step>: when <condition>, <next step>; when <condition>, <next step>

**Rules found** <omit when none>
- <requirement name>: <statement>
  - To confirm: <an example you added>

**Questions** <omit when none>
1. <question>
   Recommended: <its working answer>. "Yes" takes it.

These are drafts. Answer by number, or say "picture".
```

Done when: the reply is the filled template.

## 6. Record answers

1. Add `Answer`, and `Answered by` naming its `Owner`, to each Question answered; "yes" makes its working answer the answer. Done when: each has both.
2. Write what follows: steps, `Go to` lines with conditions, a Requirement naming the Feature for each rule, an example each side of its condition, the person's own as `said:`. Done when: every answer shows in a Flow or Requirement.
3. A screen, storage or how a system does its part goes under `### Left to engineering` on its requirement. On a solution named, not a need, read [references/cards/ladder-to-the-need.md](references/cards/ladder-to-the-need.md). Done when: no step or statement holds it.
4. After "yes" to every question, or "stop", do step 7; otherwise steps 3 to 5.

## 7. Stop asking

Do step 4. With no Question of yours unanswered, set `Status: confirmed` on the Feature's Flows. Say that `slice-requirements` makes the handover brief. End the turn.

Done when: the reply asks nothing.

---
name: scope-work
description: Scopes a piece of work by questioning, from a sentence or two, with every open question each turn, each with a recommended answer, then the Scope brief. Use when the person has an idea and little written, wants work scoped, answers a scope question, or asks for the Scope brief. Notes or a document in hand go to capture-requirements.
---

First read [RULES.md](../../shared/RULES.md).

A reply starts at step 6. "Make the brief" starts at step 7.

## 1. Read

Run `python3 <skill folder>/../../helper/ba.py check --shape all`. Read `work.md` if there is one.

Done when: you hold the shapes and any records.

## 2. Draft

Before any question, write what was said as drafts:

- the Work: a name the business would say; `Goal`, one sentence, who gets what result; each person named
- a Requirement with `Category: business` for each result the Goal needs, `Source` the person speaking
- a Feature with its `Intent` for each piece they named

Done when: `work.md` holds the Work with its `Goal`, and a business Requirement.

## 3. Questions

The scope has seven points, in order:

1. The Goal: who is better off, and how anyone would know. A solution named, not a result: read [shared/cards/ladder-to-the-need.md](../../shared/cards/ladder-to-the-need.md).
2. The name.
3. Who decides, and who else must change how they work: `Approvers`, two size lines.
4. What must be true to meet the Goal: three to seven business Requirements.
5. What is left out. They cannot say: read [shared/cards/draw-the-scope-line.md](../../shared/cards/draw-the-scope-line.md).
6. Whether it needs several features, and their names: `Several features`. On yes, read [shared/cards/map-the-features.md](../../shared/cards/map-the-features.md).
7. Whether a regulation or contract applies, or information moves from an old system.

A point is settled when the person said it or its Question has an `Answer`. Each point not settled gets a Question: `Working answer` is the answer you recommend, a statement that stands alone; `Owner` is the person.

Ask every Question that can be answered now. Hold one back only when its answer depends on a Question not yet answered.

Done when: every point is settled, a Question with both lines, or held back for the Question it depends on.

## 4. Check

Run `python3 <skill folder>/../../helper/ba.py check --fix`, do each fix, then run `python3 <skill folder>/../../helper/ba.py status`.

Done when: no finding is left.

## 5. Reply

Reply with this, filled from `work.md`.

```
**Scope so far**
- Name: <the Work's name>
- Goal: <its Goal>
- Must achieve: <business requirements, by name>
- Delivered as: <Features, by name; omit with none>
- Left out: <Out of scope lines; omit with none>
- Decides: <Approvers; "not known yet">
- <status's Size line>

**Questions**
1. <question>
   Recommended: <its working answer>. "Yes" takes it.
Held back: <points that wait for these answers; omit with none>

These are drafts. Answer by number, or say "make the brief".
```

Done when: the reply is the filled template and asks every Question that can be answered now. End the turn.

## 6. Answers

1. Add `Answer` and `Answered by` to each Question answered; "yes" makes its working answer the answer. Done when: each has both.
2. Write what each answer changes, and set `Status: confirmed` on each record an answer agreed or changed. Done when: every answer shows in a confirmed record.
3. Do steps 3 to 5.

## 7. Brief

1. Unless it is there, add the Question "Does <sponsor> agree the scope of this work?", its `Owner` the sponsor. Done when: `work.md` holds it.
2. Run `python3 <skill folder>/../../helper/ba.py bundle scope`. Done when: it wrote `faces/scope.md`.
3. Read `faces/scope.md` to the end. Put your passage in place of each slot, its quoted lines included. Done when: no line starts `> {slot:`.
4. Run `python3 <skill folder>/../../helper/ba.py check` and do each fix. Done when: it reports nothing under `faces/scope.md`.
5. Reply with your passages, the file, what is still open and who is to agree it.

To send it when asked, follow [PUBLISH.md](../../shared/PUBLISH.md) for `scope`.

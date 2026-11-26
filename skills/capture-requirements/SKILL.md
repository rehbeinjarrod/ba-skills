---
name: capture-requirements
description: Turns material into draft requirements, flows, open questions and observations of what a system does today, shows the draft, and confirms it when the person agrees. Use first, before editing any file, when the person shares notes, a transcript, an email or a document, reports what a system does, or replies to a draft. An idea with little written is scope-work; one feature in depth, define-feature.
---

First read [RULES.md](../../shared/RULES.md).

A reply to your draft starts at step 8.

## 1. Find the workspace

Run `python3 <skill folder>/../../helper/ba.py check`. If it lists records, read `work.md`.

Done when: you know the records, or that there are none.

## 2. Get the shapes

Run `python3 <skill folder>/../../helper/ba.py check --shape all`.

Done when: you hold the shapes.

## 3. Itemise the material

Each point becomes one of:

- a Requirement: something asked of the work, a deadline or a won't-have included
- a Question: something unknown or unsettled. What the material, or you, take as true meanwhile is its `Working answer`
- a step in a Flow: who does what, then what
- a line on the Work: goal, people, out of scope

Where a rule has an edge the material leaves open, add one example of your own. When a statement will not fit one sentence, or the material describes a process, read [references/records.md](references/records.md). For what a system or document does today, read [references/observed.md](references/observed.md).

Done when: every point is an item, or on a short "not used" list.

## 4. Label the items

Each item gets one label; with no records yet, **new**.

- **new**: its own record
- **duplicate of** a record that already says it: nothing
- **refines** a record (same need, more exact) or **conflicts with** one (both cannot be true): a Question whose `About` names that record and whose `Context` holds the new wording or example

Done when: every item has a label.

## 5. Write the drafts

With no `work.md`, start it with the Work record and its yes or no lines, `no` where the material is silent.

Write each item as its label says, in its shape from step 2.

Done when: every item but a duplicate is in `work.md` as a draft.

## 6. Check

Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states.

Done when: it reports no findings, and a `Home:` page is saved.

## 7. Show the draft

Reply with this, filled in from `work.md`.

```
**Captured**
- <each new requirement, in their words> (<its priority; omit with none>)
  - Example: <one they gave; omit when none>
  - To confirm: <one you added; omit when none>
- Flow, <name>: 1. <step> 2. <step, with its branches>

**Against the records** <omit when none>
- Already recorded: <the record's name>
- <Refines or Conflicts with> <the record's name>: was <its wording>, the material says <new wording>

**Assumptions so far** <omit when none>
- <each working answer>, to confirm with <its owner>
- <each of the Work's `### Assumptions`>

**Size: <Large if `Several features` is yes, else Medium if any other line is, else Small>**
- <each of the Work's yes or no lines>

**Questions first**
- <each Question that can be answered now, the most important first>

These are drafts. Say "confirm", or tell me what to change.
```

Done when: the reply is the filled template, asking every Question answerable now. End the turn.

## 8. Confirm

1. Change each record the person corrected, and each record an accepted refinement is `About`, to say the new wording, a confirmed record included. Done when: each says it.
2. On what they accepted, set `Status: confirmed` and change `proposed:` to `said:`. Add `Answer` and `Answered by` to each Question they answered or settled, a confirmed working answer included. Done when: no accepted record is a draft.
3. Run `python3 <skill folder>/../../helper/ba.py check --fix`, then do step 6. Done when: step 6 is.
4. Tell the person what is confirmed and what is still open. Done when: the reply names both.

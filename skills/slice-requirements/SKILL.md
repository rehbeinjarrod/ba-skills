---
name: slice-requirements
description: Slices requirements into features, every requirement to deliver in one, and makes the handover brief engineers start from, one a feature. Use when the person wants the work broken into features, wants something to hand to engineers, says a feature is too big, or names a tracker item for a brief. Something for approvers is prepare-signoff-brief.
---

First read [references/rules.md](references/rules.md).

A reply to your proposal starts at step 5. For a handover brief, or a tracker item to put one in, follow [references/handover.md](references/handover.md).

## 1. Read the records

Run `python3 <skill folder>/scripts/ba.py status`, then read `work.md`.

Done when: you hold each requirement's statement and `Feature` line, each Flow's steps, each Feature.

## 2. Group the requirements

A feature is fit to hand over when all three hold:

- it runs from something that happens in the business to a result a named person gets
- built, it could be shown working on its own with one of its examples
- showing it needs no feature still unbuilt

Start from the names on `Feature` lines. A requirement that holds for two features goes in both. A feature too big is sliced the same way: its parts replace it.

Done when: every requirement is in a feature whose `Starts when` and `Ends when` the records fill, or on a "left out" list with its reason.

## 3. Write the drafts

Run `python3 <skill folder>/scripts/ba.py check --shape feature`. At the end of `work.md`, write each feature in that shape as a draft, with the Flow steps it delivers. A part gets `- Sliced from: <the feature it replaces>`. Set each requirement's `- Feature:` line to its features. A requirement on your "left out" list gets `- Feature: none (<its reason>)`.

Run `python3 <skill folder>/scripts/ba.py check --fix` and do each fix it states.

Done when: it reports no finding.

## 4. Show the proposal

Run `python3 <skill folder>/scripts/ba.py status`. Reply with this, filled from it and `work.md`.

```
**Features proposed**

**<feature name>**: <its intent>
- Starts when: <what happens in the business>
- Ends when: <the named person> gets <the result>
- Shown working with: <one of its examples; omit with none>
- Requirements: <each name>
- Flow steps: <each step it delivers; omit with no flow>

**Coverage**
- <its `In a feature` line>
- Left out: <requirement>, because <reason> <omit when none>
- Replaced by its parts: <the feature sliced> <omit when none>

**Reads like a choice about how to build** <three at most; omit when none>
- <requirement> says "<that part of its statement>".
  1. Could the business change this by policy, without engineers? <your yes or no>
  2. Would it still be true if the system were replaced by paper, or another supplier? <your yes or no>
  3. Could a subject expert confirm it in the business's own words? <your yes or no>
  A "no" makes it the engineers' call. Shall I move "<the matter it settles>" out of the statement, to left to engineering?

These are drafts. Say "confirm", or tell me what to regroup or rename.
```

Done when: the reply is the filled template. End the turn.

## 5. Confirm

1. Regroup or rename as the person said. Done when: the Feature records and `Feature` lines say it.
2. For each part they agreed to move: cut it from the `Statement`, and add the matter it settles as an item under `### Left to engineering`, the last heading of that requirement. Done when: the statement still reads as a sentence.
3. Set `Status: confirmed` on each feature accepted, and `Status: withdrawn` on a feature its parts replace; one with work logged against its `Tracker` item stays as it is. Done when: no accepted feature is a draft and no other record's status changed.
4. Do step 3's check. Done when: step 3 is.
5. Tell the person what is confirmed and what is open; offer the handover briefs. Done when: the reply names all three.

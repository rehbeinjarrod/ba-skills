# Handover briefs

One brief for each feature, for the engineers who will build it. Sending a brief to the tracker starts at step 5.

## 1. Make the briefs

For each confirmed feature, or the one the person asked for, run `python3 <skill folder>/scripts/ba.py bundle handover <its ID>`.

Done when: each run says it wrote `faces/handover-<ID>.md`, or that the feature was sliced into parts.

## 2. Fill the slots

Read each brief to the end. Put your passage in place of each slot, its quoted lines included, as plain sentences.

The slots are yours; every other line is the helper's, carried from the records word for word.

Done when: no line in a brief starts `> {slot:`.

## 3. Check the briefs

Run `python3 <skill folder>/scripts/ba.py check` and do each fix it states under `faces/`. A fix that replaces a feature by its parts is steps 2 to 4 of the skill, for that feature.

Done when: it reports nothing under `faces/`, or the skill's step 4 reply is sent.

## 4. Show the briefs

Reply with this, filled in from the briefs. Leave out a line with nothing to report.

```
**Handover briefs**
- <feature name>: faces/handover-<ID>.md. Baseline: <its Baseline row>. Approval: <its Approval row>. Changed since approval: <that row, when it has one>.

<when an Approval row says "Not yet approved":> These can go to the engineers now, to plan from; sign-off is the authority to build.

**Still open**
- Blocking: <each question a brief marks Blocking, and the features it holds up>
- No brief yet: <each feature still in draft>

Say which of them to send to the tracker, and I will.
```

Done when: the reply is the filled template. End the turn.

## 5. Send a brief

For each feature the person asked to send, follow [publish.md](publish.md) with the face `handover <its ID>`.

Done when: its last step is.

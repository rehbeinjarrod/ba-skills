---
name: prepare-signoff-brief
description: Makes the sign-off brief approvers read, for the whole Work, shows what changed since an approval, and records an approver's yes. Use when the person wants something to send for approval, asks for a brief or for what changed since sign-off, or says an approver replied. A brief for engineers is slice-requirements.
---

First read [RULES.md](../../shared/RULES.md).

A brief is made whenever asked. Step 6 says what the records lack.

The brief has two forms: `moscow`, a priority table, and `process map`, the flow first.

An approver's reply starts at step 7.

## 1. Check the records

When the request names a form, first write `- Sign-off form: <form>` among the Work's own lines, above its first `###` heading.

Run `python3 <skill folder>/../../helper/ba.py check`. With no `work.md`, tell the person there are no records, and stop. Do each fix it states under `work.md`. Keep a fix that needs the person's choice for step 6.

Done when: the Work names a form the request named, and the check reports no finding under `work.md` that you can fix.

## 2. Pick the form

With no `Sign-off form` line on the Work and a Flow in the records, ask the person which of the two forms they want and end the turn.

Done when: the Work names the form, or the records hold no Flow.

## 3. Make the brief

Run `python3 <skill folder>/../../helper/ba.py bundle signoff`.

Done when: it says it wrote `faces/signoff.md`.

## 4. Fill the slots

Read `faces/signoff.md` to the end. Put your passage in place of each slot, its quoted lines included, as plain sentences.

The slots are yours; every other line is the helper's, carried from the records word for word.

Done when: no line in the file starts `> {slot:`.

## 5. Check the brief

Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states under `faces/signoff.md`.

Done when: it reports nothing under `faces/signoff.md`.

## 6. Show it

Reply with this, filled in. Leave out a line with nothing to report.

```
**Sign-off brief: <the Work's name>**

<your passage under "What you are asked to approve", as it stands in the file>

The brief is faces/signoff.md, made from records version <from its last line>.

**Still open**
- <count> questions without an answer: <each question>
- <count> records still in draft: <each name>
- <count> examples to confirm
- <count> assumptions awaiting their owner: <each, with its owner>
- <a fix kept from step 1>
- <what a slot asked for and the records lack>

It is ready to send to <the approvers>. Give me each reply and I will record it.
```

Done when: the reply is the filled template. End the turn.

To send it when asked, follow [references/baseline.md](references/baseline.md), then [PUBLISH.md](../../shared/PUBLISH.md) for `signoff`.

## 7. Record an approval

A reply that asks for a change is new material for the capture-requirements skill.

1. Get the approver's name, the date they replied and their words as written, asking the person for any not given. Done when: you hold all three.
2. Take the records version they approved from the last line of `faces/signoff.md`; for a change agreed before a brief showed it, from the `Changed since approval:` line of `python3 <skill folder>/../../helper/ba.py status`. With neither, ask the person for the last line of the brief the approver read. Done when: you hold the version.
3. Add one item under a `### Approvals` heading at the end of the Work record, making the heading if it is missing: `- <name>: approved, <date>, records version <version>, "<their words>"`. Done when: the item is in `work.md`, above the next `## ` heading.
4. Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states. Done when: it reports no findings, and nothing under `faces/signoff.md`.
5. Tell the person whose yes is recorded and against which version, and which of the Work's `Approvers` have none yet. Done when: the reply names both.

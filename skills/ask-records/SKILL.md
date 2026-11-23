---
name: ask-records
description: Answers a question about a piece of work, or the business it serves, from the records, naming the record behind each statement and saying what no record holds. Use first, before reading any file, when the person asks what was agreed, what a feature covers, what is in scope or who said so. Where the work stands and who owes what is report-status.
---

First read [references/rules.md](references/rules.md).

A "yes" to your offer starts at step 4.

## 1. Read the records

Run `python3 <skill folder>/scripts/ba.py status`, then read `work.md` and any file in `records/`. For what was approved or has changed, run `python3 <skill folder>/scripts/ba.py baseline` and read `baselines/<name>/records.md`.

Done when: you hold every record's words, ID and status.

## 2. Sort the question

The records are the only source. Give each thing the question asks one label:

- **stated**: a record that stands says it.
- **unsettled**: what bears on it is a draft, a `proposed:` example, a `Working answer` or an unanswered Question.
- **missing**: no record says it, whatever you know of the trade.

A withdrawn record is history: answer from what stands, and say what was withdrawn and why.

Done when: every thing asked has one label, and, unless missing, its record.

## 3. Reply

Reply with this, filled from step 2, and end the turn.

```
**In short**
<what is stated, in one to three sentences; with nothing stated: "The records do not say.">

**From the records** <omit when everything asked is missing>
- <the record's own words> (<who said or answered it>; <record name>, <ID>)
- <Draft, Proposed example or Working answer>: <its words> (<record name>, <ID>)
- Approved in <baseline> by <who>, <date>: <the approved wording; omit unless it differs>

**Not in the records**
- <an unsettled thing>: not settled, waiting on <its `Owner`, else "no one named"> (<Question name>, <ID>)
- <a missing thing>: no record covers this. Shall I record it as a question about <the records nearest it>?
<when everything asked is stated, only: "Nothing: the records answer what you asked.">
```

Done when: the reply is the filled template, and `work.md` is as you found it.

## 4. Record the question

1. Run `python3 <skill folder>/scripts/ba.py check --shape question`. Done when: you hold the shape.
2. Add one Question to `work.md` in that shape: its heading the missing thing as the person asked it, `Raised by` whoever asked it, else the Work's business analyst, `About` the records you named in the offer. Leave out `Working answer` and `Answer`. Done when: `work.md` holds one more record.
3. Run `python3 <skill folder>/scripts/ba.py check --fix` and do each fix it states. Done when: it reports no finding.
4. Tell the person its name and ID. Done when: the reply names it.

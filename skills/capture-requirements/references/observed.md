# Observed behaviour

What a system or document does today is evidence: an Observed record, kept out of every requirements list.

Work only from what the person gives you.

## Write one

Run `python3 <skill folder>/../../helper/ba.py check --shape observed` and copy the shape, wording each line as its comment says. `About` names the Feature or Requirement it bears on. `Owner` is who can say whether it is meant.

In your draft reply, list these under "Seen today, not yet a requirement".

Done when: the check reports no finding on the record.

## Record a verdict

For each record the person judged, by what they called it:

- intended: add `- Verdict: intended` and `- Verdict by: <who said so>`. Write a draft Requirement stating the need in the business's words, its `Source` that person, and add `- Requirement: <its handle>`.
- accidental: add the two verdict lines.
- defect, and a confirmed Requirement says what should happen: add the two verdict lines and `- Requirement: <that one>`.
- defect, and none does: add no verdict; write a Question asking what should happen, `About` this record, what you would expect as its `Working answer`.

Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states.

Done when: the check lists no fix for these records.

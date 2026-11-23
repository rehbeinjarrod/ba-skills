---
name: forecast-delivery
description: Forecasts when a piece of work will be delivered, as a range of dates for each feature from a start date and a pace, lays what has finished over it, and makes the Delivery plan. Use first, before reading any file, when the person asks when it will be done, wants a forecast, timeline or delivery plan, gives a pace or start date, or says what has finished.
---

First read [RULES.md](../../shared/RULES.md).

The helper works out every date. You write the lines it reads, and copy the dates it gives.

A reply starts at step 8.

## 1. Read the records

Run `python3 <skill folder>/../../helper/ba.py status` and `python3 <skill folder>/../../helper/ba.py check --shape work`, then read `work.md`. With no Feature record, tell the person a forecast counts features, and that `scope-work` or `slice-requirements` writes them. End there.

Done when: you hold the Work's shape and the Features that are not withdrawn.

## 2. Write the delivery lines

Under `### Delivery` on the Work, in the shape's form, write what the person said:

- `Start`: the first day of work
- `Period` and `Velocity`: how many features finish in how many weeks, slowest to fastest. "One or two a month" is `Period: 4 weeks`, `Velocity: 1 to 2`

An order they named is the `Order` line; with none, the helper takes the records' order. A line already there stays. With no `Start`, write the Monday after today; with no `Velocity`, `0.5 to 1`. Each value you supply is also a Question: its `Working answer` is that value, its `Owner` the tech lead, else the person.

Done when: `### Delivery` holds `Start` and `Velocity`, and each value you supplied has its Question.

## 3. Write the actuals

When you have tracker tools and a Feature has a `Tracker` line, or the person said what has started or finished, follow [references/actuals.md](references/actuals.md). Otherwise the Work has no `### Actuals`.

Done when: the section holds what was read or said, and nothing else.

## 4. Make the plan

Run `python3 <skill folder>/../../helper/ba.py bundle delivery`. When it names a line to add, add it as shown and run it again.

Done when: it says it wrote `faces/delivery.md`.

## 5. Fill the slot

Read `faces/delivery.md` to the end. Put your passage in place of the slot, its quoted lines included. A date in it is copied from the tables.

Done when: no line starts `> {slot:`.

## 6. Check

Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states.

Done when: it reports no finding.

## 7. Reply

Reply with this, filled from `faces/delivery.md` and `work.md`.

```
**Delivery plan: <the Work's name>**

<the first table of the plan, as it stands in the file>

<the table with a row for each feature, as it stands in the file>

**It rests on**
- <each line of `### Delivery`>: <"you said" or "assumed">
- Every feature counts as one.
- Actuals: <the `Read:` line; or "none yet. Tell me what has started or finished">

**To confirm** <omit when none>
1. <a Question from step 2>
   Assumed: <its working answer>. "Yes" keeps it.

The plan is faces/delivery.md.
```

Done when: the reply is the filled template, three questions at most. End the turn.

To send it when asked, follow [PUBLISH.md](../../shared/PUBLISH.md) for `delivery`.

## 8. On a reply

1. Add `Answer` and `Answered by` to each Question answered; "yes" makes its working answer the answer. Done when: each has both.
2. Change the `### Delivery` line an answer changes. Done when: the section says what they said.
3. Do steps 3 to 7.

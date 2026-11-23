---
name: report-status
description: Says where a piece of work stands, what to do next and who owes what, with a message to chase each. Use first, before reading any file, when the person asks where things are, what is next, who they are waiting on, or for chasers. What the records say on a subject is ask-records.
---

First read [references/rules.md](references/rules.md).

Every count, name, date and age in your reply is the helper's: copy it. This skill sends nothing, and writes only an `Asked` line.

An answer that came back, who can answer or a correction goes to the capture-requirements skill; an approver's yes, to prepare-signoff-brief.

A request for chasers, or for the messages, starts at step 3; word that a question has been asked, at step 4.

## 1. Get the status

Run `python3 <skill folder>/scripts/ba.py status`. With no `work.md`, tell the person there are no records yet, and stop.

Done when: it prints a `Next:` list.

## 2. Reply

Reply with this, filled from the printout. Leave out a part with nothing to report.

```
**<the Work's name>** (<its size>)
<one sentence: what is settled, from the `Records:` and `Approvals:` lines>

**Do next**
1. <the first line under `Next:` as one plain sentence: what to do, to which records by name>
2. <the second>
3. <the third>
<count> more. Say "all" for the rest.

**Waiting on others**
- <each line under `Waiting on:` and under `Asked, waiting on a reply:`>
Say "chasers" for a message to each.

**Changed since <baseline>**
- <each `changed:`, `added:` and `withdrawn:` line under `Baselines:`, by name>
```

Done when: the reply is the filled template. End the turn.

## 3. Give the chasers

Run `python3 <skill folder>/scripts/ba.py status --chasers`.

Reply with this, filled from the printout.

````
To <name>:
```
<their message, word for word>
```

No message for: <each item under `Nobody to ask`>
Nothing has been sent: these go from you. Say when one has gone.
````

Done when: the reply holds every message printed. End the turn.

## 4. On a reply

- "all": the rest of the `Next:` list, the same way.
- A change to a message: that message again with their change.
- A message went, or someone was asked: add `- Asked: <the day, YYYY-MM-DD>` to each Question in it, and say which.

Done when: the reply answers what they asked.

---
name: adopt-house
description: Sets up an organisation's house, meaning its words, headings and layout for briefs, drafted from documents it already approved, and the places briefs and tracker items are sent. Use when the person wants briefs to look or read like their organisation's own, gives example documents, names where briefs or tracker items go, asks to land a test there, or replies to a house you showed.
---

First read [references/rules.md](references/rules.md).

The house is one file, `house.md`, in the current folder: a pack, each part under a line `=== <name> ===`. It holds only what differs from the shipped house, `<skill folder>/scripts/house/`. It is the only copy, and a team adds to it between your turns: a change is an edit to the row or line it concerns, in the file as it now stands.

A reply to the house you showed starts at step 7.

## 1. Find the house

When the Work's `House` line is a link, fetch it as [references/home.md](references/home.md) says under "A house kept on a page". Run `python3 <skill folder>/scripts/ba.py check --adopt house.md`.

Done when: you know what the house holds, or there is no `house.md`.

## 2. Get the documents

A house is drafted from two or three documents the organisation already approved. With none given, ask for them and end the turn.

Done when: you have read each to its end.

## 3. Draft the pack

Follow [references/drafting.md](references/drafting.md): words, then templates, then hierarchy.

Done when: its three steps are, and you hold its "not used" list.

## 4. Check

Run `python3 <skill folder>/scripts/ba.py check --adopt house.md` and do each fix it states.

Done when: it reports no finding.

## 5. Make a brief through it

For each sign-off template in the pack, with `<form>` as `moscow` or `process-map`:

```
mkdir -p house-preview/<form>
cp work.md house-preview/<form>/ || python3 <skill folder>/scripts/ba.py check --shape all > house-preview/<form>/work.md
python3 <skill folder>/scripts/ba.py bundle signoff house-preview/<form> --house house.md --form <form>
```

Done when: each says it wrote `faces/signoff.md`.

## 6. Show the house

Reply with this, filled in from the pack and step 4.

```
**Your house, drafted from <each document>**

**Your words**
- "<Shown as>" where we say "<Word>", from <document>

**Layout: <template>, from <document>**
1. <each section heading, in order>
- Kept, though your document has no such section: <headings>. Give me a reason and I leave one out.

**Not used** <omit when none>
- <label or heading>: nothing in a brief stands for it

**Assumed** <omit when none>
- <each choice no document shows>

**Still not set**
- Tracker item types: what is a Feature called where your engineers work, and does the business track it elsewhere under another name? <omit when the pack has a hierarchy>
- Where briefs and tracker items go. Give me the places and I land a test page and a test item for you to look at.
- <each other "not set" the check reports>

**See it:** house-preview/<form>/faces/signoff.md, made from <your records, or made-up records> through this house. Passages are left as their instructions.

The house is house.md. Tell me what to change, or say "use it".
```

Done when: the reply is the filled template. End the turn.

## 7. Act on the reply

1. A correction, an answer or another document: read `house.md` as it now stands, and edit in it the rows and lines the reply concerns, as step 3 words them. Then do steps 4 to 6. Done when: step 6 is.
2. "Use it": add `- House: house.md` among the Work's own lines, above its first `###` heading. When the records' home is a page, save the house as [references/page.md](references/page.md) says. Done when: `python3 <skill folder>/scripts/ba.py status` names the house.
3. Places given, or a test landing asked for: follow [references/landing.md](references/landing.md). Done when: its last step is.

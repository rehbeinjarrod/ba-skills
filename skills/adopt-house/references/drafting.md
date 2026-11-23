# Drafting the pack

The pack is `house.md` in the current folder. A part it already holds is edited where it stands; a part it lacks is added at its end.

## 1. Words

Read `<skill folder>/scripts/house/words.md`. Every column name, row name and mark in a brief's tables, and every `{Word}` in a template, is shown from this list. Take each heading, column name, row name and fixed cell value in the documents. Find the shipped row that stands for the same thing, and write a row for it in the pack:

```
=== words.md ===

| Word | Shown as | More than one |
| --- | --- | --- |
| <the shipped row's Word, as written> | <the document's label, capitals included> | <its plural, where the shipped row has one> |
```

Done when: every label in the documents is a row, or on a "not used" list.

## 2. Templates

Each document takes the shipped template nearest in form:

| The document is | Template |
| --- | --- |
| requirements in a priority table | `signoff-moscow.md` |
| a process: a diagram, then a table for each step | `signoff-process-map.md` |
| what engineers build one feature from | `handover.md` |

When the pack has no part of that name, add the shipped one whole:

```
printf '\n=== templates/<template> ===\n\n' >> house.md
cat <skill folder>/scripts/house/templates/<template> >> house.md
```

Then, in the pack, give each section the document's heading for the same content, and put the sections in the document's order. A section moves whole, from its `## ` line to the line above the next. A section the document lacks stays in place. Headings and plain sentences are the house's to word.

Done when: each of the document's headings is on a section or on the "not used" list, and every line starting `{job:`, `{block:` or `>` is as shipped.

## 3. Hierarchy

Where a document or the person gives the name the tracker itself has for the item type of a Work, Feature or Requirement, write it under `=== hierarchy.md ===` in the shape of `<skill folder>/scripts/house/hierarchy.md`. With none named, the pack has no such part and the reply asks the person.

Done when: every cell holds a type name a document or the person gave, as the tracker lists it.

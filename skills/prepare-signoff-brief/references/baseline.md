# Freezing before a brief is sent

A baseline is a frozen copy of the records, which an approver's yes names.

## 1. See whether a baseline is due

Run `python3 <skill folder>/../../helper/ba.py status`. Under `Next:`, find a line starting `Baseline:` or `Changed since approval:`.

Done when: you hold that line. With none, this is the end.

## 2. Freeze

Run the `baseline` command that line gives. If it refuses, do each fix it states and run it again. For a finding only the person can settle, give them both ways forward as printed, and end the turn.

Done when: it says it froze the baseline.

## 3. Make the brief from it

Run the `bundle signoff` command the freeze printed, then read `faces/signoff.md`. It carries your passages: rewrite any that no longer fits.

Done when: each passage fits the brief.

## 4. Ask for the changes only

When the brief has a section "What changed since the last approval", rewrite the passage under "What you are asked to approve" to ask for a yes to those changes only, saying how many.

Done when: the passage holds the count the section states, or the brief has no such section.

## 5. Check

Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states under `faces/signoff.md`.

Done when: the brief's last line names the baseline, and the check reports nothing under it.

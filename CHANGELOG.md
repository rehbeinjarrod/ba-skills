# Changelog

Each release has a number of three parts. While the plugin is being piloted the first part is 0. The middle part goes up when a skill, or a brief it makes, gains or changes something a person would notice. The last part goes up for a fix that changes nothing a person has to learn.

## 0.4.0

From a large job done with 0.3.0: about 23 requirements, 30 constraints and 12 features.

- **Features can be cut one at a time.** A requirement not yet in a feature is counted, not reported: `status` says how many are in a feature, hold for the whole work, are deliberately in none, or are not yet in one. Nothing asks you to put the rest of the project into the first feature, and freezing a baseline no longer waits for it.
- **A handover brief holds what belongs to its feature.** A requirement that bears on every feature says `- Feature: all`: each brief names it, by category, and gives the link where it is stated in full, once the sign-off brief or the Scope brief has been sent. A question or an assumption recorded against the whole work stays in those briefs and is no longer repeated in every feature's. To put a question in a feature's brief, say what it is about. A feature is called too large only for its own requirements, examples and flow.
- **A requirement can be held back from a feature.** Say which, and why. The record keeps your reason in your words with your name (asked once, then kept with the people on the Work); `status` counts it; the feature's brief lists it under "Not in this Feature". Delete the two lines and it is back.
- **A priority you give is kept and shown.** The draft that capture shows carries each requirement's priority, `check` lists it, and says which requirements have none when others do. Something asked for that will not be delivered is a requirement of its own, with priority won't and who decided.
- **A house may have a feature summary.** It is a second document, your own thin template, for the business going into build; the handover brief stays the engineers'. Give the template to `adopt-house` and say what it is for. It is then made beside each handover brief and attached to the feature's tracker item as a file; when the session cannot attach, you are given the file and told which item it belongs on. A house with no such template gets the handover brief alone. A section of the summary with nothing to show keeps its heading and says "None recorded".
- **The tool says whose template it used**, and names any template file in your house that no brief reads, with the name to give it.
- **A long `work.md` can be filed by feature.** `status` says when it has grown past 40 records and gives the command: `check --split` moves each feature's own records to `records/<Feature ID>.md`, unchanged, after a backup. `work.md` keeps the work itself, what holds for all of it, and what is not yet in a feature. No record changes, and briefs and approvals are not disturbed: the records version no longer depends on which file a record is in or what order records are written in. This is for a Work kept in a folder; one kept on a page stays in one file.
- A copy for sending that was made before its passages were written now says so, and how to make it again.

A workspace made with 0.3.0 reads unchanged, with one thing to know: if its `work.md` is not in the order of its IDs, its records version is now a different figure. Nothing changed in the records, and a brief or an approval that cites the old figure still stands; `check` says so once. Two things differ when its briefs are made again: questions and assumptions about the whole work are no longer in a feature's handover brief, and a requirement that named no feature is no longer a finding.

## 0.3.0

- A skill that questions in rounds now asks every question it can ask at that point, each with its recommended answer, instead of three a turn: `scope-work`, `define-feature`, and the questions that come with the first draft in `capture-requirements`. A question waits only when its answer depends on another not yet answered. You may answer some, all or none; an unanswered question stays open.

## 0.2.0

The first release after the pilot's first jobs.

- Install the whole plugin. Nothing is copied into a skill any more: the helper, the house's default words and templates, and the shared rules and method cards are each in the release once. To limit the plugin, remove the skill folders you do not want. A skill is not installable alone.
- A house now tailors the two diagrams it can draw by their own settings in `brand.md`: `Process map style` and `Timeline style` (the Gantt chart in the Delivery plan). Each applies only to its own diagram. The one `Diagram style` line is gone; a house that still carries it is told by `check --adopt` which line to rename or remove.
- The plugin is now named `jarrodrehbein`, so a skill is called as `jarrodrehbein:capture-requirements` where it was `ba:capture-requirements`. Install it as `jarrodrehbein@ba-skills`; if you installed `ba@ba-skills`, uninstall that one first.
- The helper says plainly, and does not run, when it is started from inside the plugin's own folders, and tells you to run it from the folder your work is in.

## 0.1.0

The first release, for a pilot.

- Nine skills: `capture-requirements`, `scope-work`, `define-feature`, `slice-requirements`, `prepare-signoff-brief`, `forecast-delivery`, `report-status`, `ask-records` and `adopt-house`.
- Four briefs made from the records: the Scope brief, the Sign-off brief (as a priority table or a process map), a Handover brief for each feature, and the Delivery plan.
- A page for people about each skill, and a chooser.
- Installs in Claude Code and in Cursor from this repository.

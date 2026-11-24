# Changelog

Each release has a number of three parts. While the plugin is being piloted the first part is 0. The middle part goes up when a skill, or a brief it makes, gains or changes something a person would notice. The last part goes up for a fix that changes nothing a person has to learn.

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

# BA skills

Nine skills for Claude Code and Cursor that do a business analyst's grunt work between the conversation and the build: they turn what was said into requirements, keep track of what is unanswered and who owes it, and make the documents each audience needs, in the form your organisation expects.

They stop where engineering starts. They carry goals, business rules, examples and quality needs. They do not choose how anything is built.

## The nine skills

Say what you want in your own words; the assistant picks the skill. There is a page for each, and [a chooser](docs/skills/README.md).

| Skill | Reach for it when you want to |
|---|---|
| [capture-requirements](docs/skills/capture-requirements.md) | turn notes, a transcript or a document into requirements, process steps and open questions |
| [scope-work](docs/skills/scope-work.md) | be asked the right questions to pin down what a piece of work is |
| [define-feature](docs/skills/define-feature.md) | work through one feature: who does what, and what happens when it goes another way |
| [slice-requirements](docs/skills/slice-requirements.md) | group requirements into features and give engineers a brief to start from |
| [prepare-signoff-brief](docs/skills/prepare-signoff-brief.md) | send something for approval, or record an approver's yes |
| [forecast-delivery](docs/skills/forecast-delivery.md) | say when it will be delivered, and show progress against that |
| [report-status](docs/skills/report-status.md) | see where the work stands, what is next and who you are waiting on, with messages to chase them |
| [ask-records](docs/skills/ask-records.md) | check what was agreed, with the record behind each statement |
| [adopt-house](docs/skills/adopt-house.md) | make briefs read like your organisation's own documents, and set where they are sent |

There is no setup step. The first thing you capture starts your records, in a file called `work.md` in the folder you are working in.

## Install in Claude Code

In a Claude Code session, type these two lines, one at a time:

```
/plugin marketplace add rehbeinjarrod/ba-skills
/plugin install ba@ba-skills
```

Then start a new session. To check it worked, type `/plugin` and look for `ba` under the installed plugins, or ask "which BA skills do you have?": the answer should name the nine above.

To get a later release:

```
/plugin marketplace update ba-skills
/plugin update ba@ba-skills
```

## Install in Cursor

Cursor installs a plugin from a repository through a team's marketplace. In the Cursor dashboard, open Plugins, choose to import from a repository, and give `rehbeinjarrod/ba-skills`. Then turn the `ba` plugin on. To check it worked, ask "which BA skills do you have?" in a new chat.

One thing to know in Cursor: for a skill that takes several turns (a draft, then your reply, then a confirmation), use a custom mode (Alt+Enter), so the same skill carries on from turn to turn.

## What you need

- Claude Code or Cursor.
- Python 3, which the skills use for counting, checking and assembling. Web sessions have it. On a desktop, install it if the assistant says it cannot run its helper.
- To send briefs to a wiki or a tracker, a connection to them in your session. Without one, briefs are left in your folder for you to place by hand.

## What is in this repository

- `skills/`: the nine skills. Each folder is complete in itself.
- `docs/skills/`: the pages for people.
- `.claude-plugin/` and `.cursor-plugin/`: what lets each tool install the plugin.
- `CHANGELOG.md`: what changed in each release.
- `MANIFEST.sha256`: a list of every file in the release with its checksum.

Every file here is built from a private workshop and replaced whole at each release, so changes are not made here. To report a problem or ask for a change, open an issue.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).

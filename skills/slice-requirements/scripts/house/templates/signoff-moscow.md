<!--
Sign-off brief, MoSCoW table form.
How to read this file:
  {job: ...}    says which of the brief's jobs the section does. One under every "## " heading.
  {block: ...}  is filled in by the helper from the records.
  {work: ...}   is one line from the Work record: name, goal or tracker.
  {Word}        is a label from words.md.
  > {slot: ...} is a passage the assistant writes. The quoted lines under it are its instructions.
Everything else is printed as written. Notes like this one are left out of the brief.
-->

# {work: name}

## What changed since the last approval
{job: ask}

{block: changes}

## What you are asked to approve
{job: ask}

> {slot: up to 80 words, from the goal, the requirements and the approvers}
> Replace these quoted lines with one short paragraph, written to the approver and naming things by their names, that says what their yes covers: the change in a sentence, how many requirements it rests on, and what is still open.
> Done when a reader who stops here knows what they are agreeing to.

## What changes for whom
{job: change}

**{Goal}:** {work: goal}

> {slot: up to 120 words, from the goal, the Why of each requirement, the flow and the stakeholders}
> Replace these quoted lines with one sentence for each group of people whose day changes, written to the approver, saying what that group does today and what it will do instead.
> Done when every group named under Stakeholders or in the flow has its sentence, or a sentence saying its day does not change.

## Stakeholders
{job: approve}

{block: people}

## Open {Questions}
{job: open}

{block: questions}

{block: counts}

## {Assumptions}
{job: scope}

{block: assumptions}

## {Out of scope}
{job: scope}

{block: out of scope}

## {Requirements}
{job: rules}

Each line gives the requirement, how much it matters, the reason behind it and a worked example. An example marked "{proposed}" was suggested by the analyst and has not been confirmed by anyone.

{block: requirements}

## How it works
{job: flow}

{block: flow}

## What waiting costs
{job: wait}

> {slot: up to 60 words, from the goal and the Why of each requirement}
> Replace these quoted lines with what carries on happening, and to whom, for as long as there is no decision, using the figures in the Why column; when no requirement gives a figure or a reason to hurry, write "No cost of waiting has been stated for this change."
> Done when the passage gives a cost with its figure, or is that sentence.

## Approval
{job: approve}

Approving means you agree the requirements above say what the business needs. {How to approve}

{block: approval}

## Trace
{job: trace}

Tracker item: {work: tracker}

{block: trace}

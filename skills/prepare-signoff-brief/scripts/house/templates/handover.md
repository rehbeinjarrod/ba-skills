<!--
Handover brief: one for each feature, for the engineers who will build it and test it.
How to read this file:
  {job: ...}      says which of the brief's jobs the section does. One under every "## " heading.
  {block: ...}    is filled in by the helper from the records of this feature.
  {work: ...}     is one line from the Work record: name, goal or tracker.
  {feature: ...}  is one line from the Feature record: name, intent or tracker.
  {Word}          is a label from words.md.
  > {slot: ...}   is a passage the assistant writes. The quoted lines under it are its instructions.
Everything else is printed as written. Notes like this one are left out of the brief.
Keep a line of fixed text straight before and straight after every slot, so a filled passage can be found again.
The brief says what the business needs. Keep every line of it free of how the thing is built.
-->

# {feature: name}

This brief holds the requirements for one {Feature}: what must be true, for whom, and how you will know it is. They are one input to your detailed specification. The architecture and the test plan are the others, and those are yours. A business decision this brief does not settle is not yours to decide: ask. Both lists are near the end.

## Where this comes from
{job: version}

{block: version}

Sign-off is the authority to build. Before it, this brief is for planning: test cases, architecture, questions. The {Approval} row says which applies.

## What this {Feature} delivers
{job: intent}

> {slot: up to 100 words, from the intent, the goal, the Why of each requirement and the flow}
> Replace these quoted lines with one short paragraph, written to the engineer who will build this, that says what goes wrong today and for whom, using the figures in the Why column, and then what a named person will be able to do or see, from the first thing that happens to the last, once this is built.
> Done when an engineer who stops here could say who this is for, what that person will be able to do, and what the business would watch to see it working.

As the business recorded it:

**{Goal} of the whole work:** {work: goal}

**{Intent} of this {Feature}:** {feature: intent}

## Words used here
{job: words}

The business's own words, with what each means here. Use them as written.

{block: glossary}

## Who is involved
{job: actors}

> {slot: up to 80 words, from the Stakeholders of each step, the requirements and the examples}
> Replace these quoted lines with one sentence for each person or group that a requirement, an example or a step names, saying what that person or group does or receives here, in the business's words.
> Done when every person or group named in a step, a requirement or an example has one sentence, and every name in the passage is one of those.

Who takes part in which step:

{block: actors}

## {Requirements}
{job: rules}

Each is carried word for word from the business. One marked "{draft}" has not been agreed by the analyst yet.

{block: feature requirements}

## How well it must work
{job: rules}

{block: measures}

## {Examples}
{job: examples}

Worked cases in the business's own wording, numbered within each requirement. One marked "{said}" was given or accepted by a named person: it is safe to turn into a test. One marked "{proposed}" was suggested by the analyst and nobody has agreed it yet: treat its result as unsettled. A requirement with no example has none recorded.

{block: examples}

## How it works
{job: flow}

{block: feature flow}

## Decisions already made
{job: rules}

Each was settled by the person named. Build on it as written. If one looks wrong, ask.

{block: decisions}

## Not in this {Feature}
{job: scope}

Out of scope for the whole work:

{block: out of scope}

Other {Features} of this work, each with a brief of its own:

{block: other features}

## Taken as true
{job: scope}

{block: plain assumptions}

## Open {Questions}
{job: open}

"{Blocking}" means there is no answer and nothing to assume: leave what depends on it unbuilt until it is answered. "{Not blocking}" means the business has given an answer to build on meanwhile, and it may still change.

{block: feature questions}

## Seen in the present system
{job: open}

None of this is a requirement. Each line is something the present system or a document was seen to do, with what the business has said of it. Build to the requirements above; where it says "{unconfirmed}", ask before you rely on it or remove it.

{block: observed}

## Yours to decide
{job: yours}

This brief is the requirements part of the detailed specification, and the only part the business analyst writes. The rest is yours: how the solution is structured, what is stored and where, how its parts talk to each other and to other systems, which technology is used, how it is tested beyond the examples above, and how the build is split up and ordered.

If working that out shows this {Feature} is too large to specify as one piece, say so on the tracker item. The analyst slices it into smaller ones with you, each with a brief of its own.

Points that came up with the business and were left to you:

{block: left to engineering}

## Not yours to decide
{job: ask}

Every open question above, everything under "Taken as true", and any business decision this brief does not cover: what the rule is, who may do something, what a person is told, an amount, a date or a limit. When you meet one, ask the business analyst, on the tracker item this brief came with, giving the question in one sentence, the options you can see and the one you would take if forced. If you have to build before the answer comes, say what you built on. If the present system does something these requirements do not mention, tell the analyst what happens, in business words, and where you saw it; copy nothing from it.

{block: people}

## Trace
{job: trace}

Tracker item of the whole work: {work: tracker}

{block: feature trace}

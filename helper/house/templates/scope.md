<!--
Scope brief: for the business owner, to agree what the work is called, what it is for, what it must achieve and what it will be delivered as.
{job: ...} names the section's job; {block: ...} is filled in by the helper from the records; {work: ...} is a line from the Work;
{Word} is a label from words.md; > {slot: ...} is a passage the assistant writes. Notes like this one are left out of the brief.
Keep a line of fixed text straight before and straight after every slot.
-->

# {work: name}

## What this work is for
{job: goal}

**{Goal}:** {work: goal}

> {slot: up to 80 words, from the goal, the Why of each top requirement and the features}
> Replace these quoted lines with one short paragraph, written to the business owner, that says who is affected today and how, using the figures in the Why column, and what will be different for them when the work is done.
> Done when a reader who stops here could say what the work is for and how they would know it had worked.

Everything below is carried from the records, word for word.

## What it must achieve
{job: needs}

Each line is a result the business needs from this work, stated without saying how. The detailed {Requirements} sit under these and are agreed at sign-off.

{block: top requirements}

## What will be delivered
{job: features}

Each {Feature} is handed to the engineers as one piece. One marked "{draft}" has not been agreed by the analyst yet.

{block: features}

## Where each {Feature} fits
{job: features}

The steps are the way the work is done, in order. Beside each step is every {Feature} that delivers it.

{block: feature map}

## What is left out, and what is taken as true
{job: scope}

### {Out of scope}

{block: out of scope}

### {Assumptions}

{block: assumptions}

## Who is involved
{job: people}

{block: people}

{block: stakeholders}

## What may change without coming back to you
{job: limits}

A change inside these limits is the analyst's to make and to tell you about. Anything beyond them comes back to the people who agreed this brief.

{block: tolerances}

## Not yet settled
{job: open}

{block: questions}

{block: counts}

## What you are asked to agree
{job: agree}

> {slot: up to 60 words, from the goal, the top requirements, the features, out of scope and the open questions}
> Replace these quoted lines with one short paragraph, written to the business owner and naming things by their names, that says what their yes settles: what the work is called and for, how many results it must achieve, how many features it will be delivered as, and what stays open.
> Done when a reader who stops here knows what they are agreeing to and what they are not.

Agreeing means the name, the {Goal}, the list of what the work must achieve and what is left out are right. It is not sign-off of the detailed {Requirements}. {How to agree}

## Trace
{job: trace}

Tracker item: {work: tracker}

{block: trace}

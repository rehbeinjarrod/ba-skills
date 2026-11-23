<!--
Delivery plan: for the business owner and delivery leads, to see the forecast against what has actually been delivered.
{job: ...} names the section's job; {block: ...} is filled in by the helper from the records; {work: ...} is a line from the Work;
{Word} is a label from words.md; > {slot: ...} is a passage the assistant writes. Notes like this one are left out of the plan.
Keep a line of fixed text straight before and straight after every slot. Every date is worked out by the helper.
-->

# {work: name}: {Delivery plan}

## When it will be done
{job: answer}

**{Goal}:** {work: goal}

{block: forecast summary}

## Where each {Feature} stands
{job: features}

Every {Feature} is counted as the same size. The forecast runs from the fastest pace assumed to the slowest. "{Pace date}" is when a {Feature} finishes if the work carries on at the pace it has gone so far. Every date is the Friday of its week.

{block: forecast}

## Timeline
{job: timeline}

{block: timeline}

## What the forecast rests on
{job: basis}

{block: delivery basis}

Taken as true meanwhile:

{block: assumptions}

## What could move these dates
{job: risk}

> {slot: up to 80 words, from the open questions, the features still in draft and the forecast table}
> Replace these quoted lines with one sentence for each thing that could move a date: an open question and the feature it holds up, a feature not yet agreed, a feature finished or running later than its forecast. Name things by their names, and give no date that is not in the tables above.
> Done when each open question and each draft feature is named, or the passage is "Nothing recorded would move these dates."

As the business recorded them:

{block: questions}

## Trace
{job: trace}

Tracker item: {work: tracker}

{block: feature items}

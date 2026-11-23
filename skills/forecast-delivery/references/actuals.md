# Writing the actuals

When the person told you what has started or finished, go to step 5 with the parts they gave.

Otherwise use your tracker tools, to read only. Do steps 1 to 4 for each Feature that is not withdrawn and has a `Tracker` line.

## 1. Get the item

Get the item its `Tracker` line names.

Done when: you hold its status and its dates, or the call failed.

## 2. Finished

When its status is in the done category, its resolution date is `finished <date>`.

Done when: you hold that date, or the item is not done.

## 3. Items

Search for the items whose parent it is. `t` is how many there are; `d` is how many are done. With one or more, they are `<d> of <t> items done`.

Done when: you hold both counts.

## 4. Started

The earliest date the item, or one of its items, went into progress is `started <date>`. Leave it out when the tool does not give it.

Done when: you hold the date, or know there is none.

## 5. Write the section

Write `### Actuals` on the Work whole, in place of the one there:

```
### Actuals

- Read: <the day it was read, YYYY-MM-DD>, <the tracker and project>, by <who read it>
- <Feature name>: started <date>, finished <date>, <d> of <t> items done
```

A Feature's line holds only the parts you hold, each date `YYYY-MM-DD`. A Feature with none has no line. A Feature whose call failed has no line: name it in your reply.

Done when: the `Read:` line is first, and every Feature has its line or none.

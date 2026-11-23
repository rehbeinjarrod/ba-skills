# forecast-delivery

**Reach for it when** someone asks when the work will be done, or you want progress laid over the plan. It needs features to count: if there are none, [scope-work](scope-work.md) or [slice-requirements](slice-requirements.md) writes them first.

**Say** "Forecast delivery: we start on 2 March and finish one or two features a month." Later, "lay the actuals over it", or tell it what has started or finished.

**What comes back first** is the Delivery plan: a range of dates for each feature, earliest to latest, then "It rests on": for each figure, whether you gave it or it was assumed.

**How to tell it is working**

- Every date in the reply is in the plan's tables. They are calculated, not written by the assistant.
- A start date or pace you did not give is recorded as a question with its assumed value.
- With a tracker connected, the plan says when progress was read and from where.

**It will not** estimate features one by one, give a single date in place of a range, or change anything in your tracker: it only reads from it.

**Good to know**

- Every feature counts as one. That holds because a feature too large to hand over is sliced, so features stay near one size.
- Missing figures never stop a first plan. It assumes a start and a pace, and says so.
- Asking to send the plan is the yes.

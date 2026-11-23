# Walk a process

When: a job runs through more than one person or step, or the person says "it depends".

Steps:

1. Ask what starts it. That is the Flow's `Trigger`.
2. Ask what happens first, who does it, and what they hand on. That is a step.
3. At each step ask: "Does this always go the same way?" Each "unless" or "if" is a `Go to` with its condition.
4. Follow one branch to its end before starting the next.
5. Ask what the last person holds when it is over.

Stop when: every branch reaches a step with no `Go to`, or the person cannot say what happens next. Record that as a Question.

Output: one Flow, and a Requirement for each rule that decides a branch.

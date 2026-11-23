# Probe quality needs

When: a feature has no requirement that says how well it must work.

Steps:

1. Pick the Flow's most frequent step and its last.
2. Ask of them, one at a time: how long it may take; how many happen on the busiest day; what people do when it cannot be done; who must not see it; how long its result is kept.
3. An answer with a number becomes a Requirement with `Category: non-functional`, a `Measure` and a `Threshold`.
4. For "fast" or "always", recommend a number the records support and ask if it is right.
5. "It does not matter" is an answer.

Stop when: all five have been asked once, or three in a row did not matter.

Output: non-functional Requirements, and a Question for each number still to come.

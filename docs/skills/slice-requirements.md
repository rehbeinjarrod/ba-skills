# slice-requirements

**Reach for it when** the requirements are captured and you want them grouped into features, need something to hand to engineers, or a feature has proved too big. To work one feature through first, use [define-feature](define-feature.md).

**Say** "Slice these requirements into features", or "Cut the first feature: <its name>" to do one at a time. Then "confirm", and "make the handover briefs".

**What comes back first** is a proposal: each feature with what starts it, who gets what at the end and an example to show it working; a line counting how many requirements to deliver are in a feature so far; and any requirement that reads like a choice about how to build it.

**How to tell it is working**

- Each requirement of the feature you asked for names it. The rest wait, and are counted as not yet in a feature: that is no fault.
- After "confirm" there is one handover brief for each feature, and the reply lists what blocks each.

**It will not** decide how anything is built, or hand over a feature too large to specify as one piece: it slices it, and the parts replace it.

**Good to know**

- A question holds things up until someone gives a working answer. In a handover brief a question with no working answer is marked Blocking: engineers leave what depends on it unbuilt. Give it a working answer and they build on that while its owner confirms.
- Sign-off is an authority to build, not to explore. Engineers can have the brief before sign-off, to plan tests and architecture; it says whether it is approved.
- Slicing does not reopen sign-off: an approval is of the requirements, not of how they are grouped into features.
- A sliced feature with work already logged against its tracker item may be kept beside its parts. It is not counted and has no brief; its parts carry the requirements.
- A requirement can sit in more than one feature. It appears in each one's brief. One that bears on every feature says `all`: each brief names it and links where it is stated in full.
- To take a requirement out of a feature for now, say so and say why. It is held back: the record keeps your reason in your words with your name, and the feature's brief lists it under "Not in this Feature".
- A brief holds what belongs to its feature. A question or an assumption recorded against the whole work is in the sign-off brief, not in each feature's.
- If your house has its own summary of a feature for the business, it is made beside the engineers' brief and attached to the feature's tracker item as a file.

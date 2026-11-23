# Saving a house to a page

A team with no shared folder keeps its house on one Confluence page, whose body is one code block holding the whole of `house.md`. Save after "use it" and after each later change, with your Confluence tools.

1. With no house page yet, ask the person once where it should sit, and create a page there titled with the organisation's name and the word "house". Done when: you have its link.
2. Update the page so its whole body is: a line of four backticks, the text of `house.md` character for character, a line of four backticks. Done when: the update succeeds. If it fails, tell the person the page is behind.
3. Write `- House: <page link>` among the Work's own lines. Done when: `python3 <skill folder>/../../helper/ba.py status` names the link.

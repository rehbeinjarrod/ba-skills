# The home for a Work's records

Each Work has one home, chosen once: a folder, or a Confluence page in the person's personal space. You always work on `work.md` in the current folder. A page only carries that one file from one session to the next, so with a page as home every record stays in `work.md`. A Work whose records are filed by feature in `records/` has a folder as its home.

## A Confluence page

Use your Confluence tools. The page body is one code block holding the whole of `work.md`.

### Fetch, at the start of a session

1. Fetch the page the person named, as markdown. Done when: you hold a body that is one fenced code block. A page with text and no code block is not a records page: stop, and ask the person which page holds the records.
2. Write the text between the first and last fence lines to `work.md`, character for character: every blank line, trailing space and symbol as fetched. Done when: the check lists the records, and the Work record's `Home:` line is this page's link.

### A house kept on a page

When the Work's `House` line is a page link, fetch it the same way and write the code block to `house.md` beside `work.md`. Only the `adopt-house` skill saves to that page. Done when: `check` no longer says `house.md` is missing.

### Save, after each change to `work.md`

1. Update the page so its whole body is: a line of four backticks, the text of `work.md` character for character, a line of four backticks. Done when: the update succeeds. If it fails, tell the person the page is behind and the records are only in this session's folder.

### Choose a page as home, once

1. Ask the person for their personal space, or a page in it to sit under, unless they have said. Done when: you know where the page goes.
2. Create a page there titled with the Work's name and the word "records". Its body is a code block holding the one line `new`. Done when: you have the page's link.
3. Add `- Home: <page link>` to the Work record's lines in `work.md`. Done when: the check still lists the records.
4. Save, as above. Done when: the page holds `work.md` with its `Home:` line.

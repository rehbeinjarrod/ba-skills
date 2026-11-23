# Landing: setting where things go

A place is stored once, after the person has seen a test page and a test item land there and said yes. Every place comes from the person as a link. A Work's parent page, which its documents are created under, is held on that Work under `### Destinations`; the boards, and a page all the team's work shares, in `destinations.md` in the pack. Use your Confluence and Jira tools. With none in this session, tell the person the briefs go to `outbox/` until a session that has them, and stop.

## 1. Ask for the places

Run `python3 <skill folder>/../../helper/ba.py check --adopt house.md`. For each place it shows as `not set`, ask in one message for its link: this work's parent page (with no `work.md` here, the page all the team's work sits under), and the project for each board in the house's hierarchy. End the turn.

Done when: each is given or declined, or none was `not set`.

## 2. Write the sections

When the pack has no `=== destinations.md ===` part, add the shipped one whole:

```
printf '\n=== destinations.md ===\n\n' >> house.md
cat <skill folder>/../../helper/house/destinations.md >> house.md
```

Open each link given with your tools. Fill that section's lines, and `Site`, `Cloud ID` and `Kept by` (the person), from what the tools return. With a `work.md` here, the page's four lines go under `### Destinations` on the Work instead, as `check --shape work` shows. A declined place stays `not set`.

Done when: `python3 <skill folder>/../../helper/ba.py check --adopt house.md` shows each given section set, or the Work holds the four lines.

## 3. Make the test bodies

Run `python3 <skill folder>/../../helper/ba.py bundle landing --house house.md`.

Done when: it prints a note.

## 4. Send each

Do each `Create` line of the note, with the IDs, project, type, title and parent as written and the whole text of the file it names as the body.

Done when: you hold a link for each.

## 5. Show the person

Give each link. Ask of each: is it in the right place, and does it read properly? End the turn.

Done when: the person has answered for each.

## 6. Record the answer

For each yes, write the `Landed` line where the note says, filled in from the tool's reply. For a no, correct the line the person names and go to step 3.

Done when: `check --adopt` shows each yes as proved, or `status` does for the Work's page.

## 7. Tell the person

Say, by link, that the test page and items are still there, and that nothing reads them again: they may remove or keep them. Save the house if it is kept on a page.

Done when: the reply holds each link.

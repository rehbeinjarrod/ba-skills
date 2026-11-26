# Sending a brief

The person asked to send a brief. That request is the yes: send without asking again. The helper's note is the only source of a place.

## 1. Prepare

Run `python3 <skill folder>/../../helper/ba.py bundle <face> --outbox`, with the face the step that sent you here gave.

Done when: it prints a note. A printout that begins "Fetch" asks for a house page: do what it says, then run this step again.

## 2. Read the note

Done when: you can name each page to find or create and each `Create`, `Update`, `Attach` and `Link` line it holds, or that it holds none.

## 3. Hand over, when there is nothing to send to

With no line to do, or no Confluence or Jira tools in this session, give the person the copy and the note, and say where the note says the brief belongs. This is the end.

Done when: the reply names both files and that place.

## 4. Send

Do each line in the note's order, with the IDs, project, type, title and parent as written. Where a line names a file as the body, read the file and send its whole text, character for character. An `Attach` line names a file to attach to an item as it is; the line under it says what to do when your tools cannot.

Done when: each call has succeeded and you hold each reply's ID or key, version and link. A failed call is told to the person, and nothing is recorded.

## 5. Record

Add each line the note says to add, where it says, filled in from the replies. Run `python3 <skill folder>/../../helper/ba.py check` and do each fix it states.

Done when: the check reports nothing on those lines.

## 6. Run again, when the note says to

A note that ends "Then run this command again" has not sent the brief yet. Run that command now, in this turn, and do steps 2 to 5 with the note it prints.

Done when: the last note you followed did not end that way.

## 7. Tell the person

Say what went where: each page or item by its title, the place the note named, and its link. Give the note's `Diagram` line when it has one. Say the page is a copy: an edit made there by hand is replaced by the next sending.

Done when: the reply holds a link for each thing sent.

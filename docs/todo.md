# To do

## Where we are
- Now: To do 10, step B (Chrome button)
- Next: none (Bugs me is empty)
- Updated: 2026-11-13

## To do
Next number: 15. Numbers are permanent: never renumber or reuse one; to move a to-do, move its line.

### Now
The one to-do being built.

- To do 10: Chrome button (large; user 2026-11-11, Chrome instead of Edge 2026-11-13): docs/todo/10-chrome-button.md

### Bugs me
At most 5, in order: the next ones to build. When Now is finished, the first one here moves up.

- Nothing here now.

### Someday
Everything else, unordered (grouped by area once it grows). A Someday to-do moves up only when it starts to bug the user.

- To do 8: Playlists and whole channels (medium; user 2026-11-11; planned, then moved here by the user 2026-11-12): docs/todo/08-playlists.md
- To do 11: An .exe installer (large; user 2026-11-11): docs/todo/11-installer.md

## Later, only if the user asks
- Nothing here now (all moved into the list above on 2026-11-11).
- Never (not "later"): DRM-protected services such as Netflix, Disney+ or Spotify.

## Writing a to-do
- **Number:** the "Next number" (then raise that line by one). The line goes under Someday, unless the user says it bugs them or wants it soon: then under Bugs me where the user says (at most 5 there, so ask which one drops back to Someday), and "Next:" and "Updated:" in "Where we are" change with it.
- **Title** with size (small / medium / large) and the goal in the user's words.
- **Problem / Goal:** what is wrong or wanted, with an example. For a bug or research to-do, also what the user has seen (it exists, where, what works) and what is already ruled out.
- **Read first:** files and functions to look at, outside references.
- **Approach:** the suggested design, what to reuse.
- **Ask the user:** open questions, each with a suggested answer.
- **Test:** what Claude checks, and what the user tests by hand.

Every to-do is its own file from the start, docs/todo/NN-name.md (two-digit number, short name), starting "# To do N: title (size)" and holding the template's parts (later also its Progress list). The list holds one line per to-do and nothing more, so it stays a quick overview: `- To do N: title (size; user YYYY-MM-DD): docs/todo/NN-name.md`. When a to-do is finished, finish-step moves its file unchanged to docs/archive/.

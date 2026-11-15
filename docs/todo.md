# To do

## Where we are
- Now: Before a public release (no to-dos open)
- Next: nothing under Bugs me
- Updated: 2026-11-15

## To do
Next number: 23. Numbers are permanent: never renumber or reuse one; to move a to-do, move its line.

### Now
The one to-do being built.

- Nothing here now: the "Before a public release" list below comes next (To do 21 finished 2026-11-15).

### Bugs me
At most 5, in order: the next ones to build. When Now is finished, the first one here moves up.

- Nothing here now.

### Someday
Everything else, unordered (grouped by area once it grows). A Someday to-do moves up only when it starts to bug the user.

- To do 22: the yt-dlp updater follows yt-dlp's `_update_spec` (small; user 2026-11-14): docs/todo/22-ytdlp-update-spec.md

## Later, only if the user asks
- Nothing here now (all moved into the list above on 2026-11-11).
- Never (not "later"): DRM-protected services such as Netflix, Disney+ or Spotify.

## Before a public release
Starts once To do 21 is finished (the user, 2026-11-14: a Setup.exe that other people install must keep yt-dlp current). In this order:
- ~~A license: add a LICENSE file, MIT (the user, 2026-11-14).~~ Done 2026-11-15: "the video-downloader authors", and a License line in the README (decisions.md).
- ~~A screenshot of the window in the README (`python tests/gui/screenshots.py`).~~ Done 2026-11-15: the "history" screen as docs/images/window.png, under the README's first lines (decisions.md).
- ~~The README follows the "README" rule in ~/.claude/CLAUDE.md, checked with `/trim-readme` (it measures first and stops if the README already fits).~~ Done 2026-11-15: it fits, nothing moved. Measured: 73 lines, install at line 24, the longest section "Install and run" at 26 lines (the details already moved to docs/using.md on 2026-11-12).
- ~~A fresh subagent that hasn't seen the project checks README.md and the docs it links against the code, and only reports; the user decides the fixes.~~ Done 2026-11-15: 13 findings, 10 fixed, 3 left (decisions.md).
- ~~Start CHANGELOG.md (Keep a Changelog: Unreleased first, then versions newest first) with the first version.~~ Done 2026-11-15: version 0.1.0 (decisions.md).
- ~~Setup.exe as a download on a GitHub Release: ask the user first (suggested: yes, now that To do 21 keeps yt-dlp current). A downloaded, unsigned Setup.exe gets SmartScreen's warning (docs/research/installer.md, "Signing"), and the Chrome button is an unpacked extension, which others load in Chrome's developer mode; the README says both.~~ Done 2026-11-15: yes; the README installs from the Release, the app ships its licenses without mutagen, Setup's version is 0.1.0 plus the build time (decisions.md). The Release itself goes up with the go-public step below.
- ~~Last, so it sees every file written above: search all tracked files for the "Never in tracked files" list in CLAUDE.md. If old commits hold any of it (except the GitHub login, which old commits may hold), publish a new repo with one clean commit instead of rewriting history.~~ Done 2026-11-15: nothing found, so no new repo. Searched (measured): the 78 tracked files and all 48 commits (contents and messages) for the user folder, the login, e-mail addresses and drive paths (only made-up test paths such as `C:\Fresh`); no video or audio was ever committed; the PNGs show nothing personal and hold no metadata. Also the built app, which the Release makes public (docs/research/installer.md, "No build PC paths in the build"). The commit e-mail, which every commit carries, stays (decisions.md).
- Then the user switches the repo to public, and version 0.1.0 is released: CHANGELOG.md's date set to that day, `python installer/build.py` (with the yt-dlp update), a tag `v0.1.0` and a GitHub Release "0.1.0" with `Video Downloader Setup.exe` and the changelog's 0.1.0 section as its notes. Then check the README's install steps with the downloaded Setup.exe (SmartScreen's warning).

## Writing a to-do
- **Number:** the "Next number" (then raise that line by one). The line goes under Someday, unless the user says it bugs them or wants it soon: then under Bugs me where the user says (at most 5 there, so ask which one drops back to Someday), and "Next:" and "Updated:" in "Where we are" change with it.
- **Title** with size (small / medium / large) and the goal in the user's words.
- **Problem / Goal:** what is wrong or wanted, with an example. For a bug or research to-do, also what the user has seen (it exists, where, what works) and what is already ruled out.
- **Read first:** files and functions to look at, outside references.
- **Approach:** the suggested design, what to reuse.
- **Ask the user:** open questions, each with a suggested answer.
- **Test:** what Claude checks, and what the user tests by hand.

Every to-do is its own file from the start, docs/todo/NN-name.md (two-digit number, short name), starting "# To do N: title (size)" and holding the template's parts (later also its Progress list). The list holds one line per to-do and nothing more, so it stays a quick overview: `- To do N: title (size; user YYYY-MM-DD): docs/todo/NN-name.md`. When a to-do is finished, finish-step moves its file unchanged to docs/archive/.

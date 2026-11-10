# video-downloader

## Goal
A small Windows app for one person: paste a link to a video and get it on this PC as MP4 (or MP3, audio only), with progress shown. It is a thin layer on top of yt-dlp, which does the actual downloading; ffmpeg joins video and audio, and a JavaScript runtime (Deno) is needed for YouTube.

Don't build what's under "Later" in docs/todo.md until asked. Never: anything that gets around DRM (Netflix, Disney+, Spotify and the like).

## User and environment
- Windows 11, Python 3.13 in a project `.venv`, window made with tkinter (comes with Python).
- Outside tools: yt-dlp (Python package in the `.venv`), ffmpeg and Deno (installed with winget).
- Shell: PowerShell in the VS Code terminal.
- Real paths (project, download folder, tool locations): docs/local.md (gitignored).

## Working style
- One to-do per chat, built with the /build-todo skill (`/build-todo N`, or `/build-todo N, step B` for one step of a bigger to-do). New to-dos are written with /add-todo.
- Commit after each working step. End a step with the finish-step skill.

## Build specifics
Read by the /build-todo skill. To do 1 sets these up and replaces the rough times with measured ones.
- **Checks** (from the project folder, `.venv` active):
  - After each edit (fast): `ruff check .` and `ruff format .` (~1 s).
  - Once per step (slow): `pytest` (a few seconds; tests never touch the internet) and `pyright` (~5 s).
  - GUI test and screenshots: added by To do 2.
- **Docs to update when behaviour changes:** README.md (headline features, install and run steps, Credits) and any help text in the app. When a README section grows past about a screen, move it into docs/NAME.md and link it from the README.
- **Must keep working:** (empty for now)
- **Review checklist:** none yet: the built-in code-review skill. Add docs/review.md once the project has its own rules to check.

## Status
Now and next: the "Where we are" block at the top of docs/todo.md.

## Decisions
One line per decision to follow; reasons, who decided and what was rejected: docs/decisions.md.
- Build on yt-dlp as a Python library; never write our own site downloaders. Desktop window first, Edge button later.
- Python 3.13 with tkinter for the window.

## Project docs
- README.md: what it is, install and run, Credits.
- docs/local.md: this PC's paths and copy-ready commands (gitignored).
- docs/todo.md: to-dos and "Where we are".
- docs/decisions.md: decisions with reasons.
- docs/research/: one file per topic (start with prior-art.md).

## Never in tracked files
- Personal paths (user folder, drive paths): they go in docs/local.md. In code, build paths from the home folder (`Path.home()`), never type them out.
- The GitHub login used for pushes: it goes in docs/local.md; current files only, old commits that hold it are fine.
- Downloaded videos or audio (also blocked in .gitignore).

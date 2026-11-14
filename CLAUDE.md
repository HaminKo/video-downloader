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
Read by the /build-todo skill. Times measured 2026-11-10 (To do 1).
- **Checks** (from the project folder, `.venv` active):
  - After each edit (fast): `ruff check .` and `ruff format .` (0.1 s together).
  - Once per step (slow): `pytest` (25 to 37 s; tests never touch the internet, the download tests fetch a clip from a web server they start on this PC and need ffmpeg) and `pyright` (1-2 s). Times measured 2026-11-14 (To do 10; 9 to 14 s and 12 s on 2026-11-12, the slowest tests are the download tests).
  - The GUI test `pytest tests/gui/window_gui.py` (24 to 28 s, measured 2026-11-14; a fake download stands in for yt-dlp): once, only in a step that changes app.py, handoff.py or tests/gui. It is the only test that types and clicks in the real window and sends it a link; the other files are covered by `pytest`.
  - pytest runs with `--capture=sys` (set in pyproject.toml): the default breaks a second tkinter window (docs/research/tkinter-tests.md).
  - The GUI test opens the real window on top, on another screen with the main screen's scaling when there is one (on this PC the right-hand one), and doesn't take the keyboard or the front (the first window is in front for about 40 ms per run); real keys and clicks in the test window are ignored. A UI change gets a step in it (tests/gui/window_gui.py; helpers in tests/gui/drive.py). How it works: docs/research/gui-testing.md.
  - Screenshots: `python tests/gui/screenshots.py` (all screens) or `python tests/gui/screenshots.py NAME` (screens: start, progress, done, error, cancelled, queue, history, received). Saved to `$env:TEMP\video-downloader-screenshots\NAME.png`, paths printed. About 690 tokens each (estimate from the size, 903 × 571 px measured 2026-11-14); the title bar is grey, as the window isn't in front. A new screen gets an entry in `SCREENS` in that file.
- **Docs to update when behaviour changes:** README.md (headline features, install and run steps, Credits), docs/using.md (how each part of the window works) and any help text in the app. When a README section grows past about a screen, move it into docs/NAME.md and link it from the README.
- **Must keep working:** Enter in the link box and the Download button both start a download (checked by the GUI test).
- **Review checklist:** none yet: the built-in code-review skill. Add docs/review.md once the project has its own rules to check.

## Status
Now and next: the "Where we are" block at the top of docs/todo.md.

## Decisions
One line per decision to follow; reasons, who decided and what was rejected: docs/decisions.md.
- Build on yt-dlp as a Python library; never write our own site downloaders. Desktop window first, a Chrome button later.
- Chrome button: an unpacked extension + native messaging (Chrome's HKCU key, written by `python -m video_downloader.browser install`); links reach the open window through a named pipe as plain text (`send_bytes`, never pickle); a link only fills in the box.
- Chrome's helper is `host.py` and imports only `handoff`, never yt-dlp (it starts on every click); only web pages are sent; the button shows only failures (a red "!", why in its tooltip).
- Python 3.13 with tkinter for the window.
- Deno (yt-dlp's default) is the JavaScript runtime for YouTube, not Node.
- Reddit needs signing in (it blocks anyone not signed in); curl_cffi was tried and doesn't help.
- Signing in: a cookies.txt (Reddit's cookies only) in `%APPDATA%\video-downloader`, used whenever it's there and only read (yt-dlp gets a copy); no checkbox, no YouTube sign-ins, never a password in the app.
- ffmpeg is winget's `yt-dlp.FFmpeg` (yt-dlp's own build).
- MP4 and MP3 use yt-dlp's own `-t mp4` (H.264 + AAC, plays everywhere) and `-t mp3` presets.
- Video quality: Best, 720p or 480p, as `res:N` right after `vcodec:h264` in the mp4 sort (before `quality`, or it does nothing); 720p and 480p files are named `Title (720p).mp4`.
- Subtitles: a checkbox (MP4 only), English only, saved as a separate `Title.en.srt` next to the video, never inside the MP4 (Windows can't read them there).
- Play (default app, `os.startfile`) and Show in folder (`explorer /select,"PATH"`, one string, path quoted) buttons under the status line, for the selected row; nothing opens by itself after a download.
- Queue: every download is a row in one list; links run one after another, each with the choices it was added with; the bar and status line show the selected row; Remove never deletes a file.
- History: rows with a saved file (Done, Already there), the newest 200, in `%APPDATA%\video-downloader\history.json`, written anew after each saved file and each Remove; tests and screenshots always pass their own history file.
- Cancel button next to Download: raises yt-dlp's `DownloadCancelled` from the hooks, then deletes only files that are new since the start and named `Title.` + anything (never one that was there before); an ffmpeg step finishes first.
- MP3 sets `keepvideo`; the app deletes the file converted from only when it wasn't in the folder before (an MP4 already there stays).
- Failures show a plain message (text patterns in `PLAIN_MESSAGES`, first match wins), anything else yt-dlp's own text; ffmpeg is checked before a download starts.
- The GUI test drives the window with Tk's own key and click events in the same process, never real OS input; screenshots with Pillow (development only).
- GUI test and screenshot windows open on the topmost other screen with the main screen's scaling (picked automatically) and never take the front: focus with Windows' `SetFocus`, never `focus_force()`; `bring_to_front()` is recorded there, not called.

## Project docs
- README.md: what it is, install and run, Credits.
- docs/using.md: using the app in detail (moved out of the README 2026-11-12).
- docs/local.md: this PC's paths and copy-ready commands (gitignored).
- docs/todo.md: the list and "Where we are"; docs/todo/: one file per to-do.
- docs/archive/: finished to-dos' files, read only when a to-do names one.
- docs/decisions.md: decisions with reasons.
- docs/research/: one file per topic (start with prior-art.md).

## Never in tracked files
- Personal paths (user folder, drive paths): they go in docs/local.md. In code, build paths from the home folder (`Path.home()`), never type them out.
- The GitHub login used for pushes: it goes in docs/local.md; current files only, old commits that hold it are fine.
- Downloaded videos or audio (also blocked in .gitignore).

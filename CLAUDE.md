# video-downloader

## Goal
A small Windows app for one person: paste a link to a video and get it on this PC as MP4 (or MP3, audio only), with progress shown. It is a thin layer on top of yt-dlp, which does the actual downloading; ffmpeg joins video and audio, and a JavaScript runtime (Deno) is needed for YouTube.

Don't build what's under "Later" in docs/todo.md until asked. Never: anything that gets around DRM (Netflix, Disney+, Spotify and the like).

## User and environment
- Windows 11, Python 3.13 in a project `.venv`, window made with tkinter (comes with Python).
- Outside tools: yt-dlp (Python package in the `.venv`), ffmpeg and Deno (installed with winget); Inno Setup (winget, for the build only).
- Shell: PowerShell in the VS Code terminal.
- Real paths (project, download folder, tool locations): docs/local.md (gitignored).

## Working style
- One to-do per chat, built with the /build-todo skill (`/build-todo N`, or `/build-todo N, step B` for one step of a bigger to-do). New to-dos are written with /add-todo.
- Commit after each working step. End a step with the finish-step skill.

## Build specifics
Read by the /build-todo skill. Times measured 2026-11-10 (To do 1).
- **Checks** (from the project folder, `.venv` active):
  - After each edit (fast): `ruff check .` and `ruff format .` (0.1 s together).
  - Once per step (slow): `pytest` (47 to 64 s; tests never touch the internet, the download tests fetch a clip from a web server they start on this PC and need ffmpeg) and `pyright` (1-2 s). Times measured 2026-11-14 (To do 8, step C; 25 to 37 s earlier that day, 9 to 14 s on 2026-11-12; the slowest tests are the download tests).
  - The GUI test `pytest tests/gui/window_gui.py` (43 to 47 s, measured 2026-11-14, To do 8, step C; 24 to 28 s earlier that day; a fake download stands in for yt-dlp): once, only in a step that changes app.py, handoff.py or the window's test files (window_gui.py, drive.py). It is the only test that types and clicks in the real window and sends it a link; the other files are covered by `pytest`.
  - The popup's GUI test `pytest tests/gui/popup_gui.py` (18 s for 15 cases, measured 2026-11-14; extension/popup.html in headless Chrome with Chrome's extension functions faked, nothing shows on screen): once, only in a step that changes extension/ or its test files (popup_gui.py, popup.py, fake_chrome.js).
  - The built app `python installer/build.py --no-update` (2 min 6 s with Setup, of which Inno Setup 12 s, measured 2026-11-14, To do 11 step B; `--no-update` leaves yt-dlp in the `.venv` as it is): once, only in a step that changes installer/ or places.py. Makes `dist\Video Downloader\` and `dist\Video Downloader Setup.exe`; check that the window opens and the helper answers (docs/research/installer.md, "The build"). A step that changes setup.iss also installs and uninstalls silently and checks both, also with the installed window open (both stop: "The window open"), then puts Chrome's key back as it was: `python -m video_downloader.browser install` for the project's helper, Setup again for the installed one (same file, "The installer").
  - pytest runs with `--capture=sys` (set in pyproject.toml): the default breaks a second tkinter window (docs/research/tkinter-tests.md).
  - The GUI test opens the real window on top, on another screen with the main screen's scaling when there is one (on this PC the right-hand one), and doesn't take the keyboard or the front (the first window is in front for about 40 ms per run); real keys and clicks in the test window are ignored. A UI change gets a step in it (tests/gui/window_gui.py; helpers in tests/gui/drive.py). How it works: docs/research/gui-testing.md.
  - Screenshots: `python tests/gui/screenshots.py` (all screens) or `python tests/gui/screenshots.py NAME` (screens: start, progress, done, error, cancelled, queue, playlist, history, received, updated; the Chrome popup: popup, popup-error). Saved to `$env:TEMP\video-downloader-screenshots\NAME.png`, paths printed. About 690 tokens each (estimate from the size, 903 × 571 px measured 2026-11-14); the title bar is grey, as the window isn't in front. The popup's about 160 tokens (492 × 245 px). A new screen gets an entry in `SCREENS` (the popup's: `POPUP_SCREENS`) in that file.
- **Docs to update when behaviour changes:** README.md (headline features, install and run steps, Credits), docs/using.md (how each part of the window works) and any help text in the app. When the window's look changes, the README's picture too: `python tests/gui/screenshots.py history`, copied to docs/images/window.png. When a README section grows past about a screen, move it into docs/NAME.md and link it from the README.
- **Must keep working:** Enter in the link box and the Download button both start a download (checked by the GUI test).
- **Review checklist:** none yet: the built-in code-review skill. Add docs/review.md once the project has its own rules to check.

## Status
Now and next: the "Where we are" block at the top of docs/todo.md.

## Decisions
One line per decision to follow; reasons, who decided and what was rejected: docs/decisions.md.
- Build on yt-dlp as a Python library; never write our own site downloaders. Desktop window first, a Chrome button later.
- Public since 2026-11-15 (version 0.1.0), with its git history (the commit identity's e-mail stays in it); MIT, LICENSE says "the video-downloader authors", never a person.
- Semantic versioning from 0.1.0: a release sets the number in CHANGELOG.md and pyproject.toml (a test checks they match), then `python installer/build.py` (with the yt-dlp update), a tag `vX.Y.Z` and a GitHub Release with `Video Downloader Setup.exe` (uploaded with that name as its label: GitHub turns the spaces into dots), its notes an Install line plus the changelog's section, links pointing at the tag (docs/research/installer.md, "Releasing"). CHANGELOG.md is Keep a Changelog without compare links (the repo URL names the account); each change users can see gets one plain line under Unreleased.
- Chrome button: an unpacked extension + native messaging (Chrome's HKCU key, written by `python -m video_downloader.browser install`); links reach the open window through a named pipe as JSON (`send_bytes` and `json.loads`, never pickle); a link alone fills in the box, a link with choices (`--download mp3`) joins the list without touching the box or the front (a window opened for it starts minimized).
- Chrome's helper is `host.py` and imports only `handoff` and `places`, never yt-dlp (it starts on every click); only web pages are sent; the button opens a popup with the window's choices (its own, kept in `chrome.storage.local`) that says when it worked or, in red, why not.
- One window: `main()` takes the pipe before `tk.Tk()`; when another window has it, it hands over its link (with no link `{"show": true}`: that one to the front) and quits; `Listening` reads only from `start()`, once the window is built.
- The popup's Cancel: `{"link", "cancel": true}`, answered by the window on the same connection; it cancels every unfinished row of exactly that link (waiting ones become Cancelled), leaves the selection, and never opens a window.
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
- Playlists: every video, into `Videos\<playlist title>\` (`%(playlist_title|.).80B/`), as one row ("Video N of M" via `match_filter`); failed = the playlists' `n_entries` minus the finished videos; Cancel keeps finished videos (their files join "there before" in the post hook).
- Above 50 videos a playlist asks first: download()'s `confirm` per playlist, a Yes/No box from `check_events()` with the window brought to the front first; No = Cancelled.
- The app deletes only through `delete()`: only in the download folder or a folder directly inside it, path resolved first; "there before" is by full path over the same two levels.
- yt-dlp runs with `ignoreerrors: "only_download"` and the `Log` logger; a failure's message is the first "ERROR:" line.
- Failures show a plain message (text patterns in `PLAIN_MESSAGES`, first match wins), anything else yt-dlp's own text; ffmpeg is checked before a download starts.
- The window's icon: extension/icons' PNGs through `iconphoto` (one copy), and the app ID `VideoDownloader.App` set in `start()` before `tk.Tk()`, or the taskbar shows Python's icon.
- The app ships as .exe files: PyInstaller, one folder (`Video Downloader.exe` without a console, `chrome-helper.exe` with one, the extension folder next to them), built on this PC by `installer/build.py`, which updates yt-dlp first; `places.py` says where things are, from the project or built. mutagen (GPL, only for thumbnails) is left out of the build; build.py puts `LICENSE.txt` and `THIRD-PARTY-LICENSES.txt` (Python, Tcl/Tk and every library the spec's `build/modules.txt` names, in full; the build stops on a library without a license file) next to the .exe files.
- Setup.exe: Inno Setup (`installer/setup.iss`, its shared names checked by a test), for this user only into `%LOCALAPPDATA%\Programs\Video Downloader`, one page; its version is pyproject.toml's (build.py passes `/DAppNumber`) plus the build's date and time; build.py writes `host.json` (relative path) next to the helper, imports only `places` and `browser` (no yt-dlp), and finds ISCC.exe through Inno Setup's own uninstall entry.
- An open window holds the mutex `APP_ID` (`hold_mutex()` in `main()`, not `start()`, never closed); setup.iss's `AppMutex` makes Setup and the uninstaller ask to close it first.
- The built app only updates yt-dlp itself: at start, at most once a day, in the background, stable, the release's zipapp from yt-dlp's GitHub with its checksum, unpacked and compiled, used from the next start; copies in the app folder's `yt-dlp\`, the only place the updater deletes (version-named folders, never the one in use or the newest); a line of its own under the buttons says when a copy is ready, with Restart now (greyed out while busy; `root.quit()`, then `main()` closes the window and runs `host.start_app([])`); only the uninstaller deletes the folder (`[UninstallDelete]`), Setup keeps it.
- The updater follows the newest release's `_update_spec` as yt-dlp reads it (variant `zip`), also when the newest failed; a 404 counts as no lock, any other failure means no update that day; nothing shown.
- The GUI test drives the window with Tk's own key and click events in the same process, never real OS input; screenshots with Pillow (development only).
- GUI test and screenshot windows open on the topmost other screen with the main screen's scaling (picked automatically) and never take the front: focus with Windows' `SetFocus`, never `focus_force()`; `bring_to_front()` is recorded there, not called.

## Project docs
- README.md: what it is, install and run, Credits.
- docs/using.md: using the app in detail (moved out of the README 2026-11-12).
- CHANGELOG.md: what changed in each version, for users.
- docs/local.md: this PC's paths and copy-ready commands (gitignored).
- docs/todo.md: the list and "Where we are"; docs/todo/: one file per to-do.
- docs/archive/: finished to-dos' files, read only when a to-do names one.
- docs/decisions.md: decisions with reasons.
- docs/research/: one file per topic (start with prior-art.md).

## Never in tracked files
- Personal paths (user folder, drive paths): they go in docs/local.md. In code, build paths from the home folder (`Path.home()`), never type them out.
- The GitHub login used for pushes: it goes in docs/local.md; current files only, old commits that hold it are fine.
- Downloaded videos or audio (also blocked in .gitignore).

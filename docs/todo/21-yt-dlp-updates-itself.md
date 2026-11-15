# To do 21: yt-dlp updates itself (large)

The user (2026-11-14): "add it as a step after we build the update yt-dlp". The project goes public after this to-do ("Before a public release" in docs/todo.md), and a Setup.exe that other people install must not break when YouTube changes.

## Problem / Goal
The built app carries the yt-dlp it was built with. When YouTube changes, an old yt-dlp's YouTube downloads start failing, and today the only fix is to build again with `python installer/build.py` and run the new Setup (docs/using.md, "Updating yt-dlp"). That works on this PC only. Goal: the installed app gets a newer yt-dlp by itself.

Example: someone installs Setup.exe in December. In February YouTube changes and their downloads fail. They start the app, it fetches the new yt-dlp, and after that downloads work again without a new Setup.

## Read first
- docs/decisions.md: the 2026-11-14 ".exe files" entry (self-update was rejected then: more code, and a fallback when a new version breaks), the 2026-11-11 Reddit entry (an update at start-up rather than after a failure; a new version loads only after a restart), the 2026-11-10 setup entry (yt-dlp has a minimum version only), and the 2026-11-14 "goes public" entry.
- docs/research/installer.md: "Updating yt-dlp" and "The build".
- src/video_downloader/downloader.py: `import yt_dlp` at the top, plus `CookieLoadError`, `DownloadCancelled` and `_Params`. A replacement yt-dlp must be in place before this module is imported.
- src/video_downloader/places.py: `built()`, and `DATA_FOLDER` (where a downloaded yt-dlp could live, next to history.json).
- installer/start_app.py, installer/video-downloader.spec: how the built app starts, and what yt-dlp's PyInstaller hook bundles (yt-dlp-ejs, for YouTube's JavaScript challenges).
- yt-dlp's releases on GitHub (the `yt-dlp` zipapp, `SHA2-256SUMS` and its signature) and its own updater, `yt_dlp/update.py`: what it supports for a frozen app that isn't yt-dlp's own .exe.

## Approach
Suggested; the build session researches first.
- **Step A, research** (into docs/research/yt-dlp-update.md): what to download. Candidates, from general knowledge and not checked yet: yt-dlp's release zipapp (a zip of the Python package) put first on `sys.path`, or the wheel from PyPI unpacked into a folder. Also: whether yt-dlp-ejs must update with it; whether the compiled extras from `yt-dlp[default]` still fit a newer yt-dlp; and how to check the download (yt-dlp's published checksums).
- **Step B, build it.** Only in the built app (`places.built()`); from the project, `pip install -U` stays the way.
  - At start-up, before downloader.py is imported: use the downloaded yt-dlp in `DATA_FOLDER` if it is newer than the bundled one and imports cleanly, otherwise the bundled one.
  - In the background: ask GitHub for the latest version, download it, check its checksum, unpack it beside the old copy, and switch only once it is complete.
  - A broken, half-downloaded or failing copy never stops the app: it falls back to the bundled yt-dlp.
- This downloads code and runs it, so: HTTPS from yt-dlp's own GitHub releases only, and the checksum always checked.
- Reuse: the download tests' local web server (tests never touch the internet) can stand in for GitHub.

## Ask the user
1. How often should it look for a new yt-dlp? Suggested: at each start, at most once a day.
2. Use the new version at once, or from the next start? Suggested: from the next start, because swapping yt-dlp in a running app is fragile. A short line in the window says to restart.
3. What does the window show? Suggested: one line only when an update was installed; nothing when there's no update or no internet.
4. Stable or nightly releases? Suggested: stable (yt-dlp's default). Nightly fixes come faster, but break more often.
5. Also when running from the project? Suggested: no, `pip install -U` stays.

## Test
- **Claude:** tests with a local web server standing in for GitHub (no internet):
  - a newer version is downloaded, checked, and used at the next start;
  - a wrong checksum, a cut-off download or a copy that fails to import leaves the bundled yt-dlp in use;
  - it asks at most once a day;
  - from the project nothing happens.
  Then the built app (`python installer/build.py`): the window opens with a downloaded yt-dlp and without one.
- **The user:** install a Setup built with an older yt-dlp, start it with the internet on, and check the window's line. Restart and download a YouTube video. Then start it with the internet off: the app opens as usual.

## Progress
Design agreed 2026-11-14 (questions 1-8: all of Claude's suggestions; docs/decisions.md, "The built app updates yt-dlp itself"). Research: docs/research/yt-dlp-update.md.
- **Step A: research** (done 2026-11-14; docs only, measured with a throwaway build, no project code). docs/research/yt-dlp-update.md. The release's zipapp `yt-dlp` (no wheel on GitHub; it carries the matching `yt_dlp_ejs`); a copy first on `sys.path` wins in the built app, and a copy that fails to import falls back to the bundled one in the same process. The user's choice (Claude's suggestion): copies unpacked and compiled, so the app starts as fast as now, rather than the zipapp as one file (about 1.3 s slower at every start). Not needed: the whole standard library bundled (no case in 3 years of releases). `_update_spec` left to To do 22 (Someday).
- **Step B: the updater, no change in the window** (done 2026-11-14, tested by the user). `src/video_downloader/ytdlp_update.py` (standard library and `places` only): `use_newest()` in `installer/start_app.py` before the app is imported (copies newest first, each checked by importing `video_downloader.downloader`, the bundled yt-dlp last); `check()` in a background thread from `main()` once the window is built, built app only; `places.ytdlp_folder()` is the app folder's `yt-dlp\`. Tests: tests/test_ytdlp_update.py (a local web server as GitHub, a fake zipapp as the release). The built app was checked against the real GitHub, with a real download and with broken copies (docs/research/yt-dlp-update.md, "Step B: the updater as built"). Step B's questions (the user, on Claude's suggestions): the import check imports the app's own `downloader.py`, not only `yt_dlp`; "once a day" counts from the last time GitHub answered; a copy that fails is written down as failed, deleted at the next check, never downloaded again; the notes (`checked`, `failed`, `error`) in `yt-dlp\update.json`.
  - For step C: the window's line can read `ytdlp_update.in_use` (the copy's version, None = bundled), `bundled_version()`, and what `check()` returns (the version ready for the next start, or None) plus the notes' `error`. Until setup.iss removes `{app}\yt-dlp` on uninstall, don't install a Setup.exe built from this code. README's "To update yt-dlp, do steps 3 and 4 again" is now out of date. A copy starts the window about 0.25 s later than the bundled yt-dlp (measured; step A expected about 0.05 s, not looked into).
- **Step C: the visible part** (done 2026-11-15, tested by the user). `App.look_for_update(check)` runs the check in a thread and shows `UPDATED` in a label of its own under the Play, Show in folder and Remove buttons, placed only when a version is ready (screenshot `updated`; tests in test_app.py and window_gui.py). setup.iss's `[UninstallDelete]` removes `{app}\yt-dlp`; Setup over an install keeps it. The user's choices (Claude's suggestions): the line under the buttons, not the status line; the copies kept on install; the user's test with the installed dist-info's version lowered to 2026.1.1 (no newer release than 2026.10.26 yet). Silent round trip with a real download: docs/research/installer.md, "The downloaded yt-dlp copies".
  - The user's test feedback: closing and reopening by hand is annoying; they asked for "a new version is available" with a click that downloads and restarts the app.
- **Step D: a Restart now button** (designed 2026-11-15; the user, on Claude's suggestions: the download stays automatic, as asking first would mean waiting 10-15 s after each click; a button on the line; step D rather than a new to-do, so the public release waits for it).
  - The update line gets a **Restart now** button next to its text (the text then needn't say "Close and reopen"). Greyed out while a download runs or links wait (in `update_states()`), since a restart stops the running download and drops the waiting ones; clickable once the list is idle.
  - Click: the window closes (`root.destroy()`, which also closes the pipe) and asks main() to start the app again once `mainloop()` returns, then the process ends. Start it as `host.start_window()` does (`places.app_command()`, detached, no console, DEVNULL, fresh PATH): move that into one function both use, without a link. main() already copes with a start while the old window is still closing (pipe taken, hand-over fails, it listens again); the mutex overlaps for a moment, harmless.
  - Tests: test_app.py (a click on an idle list asks for a restart and main() starts the app once, with a fake starter; no restart while busy), a GUI test step (greyed out during a download, clickable after; the click uses a fake), the `updated` screenshot with the button. Then `python installer/build.py --no-update`, install silently, lower the installed dist-info's version as in step C, and check that Restart now opens the new window with the copy in use.
  - Docs: docs/using.md "Updating yt-dlp", the decisions entry's text for the line, CLAUDE.md's decision line.

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

# To do 22: the yt-dlp updater follows yt-dlp's `_update_spec` (small)

From To do 21, step A (the user agreed 2026-11-14, as Claude's suggestion): "once yt-dlp drops Python 3.13 (likely around 2029) the app knows the last version for it". Built only after To do 21.

## Problem / Goal
To do 21's updater always asks for yt-dlp's newest stable release. yt-dlp drops a Python version about when that version's support ends (3.10 in 2026.10.21, after its end of life in October 2026), and the built app's Python is fixed when it is built. Once yt-dlp drops 3.13, every newer release fails the app's import check: the app then keeps the last copy that imported, but only if it happened to download that one in time. yt-dlp's own updater reads a small file in every release, `_update_spec`, that names the last version for each old Python.

Example: in late 2029, yt-dlp 2029.10.20 drops Python 3.13, and 2029.10.15 is the last for it. An app last started in August has 2029.08.01. With this to-do it gets 2029.10.15; without it, it stays at 2029.08.01 until a new Setup.

## Read first
- docs/research/yt-dlp-update.md: "yt-dlp's own updater" (the lock lines) and "yt-dlp's GitHub releases" (the 2026-11-14 `_update_spec`).
- `.venv\Lib\site-packages\yt_dlp\update.py`: `_process_update_spec()` and `query_update()`; `yt_dlp/utils/_utils.py`: `system_identifier()`.
- `src/video_downloader/ytdlp_update.py` (To do 21, step B): where the newest version is asked for.

## Approach
- Download `_update_spec` from the latest release with the other files (2.8 KB).
- Read the `lockV2 yt-dlp/yt-dlp <tag> <regex>` lines and match each regex at the start of `"zip Python <version> ..."`, built like `system_identifier()` with the variant `zip` (the app uses the zipapp). A match caps the version at that tag: download that release's zipapp and `SHA2-256SUMS` instead, if it is newer than the copy in use.
- Reuse: To do 21's download, checksum and unpack steps, with a tag instead of "latest". The updater imports no yt-dlp, so this is a few lines of its own, not a call into `update.py`.

## Ask the user
1. Match as the variant `zip`? Suggested: yes, since the app downloads the zipapp. The lock lines for `zip` name the Python version only.
2. Show anything when the version is capped? Suggested: no, the same as "no update".
3. (Added 2026-11-15.) A missing `_update_spec` (a 404)? Suggested: download the newest, since the import check already keeps a too-new release from being used.

Answers (the user, 2026-11-15): all three as suggested (docs/decisions.md, 2026-11-15 "`_update_spec`").

## Test
- **Claude:** with To do 21's local web server: an `_update_spec` whose lock line matches the running Python makes the updater download the locked tag, not the latest; one that doesn't match changes nothing; a missing `_update_spec` (a 404) falls back to the latest, ~~as yt-dlp's own updater does~~ (wrong, found 2026-11-15: yt-dlp's updater stops on a 404; the app falls back anyway, question 3).
- **The user:** nothing by hand (the case can't happen before yt-dlp drops Python 3.13).

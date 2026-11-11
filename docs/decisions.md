# Decisions

Each entry: `## YYYY-MM-DD: the decision` as the heading, then the reason, who decided, and what was rejected and why. Newest first.

## 2026-11-11: Plain messages when a download fails, found by matching yt-dlp's error text; ffmpeg checked before starting
- **Reason:** yt-dlp's messages are long and talk about command-line options the app doesn't have. A private, removed or sign-in-only video is the same error type in yt-dlp; only the text differs, so the app matches text patterns in order (`PLAIN_MESSAGES` in downloader.py) and shows yt-dlp's own text for anything else. If a yt-dlp update changes a text, that case falls back to yt-dlp's text, no worse than before. Without ffmpeg, yt-dlp doesn't fail on an MP4 but quietly picks a worse file, so the app checks for ffmpeg first (docs/research/yt-dlp-library.md "Errors").
- **Who decided:** the user, on Claude's suggestions (To do 3, step B), including the wording of each message.
- **Rejected:**
  - matching yt-dlp's error types: they can't tell private from removed
  - showing yt-dlp's text under the plain message: long, and it still goes to the terminal
  - letting yt-dlp report a missing ffmpeg: for MP4 it doesn't, it only warns
- **Also chosen, on Claude's suggestions:** failures in dark red; two extra cases (country block, YouTube's bot check). Added after the code review: YouTube's rate limit gets its own message, since the bare word "unavailable" also matched a passing server error (503).

## 2026-11-11: MP4 that plays everywhere (H.264 + AAC), MP3 via ffmpeg: yt-dlp's own `-t mp4` and `-t mp3` presets
- **Reason:** Windows' own player and phones open H.264 MP4s; AV1 and VP9 often don't. yt-dlp ships these settings as presets (yt-dlp 2026.10.26: `-t mp4` sorts formats by `vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac` and merges into MP4; `-t mp3` takes the best audio and converts it with ffmpeg), so we copy theirs instead of inventing our own. On YouTube this usually means at most 1080p.
- **Who decided:** the user, on Claude's suggestion (To do 3).
- **Rejected:** highest quality (often AV1 or VP9, up to 4K): Windows' own player may not open it. Choosing the quality is on the "Later" list.
- **Also chosen in To do 3, on Claude's suggestions:**
  - file name: the video's title, cut to 150 bytes. Rejected: yt-dlp's default `Title [id]`, which never clashes but looks cluttered; the cost is that two videos with the same title share a name, so the second counts as "already there"
  - a file already there is skipped, with a message
  - a playlist or channel link downloads one video and says playlists aren't supported yet (without a setting, yt-dlp downloads all of it)
  - one download at a time, no Cancel button; closing the window stops it
  - the window opens 600 px wide at normal size, scaled with the display's DPI; that is also its smallest size
  - download folder fixed to Downloads\Videos; no "Open folder" button

## 2026-11-11: GUI test with Tk's own key and click events in the same process; Pillow for screenshots
- **Reason:** Tk's events run the same bindings as real key presses and clicks, need no extra package and leave the user's mouse and other windows alone. The whole test takes about 3 s. Pillow's `ImageGrab` is the standard way to take a screenshot (one line), and it is only a development package. Details and measurements: docs/research/gui-testing.md.
- **Who decided:** the user, on Claude's suggestion (To do 2).
- **Rejected:**
  - OS-level input (pywinauto, pyautogui, `SendInput`): it moves the real cursor and types into whichever window is in front, and breaks if the user touches the mouse.
  - About 50 lines of our own screenshot code instead of Pillow: more code to keep working for the same result.
- **Also chosen in To do 2, Claude's defaults that the user didn't discuss:**
  - GUI test files in tests/gui with names that don't start with `test_`, so a plain `pytest` skips them (they open a window on top)
  - while the test runs, real key presses and clicks in its window are ignored, added after flaky runs

## 2026-11-10: Deno for YouTube, and yt-dlp's own ffmpeg build, both from winget
- **Reason:** Deno is yt-dlp's default JavaScript runtime, so it works with no settings. `yt-dlp.FFmpeg` is yt-dlp's own ffmpeg build. The yt-dlp README recommends it for its patches against ffmpeg bugs that affect yt-dlp (general knowledge, not re-checked). Both install for this user only, with no admin prompt.
- **Who decided:** the user, on Claude's suggestion (To do 1).
- **Rejected:**
  - Node, which is already installed: it would work, but yt-dlp needs a setting to turn it on.
  - `Gyan.FFmpeg`: the usual general-purpose build, without yt-dlp's patches.
- **Also chosen in To do 1, Claude's defaults that the user didn't discuss:**
  - plain `pip` with a `.venv` and an editable install (`pip install -e ".[dev]"`), not uv
  - the hatchling build backend
  - yt-dlp with only a minimum version (2025.11.12, the first to need a JS runtime), so `pip install -U` keeps it current
  - pyright in "standard" mode
  - ruff with rules E, F, W, I, UP, B, SIM

## 2026-11-10: Commits may show the user's own GitHub account
- **Reason:** the user is fine with their name being attached to this project. The commit name matches the GitHub login, and GitHub links commits to an account by email, so the account shows on every commit if the repo goes public.
- **Who decided:** the user, after Claude pointed this out.
- **Rejected:** a separate name and an email not linked to the account: not needed for this project.
- **Still applies:** no GitHub login or personal paths written into tracked files (CLAUDE.md "Never in tracked files"); this entry covers only commit authorship.

## 2026-11-10: Python 3.13 with tkinter for the window
- **Reason:** Python 3.13 is already installed, yt-dlp is a Python library, and tkinter comes with Python, so there is nothing extra to install. It looks plain; a nicer look can come later if wanted.
- **Who decided:** the user, on Claude's suggestion.
- **Rejected:** no other toolkit was discussed in detail. A nicer-looking one (for example customtkinter) can be weighed later.

## 2026-11-10: Build our own small app on top of yt-dlp: a desktop window first, an Edge button later
- **Reason:** yt-dlp already handles thousands of sites and the hard parts (separate video and audio streams, YouTube's frequent changes). Our app only adds a simple window, and later a button in the browser. A window is the quickest first working version and the easiest to test.
- **Who decided:** the user, on Claude's suggestion.
- **Rejected:**
  - Use a ready-made yt-dlp app (Stacher, Parabolic, Media Downloader) and build nothing: no work at all, but the user wants their own tool.
  - Browser extension first: an extension alone can't join separate video and audio streams (that needs ffmpeg on the PC), and connecting it to a program on the PC (native messaging: a registry entry and the extension's ID) is fiddly for a first version. Kept on the "Later" list.
  - Writing our own site downloaders: yt-dlp's maintainers already keep up with site changes; we would fall behind.

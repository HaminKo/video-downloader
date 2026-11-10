# Decisions

Each entry: `## YYYY-MM-DD: the decision` as the heading, then the reason, who decided, and what was rejected and why. Newest first.

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

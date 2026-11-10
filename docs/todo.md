# To do

## Where we are
- Now: To do 1 (Skeleton)
- Next: To do 2, 3
- Updated: 2026-11-10

Next number: 4

## To do

### 1. Skeleton (small to medium): "get the project set up so everything runs"
- **Goal:** the environment, the dependency file and all checks running, plus a window that opens. No downloading yet.
- **Read first:** CLAUDE.md, docs/decisions.md, docs/research/prior-art.md.
- **Approach:** `pyproject.toml` with `yt-dlp[default]` (should include yt-dlp-ejs for YouTube; confirm) and dev extras pytest, ruff and pyright, with their settings in the same file. A `.venv` in the project folder. Install ffmpeg and Deno with winget, record their paths in docs/local.md, and check that yt-dlp finds both (its verbose output lists them). Package in `src/video_downloader/`; `python -m video_downloader` opens a tkinter window with a link box and a Download button that doesn't do anything yet. One placeholder test so pytest runs. Then fill in the measured check times in CLAUDE.md, the install and run steps in README.md, and copy-ready commands in docs/local.md.
- **Ask the user:** Deno, or the Node that's already installed, for YouTube? Suggested: Deno (yt-dlp's default, no extra settings).
- **Test:** Claude: all checks pass, the window starts without errors, and yt-dlp reports ffmpeg and Deno as found. User: runs the app with the command from docs/local.md and sees the window.

### 2. GUI test and screenshots (small): "Claude can see and check the window"
- **Goal:** a test that starts the real window, types into it, clicks, checks what it shows, and saves screenshots Claude can read, so later steps can check the window without the user.
- **Read first:** the gui-test skill ("Setting it up"), the window code from To do 1.
- **Approach:** as the gui-test skill describes; add the commands to CLAUDE.md "Build specifics" and docs/local.md.
- **Ask the user:** none expected.
- **Test:** Claude runs the test and reads the screenshots. User runs the command from docs/local.md once.

### 3. Download from a link (medium): "paste a link, get the video"
- **Goal:** paste a link (for example a YouTube video, or any page yt-dlp supports), pick MP4 (video) or MP3 (audio only), press Download. The file lands in the download folder (default: Videos inside the user's Downloads folder), with progress shown and a clear message when it fails (unsupported site, no internet, private video).
- **Read first:** yt-dlp README "Embedding yt-dlp" (options, `progress_hooks`, MP3 post-processing); docs/research/prior-art.md.
- **Approach:** yt-dlp as a library, running in a background thread so the window keeps responding; progress goes to the window through a queue that the window checks with `after()`. MP4: best video and audio, merged into an MP4. MP3: best audio, converted with ffmpeg.
- **Ask the user:** (a) MP4 that plays everywhere (H.264) or the highest quality (often AV1/VP9, which Windows' own player may not open)? Suggested: plays everywhere. (b) File name? Suggested: the video's title. (c) File already there? Suggested: skip it and say so.
- **Test:** Claude: tests for the download options and error messages that don't touch the internet, plus the GUI test. User: downloads a short video as MP4 and as MP3 and plays both, then tries a broken link and sees a clear message.

## Later, only if the user asks
- Edge button: send the page you're on to the app (browser extension plus native messaging; see docs/research/prior-art.md).
- Playlists and whole channels.
- Subtitles.
- Signing in (browser cookies) for private or members-only videos.
- A queue or history of downloads.
- Choosing the quality, or formats other than MP4 and MP3.
- An .exe installer.
- Never (not "later"): DRM-protected services such as Netflix, Disney+ or Spotify.

## Writing a to-do
Each to-do starts as an entry in the list above. When one grows past ~10 lines, offer to move it into its own file, docs/todo/NN-name.md.
- **Title** with size (small / medium / large) and the goal in the user's words.
- **Problem / Goal:** what is wrong or wanted, with an example. For a bug or research to-do, also what the user has seen (it exists, where, what works) and what is already ruled out.
- **Read first:** files and functions to look at, outside references.
- **Approach:** the suggested design, what to reuse.
- **Ask the user:** open questions, each with a suggested answer.
- **Test:** what Claude checks, and what the user tests by hand.

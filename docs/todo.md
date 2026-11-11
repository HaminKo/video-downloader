# To do

## Where we are
- Now: To do 3, step B (clear messages when it fails)
- Next: To do 4
- Updated: 2026-11-11

Next number: 5

## To do

### 3. Download from a link (medium): "paste a link, get the video"
In its own file, with answers and a Progress list: [docs/todo/03-download.md](todo/03-download.md). Two steps: A downloading works (done), B clear messages when it fails.

### 4. Reddit downloads (small): "add something to make Reddit work later"
- **Problem:** Reddit links fail with "Account authentication is required", also for a post in a public subreddit (the one tested). Reddit blocks yt-dlp unless its requests look like a browser's. yt-dlp can do that ("impersonation"), but only with the `curl_cffi` package, which isn't installed. Example, from To do 3's test: https://www.reddit.com/r/Asmongold/comments/1xsyq9n/meanwhile_in_us_thatll_be_36367/ . It fails with the yt-dlp command alone, so it isn't our app. YouTube and X work.
- **Read first:** docs/research/yt-dlp-library.md "Sites" (what happens, step by step); pyproject.toml `dependencies`; README "Install and run" and "Credits".
- **Approach:** yt-dlp's `curl-cffi` extra (`yt-dlp[default,curl-cffi]`), which its README calls "recommended". Put it in pyproject.toml so a fresh install gets it; no code change expected (yt-dlp's Reddit code uses impersonation by itself once it's available). Add curl_cffi to the README Credits (MIT, by lexiforest) and a decisions.md entry. Claude Code's safety check refused installing it from a Claude session (getting around a bot check), so **the user runs the install command**; Claude prepares the rest.
- **Ask the user:** (a) curl_cffi, or signing in with browser cookies instead? Suggested: curl_cffi. It needs no account; signing in is on the "Later" list, and reading Edge's or Chrome's cookies on Windows often fails (general knowledge, not checked). (b) Part of the normal install (pyproject.toml), not a separate manual step? Suggested: yes.
- **Test:** Claude: `yt-dlp --list-impersonate-targets` shows Chrome as available; the usual checks still pass. User: downloads the example link as MP4 and as MP3 and plays both, plus one more Reddit video.

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

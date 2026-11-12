# To do

## Where we are
- Now: To do 5 (Signing in)
- Next: To do 6, 7, 8, 9, 10
- Updated: 2026-11-11

## To do
Next number: 12. Numbers are permanent: never renumber or reuse one; to move a to-do, move its line.

### Now
The one to-do being built.

#### 5. Signing in (medium): "Signing in (browser cookies) for private or members-only videos, and for Reddit"
- **Goal:** download videos that need an account: Reddit (it blocks anyone not signed in, To do 4), members-only or age-restricted YouTube videos, private videos shared with you. Example: To do 4's Reddit link, https://www.reddit.com/r/Asmongold/comments/1xsyq9n/meanwhile_in_us_thatll_be_36367/ .
- **Read first:** docs/research/yt-dlp-library.md "Sites" and "Errors" (the sign-in texts); docs/decisions.md (the Reddit entry, plain messages); `options()`, `PLAIN_MESSAGES`, `SIGN_IN` and `REDDIT` in downloader.py; yt-dlp's FAQ on cookies: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
- **Approach:** yt-dlp's own cookie settings, never a password in the app: `cookiesfrombrowser` (reads the browser's sign-ins) or `cookiefile` (a cookies.txt exported from the browser). Research first which works on this PC: yt-dlp often can't read Edge's or Chrome's cookies on Windows, Firefox's work better (general knowledge, not checked). Then the `SIGN_IN` and `REDDIT` messages change.
- **Ask the user:** (a) which browser are you signed in with? Suggested: Edge, if the research shows yt-dlp can read it; otherwise a cookies.txt file. (b) always use the sign-ins, or only when ticked? Suggested: a checkbox "Use my browser sign-ins", off by default. (c) yt-dlp's wiki is thought to warn that using an account with yt-dlp can get it limited or banned on YouTube (not checked): use it for Reddit only at first? Suggested: yes; the build session checks the warning first.
- **Test:** Claude: a test that the setting reaches yt-dlp's options (no internet); GUI test step for the checkbox. User: To do 4's Reddit link as MP4 and MP3; a YouTube video without the checkbox still works.

### Bugs me
At most 5, in order: the next ones to build. When Now is finished, the first one here moves up.

#### 6. Choosing quality and formats (medium): "Choosing the quality, or formats other than MP4 and MP3"
- **Goal:** pick a lower quality to save space (e.g. 720p) or the highest there is, or another format. Today MP4 is H.264 at the best quality yt-dlp's `-t mp4` preset picks (on YouTube usually at most 1080p) and MP3 is fixed.
- **Read first:** `Kind`, `PRESETS` and `options()` in downloader.py; the MP4/MP3 radio buttons in `App.__init__` (app.py); docs/decisions.md "MP4 that plays everywhere".
- **Approach:** a quality choice as a height limit added to the MP4 preset's format sort (e.g. `res:720`), keeping H.264 first so files still play everywhere. "Highest" may give AV1 or VP9, which Windows' own player may not open, so the window would say so. Other formats only as yt-dlp's own presets (e.g. `-t aac`, `-t mkv`), as more `Kind` values.
- **Ask the user:** (a) which quality choices? Suggested: today's (best that plays everywhere), 1080p, 720p, 480p; no "Highest" unless you want 4K. (b) other formats? Suggested: none until you name one you'd use. (c) remember the choice between runs? Suggested: no for now (it needs a settings file).
- **Test:** Claude: options tests per choice; GUI test step for the new control; screenshots. User: one YouTube video at 720p and at the default; both play, and the 720p file is smaller.

#### 7. Subtitles (small): "Subtitles"
- **Goal:** save a video's subtitles with it, so the player can show them. Example: a YouTube video with English subtitles.
- **Read first:** `options()` and `PRESETS` in downloader.py; yt-dlp's subtitle settings (`writesubtitles`, `writeautomaticsub`, `subtitleslangs`, the `FFmpegEmbedSubtitle` step).
- **Approach:** a checkbox "Subtitles" (MP4 only); yt-dlp downloads them and ffmpeg puts them inside the MP4, so it stays one file.
- **Ask the user:** (a) inside the MP4, or a separate .srt file next to it? Suggested: inside, if Windows' own player shows them (the build checks); otherwise .srt. (b) which languages? Suggested: English; YouTube's automatic subtitles only when there are no real ones.
- **Test:** Claude: options test; GUI test step for the checkbox. User: a YouTube video with subtitles plays with them in Windows' Media Player.

#### 8. Playlists and whole channels (medium): "Playlists and whole channels"
- **Goal:** a playlist or channel link downloads all its videos. Today it takes only the first and the window says so. Example: a short YouTube playlist (`youtube.com/playlist?list=...`).
- **Read first:** `options()` (`noplaylist`, `playlist_items`) and `download()` in downloader.py; `PLAYLIST_NOTE` and `done_message()` in app.py; docs/decisions.md To do 3 ("a playlist or channel link downloads one video"); docs/research/yt-dlp-library.md "A page with two videos is a playlist".
- **Approach:** no `playlist_items` limit for playlist links; the progress line says "Video 3 of 12"; one failed video doesn't stop the rest, and the end message counts what was saved, skipped and failed.
- **Ask the user:** (a) a subfolder per playlist? Suggested: yes, named after the playlist. (b) a channel can have thousands of videos: ask first above some number? Suggested: ask above 50. (c) a link to one video inside a playlist (`watch?v=...&list=...`): just that video, as now? Suggested: yes.
- **Test:** Claude: the local test server's two-video page downloads both; GUI test step for "Video 1 of 2". User: a short YouTube playlist.

#### 9. Queue and history (medium): "A queue or history of downloads"
- **Goal:** paste the next link while one is downloading (queue), and see what was downloaded before (history). Today: one download at a time; Download is off while busy.
- **Read first:** `App.start_download`, `set_busy` and `check_events` in app.py; docs/decisions.md To do 3 ("one download at a time, no Cancel button").
- **Approach:** a list under the link box; downloads still run one after another in one worker thread, as now. History: past downloads kept in a small file in the app's own data folder (built from `Path.home()`). Probably two steps: queue (A), history (B).
- **Ask the user:** (a) queue first, history as step B? Suggested: yes. (b) what does clicking a history entry do? Suggested: opens the folder with the file selected. (c) a way to remove a queued link? Suggested: yes, for links not yet started.
- **Test:** Claude: GUI test with the fake download (two links, both finish in order). User: queue two YouTube videos.

#### 10. Edge button (large): "Edge button: send the page you're on to the app"
- **Goal:** on a video page in Edge, one click sends the link to the app. Example: on a YouTube video, click the button; the app comes to the front with the link filled in.
- **Read first:** docs/research/prior-art.md "Browser extensions" (general knowledge, not checked: research it first); `start()` and `main()` in app.py.
- **Approach:** a small extension loaded unpacked in Edge, plus native messaging (a JSON manifest and a registry key under `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\`) that starts a small script; the script hands the link to the running app (which needs a way to receive it, e.g. a local socket) or starts it. Research first, then a step plan in docs/todo/10-edge-button.md.
- **Ask the user:** (a) start downloading right away, or only fill in the link? Suggested: fill it in and bring the window to the front, so you still choose MP4 or MP3. (b) after the queue (To do 9), so a link sent during a download isn't lost? Suggested: yes, that's why it comes after it.
- **Test:** Claude: tests for the link hand-over without a browser. User: load the extension, click it on a YouTube page.

### Someday
Everything else, unordered (grouped by area once it grows). A Someday to-do moves up only when it starts to bug the user.

#### 11. An .exe installer (large): "An .exe installer"
- **Goal:** install and start the app like any Windows program: a Start-menu entry, no terminal, no Python setup.
- **Read first:** README "Install and run"; pyproject.toml; docs/decisions.md (ffmpeg and Deno from winget; "updating yt-dlp automatically" in the Reddit entry).
- **Approach:** research first: a bundler (e.g. PyInstaller) packs Python, tkinter and yt-dlp into an .exe, and an installer (e.g. Inno Setup) adds the Start-menu entry. Inside an .exe, `pip install -U` no longer updates yt-dlp, so updates need their own answer here (the start-up update idea from To do 4 fits).
- **Ask the user:** (a) bundle ffmpeg and Deno, or keep them from winget? Suggested: keep winget (smaller; `winget upgrade` updates them). (b) one .exe or an installer? Suggested: an installer. (c) code signing? Suggested: no; Windows SmartScreen warns on the first run ("Run anyway").
- **Test:** Claude: the build runs and the .exe starts. User: install, start from the Start menu, download a YouTube video, uninstall.

## Later, only if the user asks
- Nothing here now (all moved into the list above on 2026-11-11).
- Never (not "later"): DRM-protected services such as Netflix, Disney+ or Spotify.

## Writing a to-do
- **Number:** the "Next number" (then raise that line by one). The entry goes under Someday, unless the user says it bugs them or wants it soon: then under Bugs me where the user says (at most 5 there, so ask which one drops back to Someday), and "Next:" and "Updated:" in "Where we are" change with it.
- **Title** with size (small / medium / large) and the goal in the user's words.
- **Problem / Goal:** what is wrong or wanted, with an example. For a bug or research to-do, also what the user has seen (it exists, where, what works) and what is already ruled out.
- **Read first:** files and functions to look at, outside references.
- **Approach:** the suggested design, what to reuse.
- **Ask the user:** open questions, each with a suggested answer.
- **Test:** what Claude checks, and what the user tests by hand.

Each to-do starts as an entry in the list. When one grows past ~10 lines or gets steps (a Progress list), it moves into its own file, docs/todo/NN-name.md (two-digit number, starting "# To do N: title"), and its entry points to the file. When it is finished, finish-step moves that file unchanged to docs/archive/.

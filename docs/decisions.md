# Decisions

Each entry: `## YYYY-MM-DD: the decision` as the heading, then the reason, who decided, and what was rejected and why. Newest first.

## 2026-11-12: A queue: links wait in a list of every download and run one after another; the selected row drives the status line, Play and Show in folder
- **Reason:** the user wanted to paste the next link while one downloads. Downloads still run one at a time in one worker thread; the next starts only after the window has received the previous one's last report, so reports never mix. With a queue, the status line can't hold "the" result any more: a failure's reason would be replaced at once by the next download's progress. So every download gets a row (Video: the link until yt-dlp has looked it up, then the title; As: the choices; State), and the bar and status line show the selected row's progress or full message. A download that starts gets selected, unless the user selected another row since the previous one started. Play and Show in folder work on the selected row, also during a download; a double click on a finished row plays it. The choices stay usable during a download, and each link keeps the ones it was added with (MP3 stores no quality or subtitles). The link box empties after each accepted link. Remove (and the Delete key) takes the selected row out of the list, never a file; not the running one. Cancel stops the running download only; the next waiting one then starts. Closing the window drops the waiting links. This replaces To do 3's "one download at a time" (still true, now with a queue) and To do 12's "Play and Show in folder greyed out during a download".
- **Who decided:** the user, on Claude's suggestions (To do 9, step A).
- **Rejected:**
  - a list of only the waiting links, the status line keeping the running one: a failure in the middle of a queue would show its reason only for a moment
  - the status line always showing the running download, failure reasons only in the row: Tk's list rows can't wrap, so long messages would be cut off
  - Cancel removing a selected waiting link too: Cancel sits next to Download, far from the list; Remove next to Play is clearer
  - double click opening the folder (the to-do's first suggestion): one click has to select a row, and Show in folder is one more click
  - keeping the link in the box after a download: the next paste would have to replace it; the cost is pasting a failed link again to retry
  - grouping `download()`'s arguments into one object (left for this to-do by To do 7): the window keeps each link's choices in its row's record, so it isn't needed
- **Also chosen, Claude's defaults that the user didn't discuss:** rows a quarter taller than a line of text (Tk's own row height cut off underscores at 150% scaling); As and State columns as wide as their longest text, Video takes the rest; Cancel selects the cancelled row so "Cancelling..." shows; after Remove, the running row is selected (nothing when none runs).

## 2026-11-12: An MP3 download keeps a file that was there before: yt-dlp keeps the file it converts from, the app deletes it only when it is new
- **Reason:** on a site with no separate audio, yt-dlp took an MP4 of the same video that was already in the folder as the MP3's download, converted it and deleted it (measured; docs/research/yt-dlp-library.md "Files yt-dlp deletes"). With `keepvideo: True` (MP3 only) yt-dlp deletes nothing; the app notes the file the ExtractAudio step converts from (its hook's `info_dict["filepath"]`) and, after a finished download, deletes it unless it is the MP3 itself or was in the folder when the download started. That deletes exactly what yt-dlp deleted before, minus files that were there. When the MP4 is there, the MP3 is still made from it, without downloading again (the user's choice; faster, and on such sites it is the same file the download would get).
- **Who decided:** the user, on Claude's suggestions (To do 14).
- **Rejected:**
  - another file name for MP3's download, then a rename: yt-dlp's "already there" looks for the final name next to the download's, so it would need its own rename and check
  - yt-dlp's temp folder (`paths: {"temp": ...}`): doesn't help, since yt-dlp also finds the MP4 in the main folder and converts that one
  - a format without the `/b` fallback: MP3 would fail on every site with no separate audio
  - after an MP3, deleting every new `Title.*` file except the MP3 (Cancel's clean-up): works, but deletes more than yt-dlp would
  - `keepvideo` for MP4 too: it would keep the separate video and audio files after joining. An MP4 download only deletes files yt-dlp itself made, unless a `Title.webm` the user put in the folder is taken as the download (no case seen)

## 2026-11-12: A Cancel button next to Download; a cancelled download deletes only the new files named after its video
- **Reason:** a download started with the wrong choice (Best instead of 720p) could only be stopped by closing the window, which also lost the choices. yt-dlp has no stop call; its own way is raising `DownloadCancelled` from a hook, so both hooks (progress, and the steps after the download) raise it once the window's flag (a `threading.Event`) is set: within a second while downloading. An ffmpeg step (joining, converting to MP3) can't be stopped in the middle, so Cancel takes effect when it ends. Clean-up deletes a file only when both are true: it wasn't in the folder when the download started, and its name starts with the video's file name and a dot (`Title.`), which every file of a download does (`.part`, `-Frag`, `.ytdl`, `Title.f137.mp4`, `Title.en.srt`). Each condition alone is unsafe: "new" alone would delete a file that lands in the folder meanwhile; "named like it" alone would delete an earlier copy. yt-dlp leaves an HLS `.part` open after the error, so the clean-up runs `gc.collect()` first (measured; docs/research/yt-dlp-library.md "Cancelling"). The window says "Cancelling..." at once, then "Cancelled." in the normal color; choices stay, Play is greyed out as after a failure. This replaces To do 3's "no Cancel button", which was left out then only to keep the first version small.
- **Who decided:** the user, on Claude's suggestions (To do 13).
- **Rejected:**
  - Download turning into Cancel during a download: saves space, but a double-click would cancel right away
  - Escape cancelling too: a key that cancels by accident is worse than a click
  - keeping the half-downloaded files, as closing the window does: Cancel means "I don't want this", and they would pile up unseen
  - deleting every new file in the folder: would also delete a file saved there by something else meanwhile
  - stopping ffmpeg in the middle of a step: yt-dlp waits for it without a way in; it would need finding and killing the child process (Windows process tools or a new dependency). A Someday to-do if the wait bugs the user
  - running yt-dlp in a separate process that Cancel kills: stops at once in every phase, but a much bigger change (events between processes, killing ffmpeg too)
  - a temp folder per download (yt-dlp's `paths: {"temp": ...}`), so Cancel deletes that folder instead of matching names (suggested by the code review): safer by construction, but it changes where every download writes, needs a clean-up of folders orphaned by closing the window (more deleting code), loses resuming after a close, and may copy big files across drives. Worth another look in To do 8, which has to change the clean-up anyway
  - a Done that arrives after Cancel was clicked turned into Cancelled: the download had already finished, and the file is there; the window shows Done
  - closing the window cleaning up too: it would have to wait for the download thread before closing; the leftover `.part` lets yt-dlp continue the same video later
- **For playlists (To do 8):** Cancel stops the rest and keeps the videos already finished.

## 2026-11-12: Play and Show in folder buttons under the status line; nothing opens by itself
- **Reason:** after a download, one click plays the file or shows it in Explorer, instead of finding it in Downloads\Videos by hand. Play opens it in its default app (`os.startfile`; VLC also loads the `.en.srt` next to it). Show in folder runs `explorer /select,"PATH"` as one string with the path in quotes, because Explorer splits an unquoted path at its commas (measured; docs/research/opening-files.md). Play is greyed out until a download has finished, again after a failed one, and during a download. Show in folder is greyed out only during a download; with no finished file (none yet, a failure, or the file moved or deleted) it opens Downloads\Videos, making the folder if it isn't there. Play on a moved or deleted file says so in red. This replaces To do 3's "no Open folder button", which was left out then only to keep the first version small.
- **Changed 2026-11-12 (To do 9):** both buttons now work on the selected row of the list, also during a download (see the queue entry above).
- **Who decided:** the user, on Claude's suggestions (To do 12).
- **Rejected:**
  - opening the file by itself after each download: a player popping up unasked gets annoying, worse with playlists (To do 8)
  - Play still playing the earlier file after a failed download: it would play something other than what the status line is about
  - both buttons usable during a download: harmless, but Play would play the previous video while the status line shows the new one; greyed out like the other controls
  - the Explorer command as a list for `subprocess`: Python quotes a part only when it holds a space, so `a,b.mp4` broke (measured)
  - working around Explorer selecting nothing the first time it shows a folder: it happens once, when Downloads\Videos is new

## 2026-11-12: English subtitles as a separate `Title.en.srt` next to the MP4, from a checkbox
- **Reason:** Windows' own playback API finds no subtitles inside an MP4 (`mov_text`), while it does find SRT inside an MKV (measured; docs/research/subtitles.md). A separate .srt works in nearly every player; in VLC, the user's player, `Title.en.srt` showed by itself (user's test), so it keeps yt-dlp's name. English only (`subtitleslangs: ["en"]`): real subtitles when the video has them, otherwise automatic ones (on YouTube, possibly its automatic translation). Measured: each of 9 YouTube videos got exactly one English track. YouTube's own srt (`subtitlesformat: "srt/best"`), because its automatic captions as vtt show every line twice; other sites' vtt is converted to srt by ffmpeg. A video without English subtitles still downloads, and the window says "No English subtitles found."
- **Who decided:** the user, on Claude's suggestions (To do 7).
- **Rejected:**
  - subtitles inside the MP4 (yt-dlp's `--embed-subs`, the to-do's first idea): Windows doesn't see them; it also rewrites the whole video once more, and for a video that's already there, it would rewrite the user's file
  - both inside and a separate file: VLC would list two English tracks
  - an MKV when subtitles are ticked: Windows reads SRT inside an MKV, but the file would no longer be an MP4, and MKV plays on fewer phones and TVs
  - yt-dlp's default language choice (no `subtitleslangs`): without English it takes any language, live chat replays included
  - `en.*`: takes several tracks (en, en-US, en-GB...)
  - yt-dlp's own text for a failed subtitle download (which fails the whole download), the first plan: the review found that a missing subtitle file (HTTP 404) matched "This video isn't available", which is wrong. It now has its own plain message (measured offline)
  - downloading the video anyway when its subtitles fail (the review's idea): more code for a failure not seen on YouTube yet; a Someday to-do if it happens
  - remembering the choice between runs: needs a settings file, as for the quality
  - grouping the download choices into one object, now that `download()` takes 6 arguments: left for To do 9 (Queue), which has to store the choices per download (To do 9 didn't need it: each row keeps its choices)

## 2026-11-11: Video quality: Best, 720p or 480p, as a height limit right after H.264 in the mp4 preset's sort
- **Reason:** a lower quality saves space (on a long YouTube video, measured: 2677 MB at Best, 1513 MB at 720p, 562 MB at 480p). The limit (`res:720`) goes right after `vcodec:h264`, so files still play everywhere, and before `quality`, which YouTube fills from its own labels: after it, the limit does nothing (measured; docs/research/yt-dlp-library.md "Quality"). The choice is a row of radio buttons under MP4/MP3, greyed out while MP3 is chosen.
- **File names:** a 720p or 480p file gets the choice after its title (`Title (720p).mp4`); Best keeps `Title.mp4`. Found in the review: with the title alone, downloading a video again at 720p to save space said "already there" and kept the big file.
- **Who decided:** the user, on Claude's suggestions (To do 6).
- **Rejected:**
  - file names with the title only: see above; deleting the first file by hand would be needed
  - the real height in every MP4's name (`Title (1080p).mp4`; the user asked about it after the build): Best's names would change, so files already downloaded wouldn't count as there, and a portrait video would show its long side (a vertical Reddit clip at 720p would be named `(1280p)`). No suffix means full quality, a common convention
  - `Title (Best).mp4`: looks consistent but says nothing about the real quality
  - a 1080p choice: it gave the same file as Best on both videos measured, a 4K one included, because YouTube's H.264 stops at 1080p
  - "Highest" (VP9 or AV1, up to 4K): Windows' own player may not open it
  - the limit first, as yt-dlp's `-t mp4 -S res:720` does: on a site that has the height only in VP9 or AV1 it gives a file that may not play; the same file on YouTube
  - other formats (`-t aac`, `-t mkv`): none wanted yet
  - remembering the choice between runs: it needs a settings file; it starts at Best
  - a dropdown instead of radio buttons: more compact, but three choices fit in a row, and radio buttons show them all at once and are easier to click in the GUI test

## 2026-11-11: Signing in with a cookies.txt file in the app's own folder, Reddit only; no checkbox
- **Decision:** the app uses `%APPDATA%\video-downloader\cookies.txt` (yt-dlp's `cookiefile`) whenever the file is there. The user exports it with the "Get cookies.txt LOCALLY" extension, using "Export" on a Reddit page, so it holds Reddit's cookies only. Never a password in the app.
- **Reason:** yt-dlp can't read Edge's or Chrome's cookies on this PC (app-bound encryption, and the file is locked while the browser runs; docs/research/signing-in.md). A file exported from the browser the user already signs in with works whether the browser is open or not, and holds only the sites exported. Cookies go only to their own site, so a Reddit-only file changes nothing for YouTube; that makes a checkbox unnecessary.
- **Who decided:** the user, on Claude's suggestions (To do 5), including the window's three sign-in messages.
- **Rejected:**
  - reading Edge's or Chrome's sign-ins directly (`cookiesfrombrowser`): fails here, see above
  - signing in to Reddit in Firefox and reading Firefox's cookies: no extension or file, but a second browser, and any later Google sign-in there would put the account on every YouTube download
  - a checkbox "Use my browser sign-ins", off by default: the app saves no settings, so it would need ticking for every Reddit download, and it protects nothing a Reddit-only file doesn't
  - YouTube sign-ins: yt-dlp's wiki warns an account used with yt-dlp may be banned; members-only and age-restricted YouTube videos stay unsupported for now
  - keeping the file in the project or in Downloads: it's a sign-in key in plain text
- **The app only reads the file** (changed after the code review, Claude's suggestion; the user's plan answer had accepted yt-dlp's write-back): yt-dlp gets a copy in memory, so it can't write the file back. yt-dlp's own behaviour, writing every cookie back after each download, would have filled the file with YouTube's and other sites' cookies (so every YouTube download would share one visitor identity) and could empty it if two downloads saved at once. The cost: sign-in cookies Reddit refreshes aren't kept; if that makes the sign-in run out quickly, write-back for Reddit's cookies only is the fix.
- **Also chosen:** a broken file (JSON, not a cookies file) gets its own message, since it fails every download. The tests point the app at a temporary file, so they never use the real one.

## 2026-11-11: Reddit stays unsupported until the app can sign in; curl_cffi tried and taken out again
- **Since To do 5 (same day):** Reddit works with a sign-in file (the entry above); the user's test downloaded this entry's example link.
- **Reason:** Reddit refuses a post's data (the `.json` link yt-dlp's Reddit code reads) to anyone not signed in on this network, a real browser included: an InPrivate Edge window showed Reddit's "blocked by network security" page. yt-dlp's `curl-cffi` extra (browser impersonation, which yt-dlp's README calls "recommended") was installed and made yt-dlp's first requests get through, also with `--impersonate chrome` for every request, but the post's data stayed blocked. Kept, it would have added a compiled package (2.1 MB download), a test on a private yt-dlp function and a longer update command for no gain seen. Details, step by step: docs/research/yt-dlp-library.md "Sites".
- **Who decided:** the user, on Claude's suggestions (To do 4), including the window's Reddit message: "Reddit only allows downloads when you're signed in, and the app can't sign in yet."
- **Rejected:**
  - keeping curl_cffi anyway: it might help some other site that checks how requests look, but none has come up
  - signing in now (browser cookies): on the "Later" list. When it's wanted: yt-dlp often can't read Chrome's or Edge's cookies on Windows, Firefox's work better (general knowledge then; checked in To do 5: right for Edge and Chrome on this PC, docs/research/signing-in.md)
  - reading the post's normal web page instead of its `.json`: that would be our own Reddit downloader, which the project rules out
  - updating yt-dlp automatically when a download fails (asked during To do 4): the new version only loads after a restart, and most failures (private video, no internet) aren't fixed by an update. An update at start-up, about once a week, is the better shape if it's ever wanted; not a to-do yet.
- **Install:** the user installed and removed curl_cffi; Claude Code's safety check refused installing it from a Claude session (as getting around a bot check).

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
  - one download at a time, no Cancel button; closing the window stops it (Cancel button added 2026-11-12: To do 13; a queue of links added 2026-11-12: To do 9)
  - the window opens 600 px wide at normal size, scaled with the display's DPI; that is also its smallest size
  - download folder fixed to Downloads\Videos; no "Open folder" button (replaced 2026-11-12: To do 12 added Play and Show in folder)

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

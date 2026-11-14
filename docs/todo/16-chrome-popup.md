# To do 16: Download from Chrome without the window (medium): "lets expand our chrome extension so that rather than opening up our standalone app it can function enteriely from within chrome"

- **Goal:** pick MP4 or MP3 (and the quality and subtitles) in Chrome and start the download from there, without switching to the app's window. The app does the work in the background, as now. Example: on a YouTube video, click the button, pick "Audio only (MP3)", click Download; the popup says it was added and closes; the MP3 lands in Downloads\Videos while the window stays behind (or minimized, if it wasn't open).
- **Today:** a click sends the link to the window, which comes to the front with the link in its box; MP4 or MP3 is chosen and Download clicked there (To do 10).

## Decided when the to-do was written (2026-11-14)
The user went with Claude's suggestion: the choices move to Chrome, the downloading stays in the app. When this is built, the build session writes it into docs/decisions.md.

Rejected:
- **Everything in Chrome** (a popup or side panel with progress, the queue, Cancel, history, Play, Show in folder): a second screen in HTML/JS doing what app.py does (818 lines, counted) and a new test setup for it, as the GUI test drives only tkinter; two screens to keep in step, or the tkinter window and its tests dropped. A download run by the helper Chrome starts would likely stop when Chrome closes (estimate from how native messaging works, not tested), so it would need a background process of its own. A popup closes at any click outside it, so progress would have to be kept elsewhere and loaded again each time. Progress in Chrome can be a later to-do on top of this one, if it's missed.
- **Only Chrome, no Python:** an extension can't run programs, so yt-dlp, ffmpeg and Deno can't run in it; it would mean our own site downloaders in JavaScript, which docs/decisions.md rules out.

This changes, when built: "a link only fills in the box" and To do 10's rejected "starting the download at once" (the choices now come with the link); "the button shows only failures" (the popup says when it worked); the pipe's "plain text" if messages become JSON. It keeps: host.py imports only `handoff`; only web pages are sent; never pickle.

## Read first
- docs/archive/10-chrome-button.md; docs/research/browser-button.md (native messaging, the pipe, "Building the button"); docs/decisions.md, the 2026-11-13 and 2026-11-14 Chrome entries.
- extension/manifest.json and extension/background.js.
- host.py: `web_link()`, `answer()`, `start_window()`.
- handoff.py: `send()`, `read_link()`, `Listening.serve()`.
- app.py: `start_download()` (how a Job is built), `QUALITIES`, `check_links()` and `receive_link()`, `start()`, `main()`.
- Chrome's docs (web): `chrome.action` (`default_popup`), `chrome.storage`, native messaging from an extension page.

## Approach (suggested; the build session checks it)
- **Popup:** `action.default_popup` with popup.html and popup.js, plain HTML and CSS: the window's choices (MP4 / MP3, Best / 720p / 480p, English subtitles, greyed out for MP3) and a Download button. The last choices are kept in `chrome.storage.local` (the `storage` permission). With a popup set, `action.onClicked` no longer fires, so background.js likely goes; popup.js calls `sendNativeMessage` itself. The fixed `key` keeps the extension's ID, so `browser install` needs no change; the user reloads the extension.
- **Message:** `{"link": ..., "start": {"kind": "mp4", "quality": "720p", "subtitles": false}}`; without `start` it is the old "fill in the box". host.py checks the choices against fixed values and forwards them; it still imports only `handoff`, so the choice names could live there, shared with app.py.
- **Pipe:** a message with choices has to carry more than a link: JSON for both kinds (one format, still `send_bytes`; `json.loads` runs no code), or plain text kept for a link alone. Suggested: JSON for both.
- **Window open:** a method next to `receive_link()` adds a row with those choices, sharing the Job-building part of `start_download()`. It doesn't touch the box, the window's choices or the front. Careful: `check_links()` keeps only the newest link (the box holds one); downloads must each be kept, in order.
- **Window closed:** `start_window()` passes the choices on the command line (e.g. `python -m video_downloader LINK --start mp3`, names to pick), and `main()` starts the window minimized with that download running.

## Ask the user
- (a) Popup contents: the window's choices and Download, the last choices remembered? Suggested: yes.
- (b) Keep today's behaviour as a small "Open in the window instead" link in the popup, for when you want to look first? Suggested: yes (it's the existing path).
- (c) App closed: start it minimized on the taskbar, or open normally? Suggested: minimized.
- (d) App open: the new row joins the list, the window stays where it is and keeps its box and choices? Suggested: yes.
- (e) Chrome's feedback: "Added to Video Downloader." in the popup, which closes after about 1.5 s; a failure stays in the popup with its reason, so the "!" on the button goes? Suggested: yes.
- (f) When the download finishes: nothing in Chrome, as now (a Windows notification could be its own to-do)? Suggested: nothing.

## Test
- Claude: host.py tests for the new message (choices forwarded; an unknown kind or quality refused; a page that isn't a web page refused, as now); handoff tests for the new pipe message; app tests: a received download is queued with its own choices and leaves the box and choices alone, two arriving in one check both run, `main()` with the new options starts minimized; a GUI test step sending a download through the pipe (the fake download runs it). The popup's look: a screenshot of popup.html from headless Chrome if that works without new tools, otherwise the user's look.
- User: reload the extension; on a YouTube video, pick MP3 and Download with the window open behind Chrome, then again with the app closed; the popup remembers MP3 the next time; on a New Tab page, the popup shows the reason.

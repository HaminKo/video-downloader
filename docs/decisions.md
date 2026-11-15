# Decisions

Each entry: `## YYYY-MM-DD: the decision` as the heading, then the reason, who decided, and what was rejected and why. Newest first.

## 2026-11-14: The project goes public, after the app learns to update yt-dlp itself (To do 21)
- **Decision:** the repo goes public once To do 21 (yt-dlp updates itself) and the "Before a public release" list in docs/todo.md are done; the license is MIT. Setup.exe as a GitHub Release download is on that list, asked again then.
- **Reason:** the user wants the project public, like their other projects. Today only a new build updates yt-dlp, so a Setup.exe other people install would stop working for YouTube after its next change. The project's setup (2026-11-10) had no "Before a public release" list: its public-or-private answer wasn't written down, likely "private" (the Goal says "for one person").
- **Who decided:** the user, on Claude's suggestions (2026-11-14).
- **Rejected:**
  - public now, code only, with no Setup.exe download (Claude's first suggestion): the user wants the update first
  - staying private
- **Reverses:** "the app updating yt-dlp itself" in the rejected list of the 2026-11-14 ".exe files" entry below.

## 2026-11-14: Setup and the uninstaller ask to close the open window first (AppMutex)
- **Decision:** the window holds a mutex named `VideoDownloader.App` (the taskbar ID, `APP_ID`) until the process ends, taken by `main()` (`hold_mutex()`) just before the window is built, not by `start()`; setup.iss has `AppMutex={#TaskbarId}`, so Setup and the uninstaller show Inno's "is currently running" box (OK after closing the window, or Cancel) instead of going ahead. The project's window holds it too; test and screenshot windows don't. `CloseApplications=yes` stays. No `Global\` mutex. To do 20.
- **Reason:** uninstalling with the window open left 44 files behind (measured, To do 11), and installing over it could mix old and new files. `AppMutex` is Inno's standard way and needs one call in the app; one name for both keeps the test that checks setup.iss's names as it is.
- **Who decided:** the user, on Claude's suggestions (To do 20's questions a-d, 2026-11-14).
- **Rejected:**
  - a mutex name of its own: a second shared name to keep in step, for no gain (mutexes and taskbar IDs don't share a namespace)
  - only the installed window holding it: there is one window anyway, and a separate path would need its own code
  - taking it in `start()`, next to the taskbar ID (built first, changed after the review, by Claude): every test and screenshot window held it then, and its test couldn't fail once an earlier test had built a window
  - dropping `CloseApplications`: it still covers the Chrome helper and a window opened after Setup has started
  - a `Global\` mutex too: only needed for other users' sessions; the app installs for one user

## 2026-11-14: Setup.exe has one page, always the same folder, the build's date and time as version; build.py writes host.json and finds Inno Setup through its own registry entry
- **Decision:** `installer/setup.iss` installs into `%LOCALAPPDATA%\Programs\Video Downloader` with no folder or Start-menu-folder page and no Ready page (one page: the desktop-shortcut box and Install; then Finish with Launch ticked). Its version is the build's date and time. Before installing over an older install it deletes the old `_internal` and `extension` folders; a window still open is offered to be closed (Inno's `CloseApplications`). Uninstalling deletes Chrome's key also when it points at the project's helper. The names shared with the Python code (app name, .exe, taskbar ID, Chrome's key, host.json) are `#define` lines checked by a test, not passed in by build.py. build.py writes `host.json` (path `chrome-helper.exe`, relative) into the built folder with `browser.write_manifest()`; for that, `DATA_FOLDER` moved into places.py, so browser.py loads no yt-dlp. build.py finds `ISCC.exe` through Inno Setup's own uninstall entry, then PATH, and stops before building when it's missing. To do 11, step B.
- **Reason:** a one-person app needs no choices in Setup; a fixed folder also keeps those deletes inside the app's own folder. The date and time show in Settings > Apps which build is installed. On this PC Inno Setup sits in another project's folder, off PATH (docs/research/installer.md).
- **Who decided:** the user, on Claude's suggestions (step B's questions 1-6, 2026-11-14).
- **Rejected:**
  - build.py passing the names to ISCC (`/D`): the script couldn't be read or compiled on its own; the test keeps the two in step the way the extension is checked against the helper
  - deleting Chrome's key on uninstall only when it points at the installed app: about 10 lines of Pascal for a case one command fixes (`python -m video_downloader.browser install`)
  - a fixed path to `ISCC.exe`: it isn't in the standard folders on this PC
  - nothing against uninstalling with the window open, for now: it leaves part of the app's folder behind (measured; docs/research/installer.md). `AppMutex` would make the uninstaller ask to close the window first; To do 20 (Someday), built if it bites. Built the same day (entry above)

## 2026-11-14: The app as .exe files (PyInstaller, one folder) with an installer (Inno Setup), built on this PC
- **Decision:** PyInstaller builds one folder, `dist\Video Downloader\`, with two .exe files sharing Python and the libraries: `Video Downloader.exe` (the window, no console) and `chrome-helper.exe` (Chrome's helper, a console program because it talks through stdin and stdout; Chrome starts it hidden). The Chrome extension's folder sits next to them. An Inno Setup `Setup.exe` installs that folder for this user only (no admin prompt), with a Start-menu entry carrying the taskbar ID `VideoDownloader.App`, a desktop shortcut as an unticked checkbox, "Start Video Downloader" ticked at the end, and Chrome's helper key pointing at the installed helper; uninstalling removes the app and the key and keeps `%APPDATA%\video-downloader` (history, sign-in file). ffmpeg and Deno stay winget's; the installer doesn't touch them. yt-dlp is updated by running the build again (`installer/build.py` updates it in the `.venv` first) and installing over the old one. No code signing. Setup.exe stays in `dist\`, never published. The extension is loaded in Chrome from the installed folder. To do 11.
- **Reason:** the user wants to start the app like any Windows program, with no terminal. The built app is a copy that development in the project folder can't break, as a shortcut to the project's Python would. The one-folder build starts straight away, where a one-file .exe unpacks itself to a temp folder at every start (general knowledge, not measured). yt-dlp's own PyInstaller hook already bundles what YouTube needs (docs/research/installer.md).
- **Who decided:** the user, on Claude's suggestions (To do 11's questions a-g, 2026-11-14).
- **Rejected:**
  - a Start-menu shortcut to the project's `pythonw -m video_downloader`: far less work and `pip install -U` keeps working, but the daily app would run whatever code is in the project at the moment, half-finished steps included
  - one .exe without an installer: no Start-menu entry, no uninstall, the Chrome button set up by hand, a slower start
  - ffmpeg and Deno inside the app: bigger, and `winget upgrade` already updates them
  - the app updating yt-dlp itself at start-up: more code (downloading and loading a newer yt-dlp, falling back when it breaks) for what one build command does; a Someday to-do if YouTube breaks the app often (reversed 2026-11-14: To do 21, before going public; entry above)
  - code signing: costs money every year; a Setup.exe built on this PC has no download mark, so SmartScreen shouldn't warn (general knowledge, not tested)
- **Side effects:** after installing, the Chrome button starts the installed app (`python -m video_downloader.browser install` points it back at the project); the installed app and the project's share the pipe, so only one window runs at a time.

## 2026-11-14: A playlist above 50 videos asks first, in a Yes/No box, with the window brought to the front
- **Decision:** download() takes a `confirm(title, count)` callback, asked once per playlist (a channel's home link: per tab) on its first `match_filter` call with `n_entries`, so after yt-dlp's listing and before the first video; False raises `DownloadCancelled` there (Cancelled, nothing saved; tabs already finished are kept). The window answers yes up to `ASK_ABOVE` (50) videos; above, the download's thread hands the question to the window's thread (a queue and a Future, as the popup's Cancel does) and waits. `check_events()` asks it last, after updating the rows: `bring_to_front()`, then `messagebox.askyesno` on the window ("“Name” has 1,234 videos. Download all of them?", Yes is Enter's default). A download already cancelling gets No without a box. The tests pass a fake box (`App(..., ask=...)`). To do 8, step C.
- **Reason:** a channel can have thousands of videos (To do 8, question b). The window comes to the front because a download sent from Chrome runs in a minimized window or one behind the browser, where a box would go unseen (a box on a minimized window may not show at all: not measured) while the download waits.
- **Who decided:** the user, on Claude's suggestions (To do 8's plan, answer 2, and step C's questions 1-4, 2026-11-14).
- **Rejected:**
  - no box for a download sent from Chrome: that is where a big channel is most likely to come from
  - asking in the Chrome popup: it closes when the user clicks elsewhere, and listing a big channel can take tens of seconds (estimated)
  - No skipping only that tab of a channel's home link: more code for a link the guide already advises against (use `/videos`)
  - the limit in downloader.py: download() asks about every playlist and the window decides, so the downloader's tests use the two-video test page

## 2026-11-14: A playlist downloads all its videos into a folder of its own, as one row
- **Decision:** a playlist or channel link downloads every video (`playlist_items` dropped; `noplaylist` stays, so a `watch?v=...&list=...` link is just that video), into `Videos\<the playlist's title, cut to 80 bytes>\` (`%(playlist_title|.).80B/` in front of the file name; a single video stays in Videos). In the window it is one row: the playlist's title, "Video N of M: ..." in front of the progress (from yt-dlp's `match_filter`), the bar and the State column's percent for the current video. The end message counts saved, already there and failed videos (failed = the playlists' `n_entries` minus the finished videos) with the first failure's reason, in red only when none was saved. Play and Show in folder use the first finished video. Cancel also acts between videos, stops the rest and keeps the finished videos (`Cancelled.kept`): in the post hook a finished video's files join the "there before" set and `prefixes` is emptied. A channel's home link gets yt-dlp's default, a folder per tab. A finished playlist is kept in the history like any finished row; a cancelled one isn't. To do 8, step B.
- **Reason:** the user's To do 8 ("Playlists and whole channels").
- **Who decided:** the user, on Claude's suggestions (To do 8's plan of 2026-11-12, answers 1 and 3-9; step B's questions 1-3, 2026-11-14).
- **Rejected:**
  - counting the videos in the `match_filter` call before each lookup, or counting failures from the "ERROR:" lines: yt-dlp skips that call for entries it can't tell are single videos (Reddit, X, the generic extractor), so a failed lookup there wouldn't count (code review; docs/research/yt-dlp-library.md "Playlists and channels")
  - rewriting a channel's home link to `/videos`: YouTube-only code in the app
  - "Downloading 3 of 12" in the row's State column: one more field in `Progress` and `Job` for little gain
  - keeping a cancelled playlist with finished videos in the history: no cancelled row is kept
  - yt-dlp's `FFmpegConcat` (joins a "multi-part" video on a few sites into one file): no case seen
- **Left as is (code review, no case seen):** "Kept the N videos already finished" also counts videos that were already there; Play finding a playlist's first video gone drops the row from the history, though its other videos are still there; a playlist none of whose videos could be saved leaves its empty folder; a site that wraps a single video as a playlist of one puts it into a folder.

## 2026-11-14: A failed video doesn't end the download; yt-dlp's errors are read from a logger
- **Decision:** yt-dlp gets `ignoreerrors: "only_download"` (the command line's default) and a `logger` (`Log` in downloader.py) that prints warnings and errors to the terminal as before and keeps every line starting "ERROR:". A failed download shows the first one's plain message, the same text the `DownloadError` had; `CookieLoadError` (a broken sign-in file) is the one failure that still raises. Groundwork for playlists (To do 8, step A), no visible change.
- **Reason:** without `ignoreerrors`, one failed video ends a whole playlist (docs/research/yt-dlp-library.md "Playlists and channels").
- **Who decided:** the user, on Claude's suggestions (To do 8's plan, 2026-11-12; confirmed 2026-11-14).
- **Rejected:**
  - `ignoreerrors: True`: it also turns a subtitle download that fails into a warning, so the video would be saved without the subtitles that were asked for
  - yt-dlp's own failure count: it misses failed downloads (it counts only failed lookups)
- **Left as is (found by the code review, no case seen):** an error in the app's own hooks now shows as yt-dlp's logged text (for example `'filepath'`) instead of "Something went wrong: ..."; yt-dlp's "ffmpeg is not installed" for joining became a warning, which can only happen when `shutil.which` finds ffmpeg but yt-dlp doesn't, and then yt-dlp already picks a single file that needs no joining (`_default_format_spec`).

## 2026-11-14: A download deletes only in its folder or a folder directly inside it, compared by full path
- **Decision:** `delete()` (Cancel's clean-up and an MP3's source) first resolves the path (`..` and links) and deletes only when it lies in the download folder or in a folder directly inside it; anything else stays, with a line in the terminal. The "there before" list (`paths_in()`) covers the same two levels (a subfolder it can't list is left out), and files are compared by full path, no longer by name. download() normalizes the folder (`os.path.abspath`) as yt-dlp does its paths, so they compare equal. Groundwork for playlists (To do 8, step A), no visible change.
- **Reason:** a playlist's videos will go into a folder of their own, and yt-dlp would put those of a playlist named `..` into the folder above (docs/research/yt-dlp-library.md "Playlists and channels"). One check in `delete()` covers both kinds of deleting.
- **Who decided:** the user, on Claude's suggestions (To do 8, step A, answer 1, 2026-11-14).
- **Rejected:**
  - deleting anywhere under the download folder: the "there before" list would have to read every subfolder, however deep, before each download, and yt-dlp never writes deeper than one folder with the app's file names
  - a check that the path only starts with the folder's text: `Videos\..\x.mp4` starts with `Videos` but is in the folder above
  - also skipping folders outside before listing them (code review): safe either way, and with the one check in `delete()` the terminal says why a file was left

## 2026-11-14: One window at a time: a window takes the pipe before it is built, and a second one hands over and quits
- **Decision:** `main()` takes the pipe (`handoff.listen()`) before `tk.Tk()`. When another window has it (`PermissionError`), it hands that one its link (`send()`, with the choices if any) or, with no link, `{"show": true}` (`show()`: the open window comes to the front), and quits without showing anything. If handing over fails (the open window was closing), it takes the pipe once more; if that fails too (a stuck window), it opens a window that doesn't listen, and so does one whose pipe can't be made. `Listening` takes the pipe in `__init__` and reads only from `start()`, which `App` calls once its widgets are built; what is sent meanwhile waits in the pipe (measured, docs/research/browser-button.md). The window's first `check_links()` runs from the event loop, so a window's own link is the first row, before one handed over while it was being built. `App` and `start()` take the `listening` instead of a pipe name.
- **Reason:** two downloads sent with the app closed, within the second or two a window takes to start, opened two windows that downloaded side by side, and the one that saved last wrote history.json without the other's rows; a window opened while one was open didn't listen. Windows gives a pipe name to one listener only, so the first window to take it wins, also when two start at once; no lock file or timing needed.
- **Who decided:** the user, on Claude's suggestions (To do 17, answers a and b, 2026-11-14).
- **Rejected:**
  - a second window with no link opening as before: the user would get two windows from the Start menu
  - taking the pipe at the end of `App.__init__` as before: the second process would have built (and could show) a window before finding out
  - a window that couldn't hand over always opening without listening: the usual reason is a window just closing, whose pipe is free a moment later
  - `App` taking the pipe name and listening itself: the decision has to come before the window is built
- **Left as is:** a link handed over in the very moment the open window closes is lost (as before).

## 2026-11-14: Cancel from the Chrome popup; the window answers on the pipe
- **Decision:** the popup has "Cancel this page's download" (a link-style button on its own line under Download), always shown, greyed out with the others on pages that aren't web pages. It sends `{"link": ..., "cancel": true}` through the helper to the open window, which answers on the same connection: `{"answer": "cancelled"}` or `{"answer": "nothing to cancel"}`. The window stops every row of exactly that link that hasn't ended: the running one as its own Cancel does, waiting ones become Cancelled rows that are skipped. The selection and the window's place stay as they were. The pipe's thread hands the Cancel to Tk's thread (a `Future` through a queue, taken by `check_links()`) and waits up to 2 s; if Tk's thread hasn't taken it by then, it is withdrawn, so it never happens after the sender was told "no answer". The helper waits up to 5 s and never opens a window for a Cancel. The popup says "Cancelled." and closes after 1.5 s, or says in red: "Nothing to cancel: ...", "Video Downloader isn't open.", "Video Downloader didn't answer.". After a failure the focus goes back to the button that was used (Download, Open or Cancel), so Enter after a failed Cancel doesn't download.
- **Reason:** the user wanted to cancel without opening the window. Stopping only this tab's link can't stop the wrong video; an answer lets the popup say what happened instead of "sent". A plain "Cancel" next to Download would read as "close this popup".
- **Who decided:** the user, on Claude's suggestions (To do 19, answers a-h, 2026-11-14).
- **Rejected:**
  - cancelling whatever is downloading now: it could stop another video than the one on the page
  - showing Cancel only when the window has the page's video: a round trip to the window each time the popup opens
  - taking a waiting video off the list (as Remove does): the window then wouldn't show what happened
  - a separate message for a finished video ("downloaded already"): one "Nothing to cancel" covers not in the list, finished and failed
  - fire-and-forget Cancel (about 60 lines less, estimate): the popup couldn't say whether it worked
  - `{"cancel": LINK}` as the message: with `"link"` kept, the helper's web-page check and handoff's link check apply unchanged
- **Left as is:** with two windows open, only the one that listens gets the Cancel (since To do 17 there is only one window, except when the pipe can't be made or the open one is stuck). If Tk's thread takes the Cancel in the very moment the 2 s run out, the sender hears "no answer" though it cancelled.

## 2026-11-14: The window uses the Chrome button's icon, with a taskbar ID of its own
- **Decision:** `App.__init__` loads extension/icons' four PNGs (16, 32, 48, 128 px) and calls `root.iconphoto(True, ...)`, which sets the title bar, taskbar and Alt+Tab icon; `start()` calls `SetCurrentProcessExplicitAppUserModelID("VideoDownloader.App")` before the window opens. No .ico file yet.
- **Reason:** since To do 16 a download from Chrome opens the window minimized, so the taskbar button is all you see of it. Without the ID, the window joined the pinned Python button and showed Python's icon (measured on this PC); with it, the window gets a button of its own with the blue arrow. Reading the extension's PNGs keeps one copy of the icon. Tk passes Windows the 32 px image, scaled to 24 px in the title bar at 150%; it looks clean in the screenshot (docs/research/window-icon.md).
- **Who decided:** the user, on Claude's suggestions (To do 18, answers a-d).
- **Rejected:**
  - icons at exact sizes through Windows' `WM_SETICON` (about 25 lines of ctypes): the scaled one looks fine
  - an .ico file now: To do 11's installer makes one when it needs it
  - no taskbar ID: the taskbar keeps Python's icon
- **Drawback, left for To do 11:** pinning the window's taskbar button may not start the app (not tested); a Start-menu shortcut with the same ID would fix it.

## 2026-11-14: Downloads start from Chrome; the choices move to Chrome, the downloading stays in the app; pipe messages are JSON
- **Decision:** the Chrome button opens a popup with the window's choices (MP4 or MP3, the quality, English subtitles; its own last choices remembered) and Download; the link and the choices go to the open window, which adds a row without touching its box, its own choices or its place on the screen (with nothing downloading, the new row is selected, as with the window's own Download), or to a window that opens minimized with the download running (`python -m video_downloader LINK --download mp3 [--quality 720p] [--subtitles]`). A link alone still fills in the box ("Open in the window instead" in the popup, and `python -m video_downloader LINK`). Messages on the pipe, and from Chrome to its helper, are JSON: `{"link": ...}`, or with `"start": {"kind", "quality", "subtitles"}`; handoff.py checks them (all three choices, known values) and holds the choice names (`KINDS`, `QUALITIES`) that host.py and app.py share. Nothing shows in Chrome when a download ends (To do 16, answer f).
- **Reason:** the user wants to download from Chrome without switching to the window. The window already queues, shows progress and keeps the history; the popup only has to send the choices. A message with choices carries more than a link: JSON for both kinds keeps one format, and `json.loads` runs no code. The helper never imports yt-dlp, so the choice names live in handoff.py (which it imports) rather than in downloader.py.
- **Who decided:** the user (the goal and the design, on Claude's suggestions, when To do 16 was written; the answers a-i on Claude's suggestions, 2026-11-14). Details: docs/archive/16-chrome-popup.md.
- **Rejected:**
  - everything in Chrome (progress, the queue, Cancel, history in a popup or side panel): a second screen doing what app.py does, with a test setup of its own; a download run by the helper Chrome starts would likely stop with Chrome (estimate, not tested); a popup closes at any click outside it (To do 16 has the details)
  - only Chrome, no Python: an extension can't run yt-dlp, ffmpeg or Deno
  - plain text kept for a link alone and JSON only with choices: two formats to read
  - the window coming to the front for a download from Chrome, or opening normally when closed: the point is not to leave Chrome
- **Changes:** the 2026-11-13 entry's "the window only fills in the link" (now only for a link alone) and the pipe's plain text; To do 10's rejected "starting the download at once".
- **Also decided (step B, the user on Claude's suggestions, answers j-m):** the popup saves its choices at every change, not only on Download (picking MP3 and clicking away keeps MP3); a light look only, like the window (following Chrome's dark mode was one more look to check); "Sending..." with both buttons greyed out until the helper answers, so a double click adds the video once; Enter is Download; the popup gets a GUI test of its own in headless Chrome (rejected: only the test that its values match handoff's, which would leave a wrong message to the hand test).

## 2026-11-14: GUI test windows on another screen, without taking the keyboard
- **Decision:** drive.py opens the GUI test's and the screenshots' windows on the topmost screen other than the main one that has the main screen's scaling (on this PC the right-hand screen); with none, on the main screen as before. Picked automatically, no setting. A widget gets the focus with Windows' `SetFocus` (this program's own focus only) instead of `focus_force()`, and drive.py gives the front back if Windows put the first window in front. The GUI test's pipe step and the "received" screenshot record `bring_to_front()` instead of calling it.
- **Reason:** the test windows took the front and the keyboard while the GUI test ran (about 30 s), so typing in VS Code got lost, and Windows refused `focus_force()` now and then (the "didn't get the keyboard focus" errors). A screen with other scaling shrinks the window and blurs it, so screenshots wouldn't show what the user sees. Measurements: docs/research/gui-test-focus.md.
- **Who decided:** the user (the goal, To do 15), on Claude's suggestions. The user first asked for the topmost screen, then chose the right-hand one on hearing the topmost is at 100% scaling.
- **Rejected:**
  - the topmost screen whatever its scaling: it is at 100% on this PC, so the window shows at two thirds of its size, blurry, and screenshots come out 602 px wide instead of 903
  - the GUI test on the topmost screen and screenshots on the right-hand one: two rules, and blurry test windows
  - setting the topmost screen to 150% in Windows: it changes the user's screen for everything else
  - really bringing the window to the front in the pipe step: it takes the keyboard; the user checked it by hand in To do 10
  - a VM, Windows Sandbox, containers or another Windows desktop: docs/research/gui-test-focus.md, "Considered, not worth it"
- **Also decided (the user, on Claude's wording):** the GUI test runs only in steps that change app.py, handoff.py or tests/gui; it is the only test that types and clicks in the real window and sends it a link (handoff.py added after the review).
- **Changed 2026-11-14 (To do 16, step B, Claude):** tests/gui also holds the Chrome popup's test now, so "tests/gui" became the window's own test files (window_gui.py, drive.py); the popup's test runs in steps that change extension/ or its own test files.

## 2026-11-14: The Chrome button sends only web pages and shows only failures; its helper is a module of its own that never imports yt-dlp
- **Decision:** a click on a page that isn't a web page (New Tab, `chrome://`, a file from disk) sends nothing; the button shows a red "!" and its tooltip says why ("Only web pages can be sent.", "The helper isn't installed: ...", or Chrome's own message), until the next click that works. Nothing shows when it works: the app coming to the front is the sign. Icon: a white down arrow on a blue rounded square; name "Video Downloader". The helper Chrome starts is `host.py` (`python -m video_downloader.host`, through `host.bat`), apart from the setup in `browser.py`, and imports only `handoff`.
- **Reason:** a `chrome://` link in the box could only fail later. The helper starts once per click; importing `downloader` (yt-dlp) would add 0.18-0.37 s to each (measured 2026-11-14), while setup runs once and may import it for `DATA_FOLDER`.
- **Who decided:** the user, on Claude's suggestions (To do 10, step B); the module split by Claude in the plan the user agreed to.
- **Rejected:**
  - a sign in Chrome when it works (a short badge): the window coming to the front says it already
  - the helper inside browser.py, as first planned: every click would load yt-dlp
  - checking for web pages in the extension: the helper checks, so it's tested in Python with the rest
- **Changed 2026-11-14 (To do 16, step B):** the button opens a popup with the choices instead of sending at once, and the popup says it worked ("Added to Video Downloader.", then it closes) or why not (in red, it stays open); the red "!" and its tooltip are gone. The popup also checks for web pages itself, so it can say so as it opens (answer i); the helper still checks, and a test keeps the popup's words the helper's. The popup's own behaviour is tested in headless Chrome with Chrome's extension functions faked (tests/gui/popup_gui.py).

## 2026-11-13: The browser button is a Chrome extension (not Edge) that talks to the app through native messaging; the app gets the link through a named pipe
- **Reason:** the user mostly uses Chrome, not Edge. An unpacked (self-made) extension in Chrome no longer brings a warning (Chromium removed it in 2023), gives a toolbar button with no prompts, and only this extension can start the app. Clicking it sends the tab's link to a small helper that Chrome starts; the helper hands the link to the open window through a Windows named pipe, or opens a window with the link. The window only fills in the link and comes to the front, with "Link received: choose MP4 or MP3, then Download." in the status line; a link already in the box is replaced. A fixed `key` in the extension's manifest keeps its ID the same, so `python -m video_downloader.browser install` can write the helper's files (in `%APPDATA%\video-downloader`) and Chrome's registry key by itself; `uninstall` removes them. Research: docs/research/browser-button.md.
- **Who decided:** the user, on Claude's suggestions (To do 10).
- **Rejected:**
  - Edge (the to-do's first target): the user doesn't use it much, and Edge shows a developer-mode warning for an unpacked extension that can't be turned off. Edge reads Chrome's registry key too, so it would work if ever loaded there.
  - a bookmarks-bar button opening a link type of our own (`video-downloader:`), no extension: fewer parts and works in every browser, but Chrome asks once per site, and its bookmarks bar shows only on the New Tab page unless turned on
  - starting the download at once: MP4 or MP3 and the quality are still chosen in the window
  - a localhost port for the hand-over: any web page could send to it; a named pipe can't be reached from a web page
  - `multiprocessing.connection`'s `send`/`recv`: they unpickle, which runs whatever a sender packs in; `send_bytes`/`recv_bytes` carry plain text
  - publishing the extension to a store: an account and a review for a one-person tool

## 2026-11-13: A history: the list starts with past downloads that saved a file, kept in `%APPDATA%\video-downloader\history.json`
- **Reason:** the user wanted to see what was downloaded before. The list of downloads (To do 9, step A) already shows a finished download with its file, Play and Show in folder, so past downloads are rows in it too, above this session's, the same look; the list opens scrolled to the newest, nothing selected. Only rows with a saved file are kept (Done, Already there), the newest 200: failed and cancelled ones have nothing to open. Each save writes the whole list's saved rows anew (after each saved file, and after Remove of one), so Remove and the limit need no code of their own; the text goes into `history.json.new` first, which then replaces the file, so a save that stops halfway leaves the old one. The file sits next to `cookies.txt` (the app's own data folder; `cookies.txt` is still only read). Each entry holds the link, choices, title, state, the status line's message and the file's path.
- **Who decided:** the user, on Claude's suggestions (To do 9, step B).
- **Also chosen:** downloading the same video twice gives two rows, as a browser's download list does. A row whose file Play found moved or deleted is left out of the history at once (the history lists files the app can still find; Remove clears the rest). A broken file (not UTF-8, not JSON) is an empty history and is written anew at the next save; an entry that can't be read is left out. A file that is there but can't be opened at the start (locked by a virus scanner, no permission) is left alone for the whole session: writing it anew would lose its 200 downloads (found by the review). A save that fails (disk full, no permission, a title that isn't valid text) is skipped, the details in the terminal; it never stops the queue. With two windows open, the last one to save wins (since To do 17 there is only one window, except when the pipe can't be made or the open one is stuck). The window's list isn't cut to 200 during a session, only the file is.
- **Rejected:**
  - scrolling the list only once after loading the history, instead of once per row (review): measured 23 to 45 ms to build the window with 200 past rows either way, no difference
  - past rows in grey, or a date column: the order already shows what is older, and nothing asked for dates
  - keeping a row whose file is gone until the user removes it: about 15 more lines (the row would keep its file and its first message next to the "gone" message)
  - adding entries to the file instead of writing it anew: Remove and the 200 limit would need their own code
  - stricter checks of each entry's types (a `true` height, a `null` title shown as "None"): only a hand-edited file has them, since the app writes the types itself
  - a temporary file name of its own per window (two windows saving in the same millisecond could meet in `history.json.new`): no case seen, and "the last one wins" already holds for two windows
  - the history path as a fixed constant only: the screenshots run without pytest's conftest.py and would write fake downloads into the real history, so `App`, `start()` and the GUI test's `open_window()` take the file as a parameter

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
  - updating yt-dlp automatically when a download fails (asked during To do 4): the new version only loads after a restart, and most failures (private video, no internet) aren't fixed by an update. An update at start-up, about once a week, is the better shape if it's ever wanted; not a to-do yet (To do 21 since 2026-11-14).
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
  - a playlist or channel link downloads one video and says playlists aren't supported yet (without a setting, yt-dlp downloads all of it) (replaced 2026-11-14: To do 8 downloads all of it)
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

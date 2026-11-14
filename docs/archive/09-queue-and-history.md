# To do 9: Queue and history (medium): "A queue or history of downloads"

- **Goal:** paste the next link while one is downloading (queue), and see what was downloaded before (history). Today: one download at a time; Download is off while busy.
- **Read first:** `App.start_download`, `set_busy` and `check_events` in app.py; docs/decisions.md To do 3 ("one download at a time, no Cancel button").
- **Approach:** a list under the link box; downloads still run one after another in one worker thread, as now. History: past downloads kept in a small file in the app's own data folder (built from `Path.home()`). Probably two steps: queue (A), history (B).
- **Ask the user:** (a) queue first, history as step B? Suggested: yes. (b) what does clicking a history entry do? Suggested: opens the folder with the file selected. (c) a way to remove a queued link? Suggested: yes, for links not yet started.
- **Test:** Claude: GUI test with the fake download (two links, both finish in order). User: queue two YouTube videos.

## Answers (2026-11-12)
The user said "go with your suggestions" to Claude's questions in the build chat:
1. Two steps: A the queue (with the list), B the history.
2. One list of every download: this session's (step B adds past ones above them), oldest at the top, 6 rows tall with a scrollbar, between the choices and the progress bar. Columns: Video (the link until yt-dlp has looked it up, then the title), As (MP4, MP4 720p, MP4 subtitles, MP3), State (Waiting, Downloading 40%, Done, Already there, Failed in red, Cancelled).
3. The bar and status line show the selected row: its progress while it runs, its full message once finished (a failure in red), "Waiting." for a waiting one. A download that starts gets selected, unless the user selected another row since the previous one started. Reason: otherwise a failure's reason in the middle of a queue is on screen only for a moment.
4. Play and Show in folder work on the selected row, also during a download; double-click on a finished row plays it. With no file selected, Show in folder opens the download folder, as now.
5. Download or Enter while a download runs adds the link as "Waiting". The link box empties after every accepted link. The choices stay usable during a download; each link keeps the choices it was added with. Accepted drawback: trying a failed link again means pasting it again.
6. A Remove button (and the Delete key in the list) removes the selected row: a waiting link leaves the queue, a finished row leaves the list (from step B also the history). Never deletes a file; greyed out for the running row.
7. Cancel stops the running download only; the next waiting link then starts.
8. Closing the window with links waiting closes at once; the waiting links are lost.
9. `download()`'s arguments stay as they are (not grouped into one object): the window keeps each link's choices in its row's record.
10. Step B, to confirm in its chat: `%APPDATA%\video-downloader\history.json`, only saved files (Done and Already there), the newest 200.

## Progress
- [x] A: the queue (2026-11-13), as in the answers above. Measured: about 310 lines of code and 390 of tests (estimated 200 and 150).
  - app.py: each row is a `Job` (link, choices, state, title, message, file) in `App.jobs`, keyed by the Treeview's row id. `start_next()` starts the first waiting one. `run_job()` makes sure every download sends exactly one last report (Done, Failed or Cancelled), even after an exception. `check_events()` moves on to the next one after that report.
  - downloader.py: `Progress` carries the video's title.
  - The README's "Using it" moved into docs/using.md; the README keeps a summary.
  - For step B: finished rows come from the Done case in `check_events()`. Removing rows happens in `remove_selected()`. Past rows go in above this session's rows, as `Job`s with state Done or Already there and a `file`.
- [x] B: the history (2026-11-13). The user said "go with your suggestions": answer 10 as written; past rows look like this session's, the list opens scrolled to the newest; a file Play finds gone leaves the history; a broken file is an empty history, written anew. Decision: docs/decisions.md 2026-11-13.
  - app.py: `load_history()` / `save_history()` (the whole list's saved rows each time, through `history.json.new`), `App.update_history()` after a saved file, Remove of a saved row and a file found gone. A file that is there but locked returns None: no saves that session.
  - `App`, `start()` and the GUI test's `open_window()` take the history file; screenshots give each screen a temporary one (new screen: `history`).

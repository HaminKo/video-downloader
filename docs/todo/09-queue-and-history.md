# To do 9: Queue and history (medium): "A queue or history of downloads"

- **Goal:** paste the next link while one is downloading (queue), and see what was downloaded before (history). Today: one download at a time; Download is off while busy.
- **Read first:** `App.start_download`, `set_busy` and `check_events` in app.py; docs/decisions.md To do 3 ("one download at a time, no Cancel button").
- **Approach:** a list under the link box; downloads still run one after another in one worker thread, as now. History: past downloads kept in a small file in the app's own data folder (built from `Path.home()`). Probably two steps: queue (A), history (B).
- **Ask the user:** (a) queue first, history as step B? Suggested: yes. (b) what does clicking a history entry do? Suggested: opens the folder with the file selected. (c) a way to remove a queued link? Suggested: yes, for links not yet started.
- **Test:** Claude: GUI test with the fake download (two links, both finish in order). User: queue two YouTube videos.

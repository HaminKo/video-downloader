# To do 8: Playlists and whole channels (medium): "Playlists and whole channels"

- **Goal:** a playlist or channel link downloads all its videos. Today it takes only the first and the window says so. Example: a short YouTube playlist (`youtube.com/playlist?list=...`).
- **Read first:** `options()` (`noplaylist`, `playlist_items`) and `download()` in downloader.py; `PLAYLIST_NOTE` and `done_message()` in app.py; docs/decisions.md To do 3 ("a playlist or channel link downloads one video"); docs/research/yt-dlp-library.md "A page with two videos is a playlist".
- **Approach:** no `playlist_items` limit for playlist links; the progress line says "Video 3 of 12"; one failed video doesn't stop the rest, and the end message counts what was saved, skipped and failed.
- **Ask the user:** (a) a subfolder per playlist? Suggested: yes, named after the playlist. (b) a channel can have thousands of videos: ask first above some number? Suggested: ask above 50. (c) a link to one video inside a playlist (`watch?v=...&list=...`): just that video, as now? Suggested: yes.
- **Test:** Claude: the local test server's two-video page downloads both; GUI test step for "Video 1 of 2". User: a short YouTube playlist.

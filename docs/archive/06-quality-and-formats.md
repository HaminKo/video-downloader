# To do 6: Choosing quality and formats (medium): "Choosing the quality, or formats other than MP4 and MP3"

- **Goal:** pick a lower quality to save space (e.g. 720p) or the highest there is, or another format. Today MP4 is H.264 at the best quality yt-dlp's `-t mp4` preset picks (on YouTube usually at most 1080p) and MP3 is fixed.
- **Read first:** `Kind`, `PRESETS` and `options()` in downloader.py; the MP4/MP3 radio buttons in `App.__init__` (app.py); docs/decisions.md "MP4 that plays everywhere".
- **Approach:** a quality choice as a height limit added to the MP4 preset's format sort (e.g. `res:720`), keeping H.264 first so files still play everywhere. "Highest" may give AV1 or VP9, which Windows' own player may not open, so the window would say so. Other formats only as yt-dlp's own presets (e.g. `-t aac`, `-t mkv`), as more `Kind` values.
- **Ask the user:** (a) which quality choices? Suggested: today's (best that plays everywhere), 1080p, 720p, 480p; no "Highest" unless you want 4K. (b) other formats? Suggested: none until you name one you'd use. (c) remember the choice between runs? Suggested: no for now (it needs a settings file).
- **Test:** Claude: options tests per choice; GUI test step for the new control; screenshots. User: one YouTube video at 720p and at the default; both play, and the 720p file is smaller.

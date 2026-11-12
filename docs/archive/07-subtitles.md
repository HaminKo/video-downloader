# To do 7: Subtitles (small): "Subtitles"

- **Goal:** save a video's subtitles with it, so the player can show them. Example: a YouTube video with English subtitles.
- **Read first:** `options()` and `PRESETS` in downloader.py; yt-dlp's subtitle settings (`writesubtitles`, `writeautomaticsub`, `subtitleslangs`, the `FFmpegEmbedSubtitle` step).
- **Approach:** a checkbox "Subtitles" (MP4 only); yt-dlp downloads them and ffmpeg puts them inside the MP4, so it stays one file.
- **Ask the user:** (a) inside the MP4, or a separate .srt file next to it? Suggested: inside, if Windows' own player shows them (the build checks); otherwise .srt. (b) which languages? Suggested: English; YouTube's automatic subtitles only when there are no real ones.
- **Test:** Claude: options test; GUI test step for the checkbox. User: a YouTube video with subtitles plays with them in Windows' Media Player.

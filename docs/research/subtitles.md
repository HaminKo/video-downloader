# Subtitles: what yt-dlp does, and what Windows' player shows

Found while planning To do 7 (2026-11-12), with yt-dlp 2026.10.26 and the winget ffmpeg build (docs/local.md). "Read in the source" means read in `.venv/Lib/site-packages/yt_dlp`; "measured" means run on this PC (scratch scripts, not kept).

## Windows' own player and subtitles inside an MP4
- **Windows' media stack doesn't see subtitles inside an MP4** (measured): asked through WinRT (`MediaSource` + `MediaPlaybackItem.TimedMetadataTracks`, the playback API Windows' Media Player app is built on), an MP4 with an English `mov_text` (tx3g) track, made by yt-dlp's own `FFmpegEmbedSubtitle`, has 0 subtitle tracks. The same subtitles in an MKV: 1 track (SRT or ASS inside); WebVTT inside an MKV: 0. So the probe works, and MP4's subtitle format is the one Windows doesn't read.
- **The user's player is VLC** (user, 2026-11-12). Sample files opened there: a separate `Title.en.srt` (yt-dlp's name) and `Title.srt` both showed; the user named only those two, so subtitles inside the MP4 presumably didn't show without picking the track by hand. A real download (`Me at the zoo.mp4` with `Me at the zoo.en.srt`, made by the app) showed its subtitles in VLC. So no renaming is needed. Not tested: Windows' Media Player app itself.
- VLC, phones and browsers do show `mov_text` (general knowledge, not measured here).

## Which subtitles yt-dlp takes
- **Settings** (measured with `parse_options`): `--write-subs` = `writesubtitles`, `--write-auto-subs` = `writeautomaticsub`, `--sub-langs en` = `subtitleslangs: ["en"]`, `--convert-subs srt` = postprocessor `FFmpegSubtitlesConvertor` (`format: srt`, `when: before_dl`), `--embed-subs` = postprocessor `FFmpegEmbedSubtitle` after the remuxer (and turns on `writesubtitles` unless `--write-auto-subs` is given).
- **Real subtitles win over automatic ones** (read in the source, `process_subtitles` in YoutubeDL.py): with both settings on, the automatic captions only fill in languages that have no real subtitles.
- **`subtitleslangs` entries are regexes that must match the whole code** (`re.fullmatch`): `en` takes only `en`, not `en-US` or `en-GB`.
- **With no `subtitleslangs`**, yt-dlp takes one track: real `en`, then real `en-*`, then automatic `en`, then any real track, then anything (including `live_chat`, a JSON chat replay that can't be shown and can be large).
- **YouTube, 9 videos measured**: English-language videos with real subtitles (2), with only automatic ones (4), Dutch news with real Dutch subtitles (1) or only automatic ones (1), a cooking vlog with 17 real languages (1). All 9 had an `en` track (real, automatic, or YouTube's automatic translation), and `["en"]` took exactly that one track each time. Not seen: a video with only `en-US` or `en-GB` real subtitles; there `["en"]` would take the automatic `en` instead.
- **No English at all** (measured with a local page): the video still downloads; `requested_subtitles` is `{}` (or missing when the video has no subtitles at all), and yt-dlp prints "There are no subtitles for the requested languages".

## Formats
- YouTube offers each track as json3, srv1-3, ttml, srt and vtt; yt-dlp's default (`best`) takes the last one, vtt.
- **YouTube's automatic captions as vtt** (measured) are written for its own rolling display: each line appears twice (once as the new bottom line, once as the top line of the next cue), with word timings (`<00:00:04.240><c> up</c>`) and 10 ms in-between cues. ffmpeg drops the word timings but keeps the doubled lines, both when embedding and when converting to srt.
- **YouTube's own srt** for the same captions is clean: one line per cue (cues overlap in time). Real subtitles look the same in vtt and srt.
- So for a separate file: `subtitlesformat: "srt/best"` (YouTube's own srt) plus `FFmpegSubtitlesConvertor` to srt for sites that only have vtt.

## Files and failures
- **A separate subtitle file is named `Title.en.srt`** (read in the source, `subtitles_filename`: always `.LANG.EXT`); no setting drops the language code.
- **Video already there** (measured, separate srt): yt-dlp skips the video, still downloads the subtitles and writes `Title.en.srt` next to it; the MP4 isn't touched. It downloads them again each time (it looks for the existing file under the downloaded format, `.en.vtt`, not the converted `.en.srt`).
- **Video already there, subtitles inside** (read in the source, `FFmpegEmbedSubtitlePP.run`): the embedding step still runs and rewrites the existing MP4 through a temporary file (`-map -0:s` first drops any subtitles already in it).
- **A subtitle download that fails fails the whole download** (read in the source, `_write_subtitles`; measured with a page whose subtitle file is missing): "Unable to download video subtitles for 'en': HTTP Error 404: File not found" is an error unless `ignoreerrors` is on, which would also hide other errors. Subtitles are fetched before the video, so nothing is saved. YouTube sometimes refuses subtitle downloads with HTTP 429 (general knowledge, not checked in a source); not seen here.
  - Wrong first plan, replaced after the code review: show yt-dlp's own text. Its text ends in the cause, and "HTTP Error 404" matched the app's "This video isn't available" pattern. The subtitle pattern now comes before the others in `PLAIN_MESSAGES`.
- **The subtitle download reports progress too** (measured): the progress hooks get "downloading" for the subtitle file (`Title.en.vtt`, a few KB) before the video, so the bar filled to 100% and started again at 0. Its `info_dict` has no `format_id`; every video and audio format has one (yt-dlp gives each format without one its index, read in the source, `process_video_result`). The app shows progress only for statuses with a `format_id`.

## Testing without the internet
- yt-dlp's generic extractor reads `<track kind="subtitles" src="..." srclang="en">` inside a `<video>` on a web page (read in the source, `_parse_html5_media_entries` in extractor/common.py; measured). So the existing test web server can serve a page with a clip and a `.vtt`.

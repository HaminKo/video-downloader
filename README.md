# video-downloader

A small Windows app: paste a link to a video and it saves the video to your PC as MP4, or just the audio as MP3, showing progress as it goes. It is a simple window on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp), which does the actual downloading and supports thousands of sites.

It does not download from DRM-protected services (Netflix, Disney+, Spotify and the like).

## Status
Downloading works, and when a download fails the window says why in plain words. Reddit works once you've signed in ([Signing in](docs/signing-in.md)). What comes next is in [docs/todo.md](docs/todo.md).

## Using it
Paste a link, choose **Video (MP4)** or **Audio only (MP3)** and, for a video, its quality and whether you want English subtitles, then press Download (or Enter). The bar and the line under it show the progress.
- Files go to the **Videos** folder inside your Downloads folder, named after the video's title.
- MP4s use H.264 video with AAC sound, so they play everywhere (Windows' own player, phones).
- **Video quality:** **Best** is the best that plays everywhere, which on YouTube means at most 1080p. **720p** and **480p** save space: on a long YouTube video, 720p was a little over half the size of Best, and 480p about a fifth. A video with nothing that small comes in its smallest size above it. A 720p or 480p file has the quality after its title (`Title (720p).mp4`), so it sits next to a copy at Best instead of counting as already there. The choice starts at Best each time the app opens.
- **English subtitles:** saved as a separate file next to the video (`Title.en.srt`), because Windows can't read subtitles inside an MP4. You get the video's real English subtitles when it has them, otherwise the site's automatic ones (on YouTube, sometimes its automatic translation into English). A video without English subtitles still downloads, and the window says so. If the video is already there, only the subtitles are added. If the subtitles can't be downloaded, nothing is saved and the window says so: try again later, or untick the box. The box starts unticked each time the app opens.
- A file that is already there isn't downloaded again; the window says so.
- **Play** opens the file you just downloaded in your default player (VLC also picks up the subtitles next to it). **Show in folder** opens the Videos folder with that file selected. Nothing opens by itself. Before the first download, and after a failed one, Play is greyed out and Show in folder just opens the folder.
- One download at a time. **Cancel** stops it: the window says "Cancelled." and deletes what that download had saved (half-downloaded pieces, and its subtitles); files that were in the folder before are never touched (a half-downloaded file left by closing the window included). While ffmpeg joins video and audio or converts to MP3, Cancel takes effect when that step is done. Closing the window also stops a download, but leaves the half-downloaded file, which yt-dlp continues from if you download the same video again.
- A link to a playlist or channel downloads only its first video, and the window says so.
- When a download fails, the line under the bar says why in plain words, in red: not a link, a site or page with no video, no internet, a private or removed video, one that needs signing in, or ffmpeg missing. Anything else shows yt-dlp's own message. yt-dlp's full message is also printed in the terminal the app runs from.
- Reddit only gives a post's video to people who are signed in. To sign in, you export Reddit's sign-in from your browser once, as a file the app uses: see [Signing in](docs/signing-in.md). The app doesn't sign in to YouTube (it could get the account banned).

## Install and run
Needs Windows, Python 3.13 or newer, [ffmpeg](https://ffmpeg.org) and [Deno](https://deno.com). All commands are for PowerShell.

1. Install ffmpeg (yt-dlp's own build, which patches some ffmpeg bugs that affect yt-dlp) and Deno:
   ```powershell
   winget install --id yt-dlp.FFmpeg -e
   winget install --id DenoLand.Deno -e
   ```
   Then restart VS Code (or your terminal) so it sees the new programs.
2. In the project folder, create the virtual environment and install the app with its tools:
   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```
   If PowerShell says "running scripts is disabled on this system", allow scripts for your account once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then run the last two lines again.
3. Run it (with the `.venv` active):
   ```powershell
   python -m video_downloader
   ```

To check that yt-dlp finds ffmpeg and Deno, run `yt-dlp -v`: the `exe versions` line should list ffmpeg and the `JS runtimes` line deno. It ends with "You must provide at least one URL", which is expected.

To update yt-dlp (needed now and then when YouTube changes): `python -m pip install -U "yt-dlp[default]"`.

## Development
With the `.venv` active: `ruff check .` and `ruff format .` (lint and formatting), `pytest` (tests), `pyright` (type check).

`pytest` needs ffmpeg: two tests download a 1-second clip from a small web server they start on this PC (never the internet).

GUI test: `pytest tests/gui/window_gui.py` opens the real window for about 5 seconds, types a link, presses Enter and clicks Download, and checks what the window shows; a fake download stands in for yt-dlp. Screenshots: `python tests/gui/screenshots.py` (or one screen by name, e.g. `done`) saves them to the temp folder and prints the paths. Both bring the window to the front and take the keyboard focus while they run; keys typed then are ignored. How they work: [docs/research/gui-testing.md](docs/research/gui-testing.md).

## Credits
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) by the yt-dlp contributors, Unlicense: does all the downloading.
- [FFmpeg](https://ffmpeg.org) by the FFmpeg developers, LGPL 2.1+ or GPL 2+ depending on the build (the suggested [yt-dlp build](https://github.com/yt-dlp/FFmpeg-Builds) is GPL): joins video and audio, converts to MP3 and converts subtitles to SRT.
- [yt-dlp-ejs](https://github.com/yt-dlp/ejs) by Simon Sawicki and the yt-dlp contributors, Unlicense with bundled MIT and ISC parts: installed with yt-dlp, solves YouTube's JavaScript challenges together with Deno.
- [Deno](https://deno.com) by the Deno authors, MIT: the JavaScript runtime yt-dlp needs for YouTube.
- [Get cookies.txt LOCALLY](https://github.com/kairi003/Get-cookies.txt-LOCALLY) by kairi003, MIT: a browser extension, not part of the app, for exporting Reddit's sign-in ([Signing in](docs/signing-in.md)).
- [Python](https://www.python.org) and tkinter by the Python Software Foundation, PSF License (tkinter uses [Tcl/Tk](https://www.tcl-lang.org), BSD-style license): the app and its window.
- Development tools: [ruff](https://github.com/astral-sh/ruff) by Astral (MIT), [pyright](https://github.com/microsoft/pyright) by Microsoft (MIT), [pytest](https://pytest.org) by the pytest-dev team (MIT), [Pillow](https://python-pillow.github.io) by Jeffrey A. Clark and contributors (MIT-CMU, screenshots for the GUI test), [hatchling](https://github.com/pypa/hatch) by the Python Packaging Authority (MIT, builds the package for the install).

# video-downloader

A small Windows app: paste a link to a video and it saves the video to your PC as MP4, or just the audio as MP3, showing progress as it goes. It is a simple window on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp), which does the actual downloading and supports thousands of sites.

It does not download from DRM-protected services (Netflix, Disney+, Spotify and the like).

## Status
Downloading works, and when a download fails the window says why in plain words. What comes next is in [docs/todo.md](docs/todo.md).

## Using it
Paste a link, choose **Video (MP4)** or **Audio only (MP3)**, and press Download (or Enter). The bar and the line under it show the progress.
- Files go to the **Videos** folder inside your Downloads folder, named after the video's title.
- MP4s use H.264 video with AAC sound, so they play everywhere (Windows' own player, phones). On YouTube that usually means at most 1080p.
- A file that is already there isn't downloaded again; the window says so.
- One download at a time. Closing the window stops a download.
- A link to a playlist or channel downloads only its first video, and the window says so.
- When a download fails, the line under the bar says why in plain words, in red: not a link, a site or page with no video, no internet, a private or removed video, one that needs signing in, or ffmpeg missing. Anything else shows yt-dlp's own message. yt-dlp's full message is also printed in the terminal the app runs from.
- Reddit doesn't work: Reddit only gives a post's video to people who are signed in, and the app can't sign in yet (signing in is on the "Later" list in [docs/todo.md](docs/todo.md)).

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
- [FFmpeg](https://ffmpeg.org) by the FFmpeg developers, LGPL 2.1+ or GPL 2+ depending on the build (the suggested [yt-dlp build](https://github.com/yt-dlp/FFmpeg-Builds) is GPL): joins video and audio, converts to MP3.
- [yt-dlp-ejs](https://github.com/yt-dlp/ejs) by Simon Sawicki and the yt-dlp contributors, Unlicense with bundled MIT and ISC parts: installed with yt-dlp, solves YouTube's JavaScript challenges together with Deno.
- [Deno](https://deno.com) by the Deno authors, MIT: the JavaScript runtime yt-dlp needs for YouTube.
- [Python](https://www.python.org) and tkinter by the Python Software Foundation, PSF License (tkinter uses [Tcl/Tk](https://www.tcl-lang.org), BSD-style license): the app and its window.
- Development tools: [ruff](https://github.com/astral-sh/ruff) by Astral (MIT), [pyright](https://github.com/microsoft/pyright) by Microsoft (MIT), [pytest](https://pytest.org) by the pytest-dev team (MIT), [Pillow](https://python-pillow.github.io) by Jeffrey A. Clark and contributors (MIT-CMU, screenshots for the GUI test), [hatchling](https://github.com/pypa/hatch) by the Python Packaging Authority (MIT, builds the package for the install).

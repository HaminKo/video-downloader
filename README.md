# video-downloader

A small Windows app: paste a link to a video and it saves the video to your PC as MP4, or just the audio as MP3, showing progress as it goes. It is a simple window on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp), which does the actual downloading and supports thousands of sites.

It does not download from DRM-protected services (Netflix, Disney+, Spotify and the like).

## Status
Downloading works, and when a download fails the window says why in plain words. Reddit works once you've signed in ([Signing in](docs/signing-in.md)). What comes next is in [docs/todo.md](docs/todo.md).

## Using it
Paste a link, choose **Video (MP4)** or **Audio only (MP3)** and, for a video, its quality (Best, 720p or 480p) and whether you want English subtitles, then press Download (or Enter).
- Paste more links while one downloads: they wait in the list and download one after another, each with the choices it was added with.
- The list also shows what you downloaded before (the newest 200), so you can play an earlier download again.
- Files go to the **Videos** folder inside your Downloads folder: MP4s that play everywhere (H.264 video with AAC sound), or MP3s.
- Click a row in the list to see its progress or message. **Play** and **Show in folder** open its file, **Remove** takes it out of the list (never deletes a file), and **Cancel** stops the running download.
- When a download fails, the window says why in plain words. Reddit needs a sign-in file: see [Signing in](docs/signing-in.md).
- A button in Chrome sends the page you're on to the app with one click: see [The Chrome button](docs/using.md#the-chrome-button).

Everything in detail: [Using the app](docs/using.md).

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
   With a link after it (`python -m video_downloader LINK`), the link goes into the box of the window that is open, or a new window opens with it.
4. Optional, the Chrome button: run `python -m video_downloader.browser install`, then load the project's `extension` folder in Chrome. Step by step: [The Chrome button](docs/using.md#the-chrome-button).

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
- Development tools: [ruff](https://github.com/astral-sh/ruff) by Astral (MIT), [pyright](https://github.com/microsoft/pyright) by Microsoft (MIT), [pytest](https://pytest.org) by the pytest-dev team (MIT), [Pillow](https://python-pillow.github.io) by Jeffrey A. Clark and contributors (MIT-CMU, screenshots for the GUI test; drew the Chrome button's icons), [hatchling](https://github.com/pypa/hatch) by the Python Packaging Authority (MIT, builds the package for the install).

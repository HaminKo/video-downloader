# video-downloader

A small Windows app: paste a link to a video and it saves the video to your PC as MP4, or just the audio as MP3, showing progress as it goes. It is a simple window on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp), which does the actual downloading and supports thousands of sites.

It does not download from DRM-protected services (Netflix, Disney+, Spotify and the like).

## Status
Just started: project setup only, no working app yet. What comes next is in [docs/todo.md](docs/todo.md).

## Install and run
Needs Windows, Python 3.13 or newer, [ffmpeg](https://ffmpeg.org) and [Deno](https://deno.com) (both can be installed with winget).

Step-by-step install and run commands are added with the first working version (To do 1, Skeleton).

## Credits
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) by the yt-dlp contributors, Unlicense: does all the downloading.
- [FFmpeg](https://ffmpeg.org) by the FFmpeg developers, LGPL 2.1+ or GPL 2+ depending on the build: joins video and audio, converts to MP3.
- [Deno](https://deno.com) by the Deno authors, MIT: the JavaScript runtime yt-dlp needs for YouTube.
- [Python](https://www.python.org) and tkinter by the Python Software Foundation, PSF License (tkinter uses [Tcl/Tk](https://www.tcl-lang.org), BSD-style license): the app and its window.
- Development tools: [ruff](https://github.com/astral-sh/ruff) by Astral (MIT), [pyright](https://github.com/microsoft/pyright) by Microsoft (MIT), [pytest](https://pytest.org) by the pytest-dev team (MIT).

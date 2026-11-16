# Development

Building the app yourself and working on it. Installing and using it: the [README](../README.md).

## Building it yourself
This needs Python 3.13 and [Inno Setup](https://jrsoftware.org/isinfo.php) too. All commands are for PowerShell, in the project folder.

Get the project first: on its GitHub page, **Code > Download ZIP**, then extract it (or `git clone` it), and open its folder in PowerShell.

1. Install ffmpeg, Deno, Inno Setup and Python 3.13:
   ```powershell
   winget install --id yt-dlp.FFmpeg -e
   winget install --id DenoLand.Deno -e
   winget install --id JRSoftware.InnoSetup -e
   winget install --id Python.Python.3.13 -e
   ```
   Then restart VS Code (or your terminal) so it sees the new programs.
2. Create the virtual environment and install the app's code with its tools:
   ```powershell
   py -3.13 -m venv .venv
   .venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```
   If PowerShell says "running scripts is disabled on this system", allow scripts for your account once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then run the last two lines again.
3. Build the installer (it takes a few minutes, and updates yt-dlp first):
   ```powershell
   python installer/build.py
   ```
4. Run `dist\Video Downloader Setup.exe`, as in [Install and run](../README.md#install-and-run).

## Working on the app
Run the app straight from the project, with the `.venv` active: `python -m video_downloader` (with a link after it, the link goes into the open window's box). The Chrome button then needs `python -m video_downloader.browser install`, which points Chrome at the project's helper instead of the installed one ([The Chrome button](using.md#the-chrome-button)). Updating yt-dlp here: `python -m pip install -U "yt-dlp[default]"`. To check that yt-dlp finds ffmpeg and Deno, run `yt-dlp -v`: the `exe versions` line should list ffmpeg and the `JS runtimes` line deno; the closing "You must provide at least one URL" is expected.

Checks, with the `.venv` active: `ruff check .` and `ruff format .` (lint and formatting), `pytest` (tests), `pyright` (type check).

`pytest` needs ffmpeg for the download tests: they download a 1-second clip from a small web server they start on this PC (never the internet). Without ffmpeg they are skipped.

The build: `python installer/build.py` updates yt-dlp, builds the app into `dist\Video Downloader\` (`Video Downloader.exe` there starts it without installing; `THIRD-PARTY-LICENSES.txt` there holds the licenses of everything it includes) and makes `dist\Video Downloader Setup.exe` from it. `--no-update` leaves yt-dlp as it is.

GUI test: `pytest tests/gui/window_gui.py` (about 45 seconds) opens the real window, types a link, presses Enter and clicks Download, and checks what the window shows; a fake download stands in for yt-dlp. Screenshots: `python tests/gui/screenshots.py` (or one screen by name, e.g. `done`) saves them to the temp folder and prints the paths. Both open the window on top, on another screen if there is one, and don't take your keyboard; keys and clicks in their window are ignored. How they work: [docs/research/gui-testing.md](research/gui-testing.md). The Chrome button's popup has its own test, `pytest tests/gui/popup_gui.py`, which needs Chrome and shows nothing on screen.

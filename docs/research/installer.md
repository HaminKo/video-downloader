# An .exe and an installer (To do 11)

Started 2026-11-14 (To do 11, questions and plan). Marked by how each fact is known: read (in code or docs), measured (run on this PC), or general knowledge (not checked).

## The two parts
- **The app as an .exe:** a bundler packs Python, tkinter, yt-dlp and the app into a folder with `Video Downloader.exe`, started by double-click, no console window. PyInstaller is the usual one; yt-dlp's own `yt-dlp.exe` is built with it (general knowledge).
- **The installer:** a `Setup.exe`, run once, that copies that folder into the user's programs folder and adds a Start-menu entry and an entry in Settings > Apps to uninstall. Inno Setup is the usual free one for this (general knowledge).
- **One-file vs. one-folder:** PyInstaller's one-file .exe unpacks itself into a temp folder at every start (slower start, more antivirus false alarms); the one-folder build starts straight away. With an installer the folder is hidden anyway (general knowledge, start times not measured).

## What the bundle needs
- **yt-dlp ships its own PyInstaller hook** (read 2026-11-14 in the `.venv`, yt-dlp 2026.10.26: `yt_dlp/__pyinstaller/hook-yt_dlp.py`): it adds yt-dlp's lazily imported modules, websockets, requests, urllib3, mutagen, brotli, certifi and pycryptodomex, and `collect_data_files('yt_dlp_ejs', includes=['**/*.js'])`, so the JavaScript files YouTube needs (with Deno) go into the bundle without settings of our own.
- **The icons:** `app.ICONS` and `browser.EXTENSION_FOLDER` are found from `__file__` (read). In a built app they need a path from the .exe's folder (`sys.frozen`, `sys.executable`), with the extension folder copied next to the .exe.
- **The Chrome helper:** today `host.bat` runs `python -m video_downloader.host`, and `host.start_window` starts `pythonw.exe -m video_downloader` (read). In a built app both need .exe files of their own: the helper must use stdin and stdout, so it is a console .exe; Chrome starts an `.exe` directly and hidden, anything else through `cmd.exe` (docs/research/browser-button.md, read in Chromium's code 2026-11-13). The host manifest's `path` may be relative to the manifest's folder on Windows (same file, from Chrome's docs), so a `host.json` next to the helper .exe needs no path written at install time.

## The build (step A, measured 2026-11-14)
- **Tools:** PyInstaller 6.22.3 (pyinstaller-hooks-contrib 2026.10) in the `.venv`, Python 3.13.1, yt-dlp 2026.10.26.
- **Two .exe files in one folder:** a spec file with two `Analysis` and two `EXE` (`exclude_binaries=True`) and one `COLLECT` gives `Video Downloader.exe` (11.4 MB, no console) and `chrome-helper.exe` (2.2 MB, console) sharing one `_internal` folder. Each .exe holds its own module archive: the helper's has neither yt-dlp nor tkinter (checked in `build/pyinstaller/video-downloader/PYZ-01.toc`); the app's has yt-dlp's extractors (`yt_dlp.extractor._extractors`, `youtube`, `reddit`) and `yt_dlp_ejs`, whose two `.js` files are in `_internal/yt_dlp_ejs/yt/solver/`.
- **Entry scripts:** `installer/start_app.py` and `start_helper.py` import `main` and call it. They are plain imports so PyInstaller follows them (`runpy` would hide the module from it), and they keep `src/video_downloader/` off PyInstaller's search path, where the package's modules would also count as top-level ones.
- **Size and time:** `python installer/build.py --no-update` took 73 s the first time and 28 s the second; the folder is 43 MB. It includes `setuptools` (pulled in by some dependency; not looked into). Two harmless warnings: urllib3's emscripten part (browser-only) and curl_cffi (not installed).
- **The helper:** one message (`{"link": "chrome://extensions"}`, which never reaches the pipe) got `{"ok": false, "error": "Only web pages can be sent."}` back, nothing else on stdout or stderr; 0.84 s the first time (a new .exe, likely Defender scanning it: not checked), then 0.08 s.
- **The window:** `Video Downloader.exe` showed its window after 2.96 s the first time and 0.47 s the second, and closed on `WM_CLOSE` with exit code 0. No antivirus warning.
- **build.py imports only `places`:** importing the app would load yt-dlp's compiled parts (`_brotli`, `Cryptodome`; seen loaded by the review), and on Windows pip can't replace a `.pyd` a running program has open, so the yt-dlp update could fail when one of them has a new release (the review's finding, from general knowledge; not reproduced). The icon sizes come from the PNGs' names instead of `app.ICON_SIZES`.
- **Not checked by Claude:** a real download from the built app (it would save into the user's Videos folder and history); the user's hand test does that.

## Updating yt-dlp
- Inside a built app, `pip install -U` can't update yt-dlp (general knowledge). Options: build and install again with a newer yt-dlp, or the app fetches a newer yt-dlp itself at start-up (docs/decisions.md, 2026-11-11 Reddit entry: "about once a week, if it's ever wanted").

## Signing
- An unsigned `Setup.exe` downloaded from the internet gets SmartScreen's "Windows protected your PC". A file built on this PC carries no download mark, so SmartScreen shouldn't ask (general knowledge, not tested).

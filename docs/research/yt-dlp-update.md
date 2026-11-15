# The built app updating yt-dlp itself (To do 21)

Started 2026-11-14 (To do 21, questions and plan). Marked by how each fact is known: read (in code or docs), measured (run on this PC), or general knowledge (not checked).

## yt-dlp's own updater (read 2026-11-14, yt-dlp 2026.10.26, `yt_dlp/update.py`)
- **It refuses the built app:** a PyInstaller app whose `sys._MEIPASS` is `<exe folder>\_internal` counts as the variant `win_dir`, and `_NON_UPDATEABLE_REASONS` says for it "Auto-update is not supported for unpackaged executables; Re-download the latest release". The bundled yt-dlp is pip's anyway: its `version.py` has `VARIANT = 'pip'` and an `UPDATE_HINT` ("Use that to update"), which `is_non_updateable()` returns first. So `Updater(ydl).update()` can't be used; the app needs its own few steps.
- **What it does where it does update**, worth doing the same way:
  - The newest version: `GET https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest` (headers `Accept: application/vnd.github+json`, `User-Agent: yt-dlp`, `X-GitHub-Api-Version`); its `tag_name` is the version.
  - A release's files: `https://github.com/yt-dlp/yt-dlp/releases/download/<tag>/<name>` (`latest/download/<name>` for the newest).
  - GitHub can answer 200 with an HTML error page (yt-dlp issue 17550): it checks the first 512 bytes for `<!DOCTYPE html>`.
  - `_update_spec`, a small file in each release: lines `lock <tag> <regex>` (or `lockV2 <repo> <tag> <regex>`) matched against `"<variant> <system_identifier()>"`, which holds the Python version and Windows version; a match caps the update at that tag (for Pythons or systems a newer yt-dlp no longer supports).
  - The checksum: `SHA2-256SUMS` from the same release, one line per file, the SHA-256 first and the file name last. Without it, yt-dlp warns and doesn't restart into the new version. It doesn't check `SHA2-256SUMS.sig` (the GPG signature).
  - The zipapp (`yt-dlp`, no extension; variant `zip`) is replaced in place.
- **Channels:** stable `yt-dlp/yt-dlp`, nightly `yt-dlp/yt-dlp-nightly-builds`, master `yt-dlp/yt-dlp-master-builds`.

## YouTube's scripts (yt-dlp-ejs) (read, same version, `yt_dlp/extractor/youtube/jsc/_builtin/ejs.py`)
- **Where yt-dlp gets them, in order:** the `yt_dlp_ejs` package (its comment: "PyPI, PyInstaller exe, zipimport binary, etc"; the zipapp does carry the package, measured below), yt-dlp's cache, a copy inside yt-dlp itself (`vendor/`: the core script, and the lib script only as Deno's or Bun's npm variant), and the web (only with `remote_components` `ejs:github`, which the app doesn't set).
- **Only a matching version is used:** a script's major.minor must equal yt-dlp's `vendor.VERSION` (0.8.0 in 2026.10.26) and its hash must be in `vendor.HASHES`. So a newer yt-dlp that expects a newer EJS version skips the bundled `yt_dlp_ejs` 0.8.0 and falls back to its own copy. Whether that copy works with Deno here (the npm variant, which Deno would fetch from npm) is not checked, and no longer matters: the zipapp brings its own matching `yt_dlp_ejs` (below).

## The built app (read 2026-11-14 in `dist\Video Downloader\_internal`)
- **No `yt_dlp-*.dist-info`** in the build (only websockets'), and yt-dlp's modules are inside the .exe's module archive. So `importlib.metadata` can't tell the bundled version, and `import yt_dlp.version` first runs `yt_dlp/__init__.py`, which loads the whole bundled yt-dlp. The bundled version must come from somewhere else (answer below: `copy_metadata` in the spec).
- **Only the parts of Python the bundle uses:** PyInstaller bundles the standard-library modules the bundled code imports (general knowledge), so a newer yt-dlp importing one more would fail at that import (measured below: no case in 3 years).
- **The app loads yt-dlp at once:** `app.py` imports `downloader`, which imports `yt_dlp`, and `installer/start_app.py` imports `app`. A downloaded copy must be on `sys.path` before that import.

## yt-dlp's GitHub releases (measured 2026-11-14)
- **The newest stable is 2026.10.26**, the version the app bundles. `GET https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest` answered 200 with `X-RateLimit-Limit: 60` (per hour, without signing in), 47 KB of JSON: `tag_name` `2026.10.26`, `prerelease` false, and every file with its size and a `digest` (`sha256:...`, GitHub's own; for `yt-dlp` the same as in `SHA2-256SUMS`).
- **How often:** the last 100 releases go back to 2021.10.09; 12 releases in 2026 up to 2026-10-26, the longest gap 2026.03.17 to 2026.06.09 (about 12 weeks).
- **The files:** the zipapp `yt-dlp` (3,073,072 bytes), `yt-dlp.tar.gz` (the source, 6 MB), the .exe and Linux/macOS builds (19-54 MB), `SHA2-256SUMS`, `SHA2-512SUMS`, their `.sig` files, and `_update_spec`. **No wheel:** the wheel is on PyPI only, which the decision rules out (yt-dlp's GitHub only).
- **Downloading:** `https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp` redirected twice (to `release-assets.githubusercontent.com`) and took 0.82 s for the zipapp, 0.29 s each for `SHA2-256SUMS` (1,595 bytes) and `_update_spec` (2,777 bytes).
- **`SHA2-256SUMS`:** one line per file, `<64 hex digits>  <name>`, the zipapp's line ends `  yt-dlp`. The downloaded zipapp's SHA-256 matched it.
- **`_update_spec`:** yt-dlp 2026.10.21 dropped Python 3.10 (`lock 2026.10.21 zip Python 3\.10`), 2025.10.14 Python 3.9. The app's Python 3.13 isn't locked. Python 3.10's end of life was October 2026, so 3.13 likely lasts until about October 2029 (an estimate from that pattern).

## The zipapp (measured 2026-11-14, 2026.10.26's `yt-dlp`)
- A line `#!/usr/bin/env python3`, then a zip: 1,051 entries, 10.2 MB unpacked. `yt_dlp/` (1,044), **`yt_dlp_ejs/` (6, with `core.min.js` and `lib.min.js`)** and `__main__.py`. Only `.py` and `.js`, no compiled `.pyc`. `lazy_extractors.py` is in it. The longest path inside is 66 characters.
- Its `version.py`: `__version__ = '2026.10.26'`, `VARIANT = None`, `UPDATE_HINT = None`, `CHANNEL = 'stable'`.
- So the zipapp brings the yt-dlp-ejs that matches its yt-dlp, and the "matching version" question above doesn't arise.

## Loading a copy in the built app (measured 2026-11-14 with a throwaway build)
A probe .exe built like the app (the same spec settings, bundling `video_downloader.app`, PyInstaller 6.22.3, Python 3.13.1), run with a copy's path as an argument; nothing in the project changed.
- **A copy put first on `sys.path` wins:** `yt_dlp`, its YouTube extractor, `ejs.py` and `yt_dlp_ejs` all came from the copy, for the zipapp as it is and for an unpacked folder. PyInstaller 6 finds its bundled modules through a path hook for `_internal` (`sys.meta_path`: `BuiltinImporter`, `FrozenImporter`, `PathFinder`; `sys.path_hooks`: `zipimporter`, PyInstaller's `path_hook`, `FileFinder`'s), so `sys.path`'s order decides.
- **The bundled version:** with `datas=copy_metadata("yt-dlp")` in the spec, `_internal` gets `yt_dlp-2026.10.26.dist-info` and `importlib.metadata.version("yt-dlp")` gives `2026.10.26` without importing yt-dlp. The real build has no such folder today (read above).
- **The built app writes no `.pyc`:** `sys.flags.dont_write_bytecode` is 1. A copy of `.py` files is compiled again at every start.
- **Import times**, `import yt_dlp` (and then the YouTube extractor), 3 runs each, whole probe process in brackets:

  | yt-dlp from | import | YouTube extractor | process |
  |---|---|---|---|
  | the bundle | 0.21-0.22 s | 0.13 s | 0.87-0.93 s |
  | the zipapp as it is | 1.00-1.20 s | 0.57-0.68 s | 2.14-2.49 s |
  | an unpacked folder | 0.60-0.65 s | 0.34-0.37 s | 1.45-1.57 s |
  | an unpacked folder, compiled | 0.23-0.32 s | 0.14-0.17 s | 0.88-1.08 s |

  The compiled folder's first run took 1.30 s, once (likely a cold disk cache or Defender reading the new files: not checked).
- **Compiling in the built app:** `py_compile` is in the bundle (`compileall` isn't); compiling the 1,046 `.py` files with `py_compile.compile(file, cfile=importlib.util.cache_from_source(file), doraise=True)` took 4.8-5.1 s, and the copy then imported in 0.28-0.32 s. Size on disk: 13 MB unpacked, 25 MB with the `.pyc` files.
- **Falling back in the same process works:** a copy whose `YoutubeDL.py` imports a missing module (`graphlib`: `ModuleNotFoundError` after 66 of its modules had loaded), and one with a cut-off `utils/_utils.py` (`SyntaxError`, 7 loaded): removing the copy from `sys.path`, deleting every `yt_dlp*` and `yt_dlp_ejs*` entry from `sys.modules` and `importlib.invalidate_caches()`, then `import yt_dlp` loaded the bundled one, and its YouTube extractor loaded too.
- **yt-dlp's own guard:** `yt_dlp/__init__.py` raises `ImportError` on a Python older than it supports (3.11 now, read). A release that drops the app's Python fails the import check rather than breaking later.

## Parts a newer yt-dlp might miss (measured 2026-11-14)
- **Python's standard library:** the built app lacks 48 of its modules (most of them development tools or Unix-only: `unittest`, `pdb`, `zoneinfo`, `graphlib`, `difflib`, `smtplib`, `compileall`, `fcntl`, ...). The static imports of 10 zipapps from 2023.11.16 to 2026.10.26 (about one per 4 months) added 5 standard-library modules over those 3 years (`glob`, `textwrap`, `secrets`, `array`, `sysconfig`), all of them in the bundle. The only lacking one any of them imports is `fcntl` (Unix only, guarded), in all ten. So no case in 3 years; bundling the whole standard library isn't needed (and the import check falls back if it ever happens).
- **The bundled packages stay at the build's versions** (read in yt-dlp 2026.10.26): its network code turns a handler off when a package is too old (`urllib3 < 2.0.2`, `websockets < 13.0`; the bundle has 2.8.0 and 17.4), and `certifi` (the list of trusted certificate authorities) ages until a new Setup. None of this stops the import.

## What this means for step B
- **Download the zipapp** (`yt-dlp`; unpacked and compiled, the user's choice 2026-11-14, rather than kept as one file) from the release named by `releases/latest`, check it against that release's `SHA2-256SUMS`, unpack it into `yt-dlp\<version>.partial\`, compile it with `py_compile`, then rename the folder to `yt-dlp\<version>\`. About 1 s of download and 5 s of compiling, in the background.
- **At start**, before the app is imported: the bundled version from `importlib.metadata` (the spec gets `copy_metadata("yt-dlp")`), the newest complete copy that is newer and hasn't failed, put first on `sys.path`, `import yt_dlp`; on any exception, the fallback above and the version written down as failed.
- **Not needed:** the wheel (not on GitHub), bundling the whole standard library (no case in 3 years), a separate yt-dlp-ejs download (the zipapp carries it).
- **Left out for now:** reading `_update_spec` (To do 22, Someday). It matters only once yt-dlp drops Python 3.13 (likely around 2029); until the app is built with a newer Python, the app then keeps the last copy that imported.
- **Not checked:** HTTPS from the built app with Python's own `urllib` (Windows' certificate store, as yt-dlp isn't used for the update itself); step B's build check does the first real request.

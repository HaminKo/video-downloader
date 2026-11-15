# PyInstaller's recipe for the built app. installer/build.py runs it, with
# the .venv's Python (where the app is installed), after making the icon.
#
# One folder, dist/Video Downloader/, with two .exe files that share Python
# and the libraries in _internal/ (places.py names them):
# - Video Downloader.exe: the window (app.main), no console.
# - chrome-helper.exe: Chrome's helper (host.main), a console program, since
#   it talks to Chrome through stdin and stdout; Chrome starts it hidden.
# yt-dlp's own PyInstaller hook adds the modules yt-dlp loads by name and the
# JavaScript files YouTube needs (docs/research/installer.md).
import re
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

from video_downloader.places import APP_EXE, APP_NAME, HELPER_EXE

HERE = Path(SPECPATH)
ICON = str(HERE.parent / "build" / "icon.ico")  # made by build.py
# The top-level modules both .exe files include, one per line, for the
# licenses build.py lists (THIRD-PARTY-LICENSES.txt).
MODULES = HERE.parent / "build" / "modules.txt"

# yt-dlp's dist-info, so the app can tell the bundled yt-dlp's version
# without importing it (ytdlp_update.bundled_version()). mutagen (GPL) only
# embeds thumbnails into files, which the app never asks yt-dlp to do; yt-dlp
# runs without it.
app = Analysis(
    [str(HERE / "start_app.py")],
    datas=copy_metadata("yt-dlp"),
    excludes=["mutagen"],
)
helper = Analysis([str(HERE / "start_helper.py")])

# Modules by dotted name (yt_dlp.utils), compiled parts by path
# (Cryptodome\Cipher\_raw_aes.pyd, _brotli.cp313-win_amd64.pyd).
included = [*app.pure, *helper.pure, *app.binaries, *helper.binaries]
top_level = {re.split(r"[./\\]", name)[0] for name, *_ in included}
MODULES.write_text("\n".join(sorted(top_level)) + "\n", encoding="utf-8")

# upx=False: packed .exe files trip antivirus programs more often.
app_exe = EXE(
    PYZ(app.pure),
    app.scripts,
    exclude_binaries=True,
    name=Path(APP_EXE).stem,
    console=False,
    icon=ICON,
    upx=False,
)
helper_exe = EXE(
    PYZ(helper.pure),
    helper.scripts,
    exclude_binaries=True,
    name=Path(HELPER_EXE).stem,
    console=True,
    icon=ICON,
    upx=False,
)
COLLECT(
    app_exe,
    app.binaries,
    app.datas,
    helper_exe,
    helper.binaries,
    helper.datas,
    name=APP_NAME,
    upx=False,
)

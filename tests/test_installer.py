"""The installer's recipe (installer/setup.iss) and what installer/build.py
adds to the built app. The build itself runs by hand (python
installer/build.py; docs/research/installer.md), as it takes a minute."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from video_downloader import app, browser, places

PROJECT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT / "installer" / "build.py"
SETUP_SCRIPT = PROJECT / "installer" / "setup.iss"


def load_build() -> ModuleType:
    """installer/build.py as a module (it isn't in a package), without
    running its main()."""
    spec = importlib.util.spec_from_file_location("build", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_uses_the_apps_names() -> None:
    """The names Setup gives the Start-menu entry, the taskbar button and
    Chrome's key are the ones the app and its helper use."""
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    defines = dict(re.findall(r'^#define (\w+) "(.*)"$', text, re.MULTILINE))
    assert defines == {
        "AppName": places.APP_NAME,
        "AppExe": places.APP_EXE,
        "TaskbarId": app.APP_ID,
        "ChromeKey": browser.KEY,
        "HostManifest": browser.MANIFEST,
    }
    assert "OutputBaseFilename={#AppName} Setup\n" in text
    assert load_build().SETUP.name == f"{places.APP_NAME} Setup.exe"


def test_the_built_app_gets_the_extension_and_a_manifest_next_to_the_helper(
    tmp_path: Path,
) -> None:
    load_build().add_files(tmp_path)
    assert (tmp_path / "extension" / "manifest.json").is_file()
    manifest = json.loads((tmp_path / "host.json").read_text(encoding="utf-8"))
    assert manifest == browser.host_manifest(Path(places.HELPER_EXE))
    assert manifest["path"] == "chrome-helper.exe"  # wherever it's installed


def test_build_loads_no_yt_dlp() -> None:
    """build.py updates yt-dlp with pip, which can't replace yt-dlp's compiled
    parts while a program has them loaded."""
    code = (
        "import runpy, sys; "
        f"runpy.run_path({str(BUILD_SCRIPT)!r}); "  # not as __main__: no build
        "print(sorted(name for name in sys.modules if name.startswith('yt_dlp')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert result.stdout == "[]\n"

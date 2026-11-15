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
    assert "AppMutex={#TaskbarId}\n" in text  # the window's (app.start())
    # The uninstaller deletes the folder of downloaded yt-dlp copies.
    folder = places.ytdlp_folder().name
    assert f'Type: filesandordirs; Name: "{{app}}\\{folder}"\n' in text
    assert load_build().SETUP.name == f"{places.APP_NAME} Setup.exe"


def test_the_built_app_gets_the_extension_and_a_manifest_next_to_the_helper(
    tmp_path: Path,
) -> None:
    load_build().add_files(tmp_path)
    assert (tmp_path / "extension" / "manifest.json").is_file()
    manifest = json.loads((tmp_path / "host.json").read_text(encoding="utf-8"))
    assert manifest == browser.host_manifest(Path(places.HELPER_EXE))
    assert manifest["path"] == "chrome-helper.exe"  # wherever it's installed


def test_the_version_is_the_changelogs_newest() -> None:
    """A release sets the number in both pyproject.toml (Setup's version)
    and CHANGELOG.md."""
    changelog = (PROJECT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert versions[0] == load_build().app_version()
    text = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert "AppVersion={#Version}\n" in text
    assert "VersionInfoVersion={#AppNumber}\n" in text


def test_libraries_are_found_by_their_modules() -> None:
    """The standard library's modules and the app's own belong to no
    library; a compiled part (_brotli) to its library."""
    build = load_build()
    modules = ["yt_dlp", "requests", "_brotli", "json", "video_downloader"]
    names = [library.name for library in build.bundled_libraries(modules)]
    assert names == ["brotli", "requests", "yt-dlp"]


def test_the_license_file_holds_each_license_in_full(tmp_path: Path) -> None:
    build = load_build()
    build.add_licenses(tmp_path, ["requests", "certifi", "json"])
    assert (tmp_path / "LICENSE.txt").read_text(encoding="utf-8") == (
        PROJECT / "LICENSE"
    ).read_text(encoding="utf-8")
    text = (tmp_path / build.THIRD_PARTY).read_text(encoding="utf-8")
    titles = re.findall(rf"^{build.RULE}\n(.+)\n{build.RULE}$", text, re.MULTILINE)
    assert [title.split()[0] for title in titles] == [
        "Python",
        "Tcl/Tk",
        "certifi",
        "requests",
    ]
    assert "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in text
    assert "Mozilla Public License" in text  # certifi's
    assert "Apache License" in text  # requests'


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

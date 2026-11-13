# Opening a downloaded file, or its folder with the file selected

Found while building To do 12 (2026-11-12) on Windows 11 (build 26300), Python 3.13. "Measured" means run on this PC (scratch scripts, not kept), with test files in a folder under the temp folder.

## Show in folder: `explorer /select,"PATH"`
- **The command line must be a string with the path in quotes** (measured). Four forms, each started with `subprocess.Popen`:

  | Form | File | Command line Python made | Result |
  |---|---|---|---|
  | string | `with space\Cats, dogs & más 日本 (720p).mp4` | `explorer /select,"…\Cats, dogs & más 日本 (720p).mp4"` | right folder, file selected |
  | list `["explorer", "/select,", path]` | the same | `explorer /select, "…\Cats, dogs & más 日本 (720p).mp4"` | right folder, file selected |
  | string | `nospace\a,b.mp4` | `explorer /select,"…\a,b.mp4"` | right folder (selection: see below) |
  | list | the same | `explorer /select, …\a,b.mp4` | no Explorer window in the test folder: Explorer split the path at the comma |

  Python's list form quotes a part only when it holds a space or tab ([subprocess docs](https://docs.python.org/3/library/subprocess.html#converting-an-argument-sequence-to-a-string-on-windows)), so a title with a comma but no space breaks it. Windows file names can't contain `"`, so quoting the path ourselves is always safe. Spaces, commas, `&`, accents and Japanese characters all worked in the string form.
- **The app runs Explorer by its full path**, `"%WINDIR%\explorer.exe" /select,"PATH"` (found in the review): Windows looks for a bare `explorer` in Python's own folder and the current folder before its own. The app's `Files().show` with this command selected the Japanese-and-comma file above (measured).
- **explorer.exe returns exit code 1 even when it worked** (measured: all 4 forms, the working ones included), and returns after 0.28 to 0.43 s. So the app doesn't check the exit code and doesn't wait for it (`Popen`, not `run`), which would freeze the window for that time.
- **The first time Explorer shows a folder, nothing is selected** (measured: 3 of 3 first views selected nothing; 6 of 6 later views of the same folders selected the file). The folder does open. It isn't the file being new: a file made just before, in a folder Explorer had shown before, was selected. In the app this can only happen on the first Show in folder after Downloads\Videos was made, so it isn't worked around. Not tried: the Shell API `SHOpenFolderAndSelectItems` (through ctypes), which might not have this.
- **How the selection was checked** without looking at the screen: PowerShell's `(New-Object -ComObject Shell.Application).Windows()` lists the open Explorer windows; for each, `.Document.Folder.Self.Path` is its folder and `.Document.SelectedItems()` the selected files; `.Quit()` closes it. Set `[Console]::OutputEncoding` to UTF-8 first, or non-ASCII names come out garbled.

## Play: `os.startfile`
- `os.startfile(path)` opens a file in its default app, like a double-click in Explorer ([os docs](https://docs.python.org/3/library/os.html#os.startfile)). It doesn't wait for the app.
- **A missing file raises `FileNotFoundError`** (WinError 2, measured). The app checks that the file is there first and shows a message instead.
- VLC (the user's player) loads `Title.en.srt` next to the video by itself (docs/research/subtitles.md).
- A folder works too: `os.startfile(folder)` opens it in Explorer.

## Not measured
- Paths longer than 260 characters, files on a network drive.

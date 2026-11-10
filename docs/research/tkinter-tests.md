# Testing the tkinter window with pytest

## A second window fails under pytest's default output capture (2026-11-10, To do 1)
- **Seen:** two tests that each create and destroy a `tk.Tk()`: the second one often fails in `tk.Tk()` with `_tkinter.TclError: invalid command name "tcl_findLibrary"`. Python 3.13.1, Windows 11.
- **Measured:**
  - Outside pytest, 20 `tk.Tk()` create-and-destroy rounds in a row: 0 failures (also with the app's widgets and a `StringVar`).
  - pytest default (`--capture=fd`): 8 of 15 runs failed.
  - `--capture=sys`: 0 of 21 runs failed. `-s` (no capture): 0 of 6.
  - Turning off pytest's faulthandler plugin (`-p no:faulthandler`) didn't help: 3 of 3 failed.
- **Cause, not checked:** fd-level capture swaps the process's stdin/stdout/stderr handles, and Tcl seems to trip over that when it starts its second interpreter. The cause wasn't dug into further, because the fix below works.
- **Fix in use:** `addopts = "--capture=sys"` in pyproject.toml. It captures print output as usual; only output written straight to the handles by C code isn't captured.
- **Fallback if it comes back:** one `tk.Tk()` for the whole test run, with a `tk.Toplevel` per test.

## Key presses don't reach a hidden window (2026-11-10, To do 1)
- `link_entry.event_generate("<Return>")` on a withdrawn window did nothing: the test failed 10 of 10 runs. Tk delivers key events to the window that has keyboard focus, and a hidden window has none.
- The pytest tests check that the binding is there (`widget.bind("<Return>")` returns its script). Real key presses belong in the GUI test with a visible window (To do 2).

## Finding the real window from outside (2026-11-10, To do 1; notes for To do 2)
- `.venv\Scripts\python.exe` is a small launcher that starts the real Python as a **child process**. That child owns the window, so the launcher's `MainWindowHandle` is 0.
- The launcher has **two** children, `conhost.exe` and `python.exe`. Filter on `Name='python.exe'` (`Get-CimInstance Win32_Process -Filter "ParentProcessId=$id AND Name='python.exe'"`). Taking the first child picked conhost, which has no window, so it looked as if the app showed none. That was wrong: with the filter, the app's window was visible, titled "Video Downloader", 2 s after start.
- In PowerShell, passing `$null` to a P/Invoke `string` parameter sends an empty string, so `FindWindow($null, "Video Downloader")` finds nothing. Use `[NullString]::Value` instead.
- A screenshot from outside wasn't finished in To do 1. To do 2 should do screenshots from inside the app or test instead.

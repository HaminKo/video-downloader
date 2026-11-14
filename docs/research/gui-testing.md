# GUI test and screenshots for the tkinter window

Built in To do 2 (2026-11-11). Files: tests/gui/drive.py (open the window, type, click, screenshot), tests/gui/window_gui.py (the GUI test), tests/gui/screenshots.py. Commands: CLAUDE.md "Build specifics".

## How it works
- **Starting the window:** `video_downloader.app.start()`, the same function `main()` uses, so the window is DPI-aware like the user's. Then `-topmost`, so nothing covers it for the screenshot. Since To do 15 it opens on another screen and doesn't take the keyboard or the front: gui-test-focus.md.
- **Input:** Tk's own `event_generate` in the same process: `<KeyPress>` with a key name (`keysym`) per character, and `<Enter>`, `<ButtonPress-1>`, `<ButtonRelease-1>` in the middle of a button. These run the same Tk bindings a real key press or click runs. The real mouse doesn't move.
- **Checks:** texts and `StringVar` values, and widget edges from `winfo_rootx/rooty/width/height` (inside the window, link box not overlapping the button, link box at least half the window's width). No pixel comparisons.
- **Sizes:** the size the window opens with (also its smallest: 600 px at normal size, scaled with the DPI, so 900 px on this PC since To do 3; 480 px before) and 1200 px wide.
- **Screenshots:** Pillow's `ImageGrab.grab(bbox=..., all_screens=True)`, with the box from `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)`: the visible window with its title bar. `GetWindowRect` would add Windows 10/11's invisible resize border (general knowledge, not tried here). Pillow 13 also has `ImageGrab.grab(window=hwnd)`, not tried.
- **Plain `pytest` skips the GUI test:** the file is `window_gui.py`, and pytest only collects `test_*.py` and `*_test.py` on its own. A file named on the command line is collected anyway, with pytest's readable assert messages.

## Measured (2026-11-11, this PC: Windows 11, display at 150% scaling, Tk 8.6, Python 3.13.1)
- **Correction (2026-11-11):** this section first said 200% scaling. That was wrong: it came from `tk scaling` = 2.0, which is pixels per point (2.0 × 72 = 144 DPI). Measured with `GetDpiForSystem()`: 144 DPI = 150%.
- **Pillow 13.0.0:** 7.3 MB wheel download, 16 MB installed. A reinstall from pip's cache took 3.2 s. The first install's time wasn't measured (the timing command failed).
- **GUI test:** 6 tests (3 tests × 2 sizes), 1.4 to 3.7 s by pytest's report, about 3 s in all.
- **Screenshots:** both screens in 1.5 s. Each is 484 × 172 px, 9 to 10 KB. About 110 tokens each: an **estimate** from width × height / 750.
- **Shows it can fail:** with Enter bound to Tab instead of Return, the Enter test failed at both sizes with `AssertionError: Enter in the link box should start a download` / `assert '' == "Downloading isn't built yet."`.

## Flaky first version: stray characters and lost focus (fixed)
- **Seen:** the first version took the keyboard focus once at the start and typed with no filter. 5 of 10 runs had a failure, in three kinds:
  - "the link box didn't get keyboard focus" right at the start
  - typing stopped partway (`https://www.youtube.com/watch?v`)
  - extra characters (`htctps://...`, `ohttps://...`)
- **Likely cause (not proven):** the test window takes the foreground and the keyboard focus. Keys the user types elsewhere at that moment land in it, and a click elsewhere (or Windows activating another window) takes the focus away mid-typing. The extra characters can only come from real key presses. In a later probe with no one typing, 12 of 12 windows typed correctly.
- **Also measured in that probe:** Windows brings only a process's first window to the front by itself. Windows 2 to 12 were not in front after opening (11 of 11) and were in front after `focus_force()` (12 of 12).
- **Fix:**
  1. A bind tag put first on every widget drops key presses and clicks unless drive.py is sending them (a flag set around its own `event_generate` calls).
  2. Before each key press, drive.py takes the focus back if the link box lost it.
- **Checked:** keys posted straight to the test window's own handle (`PostMessage`, so nothing reached any other window) were dropped (`ignored: ['2 q', '3 q']`). A second window that took the focus mid-typing: the focus was taken back and the link came out right. After the fix, 10 of 10 runs passed, but no one was typing then, so the real-typing case is covered only by the probe.
- **Tried, didn't work:** telling Tk's own events apart from real ones with the event's `send_event` field (`%E`): it is false for `event_generate` keys too.
- **Seen once since (2026-11-12, To do 9):** "didn't get the keyboard focus" from `focus()` in one of 24 tests (`test_mp3_choice_reaches_the_download[wide]`), in 1 of 3 runs; the other two runs passed fully. `focus_force()` itself didn't get the focus back, so Windows refused it, likely while the user was working in another window (not proven). No fix tried; if it comes back often, retrying `focus_force()` a few times is the next thing to try.
- **Seen again (2026-11-13, To do 10, step A):** one ERROR (not a failure, so in the fixture's setup or teardown) in `test_failure_shows_a_plain_message_in_red[wide]`, in 1 of 4 runs that day; the other runs passed fully (27 tests). Its text wasn't kept, so it isn't proven to be the same focus error; the user was watching a video in Chrome meanwhile (Chrome was the window in front at a check minutes earlier). The step had just added listening on a pipe of each test's own to the GUI test's windows, which doesn't touch the focus. Twice in two days now: if it comes back, keep the output (`pytest tests/gui/window_gui.py *> FILE`) and try the retry.
- **Replaced (To do 15, 2026-11-14):** `focus_force()` is gone. drive.py's `focus()` uses Windows' `SetFocus`, which doesn't need Windows' permission to come to the front and doesn't take it (gui-test-focus.md), so the retry above shouldn't be needed. The filter tag and taking the focus back before each key press stay.

## Rejected
- **OS-level input** (pywinauto, pyautogui, Windows' `SendInput`): it moves the real cursor and types into whichever window is in front, so a run could type into the user's editor. It also breaks if the user touches the mouse.
- **Our own screenshot code** (about 50 lines of ctypes, no Pillow): more code to keep working for the same result.

## Things to know for later steps
- Key presses go to the widget with the keyboard focus, not to the widget `event_generate` is called on. drive.py's `press()` focuses the widget first. A hidden (withdrawn) window gets no key presses at all (tkinter-tests.md).
- Only letters and digits work as their own key names. Other characters need Tk's name (`colon`, `slash`, ...): `KEY_NAMES` in drive.py has all printable ASCII characters. All 94 printable ASCII characters typed correctly (2026-11-11). Anything else (`é`) stops the test with "add its Tk key name to KEY_NAMES".
- The filter tag goes on every widget when the window opens, and again before each key press and click, so widgets added later (To do 3 may add some) get it too. Between being created and the next key press or click, a new widget still takes real input.
- The window opens at its smallest size, 480 px wide (484 with its frame). At this PC's 150% scaling, that is about 320 px at normal size: the link box shows about 30 characters of a link (seen in the screenshot). (First written as 200% and 240 px: wrong, see the correction above.) Widened in To do 3: now 900 px (903 with its frame), and the GUI test checks that a typical YouTube link fits in the link box (`xview()` is `(0.0, 1.0)`).

## Sources
- Tk `event generate`: https://www.tcl-lang.org/man/tcl8.6/TkCmd/event.htm
- Pillow ImageGrab: https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html
- DwmGetWindowAttribute and DWMWA_EXTENDED_FRAME_BOUNDS: https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmgetwindowattribute
- pytest collecting files named on the command line, and `python_files`: https://docs.pytest.org/en/stable/reference/reference.html#confval-python_files

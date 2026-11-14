# GUI test on another screen, without taking the computer's focus

Probe on 2026-11-13; nothing in tests/gui uses this yet. Kept apart from gui-testing.md because another session had that file open; merge it in (or link it) later. Background on how the GUI test works now: gui-testing.md.

The question (user, 2026-11-13): can the GUI test's windows open on another screen and leave the user's keyboard and mouse alone while it runs?

## How it was tested
A probe script outside the project: a plain Tk window with an Entry and a `<Return>` binding, DPI setup as in `app.start()` (`SetProcessDpiAwareness(1)`), placed on a second screen. Each way of getting the focus was tried after the window had lost it (thread focus cleared with `SetFocus(NULL)`, plus a `WM_KILLFOCUS` message for the faked case). Then three keys and Enter with `event_generate`, as drive.py does.

## Why the test takes the focus now
Tk only delivers key events (also `event_generate` ones) when it believes it has the keyboard focus. drive.py's `focus()` uses `focus_force()`, which on Windows makes the window the foreground window: that is what takes the user's keyboard, and what Windows sometimes refuses (the "didn't get the keyboard focus" errors in gui-testing.md).

## Windows keeps a focus per thread
A thread's own focus window is separate from the foreground window (the one that gets the real keyboard). A thread can set its own focus with user32 `SetFocus(hwnd)` without coming to the front; Windows then sends that window `WM_SETFOCUS`, and Tk counts it as having the focus.

## Measured (5 runs unless said)
- No trick: keys dropped, 5 of 5.
- `root.event_generate("<FocusIn>", detail="NotifyNonlinear")`: keys dropped, 5 of 5. Tk doesn't let generated focus events change its focus tracking.
- `SendMessage(root.winfo_id(), WM_SETFOCUS, 0, 0)`, a faked message: keys typed and Enter ran, 8 of 8 (3 of them in an earlier version of the probe); the window was never in front. Tk and Windows then disagree about the focus, so this is the second choice.
- `SetFocus(entry.winfo_id())`, thread-only and real: keys typed and Enter ran, 5 of 5; the window was never in front. **The one to build on.**
- Clicks (`event_generate` ButtonPress and ButtonRelease on a Button) work with no focus at all (1 of 1).
- **The first window of a process:** Windows put it in front by itself in 5 of 10 runs, likely when the user hadn't touched the mouse or keyboard for a while (Windows' foreground lock timeout; not proven). `SetForegroundWindow(the window that was in front before)` right after showing gave the front back 5 of 5, within one `update()`. The user's window still loses the front for a moment (a few ms: an estimate, not timed). A fullscreen game may notice that moment (the probes ran while one was open). Avoiding it fully, for example with `WS_EX_NOACTIVATE` on the window, wasn't tried.

## Placing the window on another screen
- `root.geometry("+X+Y")` with the screen's corner from `EnumDisplayMonitors` and `GetMonitorInfo`. The window opened at the asked spot on a screen above and to the right of the main one (negative y), 3 of 3.
- Pick a screen with the same scaling as the main screen (`GetDpiForMonitor`). `app.start()` makes the app system-DPI-aware, so on a screen with other scaling Windows stretches the window as a bitmap (general knowledge, not tried here): sizes change and screenshots blur. With no such screen, stay on the main one.
- Pillow's `ImageGrab.grab(all_screens=True)` crops by virtual-screen coordinates, so negative ones are fine (read in Pillow's code, not tried).

## Not checked
- How the title bar looks in screenshots when the window isn't in front (probably the grey inactive look).
- The whole GUI test with these changes; only the probe ran.

## Considered, not worth it
- A separate Windows desktop (`CreateDesktop`): screenshots of a desktop that isn't shown don't work, and it's a lot of code.
- Windows Sandbox or Hyper-V: not available on Windows 11 Home. Windows Sandbox (Pro and up) is the lightest real Windows to test in: a throwaway Windows in a window, erased when closed, so Python, ffmpeg and Deno would have to be installed again each time or by a start-up script (general knowledge, not tried).
- Claude Code's own sandbox for its commands (asked 2026-11-13): the docs say it runs on macOS, Linux and WSL2 only; on native Windows commands run unsandboxed. Source: https://code.claude.com/docs/en/sandboxing. Running Claude Code in WSL2 for it would mean a Linux setup for a Windows app.
- A Windows VM in VirtualBox or VMware (asked 2026-11-13): full isolation, but it needs a Windows license or the 90-day evaluation copy, 4-8 GB RAM while running and 30-60 GB disk (estimates; this PC had 3.5 GB of 32 GB free when measured), its own Python, ffmpeg and Deno, and every check from Claude would go over SSH or a shared folder. Worth it only for an occasional fresh-install check (README steps, the Chrome button's registry key), not for every step.
- Linux, via WSL or Docker (Docker Desktop on Home runs Linux containers): Tk can run on an invisible screen (Xvfb), but it would test the Linux version of the window (look, fonts, no Windows scaling, no Play or Show in folder).
- Windows containers (asked 2026-11-13): Microsoft's base images cost nothing, but Windows 11 Home can't run them (they need Pro or Enterprise), and they have no screen to show a window on. From Microsoft's and Docker's docs as known, not tried.
- Filling the link box with `entry.insert` instead of key presses: no focus needed, but a weaker test of the real bindings.
- Running the GUI test only on GitHub Actions: off this PC entirely, but slow feedback for the build loop.

## Sources
- SetFocus (focus is per thread, attached to the calling thread's message queue): https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setfocus
- SetForegroundWindow and the rules for when Windows allows it: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow
- GetMonitorInfo: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getmonitorinfow

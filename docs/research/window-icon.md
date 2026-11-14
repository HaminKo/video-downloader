# The window's icon on Windows (title bar, taskbar, Alt+Tab)

Researched 2026-11-14 for To do 18. Each point says whether it was measured on this PC or is general knowledge (not checked). This PC: Windows 11, Python 3.13 with Tk 8.6.15, main screen at 150% (small icon 24 px, big icon 48 px: `GetSystemMetrics` with `SM_CXSMICON` and `SM_CXICON`, measured in a system-DPI-aware process like the app).

## What Tk's `iconphoto` sets (measured)
- Probe: a Tk window, `root.iconphoto(True, *images)` with the PNGs from extension/icons, then the window's icons read back with `WM_GETICON` and `GetClassLongPtrW` (`GCLP_HICON`, `GCLP_HICONSM`), each `HICON`'s size from `GetIconInfo` and `GetObjectW`.
- `WM_GETICON` returns nothing, with or without `iconphoto`: Tk sets the window class's icons, not the window's own.
- Without `iconphoto`: Tk's feather, big 48 px, small 24 px.
- With 16, 32, 48 and 128 px images, in either order: big 32 px, small 24 px. With only the 16 px image: big 16 px. So Tk takes the 32 px image for the big icon whatever the screen's scaling, and the first image when there is none; a 24 or 48 px image isn't used for it. Whether the 24 px small one is made from the 32 px or the 16 px image could not be told from the outside.
- So at 150% Windows scales the icon: 32 to 24 px in the title bar. Exact sizes would need `WM_SETICON` with icons made by the app itself (ctypes), not tried.
- The result in the app's screenshot (title bar, zoomed in): a clean 24 px blue square with the white arrow, only slightly soft at the edges. Good enough; the user judges the taskbar and Alt+Tab in the hand test.

## The taskbar (measured)
- Probe: a `pythonw` child opening an invisible Tk window with the icon, then each taskbar (`Shell_TrayWnd`, `Shell_SecondaryTrayWnd`) captured with Pillow, once without and once with `shell32.SetCurrentProcessExplicitAppUserModelID` called before `tk.Tk()`.
- Without it: no button of its own; the window joined the pinned Python button, which kept Python's icon. (Python is pinned to the taskbar on this PC; without the pin it would still be grouped as pythonw.exe: general knowledge, not tested.)
- With it: a button of its own at the end of the taskbar, showing the blue arrow.
- An app ID that no Start-menu shortcut carries means pinning that button may pin plain pythonw.exe instead of the app (general knowledge, not tested). An installer's shortcut with the same ID would fix that (To do 11).

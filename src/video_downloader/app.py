"""The main window: a link box, a Download button and a status line."""

import sys
import tkinter as tk
from tkinter import ttk

TITLE = "Video Downloader"
NOT_BUILT_YET = "Downloading isn't built yet."


class App:
    """The window's widgets and what happens when they are used."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(TITLE)
        root.minsize(480, 0)
        root.columnconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Link to a video:").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.link = tk.StringVar()
        self.link_entry = ttk.Entry(frame, textvariable=self.link)
        self.link_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.download_button = ttk.Button(frame, text="Download", command=self.download)
        self.download_button.grid(row=1, column=1)

        # Progress and error messages go here (To do 3).
        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        self.link_entry.focus_set()
        self.link_entry.bind("<Return>", lambda _event: self.download())

    def download(self) -> None:
        """Placeholder until To do 3 builds the real download."""
        self.status.set(NOT_BUILT_YET)


def start() -> App:
    """Build the window as the user sees it; the GUI test starts it this way too."""
    if sys.platform == "win32":
        # Without this, Windows scales the window up and the text looks blurry.
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    return App(tk.Tk())


def main() -> None:
    start().root.mainloop()

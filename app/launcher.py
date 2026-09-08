"""Vox Studio launcher.

No-argument launch opens the native desktop GUI. The legacy localhost dashboard
is retained only behind the explicit ``--web`` argument; CLI commands continue
to delegate to ``app.cli``.
"""

from __future__ import annotations

import contextlib
import sys
import threading
import webbrowser

from app.version import APP_VERSION


def _start_server(host: str, port: int, ready_event: threading.Event) -> None:
    """Run uvicorn in a thread."""
    import uvicorn

    class _ReadyServer(uvicorn.Server):
        def startup(self, sockets=None):
            result = super().startup(sockets)
            ready_event.set()
            return result

    config = uvicorn.Config(
        "app.api.web_app:app",
        host=host,
        port=port,
        log_level="warning",
    )
    server = _ReadyServer(config)
    server.run()


def _launch_gui(host: str, port: int) -> None:
    """Legacy internal helper retained for compatibility; use --web."""
    import tkinter as tk

    url = f"http://{host}:{port}"
    ready = threading.Event()

    # Start server thread
    t = threading.Thread(target=_start_server, args=(host, port, ready), daemon=True)
    t.start()

    # Build GUI
    root = tk.Tk()
    root.title(f"Vox Studio v{APP_VERSION}")
    root.geometry("400x200")
    root.configure(bg="#0f1117")
    root.resizable(False, False)

    # Try to set icon if available
    with contextlib.suppress(Exception):
        root.iconbitmap(default="")

    title = tk.Label(
        root, text=f"🎬 Vox Studio v{APP_VERSION}",
        font=("Segoe UI", 14, "bold"), fg="#e4e4e7", bg="#0f1117",
    )
    title.pack(pady=(20, 5))

    status_var = tk.StringVar(value="Starting server...")
    status = tk.Label(
        root, textvariable=status_var,
        font=("Segoe UI", 10), fg="#8b8d98", bg="#0f1117",
    )
    status.pack(pady=5)

    url_label = tk.Label(
        root, text=url,
        font=("Cascadia Code", 10), fg="#6366f1", bg="#0f1117", cursor="hand2",
    )
    url_label.pack(pady=5)
    url_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    btn_frame = tk.Frame(root, bg="#0f1117")
    btn_frame.pack(pady=15)

    open_btn = tk.Button(
        btn_frame, text="🌐 Open Browser", font=("Segoe UI", 10),
        bg="#6366f1", fg="white", relief="flat", padx=15, pady=5,
        command=lambda: webbrowser.open(url),
    )
    open_btn.pack(side="left", padx=5)

    quit_btn = tk.Button(
        btn_frame, text="⏹ Stop & Exit", font=("Segoe UI", 10),
        bg="#2a2d3a", fg="#e4e4e7", relief="flat", padx=15, pady=5,
        command=root.destroy,
    )
    quit_btn.pack(side="left", padx=5)

    def _check_ready():
        if ready.is_set():
            status_var.set(f"Server running at {url}")
            status.configure(fg="#22c55e")
            webbrowser.open(url)
        else:
            root.after(200, _check_ready)

    root.after(200, _check_ready)
    root.mainloop()


def _launch_legacy_web() -> None:
    """Explicit compatibility mode for the old localhost dashboard."""
    import tkinter as tk

    from app.settings import get_settings

    settings = get_settings()
    host = settings.app_host
    port = settings.app_port
    url = f"http://{host}:{port}"
    ready = threading.Event()
    thread = threading.Thread(target=_start_server, args=(host, port, ready), daemon=True)
    thread.start()
    root = tk.Tk()
    root.title(f"Vox Studio Web Compatibility v{APP_VERSION}")
    root.geometry("420x220")
    root.configure(bg="#0f1117")
    tk.Label(root, text="Vox Studio — Web compatibility", fg="#e4e4e7", bg="#0f1117", font=("Segoe UI", 14, "bold")).pack(pady=(22, 8))
    status_var = tk.StringVar(value=f"Starting {url}...")
    tk.Label(root, textvariable=status_var, fg="#8b8d98", bg="#0f1117", font=("Segoe UI", 10)).pack(pady=5)
    tk.Button(root, text="Open browser", command=lambda: webbrowser.open(url), bg="#6366f1", fg="white", relief="flat", padx=16, pady=6).pack(pady=18)

    def check_ready() -> None:
        if ready.is_set():
            status_var.set(f"Server running at {url}")
        else:
            root.after(200, check_ready)

    root.after(200, check_ready)
    root.mainloop()



def _prepare_frozen_tk() -> None:
    """Expose bundled Tcl/Tk data for a PyInstaller onedir runtime."""
    import os
    from pathlib import Path

    root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    candidates = [
        root / "tcl",
        root / "_internal" / "tcl",
        root / "tcl" / "tcl8.6",
        root / "_internal" / "tcl" / "tcl8.6",
    ]
    tk_candidates = [
        root / "tk",
        root / "_internal" / "tk",
        root / "tcl" / "tk8.6",
        root / "_internal" / "tcl" / "tk8.6",
    ]
    tcl_dir = next((path for path in candidates if path.is_dir()), None)
    tk_dir = next((path for path in tk_candidates if path.is_dir()), None)
    if tcl_dir and tk_dir:
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))

def main() -> int:
    """Native GUI by default; explicit web compatibility or CLI otherwise."""
    argv = sys.argv[1:]
    if argv == ["--web"]:
        _launch_legacy_web()
        return 0
    if argv:
        from app.cli import main as cli_main

        return cli_main(argv)
    from app.gui_qt import launch_qt

    launch_qt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

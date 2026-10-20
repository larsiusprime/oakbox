"""Start Oakbox: the local app service plus a window to show it in.

Usage: python -m oakbox [--browser] [--port N] [--no-window]

Opens a native window (Edge WebView2 on Windows, WebKitGTK on Linux when
installed). On Linux without WebKitGTK, or with --browser, it opens the UI in
Chromium/Chrome "app" mode if available, else in the default browser (SPEC §6.1).
"""

from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from typing import Any

import uvicorn

from oakbox.app import create_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            return
        except OSError:
            time.sleep(0.1)


def _open_browser(url: str) -> None:
    for exe in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge"):
        path = shutil.which(exe)
        if path:
            subprocess.Popen([path, f"--app={url}", "--new-window"])
            return
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(prog="oakbox")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--browser", action="store_true", help="open in a browser instead of a window")
    parser.add_argument("--no-window", action="store_true", help="only run the server")
    args = parser.parse_args()

    port = args.port or _free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    if args.no_window:
        print(f"OAK box is running at {url}")
        server.run()
        return

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_until_up(url)

    if not args.browser:
        try:
            import webview

            picker = _Picker()
            picker.window = webview.create_window(
                "OAK box", url, width=1280, height=860, min_size=(960, 640), js_api=picker
            )
            webview.start()
            server.should_exit = True
            return
        except Exception:  # noqa: BLE001 - no usable native window toolkit; fall back
            pass
    _open_browser(url)
    print(f"OAK box is running at {url}. Close this window to quit.")
    try:
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True


class _Picker:
    """Exposed to the UI as window.pywebview.api: native folder dialogs."""

    def __init__(self) -> None:
        self.window: Any = None

    def pick_folder(self) -> str | None:
        import webview

        if self.window is None:
            return None
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        return str(result[0]) if result else None


if __name__ == "__main__":
    main()

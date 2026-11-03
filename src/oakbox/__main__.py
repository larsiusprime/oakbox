"""Start Oakbox: the local app service plus a window to show it in.

Usage: python -m oakbox [--browser] [--port N] [--no-window] [--selftest-menus]

Opens a native window (Edge WebView2 on Windows, Qt on Linux). Where Qt can't open a
window, or with --browser, it opens the UI in Chromium/Chrome "app" mode if available,
else in the default browser (SPEC §6.1).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
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
    # What's printed is UTF-8 even where the console's code page isn't (Windows); pythonw has no console at all.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(prog="oakbox")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--browser", action="store_true", help="open in a browser instead of a window")
    parser.add_argument("--no-window", action="store_true", help="only run the server")
    parser.add_argument(
        "--ui-url",
        help="developers: show the page from this local address (the Vite dev server, e.g. npm run dev:wording)"
        " instead of the built one; the app service still runs on --port",
    )
    parser.add_argument("--selftest-menus", action="store_true", help="open the window, check its menus, and exit (CI)")
    args = parser.parse_args()
    if args.ui_url and not re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?/?$", args.ui_url):
        parser.error("--ui-url must be a local address, http://127.0.0.1:<port>")
    if args.selftest_menus:
        os.environ.setdefault("OAKBOX_HOME", tempfile.mkdtemp(prefix="oakbox-menus-"))

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
    # The page itself: the built one, or (developers) a dev server's, which proxies /api to this service.
    page = url
    if args.ui_url:
        page = args.ui_url.rstrip("/")
        _wait_until_up(page, timeout=90)

    if not args.browser and _window(page, selftest=args.selftest_menus):
        server.should_exit = True
        return
    _open_browser(page)
    print(f"OAK box is running at {page}. Close this window to quit.")
    try:
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True


def _window(url: str, selftest: bool = False) -> bool:
    """Show the app in a native window until it closes. False if there's no usable window toolkit."""
    try:
        import webview

        from oakbox import menus, qtmenu, winmenu

        picker = _Picker()
        window = webview.create_window("OAK box", url, width=1280, height=860, min_size=(960, 640), js_api=picker)
    except Exception:  # noqa: BLE001 - no usable native window toolkit
        return False
    if window is None:
        return False
    controller = menus.Controller(send=menus.page_sender(window), close=window.destroy, set_title=window.set_title)
    picker._window, picker._controller = window, controller

    # Native menus (SPEC §3.14): the Win32 menu bar on Windows, Qt's on Linux. Both are
    # added once the window exists. Anywhere else, pywebview's own (simpler) menus.
    native: Any = None
    gui = None
    if sys.platform == "win32":
        why_not, native = winmenu.unavailable(), winmenu.WinMenu
    elif sys.platform.startswith("linux"):
        qtmenu.prepare()
        why_not, native, gui = qtmenu.unavailable(), qtmenu.QtMenu, "qt"
    else:
        why_not = "no native menus on this platform yet"
    if why_not is not None:
        native = gui = None
    if native is not None:
        menu_class = native

        def attach() -> None:
            picker._menu = menu_class(window.native, controller)
            picker._menu.attach()

        window.events.shown += attach
    elif selftest:
        sys.exit(f"The menu self-test needs native menus, which aren't available: {why_not}")

    failures: list[str] = []
    try:
        if selftest:
            webview.start(func=_selftest_menus, args=(window, picker, url, failures), gui=gui)
        elif native is not None:
            webview.start(gui=gui)
        else:
            webview.start(menu=menus.pywebview_menus(controller))  # elsewhere: pywebview's own menus
    except Exception:  # noqa: BLE001 - the toolkit failed to start; fall back to a browser
        if selftest:
            raise
        return False
    if gui == "qt":
        # Qt WebEngine's threads abort the process ("terminate called without an active
        # exception") if Python tears Qt down at exit. Nothing is left to save (settings and
        # projects are written as they change), so leave without that teardown.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1 if failures else 0)
    if selftest:
        sys.exit(1 if failures else 0)
    return True


class _Picker:
    """Exposed to the UI as window.pywebview.api: native file and folder dialogs, and the title.

    pywebview exposes every public attribute of this object to the page, walking into
    nested objects. Anything that isn't meant for the page must start with "_": a public
    reference to the window makes pywebview crawl the whole window and hang at startup.
    """

    def __init__(self) -> None:
        self._window: Any = None
        self._controller: Any = None
        self._menu: Any = None
        self._viewer: Any = None

    def set_context(self, title: str, project_id: str | None) -> None:
        """Where the page is: the title bar says so (SPEC D44), and the menus follow (§3.14)."""
        if self._controller is not None:
            self._controller.set_context(title, project_id)

    def menu_key(self, key: str) -> None:
        """Alt (+ a letter) typed in the page opens the menu bar (the web view keeps those keys)."""
        if self._menu is not None:
            self._menu.menu_key(key)

    def view_url(self, url: str, title: str) -> None:
        """A page from elsewhere (Street View, the aerial, Zillow, Redfin) in one viewer window beside the app,
        reused from sale to sale; opened again if it was closed. Only web addresses."""
        import webview

        if not url.startswith("https://"):
            return
        if self._viewer is not None:
            try:
                self._viewer.load_url(url)
                self._viewer.set_title(title)
                return
            except Exception:  # noqa: BLE001 - closed since: open a new one
                self._viewer = None
        viewer = webview.create_window(title, url, width=1100, height=800)
        if viewer is not None:
            viewer.events.closed += lambda: setattr(self, "_viewer", None)
        self._viewer = viewer

    def pick_folder(self) -> str | None:
        import webview

        if self._window is None:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return str(result[0]) if result else None

    def pick_file(self) -> str | None:
        """A data file OpenAVMKit can read (SPEC §3.0 F2)."""
        import webview

        if self._window is None:
            return None
        types = ("Data files (*.csv;*.parquet;*.geoparquet;*.gpkg;*.shp)", "All files (*.*)")
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=types)
        return str(result[0]) if result else None


def _selftest_menus(window: Any, picker: _Picker, url: str, failures: list[str]) -> None:
    """Check the real native menu bar end to end, then close (CI: python -m oakbox --selftest-menus)."""
    from oakbox import appsettings

    def check(label: str, ok: bool, detail: object = "") -> None:
        print(f"PASS: {label}" if ok else f"FAIL: {label} {detail}", flush=True)
        if not ok:
            failures.append(label)

    def wait(js: str, want: object, seconds: float = 15) -> object:
        deadline = time.time() + seconds
        got = None
        while time.time() < deadline:
            got = window.evaluate_js(js)
            if got == want:
                break
            time.sleep(0.25)
        return got

    try:
        deadline = time.time() + 60
        while picker._menu is None and time.time() < deadline:
            time.sleep(0.25)
        menu = picker._menu
        check("menu bar attached", menu is not None)
        if menu is None:
            return
        wait("document.title", "OAK box")
        items = {path: (enabled, checked) for path, enabled, checked in menu.snapshot()}
        tops = list(dict.fromkeys(path[0] for path in items))
        check("File, View, Project, Help", tops == ["File", "View", "Project", "Help"], tops)
        check("File > New project… enabled", items.get(("File", "New project…")) == (True, False))
        check("Project > Metadata greyed out on Projects", items.get(("Project", "Metadata")) == (False, False))
        check("View > Density > Default checked", items.get(("View", "Density", "Default")) == (True, True))

        menu.click("File", "New project…")
        check("New project… opens the form", wait("location.hash", "#/new") == "#/new")

        menu.click("View", "Zoom in")
        got = wait("document.documentElement.style.getPropertyValue('--zoom')", "1.1")
        check("Zoom in restyles the page", got == "1.1", got)
        check("Zoom in saved", appsettings.load().zoom == 110)
        menu.click("View", "Actual size")
        got = wait("document.documentElement.style.getPropertyValue('--zoom')", "1")
        check("Actual size puts it back", got == "1", got)

        body = {
            "name": "Menu test",
            "country": "US",
            "region": "VA",
            "jurisdiction": "Test",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "units": "imperial",
        }
        req = urllib.request.Request(
            url + "/api/projects", data=json.dumps(body).encode(), headers={"content-type": "application/json"}
        )
        pid = json.loads(urllib.request.urlopen(req, timeout=30).read())["id"]
        window.evaluate_js(f"location.hash = '#/projects/{pid}/metadata'")
        check("title names the project", wait("document.title", "Menu test – OAK box") == "Menu test – OAK box")
        time.sleep(1)
        items = {path: (enabled, checked) for path, enabled, checked in menu.snapshot()}
        check("Project > Metadata enabled in a project", items.get(("Project", "Metadata")) == (True, False))
        check("File > Open recent lists it", ("File", "Open recent", "1 Menu test") in items, sorted(items))

        menu.click("Project", "Data")
        hash_ = f"#/projects/{pid}/fields"
        check("Project > Data switches tab", wait("location.hash", hash_) == hash_)
        menu.click("Help", "About OAK box")
        check("Help > About opens", wait("!!document.querySelector('.modal')", True) is True)
        # Not tested here: Alt (+ a letter) opens a real menu, whose loop would hold the window open.
    except Exception as e:  # noqa: BLE001 - report, then close the window
        check("self-test ran", False, repr(e))
    finally:
        window.destroy()


if __name__ == "__main__":
    from oakbox.net import use_system_certificates

    use_system_certificates()
    main()

"""Linux: a Qt menu bar on pywebview's Qt window (SPEC §3.14, D44).

On Linux OAK box runs pywebview with Qt (PySide6, LGPL), whose window (``window.native``)
is a QMainWindow. Its menu bar has everything the menus need: shortcut labels, check marks,
radio groups, greyed-out items and Alt-key letters. Each menu is brought up to date as it
opens (``aboutToShow``), Open recent included.

Qt objects belong to the GUI thread; work for them is posted there (``_on_ui``). Clicks run
their command on a worker thread, since commands talk to the page.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Any

from oakbox.menus import MENUS, Controller, Item, Submenu, plain


def unavailable() -> str | None:
    """Why the Qt window can't be used here, or None when it can.

    Qt can't report a missing display plugin library (e.g. libxcb-cursor0 on X11) as an
    error: it aborts the process. So a window is first tried in a short-lived process.
    """
    if not sys.platform.startswith("linux"):
        return "not Linux"
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        from PySide6.QtWidgets import QMenuBar  # noqa: F401
    except Exception as e:  # noqa: BLE001 - e.g. a system library Qt needs (libEGL) is missing
        return f"{type(e).__name__}: {e}"
    probe = "import sys; from PySide6.QtWidgets import QApplication; QApplication(sys.argv)"
    try:
        tried = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Qt didn't start: {e}"
    if tried.returncode != 0:
        last = (tried.stderr.strip().splitlines() or ["no message"])[-1]
        return f"Qt can't open a window here: {last}"
    return None


def prepare() -> None:
    """Settings for Qt's web engine, before the window starts.

    The window only ever shows OAK box's own UI from 127.0.0.1, so Chromium's sandbox, which
    can't start on some systems (root, or Ubuntu 24.04's user-namespace restriction) and then
    stops the page from loading, is switched off for it.
    """
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


_invoker: Any = None


def _on_ui(fn) -> Any:
    """Run fn on Qt's GUI thread, wait for it, and return its result."""
    from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() == app.thread():
        return fn()

    global _invoker
    if _invoker is None:

        class Invoker(QObject):
            call = Signal(object)

        _invoker = Invoker()
        _invoker.moveToThread(app.thread())  # its slot then runs on the GUI thread
        _invoker.call.connect(lambda job: job())

    done = threading.Event()
    result: list[Any] = []
    error: list[BaseException] = []

    def job() -> None:
        try:
            result.append(fn())
        except BaseException as e:  # noqa: BLE001 - re-raised on the calling thread
            error.append(e)
        finally:
            done.set()

    _invoker.call.emit(job)
    done.wait()
    if error:
        raise error[0]
    return result[0] if result else None


class QtMenu:
    def __init__(self, window: Any, controller: Controller) -> None:
        self.window = window  # pywebview's QMainWindow
        self.controller = controller
        self.items: dict[str, Item] = {}  # QAction objectName -> what it does
        self.fills: dict[str, Submenu] = {}  # QMenu objectName -> submenu made as it opens
        self._next = 0

    def _tag(self, obj: Any) -> str:
        self._next += 1
        tag = f"oakbox-{self._next}"
        obj.setObjectName(tag)
        return tag

    def attach(self) -> None:
        _on_ui(self._build)

    def _build(self) -> None:
        bar = self.window.menuBar()
        bar.clear()
        for menu in MENUS:
            bar.addMenu(self._menu(menu, bar))

    def _menu(self, sub: Submenu, parent: Any) -> Any:
        from PySide6.QtGui import QActionGroup
        from PySide6.QtWidgets import QMenu

        menu = QMenu(sub.title, parent)
        if sub.fill:
            self.fills[self._tag(menu)] = sub
        group = None
        for entry in sub.items:
            if entry is None:
                menu.addSeparator()
            elif isinstance(entry, Submenu):
                menu.addMenu(self._menu(entry, menu))
            else:
                action = self._action(entry, menu)
                if entry.radio:
                    group = group or QActionGroup(menu)
                    group.addAction(action)
        menu.aboutToShow.connect(lambda menu=menu: self.refresh(menu))
        return menu

    def _action(self, entry: Item, menu: Any) -> Any:
        # Text after a tab is the shortcut label. The keys themselves reach the page (the web
        # view has the focus), which handles them; binding them here too would run them twice.
        action = menu.addAction(entry.title + (f"\t{entry.shortcut}" if entry.shortcut else ""))
        action.setCheckable(entry.checked is not None)
        action.triggered.connect(lambda _checked=False, command=entry.command: self._run(command))
        self.items[self._tag(action)] = entry
        return action

    def _run(self, command: str) -> None:
        threading.Thread(target=self.controller.run, args=(command,), daemon=True).start()

    def refresh(self, menu: Any) -> None:
        """Bring a menu's items up to date as it opens (GUI thread)."""
        context = self.controller.context()
        fill = self.fills.get(menu.objectName())
        if fill is not None and fill.fill is not None:
            menu.clear()
            made = fill.fill(context)
            for entry in made:
                self._action(entry, menu)
            if not made:
                menu.addAction("(none)").setEnabled(False)
        for action in menu.actions():
            item = self.items.get(action.objectName())
            if item is not None:
                action.setEnabled(item.enabled(context) if item.enabled else True)
                if item.checked is not None:
                    action.setChecked(item.checked(context))

    def menu_key(self, key: str) -> None:
        """Alt (+ letter) typed in the page: open the menu bar as Qt would (the web view keeps the keys)."""

        def open_menu() -> None:
            bar = self.window.menuBar()
            actions = bar.actions()
            target = next((a for a in actions if key and f"&{key.lower()}" in a.text().lower()), None)
            if target is None:
                if not key and actions:
                    bar.setFocus()
                    bar.setActiveAction(actions[0])
                return
            target.menu().popup(bar.mapToGlobal(bar.actionGeometry(target).bottomLeft()))

        _on_ui(open_menu)

    # ---------- For the self-test (python -m oakbox --selftest-menus) ----------

    def snapshot(self) -> list[tuple[tuple[str, ...], bool, bool]]:
        """Every item as Qt has it after its menu opened: (path, enabled, checked)."""

        def collect() -> list[tuple[tuple[str, ...], bool, bool]]:
            out: list[tuple[tuple[str, ...], bool, bool]] = []

            def walk(menu: Any, path: tuple[str, ...]) -> None:
                self.refresh(menu)
                for action in menu.actions():
                    if action.isSeparator():
                        continue
                    title = plain(action.text().split("\t")[0])
                    if action.menu() is not None:
                        walk(action.menu(), (*path, title))
                    else:
                        out.append(((*path, title), action.isEnabled(), action.isChecked()))

            for top in self.window.menuBar().actions():
                walk(top.menu(), (plain(top.text()),))
            return out

        return _on_ui(collect)

    def click(self, *path: str) -> None:
        """Click a menu item by its path, e.g. ("File", "New project…")."""

        def find_and_click() -> None:
            actions = self.window.menuBar().actions()
            action = None
            for title in path:
                action = next(a for a in actions if plain(a.text().split("\t")[0]) == title)
                if action.menu() is not None:
                    self.refresh(action.menu())
                    actions = action.menu().actions()
            assert action is not None
            action.trigger()

        _on_ui(find_and_click)

"""Windows: a real Win32 menu bar on pywebview's window (SPEC §3.14, D44).

pywebview's window on Windows is a .NET Windows Forms form (``window.native``), on the
.NET Framework that comes with Windows. Its classic ``MainMenu`` is the Win32 menu bar,
drawn by Windows itself: shortcut labels, check marks, radio items, greyed-out items and
Alt-key letters all behave natively. Each menu is brought up to date as it opens
(``Popup``), so it always shows the current state, including Open recent.

Clicks run their command on a worker thread: commands talk to the page, which needs the
UI thread free.
"""

from __future__ import annotations

import threading
from typing import Any

from oakbox.menus import MENUS, Controller, Item, Submenu, plain

WM_SYSCOMMAND = 0x0112
SC_KEYMENU = 0xF100


def available() -> bool:
    try:
        import clr  # type: ignore[import-not-found]  # noqa: F401  # pythonnet, which pywebview uses on Windows
        from System.Windows.Forms import MainMenu  # type: ignore[import-not-found]  # noqa: F401
    except Exception:  # noqa: BLE001 - not Windows, or a .NET without the classic menus
        return False
    return True


def _on_ui(form: Any, fn) -> Any:
    """Run fn on the form's UI thread and return its result."""
    from System import Action  # type: ignore[import-not-found]

    result: list[Any] = []
    error: list[BaseException] = []

    def call() -> None:
        try:
            result.append(fn())
        except BaseException as e:  # noqa: BLE001 - re-raised on the calling thread
            error.append(e)

    if form.InvokeRequired:
        form.Invoke(Action(call))
    else:
        call()
    if error:
        raise error[0]
    return result[0] if result else None


class WinMenu:
    def __init__(self, form: Any, controller: Controller) -> None:
        self.form = form
        self.controller = controller
        # Keyed by each .NET MenuItem's Tag: pythonnet may wrap the same item in new objects.
        self.items: dict[str, Item] = {}  # what an item does
        self.fills: dict[str, Submenu] = {}  # submenus made as they open
        self._next = 0

    def _tag(self, node: Any) -> str:
        self._next += 1
        node.Tag = tag = str(self._next)
        return tag

    def attach(self) -> None:
        _on_ui(self.form, self._build)

    def _build(self) -> None:
        from System.Windows.Forms import MainMenu  # type: ignore[import-not-found]

        bar = MainMenu()
        for menu in MENUS:
            bar.MenuItems.Add(self._menu(menu))
        self.form.Menu = bar

    def _menu(self, sub: Submenu) -> Any:
        from System.Windows.Forms import MenuItem  # type: ignore[import-not-found]

        node = MenuItem(sub.title)
        for entry in sub.items:
            node.MenuItems.Add(self._entry(entry))
        if sub.fill:
            self.fills[self._tag(node)] = sub
        node.Popup += lambda sender, _args: self.refresh(sender)
        return node

    def _entry(self, entry: Item | Submenu | None) -> Any:
        from System.Windows.Forms import MenuItem  # type: ignore[import-not-found]

        if entry is None:
            return MenuItem("-")
        if isinstance(entry, Submenu):
            return self._menu(entry)
        # Text after a tab is the right-aligned shortcut label. The keys themselves reach the
        # page (the web view has the focus), which handles them.
        node = MenuItem(entry.title + (f"\t{entry.shortcut}" if entry.shortcut else ""))
        node.RadioCheck = entry.radio
        node.Click += lambda _sender, _args, command=entry.command: self._run(command)
        self.items[self._tag(node)] = entry
        return node

    def _run(self, command: str) -> None:
        threading.Thread(target=self.controller.run, args=(command,), daemon=True).start()

    def refresh(self, node: Any) -> None:
        """Bring a menu's items up to date as it opens (UI thread)."""
        from System.Windows.Forms import MenuItem  # type: ignore[import-not-found]

        context = self.controller.context()
        for child in list(node.MenuItems):
            tag = str(child.Tag) if child.Tag is not None else ""
            fill = self.fills[tag].fill if tag in self.fills else None
            if fill is not None:
                child.MenuItems.Clear()
                made = fill(context)
                for entry in made:
                    child.MenuItems.Add(self._entry(entry))
                if not made:
                    none = MenuItem("(none)")
                    none.Enabled = False
                    child.MenuItems.Add(none)
            item = self.items.get(tag)
            if item is not None:
                child.Enabled = item.enabled(context) if item.enabled else True
                child.Checked = item.checked(context) if item.checked else False

    def menu_key(self, key: str) -> None:
        """Alt (+ letter) typed in the page: open the menu bar as Windows would.

        The web view keeps the keyboard, so Windows never sees the Alt key itself.
        """
        import ctypes

        letter = ord(key.lower()) if key else 0
        ctypes.windll.user32.PostMessageW(int(self.form.Handle.ToInt64()), WM_SYSCOMMAND, SC_KEYMENU, letter)  # type: ignore[attr-defined]

    # ---------- For the self-test (python -m oakbox --selftest-menus) ----------

    def snapshot(self) -> list[tuple[tuple[str, ...], bool, bool]]:
        """Every item as Windows has it after its menu opened: (path, enabled, checked)."""

        def collect() -> list[tuple[tuple[str, ...], bool, bool]]:
            out: list[tuple[tuple[str, ...], bool, bool]] = []

            def walk(node: Any, path: tuple[str, ...]) -> None:
                self.refresh(node)
                for child in list(node.MenuItems):
                    title = plain(str(child.Text).split("\t")[0])
                    if title == "-":
                        continue
                    if child.MenuItems.Count:
                        walk(child, (*path, title))
                    else:
                        out.append(((*path, title), bool(child.Enabled), bool(child.Checked)))

            for top in list(self.form.Menu.MenuItems):
                walk(top, (plain(str(top.Text)),))
            return out

        return _on_ui(self.form, collect)

    def click(self, *path: str) -> None:
        """Click a menu item by its path, e.g. ("File", "New project…")."""

        def find_and_click() -> None:
            nodes = list(self.form.Menu.MenuItems)
            node = None
            for title in path:
                node = next(n for n in nodes if plain(str(n.Text).split("\t")[0]) == title)
                self.refresh(node)
                nodes = list(node.MenuItems)
            assert node is not None
            node.PerformClick()

        _on_ui(self.form, find_and_click)

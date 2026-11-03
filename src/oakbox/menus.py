"""The menus (SPEC §3.14, D44): File, View, Project, Help.

One definition, two ways to show it:
- on Windows, a real Win32 menu bar on pywebview's window (``winmenu``), with shortcut
  labels, check marks, greyed-out items, and Open recent filled as the menu opens;
- elsewhere, pywebview's own menus, which are fixed at start-up (no check marks or
  greyed items, Open recent as it was at start-up).

Python keeps the state the menus show: the display settings and recent projects are in
OAK box's settings, and the page says which project is open (``Controller.set_context``).
Commands the page carries out are sent to it (window.oakboxMenu, web/src/menu.ts).
"""

from __future__ import annotations

import json
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from oakbox import appsettings, projects

OPENAVMKIT_DOCS = "https://www.openavmkit.com/docs/"
RECENT = 8

# Commands the page carries out (web/src/menu.ts). "open-project:<id>" and "display" too.
PAGE_COMMANDS = (
    "new-project",
    "show-folder",
    "close-project",
    "tab-metadata",
    "tab-data",
    "about",
)


@dataclass(frozen=True)
class Context:
    """What the menus show: is a project open, the display settings, recent projects."""

    project_open: bool
    settings: appsettings.AppSettings
    recent: list[tuple[str, str]]  # (project id, name), most recent first


@dataclass(frozen=True)
class Item:
    command: str
    title: str  # "&" marks the Alt-key letter
    shortcut: str | None = None  # shown in the menu; the page handles the keys
    checked: Callable[[Context], bool] | None = None
    radio: bool = False
    enabled: Callable[[Context], bool] | None = None


@dataclass(frozen=True)
class Submenu:
    title: str
    items: tuple[Item | Submenu | None, ...] = ()  # None is a separator
    fill: Callable[[Context], list[Item]] | None = None  # contents made as it opens (Open recent)


def _in_project(c: Context) -> bool:
    return c.project_open


def _recent(c: Context) -> list[Item]:
    return [Item(f"open-project:{pid}", f"&{i + 1} {name}") for i, (pid, name) in enumerate(c.recent)]


ZOOM_STEPS = {"zoom-in": 1, "zoom-out": -1, "zoom-reset": 0}

MENUS: tuple[Submenu, ...] = (
    Submenu(
        "&File",
        (
            Item("new-project", "&New project…", "Ctrl+N"),
            Submenu("Open &recent", fill=_recent),
            Item("show-folder", "Show project &folder", enabled=_in_project),
            Item("close-project", "&Close project", enabled=_in_project),
            None,
            Item("exit", "E&xit"),
        ),
    ),
    Submenu(
        "&View",
        (
            Submenu(
                "&Density",
                (
                    Item("density-default", "&Default", radio=True, checked=lambda c: c.settings.density != "compact"),
                    Item("density-compact", "&Compact", radio=True, checked=lambda c: c.settings.density == "compact"),
                ),
            ),
            None,
            Item("zoom-in", "Zoom &in", "Ctrl+="),
            Item("zoom-out", "Zoom &out", "Ctrl+-"),
            Item("zoom-reset", "&Actual size", "Ctrl+0"),
        ),
    ),
    Submenu(
        "&Project",
        (
            Item("tab-metadata", "&Metadata", "Ctrl+1", enabled=_in_project),
            # The Input files tab is out of the flow for now (files are added on the Data wizard's steps).
            Item("tab-data", "&Data", "Ctrl+2", enabled=_in_project),
        ),
    ),
    Submenu(
        "&Help",
        (
            Item("docs", "OpenAVMKit &documentation"),
            Item("about", "&About OAK box"),
        ),
    ),
)


@dataclass
class Controller:
    """Runs menu commands and knows what the menus should show."""

    send: Callable[[str], None]  # run a command in the page
    close: Callable[[], None]
    set_title: Callable[[str], None]
    open_url: Callable[[str], Any] = webbrowser.open
    project_id: str | None = None

    def context(self) -> Context:
        s = appsettings.load()
        names = {p.id: p.name for p in projects.list_projects()}
        recent = [(pid, names[pid]) for pid in s.recent if pid in names]
        return Context(project_open=self.project_id is not None, settings=s, recent=recent)

    def set_context(self, title: str, project_id: str | None) -> None:
        """The page says where it is: the title bar, and the project (for its menus and Open recent)."""
        self.set_title(title)
        self.project_id = project_id
        if project_id:
            with appsettings.LOCK:
                s = appsettings.load()
                s.recent = [project_id, *[p for p in s.recent if p != project_id]][:RECENT]
                appsettings.save(s)

    def run(self, command: str) -> None:
        if command == "exit":
            self.close()
        elif command == "docs":
            self.open_url(OPENAVMKIT_DOCS)
        elif command in ("density-default", "density-compact", *ZOOM_STEPS):
            with appsettings.LOCK:
                s = appsettings.load()
                if command.startswith("density-"):
                    s.density = command.removeprefix("density-")  # type: ignore[assignment]
                else:
                    s.zoom = appsettings.zoom_step(s.zoom, ZOOM_STEPS[command])
                appsettings.save(s)
            self.send("display")  # the page re-reads the settings and restyles
        else:
            self.send(command)


def page_sender(window: Any) -> Callable[[str], None]:
    """Run a command in the page."""

    def send(command: str) -> None:
        window.evaluate_js(f"window.oakboxMenu && window.oakboxMenu({json.dumps(command)})")

    return send


def plain(title: str) -> str:
    return title.replace("&", "")


def pywebview_menus(controller: Controller) -> list:
    """The fallback: pywebview's own menus, fixed at start-up."""
    from webview.menu import Menu, MenuAction, MenuSeparator

    context = controller.context()

    def convert(entries) -> list:
        out = []
        for entry in entries:
            if entry is None:
                out.append(MenuSeparator())
            elif isinstance(entry, Submenu):
                children = list(entry.items) + (entry.fill(context) if entry.fill else [])
                if children:
                    out.append(Menu(plain(entry.title), convert(children)))
            else:
                out.append(MenuAction(plain(entry.title), lambda c=entry.command: controller.run(c)))
        return out

    return convert(MENUS)


def walk(entries=MENUS, context: Context | None = None, path: tuple[str, ...] = ()):
    """Every item with its menu path (for tests and the self-test); fills dynamic menus from context."""
    for entry in entries:
        if isinstance(entry, Submenu):
            children = list(entry.items) + (entry.fill(context) if entry.fill and context else [])
            yield from walk(children, context, (*path, plain(entry.title)))
        elif entry is not None:
            yield (*path, plain(entry.title)), entry

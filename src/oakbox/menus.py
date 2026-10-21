"""The native menus (SPEC §3.14, D44): File, View, Project, Help.

pywebview menus are fixed at start-up: no shortcuts, check marks or greyed-out items.
So each item only names a command; the page carries it out (window.oakboxMenu), and
knows what's open. Items that need nothing from the page run here.
"""

from __future__ import annotations

import json
import webbrowser
from collections.abc import Callable
from typing import Any

OPENAVMKIT_DOCS = "https://www.openavmkit.com/"

# Commands the page handles (web/src/menu.ts), in menu order.
PAGE_COMMANDS = (
    "new-project",
    "show-folder",
    "close-project",
    "density-compact",
    "density-comfortable",
    "large-text",
    "high-contrast",
    "tab-metadata",
    "tab-files",
    "add-file",
    "about",
)


def build(send: Callable[[str], None], close: Callable[[], None], open_url: Callable[[str], Any] = webbrowser.open):
    """The menus, as pywebview Menu objects. ``send`` passes a command to the page."""
    from webview.menu import Menu, MenuAction, MenuSeparator

    def page(command: str) -> Callable[[], None]:
        return lambda: send(command)

    return [
        Menu(
            "File",
            [
                MenuAction("New project…", page("new-project")),
                MenuAction("Show project folder", page("show-folder")),
                MenuAction("Close project", page("close-project")),
                MenuSeparator(),
                MenuAction("Exit", close),
            ],
        ),
        Menu(
            "View",
            [
                Menu(
                    "Density",
                    [
                        MenuAction("Compact", page("density-compact")),
                        MenuAction("Comfortable", page("density-comfortable")),
                    ],
                ),
                MenuAction("Large text", page("large-text")),
                MenuAction("High contrast", page("high-contrast")),
            ],
        ),
        Menu(
            "Project",
            [
                MenuAction("Metadata", page("tab-metadata")),
                MenuAction("Input files", page("tab-files")),
                MenuAction("Add a file…", page("add-file")),
            ],
        ),
        Menu(
            "Help",
            [
                MenuAction("OpenAVMKit documentation", lambda: open_url(OPENAVMKIT_DOCS)),
                MenuAction("About OAK box", page("about")),
            ],
        ),
    ]


def page_sender(window: Any) -> Callable[[str], None]:
    """Run a menu command in the page."""

    def send(command: str) -> None:
        window.evaluate_js(f"window.oakboxMenu && window.oakboxMenu({json.dumps(command)})")

    return send

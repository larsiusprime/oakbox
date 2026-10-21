"""Native menus and the window (SPEC §3.14, D44), and the display settings (D43)."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from webview.menu import Menu, MenuAction

from oakbox import menus
from oakbox.app import create_app


def _actions(items, path=()):
    for item in items:
        if isinstance(item, Menu):
            yield from _actions(item.items, (*path, item.title))
        elif isinstance(item, MenuAction):
            yield (*path, item.title), item.function


def test_every_menu_item_does_something():
    sent, closed, opened = [], [], []
    built = menus.build(sent.append, lambda: closed.append(True), opened.append)
    assert [m.title for m in built] == ["File", "View", "Project", "Help"]
    for _, run in _actions(built):
        run()
    assert sent == list(menus.PAGE_COMMANDS)  # each page command once, in menu order
    assert closed == [True] and opened == [menus.OPENAVMKIT_DOCS]


def test_the_page_handles_every_menu_command():
    source = (Path(__file__).parents[1] / "web" / "src" / "menu.ts").read_text()
    listed = re.search(r"MENU_COMMANDS = \[(.*?)\] as const", source, re.S)
    assert listed is not None
    assert tuple(re.findall(r'"([a-z-]+)"', listed.group(1))) == menus.PAGE_COMMANDS


def test_page_sender_runs_the_command_in_the_page():
    class Window:
        script = ""

        def evaluate_js(self, script):
            self.script = script

    window = Window()
    menus.page_sender(window)("add-file")
    assert window.script == 'window.oakboxMenu && window.oakboxMenu("add-file")'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path))
    return TestClient(create_app())


def test_display_settings_are_kept(client):
    assert client.get("/api/app-settings").json()["display"] == {
        "density": None,
        "large_text": False,
        "high_contrast": False,
    }
    body = {"density": "comfortable", "large_text": True, "high_contrast": False}
    assert client.put("/api/app-settings/display", json=body).json()["display"] == body
    assert client.get("/api/app-settings").json()["display"] == body  # saved in OAK box's settings
    assert client.put("/api/app-settings/display", json=body | {"density": "huge"}).status_code == 422


def test_version_names_openavmkit(client):
    v = client.get("/api/version").json()
    assert v["version"] and v["openavmkit"] not in ("", "unknown")

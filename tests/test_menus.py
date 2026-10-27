"""Menus and the window (SPEC §3.14, D44), and the display settings (D43).

The Windows menu bar itself is checked on Windows by `python -m oakbox --selftest-menus` (CI).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from webview.menu import Menu, MenuAction

from oakbox import appsettings, menus
from oakbox.app import create_app

NEW = {
    "name": "Travis County 2026",
    "country": "US",
    "region": "TX",
    "jurisdiction": "Travis County",
    "tax_year": 2026,
    "valuation_date": "2026-01-01",
    "units": "imperial",
}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path))


@pytest.fixture
def client():
    return TestClient(create_app())


class Recorder:
    def __init__(self):
        self.sent, self.titles, self.opened, self.closed = [], [], [], 0

    def controller(self):
        def close():
            self.closed += 1

        return menus.Controller(
            send=self.sent.append, close=close, set_title=self.titles.append, open_url=self.opened.append
        )


def _items(context=None):
    return {path: item for path, item in menus.walk(context=context)}


def test_the_menus_and_their_shortcut_labels():
    items = _items()
    assert list(dict.fromkeys(p[0] for p in items)) == ["File", "View", "Project", "Help"]
    assert items[("File", "New project…")].shortcut == "Ctrl+N"
    assert items[("Project", "Metadata")].shortcut == "Ctrl+1"
    assert items[("Project", "Data")].shortcut == "Ctrl+2"


def test_project_items_are_greyed_out_until_a_project_is_open(client):
    r = Recorder()
    c = r.controller()
    items = _items()
    assert not items[("Project", "Data")].enabled(c.context())
    assert items[("File", "New project…")].enabled is None  # always available
    pid = client.post("/api/projects", json=NEW).json()["id"]
    c.set_context("Travis County 2026 – OAK box", pid)
    assert items[("Project", "Data")].enabled(c.context())
    assert r.titles == ["Travis County 2026 – OAK box"]


def test_view_items_save_the_setting_check_it_and_restyle_the_page():
    r = Recorder()
    c = r.controller()
    items = _items()
    large, compact = items[("View", "Large text")], items[("View", "Density", "Compact")]
    assert not large.checked(c.context()) and compact.checked(c.context())
    c.run("large-text")
    c.run("density-comfortable")
    s = appsettings.load()
    assert s.large_text and s.density == "comfortable"
    assert large.checked(c.context()) and not compact.checked(c.context())
    assert items[("View", "Density", "Comfortable")].checked(c.context())
    assert r.sent == ["display", "display"]  # the page re-reads the settings


def test_open_recent_lists_projects_most_recent_first(client):
    r = Recorder()
    c = r.controller()
    a = client.post("/api/projects", json=NEW).json()["id"]
    b = client.post("/api/projects", json=NEW | {"name": "Travis 2027"}).json()["id"]
    for pid in (a, b, a):
        c.set_context("…", pid)
    recent = [(path[-1], item.command) for path, item in menus.walk(context=c.context()) if "Open recent" in path]
    assert recent == [("1 Travis County 2026", f"open-project:{a}"), ("2 Travis 2027", f"open-project:{b}")]
    c.run(f"open-project:{b}")
    assert r.sent == [f"open-project:{b}"]


def test_exit_and_documentation_run_here_the_rest_in_the_page():
    r = Recorder()
    c = r.controller()
    c.run("exit")
    c.run("docs")
    for command in menus.PAGE_COMMANDS:
        c.run(command)
    assert r.closed == 1 and r.opened == [menus.OPENAVMKIT_DOCS]
    assert r.sent == list(menus.PAGE_COMMANDS)


def test_every_menu_command_is_handled():
    handled_here = {"exit", "docs", "density-compact", "density-comfortable", "large-text", "high-contrast"}
    commands = {item.command for _, item in menus.walk()}
    assert commands == handled_here | set(menus.PAGE_COMMANDS)


def test_the_page_handles_every_page_command():
    source = (Path(__file__).parents[1] / "web" / "src" / "menu.ts").read_text()
    listed = re.search(r"MENU_COMMANDS = \[(.*?)\] as const", source, re.S)
    assert listed is not None
    assert tuple(re.findall(r'"([a-z-]+)"', listed.group(1))) == (*menus.PAGE_COMMANDS, "display")


def test_fallback_pywebview_menus_mirror_the_definition():
    r = Recorder()
    built = menus.pywebview_menus(r.controller())
    assert [m.title for m in built] == ["File", "View", "Project", "Help"]

    def actions(items):
        for item in items:
            if isinstance(item, Menu):
                yield from actions(item.items)
            elif isinstance(item, MenuAction):
                yield item

    titles = [a.title for a in actions(built)]
    assert "New project…" in titles and "Large text" in titles and "&" not in "".join(titles)


def test_page_sender_runs_the_command_in_the_page():
    class Window:
        script = ""

        def evaluate_js(self, script):
            self.script = script

    window = Window()
    menus.page_sender(window)("tab-data")
    assert window.script == 'window.oakboxMenu && window.oakboxMenu("tab-data")'


def test_display_settings_are_kept(client):
    assert client.get("/api/app-settings").json()["display"] == {
        "density": None,
        "large_text": False,
        "high_contrast": False,
    }
    body = {"density": "comfortable", "large_text": True, "high_contrast": False}
    assert client.put("/api/app-settings/display", json=body).json()["display"] == body
    assert client.get("/api/app-settings").json()["display"] == body
    assert client.put("/api/app-settings/display", json=body | {"density": "huge"}).status_code == 422


def test_version_names_openavmkit(client):
    v = client.get("/api/version").json()
    assert v["version"] and v["openavmkit"] not in ("", "unknown")

import json

import pytest
from fastapi.testclient import TestClient

from oakbox import projects
from oakbox.app import create_app


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    """The projects straight in tmp_path (not conftest's tmp_path/home), and the desktop trash beside them."""
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))  # the desktop trash, for Delete
    return tmp_path


def test_smoke_settings_are_complete_and_explicit():
    # The engine smoke test runs OpenAVMKit on Petersburg with these checked-in settings.
    from importlib import resources

    s = json.loads(
        resources.files("oakbox.smokedata").joinpath("us-va-petersburgcity-settings.json").read_text(encoding="utf-8")
    )
    load = s["data"]["load"]
    assert all(entry["dupes"]["subset"] for entry in load.values())  # SPEC §6.3
    assert set(load["sales"]["calc"]) == {"valid_sale", "vacant_sale", "key_sale"}
    assert s["locality"]["slug"] == "us-va-cityofpetersburg"


def test_sample_projects_from_earlier_builds_are_not_listed(oakbox_home):
    # SPEC D19: the sample county is gone; projects made from it are no longer listed.
    old = oakbox_home / "City of Petersburg 2026 (sample)"
    old.mkdir()
    (old / "oakbox.json").write_text(
        json.dumps(
            {
                "id": "abc123",
                "name": "x",
                "created_at": "2026-10-01T00:00:00Z",
                "tax_year": 2026,
                "sample": "us-va-petersburgcity",
                "answers": {},
                "steps": {},
            }
        ),
        encoding="utf-8",
    )
    assert projects.list_projects() == []
    assert TestClient(create_app()).get("/api/projects/abc123").status_code == 404
    assert "/api/samples" not in TestClient(create_app()).get("/openapi.json").json()["paths"]


def test_ui_assets_have_browser_safe_content_types(tmp_path, monkeypatch):
    # Regression: on Windows, Python's mimetypes reads the registry, which often maps .js to
    # text/plain, and browsers refuse module scripts served that way (blank window).
    import mimetypes

    from oakbox import app as app_module

    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<script type=module src=/assets/app.js></script>", encoding="utf-8")
    (web / "assets" / "app.js").write_text("export {}", encoding="utf-8")
    (web / "assets" / "app.css").write_text("body{}")
    monkeypatch.setattr(app_module, "WEB_DIST", web)
    mimetypes.add_type("text/plain", ".js")  # what a bad Windows registry entry does
    client = TestClient(app_module.create_app())
    assert client.get("/assets/app.js").headers["content-type"].startswith("text/javascript")
    assert client.get("/assets/app.css").headers["content-type"].startswith("text/css")
    assert client.get("/").headers["content-type"].startswith("text/html")


def test_desktop_api_exposes_only_its_functions():
    # Regression: pywebview exposes every public attribute of js_api to the page, walking into
    # nested objects. A public reference to the window made it crawl the window and hang at startup.
    import inspect

    from oakbox.__main__ import _Picker

    picker = _Picker()
    picker._window = object()
    public = {name: getattr(picker, name) for name in dir(picker) if not name.startswith("_")}
    assert public and all(inspect.ismethod(v) for v in public.values()), public

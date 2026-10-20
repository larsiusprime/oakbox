import json

import pytest
from fastapi.testclient import TestClient

from oakbox import projects
from oakbox.app import create_app
from oakbox.samples import SAMPLES
from oakbox.settings_gen import generate


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))  # the desktop trash, for Delete
    return tmp_path


def _sample():
    return projects.create_from_sample(SAMPLES["us-va-petersburgcity"].answers(), "us-va-petersburgcity")


def test_petersburg_settings_are_explicit():
    s = generate(SAMPLES["us-va-petersburgcity"].answers())
    load = s["data"]["load"]
    # Every file states its de-dupe key (SPEC §6.3).
    assert all(entry["dupes"]["subset"] for entry in load.values())
    assert set(load["sales"]["calc"]) == {"valid_sale", "vacant_sale", "key_sale"}
    assert s["data"]["process"]["merge"] == {"universe": ["parcels"], "sales": ["sales"]}
    assert s["modeling"]["instructions"]["main"]["run"] == ["lightgbm"]
    assert s["data"]["process"]["enrich"]["spatial_lag"]["model_groups"]["all"]["sample_from"] == ["all"]
    ind_vars = s["modeling"]["models"]["main"]["default"]["ind_vars"]
    assert "bldg_effective_age_years" in ind_vars and "neighborhood" in ind_vars
    assert "bldg_condition_num" not in ind_vars  # Petersburg has no condition field


def test_create_project_writes_settings_and_steps(oakbox_home):
    p = _sample()
    pdir = oakbox_home / "City of Petersburg 2026 (sample)"
    assert projects.project_dir(p.id) == pdir
    assert json.loads((pdir / "in" / "settings.json").read_text())["locality"]["slug"] == "us-va-cityofpetersburg"
    assert [s for s in p.steps] == list(projects.STEP_ORDER)
    p2 = _sample()
    assert p2.id != p.id and projects.project_dir(p2.id).name == "City of Petersburg 2026 (sample) (2)"


def test_finishing_a_step_marks_later_steps_stale():
    p = _sample()
    for step in projects.STEP_ORDER:
        p = projects.mark_step(p, step, "done")
    p = projects.mark_step(p, "check_sales", "done")
    assert p.steps["check_values"].state == "stale"
    assert p.steps["bring_in_data"].state == "done"


def test_api_lists_and_guards_step_order():
    client = TestClient(create_app())
    assert client.get("/api/samples").json()[0]["id"] == "us-va-petersburgcity"
    p = _sample()
    assert client.get("/api/projects").json()[0]["id"] == p.id
    r = client.post(f"/api/projects/{p.id}/steps/check_values/run")
    assert r.status_code == 409
    assert client.get("/api/projects/nope").status_code == 404
    assert "/api/projects/{project_id}/results/value-studies" in client.get("/openapi.json").json()["paths"]


def test_ui_assets_have_browser_safe_content_types(tmp_path, monkeypatch):
    # Regression: on Windows, Python's mimetypes reads the registry, which often maps .js to
    # text/plain, and browsers refuse module scripts served that way (blank window).
    import mimetypes

    from oakbox import app as app_module

    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<script type=module src=/assets/app.js></script>")
    (web / "assets" / "app.js").write_text("export {}")
    (web / "assets" / "app.css").write_text("body{}")
    monkeypatch.setattr(app_module, "WEB_DIST", web)
    mimetypes.add_type("text/plain", ".js")  # what a bad Windows registry entry does
    client = TestClient(app_module.create_app())
    assert client.get("/assets/app.js").headers["content-type"].startswith("text/javascript")
    assert client.get("/assets/app.css").headers["content-type"].startswith("text/css")
    assert client.get("/").headers["content-type"].startswith("text/html")

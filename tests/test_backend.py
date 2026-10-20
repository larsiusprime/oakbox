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
    return tmp_path


def test_petersburg_settings_are_explicit():
    s = generate(SAMPLES["us-va-petersburgcity"].setup())
    load = s["data"]["load"]
    # Every file states its de-dupe key (SPEC §6.3), and OpenAVMKit reads the stitched tables.
    assert all(entry["dupes"]["subset"] for entry in load.values())
    assert {e["filename"] for e in load.values()} == {
        "stitched/geo_parcels.geoparquet",
        "stitched/parcels.parquet",
        "stitched/sales.parquet",
    }
    assert set(load["sales"]["calc"]) == {"valid_sale", "vacant_sale", "key_sale"}
    assert s["data"]["process"]["merge"] == {"universe": ["parcels"], "sales": ["sales"]}
    assert s["modeling"]["instructions"]["main"]["run"] == ["lightgbm"]
    assert s["data"]["process"]["enrich"]["spatial_lag"]["model_groups"]["all"]["sample_from"] == ["all"]
    ind_vars = s["modeling"]["models"]["main"]["default"]["ind_vars"]
    assert "bldg_effective_age_years" in ind_vars and "neighborhood" in ind_vars
    assert "bldg_condition_num" not in ind_vars  # Petersburg has no condition field


def test_sample_project_starts_unconfirmed_and_writes_settings(oakbox_home):
    p = projects.create_from_sample("us-va-petersburgcity")
    assert all(st.state == "todo" for st in p.stages.values())  # a walkthrough, not magic
    assert p.notes["stitch"]
    path = projects.write_settings(p)
    assert json.loads(path.read_text())["locality"]["slug"] == "us-va-cityofpetersburg"
    assert projects.create_from_sample("us-va-petersburgcity").id == p.id + "-2"


def test_changing_a_decision_reopens_it_and_stales_what_follows():
    p = projects.create_from_sample("us-va-petersburgcity")
    for s in ("basics", "files", "stitch"):
        p = projects.confirm_stage(p, s)
    p = projects.mark_step(p, "bring_in_data", "done")
    new = p.setup.model_copy(deep=True)
    new.files[1].id_columns = ["Other"]
    p = projects.change_setup(p, new, "Files changed.")
    assert p.stages["basics"].state == "done"
    assert p.stages["files"].state == "todo"
    assert p.stages["stitch"].state == "stale" and p.stages["stitch"].reason == "Files changed."
    assert p.steps["bring_in_data"].state == "stale"
    # Re-saving identical decisions changes nothing.
    p = projects.confirm_stage(p, "files")
    p = projects.change_setup(p, p.setup.model_copy(deep=True), "x")
    assert p.stages["files"].state == "done"


def test_finishing_a_step_marks_later_steps_stale():
    p = projects.create_from_sample("us-va-petersburgcity")
    for step in projects.STEP_ORDER:
        p = projects.mark_step(p, step, "done")
    p = projects.mark_step(p, "check_sales", "done")
    assert p.steps["check_values"].state == "stale"
    assert p.steps["bring_in_data"].state == "done"


def test_api_guards_stage_and_step_order():
    client = TestClient(create_app())
    assert client.get("/api/samples").json()[0]["id"] == "us-va-petersburgcity"
    p = projects.create_from_sample("us-va-petersburgcity")
    assert client.get("/api/projects").json()[0]["id"] == p.id
    # Steps wait for every setup stage; stages wait for the ones before them.
    assert client.post(f"/api/projects/{p.id}/steps/bring_in_data/run").status_code == 409
    r = client.post(f"/api/projects/{p.id}/stages/stitch/confirm")
    assert r.status_code == 409 and "basics" in r.json()["detail"]
    assert client.post(f"/api/projects/{p.id}/stages/basics/confirm").status_code == 200
    r = client.post(f"/api/projects/{p.id}/stages/files/confirm")
    assert r.status_code == 409 and "Check" in r.json()["detail"]
    assert client.get("/api/projects/nope").status_code == 404
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/projects/{project_id}/stages/{stage}/under-the-hood" in paths


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

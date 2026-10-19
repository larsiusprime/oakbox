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
    p = projects.create(SAMPLES["us-va-petersburgcity"].answers(), sample="us-va-petersburgcity")
    pdir = oakbox_home / p.id
    assert json.loads((pdir / "in" / "settings.json").read_text())["locality"]["slug"] == "us-va-cityofpetersburg"
    assert [s for s in p.steps] == list(projects.STEP_ORDER)
    p2 = projects.create(SAMPLES["us-va-petersburgcity"].answers())
    assert p2.id == p.id + "-2"


def test_finishing_a_step_marks_later_steps_stale():
    p = projects.create(SAMPLES["us-va-petersburgcity"].answers())
    for step in projects.STEP_ORDER:
        p = projects.mark_step(p, step, "done")
    p = projects.mark_step(p, "check_sales", "done")
    assert p.steps["check_values"].state == "stale"
    assert p.steps["bring_in_data"].state == "done"


def test_api_lists_and_guards_step_order():
    client = TestClient(create_app())
    assert client.get("/api/samples").json()[0]["id"] == "us-va-petersburgcity"
    p = projects.create(SAMPLES["us-va-petersburgcity"].answers())
    assert client.get("/api/projects").json()[0]["id"] == p.id
    r = client.post(f"/api/projects/{p.id}/steps/check_values/run")
    assert r.status_code == 409
    assert client.get("/api/projects/nope").status_code == 404
    assert "/api/projects/{project_id}/results/value-studies" in client.get("/openapi.json").json()["paths"]

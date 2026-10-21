"""F3d the Fields wizard (SPEC §3.0): roles, parcel IDs and joins, guesses, and what OpenAVMKit gets."""

import json
import os

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box
from test_data_files import NEW

from oakbox import projects
from oakbox.app import create_app


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))


@pytest.fixture
def client():
    return TestClient(create_app())


IDS = [f"0012-{n:03d}" for n in range(1, 7)]


def _files(folder):
    gpd.GeoDataFrame(
        {"PARCEL_ID": IDS, "ZONE": ["R1", "R1", "R2", "C1", "R1", "R2"]},
        geometry=[box(i, 0, i + 1, 1) for i in range(6)],
        crs="EPSG:4326",
    ).to_parquet(folder / "shapes.parquet")
    pd.DataFrame(
        {
            "PROP_ID": IDS[:5] + ["9999-999"],  # one CAMA row has no parcel
            "YR_BLT": [1987, 2003, 1954, 1968, 2011, 1999],
            "LIVING_AREA": [1500, 2200, 980, 1750, 3100, 1200],
            "NBHD": ["A1", "A1", "B2", "B2", "C3", "C3"],
            "QUALITY": ["Good", "Avg", "Avg", "Good", "Exc", "Fair"],
            "OWNER_NAME": ["OWNER 1", "OWNER 2", "OWNER 3", "OWNER 4", "OWNER 5", "OWNER 6"],
        }
    ).to_csv(folder / "cama.csv", index=False)
    pd.DataFrame(
        {
            "PROP_ID": [IDS[0], IDS[0], IDS[2], IDS[3]],
            "SALE_PRICE": [185000, 210000, 92500, 240000],
            "SALE_DT": ["03/14/2023", "11/02/2024", "01/09/2024", "06/30/2025"],
        }
    ).to_csv(folder / "sales.csv", index=False)
    pd.DataFrame({"PROP_ID": [IDS[0], IDS[0], IDS[1]], "PERMIT": ["roof", "deck", "pool"]}).to_csv(
        folder / "permits.csv", index=False
    )


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    _files(tmp_path)
    for name in ("shapes", "cama", "sales", "permits"):
        ext = "parquet" if name == "shapes" else "csv"
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    return pid


def _settings(pid):
    return json.loads((projects.project_dir(pid) / "in" / "settings.json").read_text())


def _file(w, name):
    return next(f for f in w["files"] if f["name"] == name)


def _field(w, key):
    return next(f for f in w["fields"] if f["key"] == key)


def test_your_files_guesses_roles_ids_and_the_base(client, pid):
    w = client.post(f"/api/projects/{pid}/wizard/steps/files/visit").json()
    shapes = _file(w, "geo_parcels")  # the base is named as OpenAVMKit requires
    assert shapes["filename"] == "shapes.parquet" and shapes["base"] and shapes["holds"] == "parcels"
    assert shapes["id_column"] == "PARCEL_ID"
    assert shapes["id_check"] == {"ok": True, "text": "✓ 6 parcels, all different · has shapes"}
    cama = _file(w, "cama")
    assert (cama["holds"], cama["id_column"]) == ("parcels", "PROP_ID")
    assert cama["id_check"]["text"] == "✓ one row per parcel · 83% match parcels"
    sales = _file(w, "sales")
    assert (sales["holds"], sales["id_column"]) == ("sales", "PROP_ID")
    assert sales["id_check"]["text"] == "100% of sales match a parcel"
    permits = _file(w, "permits")
    assert permits["holds"] == "unused" and permits["id_check"]["text"] == "several rows per parcel"
    assert w["sale_id"] == {"file": "sales", "column": None, "made": True, "check": w["sale_id"]["check"]}
    assert w["sale_id"]["check"]["ok"] is False  # made from parcel ID + sale date, and no sale date yet

    merge = _settings(pid)["data"]["process"]["merge"]
    assert merge == {"universe": ["geo_parcels", "cama"], "sales": ["sales"]}


def test_a_file_with_repeats_cant_hold_parcels_and_one_sales_file(client, pid):
    client.post(f"/api/projects/{pid}/wizard/steps/files/visit")
    r = client.put(f"/api/projects/{pid}/wizard/files/permits", json={"holds": "parcels"})
    assert r.status_code == 422 and "several rows per parcel" in r.json()["detail"]
    r = client.put(f"/api/projects/{pid}/wizard/files/cama", json={"holds": "sales"})
    assert r.status_code == 422 and "Only one file" in r.json()["detail"]


def test_field_steps_guess_by_name_once_and_check_types(client, pid):
    client.post(f"/api/projects/{pid}/wizard/steps/files/visit")
    w = client.post(f"/api/projects/{pid}/wizard/steps/building_age/visit").json()
    year = _field(w, "bldg_year_built")
    assert year["sources"] == [{"file": "cama", "column": "YR_BLT"}]
    assert year["check"] == {"ok": True, "text": "✓ years 1954–2011"}
    assert _field(w, "bldg_age_years")["hidden"]  # worked out from year built

    w = client.post(f"/api/projects/{pid}/wizard/steps/building_quality/visit").json()
    assert _field(w, "bldg_quality_txt")["sources"] == [{"file": "cama", "column": "QUALITY"}]
    assert _field(w, "bldg_quality_num")["sources"] == []  # text, so not the number field

    # A choice of (none) is never replaced by a guess.
    client.put(f"/api/projects/{pid}/wizard/fields/bldg_year_built", json={})
    w = client.post(f"/api/projects/{pid}/wizard/steps/building_age/visit").json()
    assert _field(w, "bldg_year_built")["sources"] == []

    r = client.put(f"/api/projects/{pid}/wizard/fields/bldg_year_built", json={"file": "cama", "column": "NBHD"})
    assert r.status_code == 422 and "not numbers" in r.json()["detail"]
    r = client.put(f"/api/projects/{pid}/wizard/fields/sale_price", json={"file": "cama", "column": "LIVING_AREA"})
    assert r.status_code == 422 and "sales file" in r.json()["detail"]


def test_sales_with_assumptions_and_the_review(client, pid):
    client.post(f"/api/projects/{pid}/wizard/steps/files/visit")
    w = client.post(f"/api/projects/{pid}/wizard/steps/sales/visit").json()
    assert _field(w, "sale_price")["sources"] == [{"file": "sales", "column": "SALE_PRICE"}]
    assert _field(w, "sale_date")["check"] == {"ok": True, "text": "✓ reads as month/day/year"}
    assert "No valid sale." in w["problems"] and "No vacant sale." in w["problems"]
    for key in ("valid_sale", "vacant_sale"):
        w = client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True}).json()
        assert _field(w, key)["assumed"]
    assert w["sale_id"]["check"] == {"ok": True, "text": "from parcel ID + sale date"}
    assert client.post(f"/api/projects/{pid}/wizard/steps/sales/skip").status_code == 422

    entry = _settings(pid)["data"]["load"]["sales"]
    assert entry["dupes"] == {"subset": ["key_sale"], "sort_by": ["key_sale", "asc"], "drop": True}
    assert entry["calc"] == {
        "key_sale": ["join", ["values", "key", "sale_date"], "str:-"],
        "valid_sale": ["set", True],
        "vacant_sale": ["set", False],
    }
    assert entry["load"]["sale_date"] == ["SALE_DT", "datetime", "%m/%d/%Y"]
    assert {"file": "cama", "columns": ["YR_BLT", "LIVING_AREA", "NBHD", "QUALITY", "OWNER_NAME"]} in w["not_loaded"]


def test_skip_and_advanced_view_conflicts(client, pid):
    client.post(f"/api/projects/{pid}/wizard/steps/files/visit")
    client.post(f"/api/projects/{pid}/wizard/steps/location/visit")
    w = client.post(f"/api/projects/{pid}/wizard/steps/location/skip").json()
    assert next(s for s in w["steps"] if s["key"] == "location")["status"] == "skipped"
    assert _field(w, "neighborhood")["sources"] == []
    # The same field loaded from two parcel files (possible in the Advanced view) is a conflict.
    for name, col in (("cama", "NBHD"), ("geo_parcels", "ZONE")):
        load = projects.load(pid).model_copy().files
        entry = next(f for f in load if f.name == name)
        r = client.put(
            f"/api/projects/{pid}/files/{name}/load", json={"load": {**entry.load, "neighborhood": [col, "string"]}}
        )
        assert r.status_code == 200
    w = client.get(f"/api/projects/{pid}/wizard").json()
    assert _field(w, "neighborhood")["check"] == {"ok": False, "text": "loaded from more than one file"}


def test_openavmkit_loads_and_joins_what_the_wizard_wrote(client, pid, monkeypatch):
    client.post(f"/api/projects/{pid}/wizard/steps/files/visit")
    for step in ("land", "building_age", "building_size", "sales"):
        client.post(f"/api/projects/{pid}/wizard/steps/{step}/visit")
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True})
    w = client.get(f"/api/projects/{pid}/wizard").json()
    assert w["problems"] == []

    from openavmkit.data import _merge_dict_of_dfs
    from openavmkit.pipeline import load_dataframes, load_settings

    monkeypatch.chdir(projects.project_dir(pid))
    settings = load_settings("in/settings.json")
    dfs = load_dataframes(settings)
    merge = settings["data"]["process"]["merge"]
    univ = _merge_dict_of_dfs(dfs, merge["universe"], settings, required_key="key")
    sales = _merge_dict_of_dfs(dfs, merge["sales"], settings, required_key="key_sale")
    assert len(univ) == 6 and univ["bldg_year_built"].notna().sum() == 5  # every parcel kept; 5 have CAMA
    assert {"geometry", "zoning", "bldg_area_finished_sqft"} <= set(univ.columns)
    assert len(sales) == 4  # both sales of 0012-001 kept: de-duplicated on the sale ID, not the parcel
    assert sales["key_sale"].tolist()[0] == "0012-001-2023-03-14"
    assert bool(sales["valid_sale"].all()) and not bool(sales["vacant_sale"].any())
    assert os.path.basename(settings["data"]["load"]["geo_parcels"]["filename"]) == "shapes.parquet"

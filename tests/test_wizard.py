"""F3d the Fields wizard (SPEC §3.0): roles, parcel IDs and joins, guesses, and what OpenAVMKit gets."""

import json

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
        {"PARCEL_ID": IDS, "MAP_NO": [f"M{n}" for n in range(6)], "ZONE": ["R1", "R1", "R2", "C1", "R1", "R2"]},
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
    # Sales that only carry the second ID (a map number).
    pd.DataFrame(
        {
            "MAP_NO": ["M0", "M0", "M3"],
            "PRICE": [185000, 210000, 240000],
            "DATE": ["2023-03-14", "2024-11-02", "2025-06-30"],
        }
    ).to_csv(folder / "sales_by_map.csv", index=False)


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    _files(tmp_path)
    for name in ("shapes", "cama", "sales", "permits", "sales_by_map"):
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


def _put_file(client, pid, name, **body):
    return client.put(f"/api/projects/{pid}/wizard/files/{name}", json=body)


def _start(client, pid):
    """The parcel universe and the sales, as the first two steps set them."""
    assert _put_file(client, pid, "shapes", universe=True).status_code == 200
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    assert _put_file(client, pid, "sales", holds="sales").status_code == 200
    return client.post(f"/api/projects/{pid}/wizard/steps/sales/visit").json()


def test_universe_then_sales(client, pid):
    r = _put_file(client, pid, "cama", universe=True)
    assert r.status_code == 422 and "no shapes" in r.json()["detail"]
    w = _start(client, pid)
    base = _file(w, "geo_parcels")  # the universe is named as OpenAVMKit requires
    assert base["filename"] == "shapes.parquet" and base["base"] and base["id_column"] == "PARCEL_ID"
    assert base["id_check"] == {"ok": True, "text": "✓ 6 parcels, all different · has shapes"}
    sales = _file(w, "sales")
    assert (sales["holds"], sales["match"], sales["id_column"]) == ("sales", "key", "PROP_ID")
    assert sales["id_check"]["text"] == "100% of sales match a parcel"
    assert w["sale_id"]["made"] and w["sale_id"]["check"] == {"ok": True, "text": "from parcel ID + sale date"}
    assert _field(w, "sale_price")["sources"] == [{"file": "sales", "column": "SALE_PRICE"}]
    assert _field(w, "sale_date")["check"] == {"ok": True, "text": "✓ reads as month/day/year"}
    assert "No valid sale." in w["problems"] and "No vacant sale." in w["problems"]
    assert "No building area (finished) in square feet: a model needs it." in w["problems"]
    merge = _settings(pid)["data"]["process"]["merge"]
    assert merge == {"universe": ["geo_parcels"], "sales": ["sales"]}


def test_a_field_from_another_file_with_its_key(client, pid):
    _start(client, pid)
    # "It's in another file": the file, its ID column, then the field.
    w = _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID").json()
    assert _file(w, "cama")["id_check"]["text"] == "✓ one row per parcel · 83% match parcels"
    r = client.put(
        f"/api/projects/{pid}/wizard/fields/bldg_area_finished_sqft", json={"file": "cama", "column": "LIVING_AREA"}
    )
    w = r.json()
    assert _field(w, "bldg_area_finished_sqft")["sources"] == [{"file": "cama", "column": "LIVING_AREA"}]
    assert not any("a model needs it" in p for p in w["problems"])
    assert w["warnings"] == [  # Big five not visited yet, so nothing guessed for these
        "No building year built: recommended for a good model.",
        "No building quality: recommended for a good model.",
        "No building condition: recommended for a good model.",
    ]
    r = _put_file(client, pid, "permits", holds="parcels", id_column="PROP_ID")
    assert r.status_code == 422 and "several rows per parcel" in r.json()["detail"]
    assert _settings(pid)["data"]["process"]["merge"]["universe"] == ["geo_parcels", "cama"]


def test_guesses_once_and_type_checks(client, pid):
    _start(client, pid)
    _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID")
    w = client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit").json()
    assert _field(w, "bldg_year_built")["sources"] == [{"file": "cama", "column": "YR_BLT"}]
    assert _field(w, "bldg_year_built")["check"] == {"ok": True, "text": "✓ years 1954–2011"}
    assert _field(w, "bldg_age_years")["hidden"]
    assert _field(w, "bldg_quality_txt")["sources"] == [{"file": "cama", "column": "QUALITY"}]
    client.put(f"/api/projects/{pid}/wizard/fields/bldg_year_built", json={})
    w = client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit").json()
    assert _field(w, "bldg_year_built")["sources"] == []  # (none) is never replaced by a guess
    r = client.put(f"/api/projects/{pid}/wizard/fields/bldg_year_built", json={"file": "cama", "column": "NBHD"})
    assert r.status_code == 422 and "not numbers" in r.json()["detail"]


def test_sales_assumptions_and_settings(client, pid):
    _start(client, pid)
    for key in ("valid_sale", "vacant_sale"):
        w = client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True}).json()
        assert _field(w, key)["assumed"]
    assert client.post(f"/api/projects/{pid}/wizard/steps/sales/skip").status_code == 422
    entry = _settings(pid)["data"]["load"]["sales"]
    assert entry["dupes"] == {"subset": ["key_sale"], "sort_by": ["key_sale", "asc"], "drop": True}
    assert entry["calc"] == {
        "key_sale": ["join", ["values", "key", "sale_date"], "str:-"],
        "valid_sale": ["set", True],
        "vacant_sale": ["set", False],
    }


def _engine(pid, monkeypatch):
    from openavmkit.data import _merge_dict_of_dfs, _perform_ref_tables
    from openavmkit.pipeline import load_dataframes, load_settings

    monkeypatch.chdir(projects.project_dir(pid))
    settings = load_settings("in/settings.json")
    dfs = load_dataframes(settings)
    process = settings["data"]["process"]
    univ = _merge_dict_of_dfs(dfs, process["merge"]["universe"], settings, required_key="key")
    sales = _merge_dict_of_dfs(dfs, process["merge"]["sales"], settings, required_key="key_sale")
    ref = process.get("enrich", {}).get("ref_tables", {}).get("sales", [])
    return univ, _perform_ref_tables(sales, ref, dfs) if ref else sales


def test_openavmkit_loads_and_joins_what_the_wizard_wrote(client, pid, monkeypatch):
    _start(client, pid)
    _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID")
    for step in ("big_five", "land"):
        client.post(f"/api/projects/{pid}/wizard/steps/{step}/visit")
    client.put(
        f"/api/projects/{pid}/wizard/fields/bldg_area_finished_sqft", json={"file": "cama", "column": "LIVING_AREA"}
    )
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True})
    assert client.get(f"/api/projects/{pid}/wizard").json()["problems"] == []
    univ, sales = _engine(pid, monkeypatch)
    assert len(univ) == 6 and univ["bldg_year_built"].notna().sum() == 5  # every parcel kept; 5 have CAMA
    assert {"geometry", "bldg_area_finished_sqft"} <= set(univ.columns)
    assert len(sales) == 4  # both sales of 0012-001 kept: de-duplicated on the sale ID, not the parcel
    assert sales["key_sale"].tolist()[0] == "0012-001-2023-03-14"


def test_sales_matched_by_the_second_id(client, pid, monkeypatch):
    assert _put_file(client, pid, "shapes", universe=True, key2_column="MAP_NO", key2_set=True).status_code == 200
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    _put_file(client, pid, "sales_by_map", holds="sales")
    w = client.post(f"/api/projects/{pid}/wizard/steps/sales/visit").json()
    sales = _file(w, "sales_by_map")
    assert (sales["match"], sales["id_column"]) == ("key2", "MAP_NO")
    assert sales["id_check"]["text"] == "100% of sales match a parcel"
    process = _settings(pid)["data"]["process"]
    assert process["enrich"]["ref_tables"]["sales"] == [
        {"id": "geo_parcels", "key_ref_table": "key2", "key_target": "key2", "add_fields": ["key"]}
    ]
    client.put(f"/api/projects/{pid}/wizard/fields/sale_price", json={"file": "sales_by_map", "column": "PRICE"})
    client.put(f"/api/projects/{pid}/wizard/fields/sale_date", json={"file": "sales_by_map", "column": "DATE"})
    _, sales_df = _engine(pid, monkeypatch)
    assert sales_df["key"].tolist() == ["0012-001", "0012-001", "0012-004"]  # looked up by map number
    assert sales_df["key_sale"].tolist()[0] == "M0-2023-03-14"


def test_names_say_the_jurisdiction(client, pid):
    w = client.get(f"/api/projects/{pid}/wizard").json()
    jurisdiction = projects.load(pid).jurisdiction
    assert _field(w, "assr_land_value")["name"] == f"{jurisdiction} land value"
    plain = {f["key"]: f for f in client.get("/api/dictionary").json()}
    assert plain["assr_land_value"]["name"] == "Assessor's land value"


def test_guesses_come_when_the_file_is_added_after_the_step_is_shown(client, pid):
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    client.post(f"/api/projects/{pid}/wizard/steps/sales/visit")  # no sales file yet: nothing decided
    w = _put_file(client, pid, "shapes", universe=True).json()
    assert _file(w, "geo_parcels")["id_column"] == "PARCEL_ID"
    w = _put_file(client, pid, "sales", holds="sales").json()
    assert _file(w, "sales")["id_column"] == "PROP_ID"
    assert _field(w, "sale_price")["sources"] == [{"file": "sales", "column": "SALE_PRICE"}]
    # Big five seen with only the universe; adding the CAMA file for one field picks up the rest.
    client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit")
    w = _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID").json()
    assert _field(w, "bldg_year_built")["sources"] == [{"file": "cama", "column": "YR_BLT"}]

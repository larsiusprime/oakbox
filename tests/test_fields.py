"""F3c Choosing a file's fields (SPEC §3.0): previews, the dictionary, and the entry's load."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from test_data_files import NEW, _settings

from oakbox import projects
from oakbox.app import create_app


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    pd.DataFrame(
        {
            "PIN": ["0012-001", "0012-002", "0013-001"],
            "PRICE": [185000, 92500, 240000],
            "SALEDT": ["03/14/2025", "11/02/2024", ""],
            "VAC": ["Y", "N", "Y"],
            "YEAR": ["1987", "", "2003"],  # pandas reads a number column with a blank as 1987.0
        }
    ).to_csv(tmp_path / "cama.csv", index=False)
    body = {"path": str(tmp_path / "cama.csv"), "mode": "copy", "name": "cama"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    return pid


LOAD = {
    "key": ["PIN", "string"],
    "sale_price": ["PRICE", "float"],
    "sale_date": ["SALEDT", "datetime", "%m/%d/%Y"],
    "is_vacant": ["VAC", "bool", "na_false"],
}


def test_columns_preview_types_samples_and_date_formats(client, pid):
    r = client.get(f"/api/projects/{pid}/files/cama/columns").json()
    cols = {c["name"]: c for c in r["columns"]}
    assert r["rows"] is None and not r["geometry"]  # CSV: no row count without reading it all
    assert cols["PRICE"]["type"] == "number" and cols["PIN"]["type"] == "text"
    assert cols["SALEDT"]["samples"] == ["03/14/2025", "11/02/2024"]  # blanks left out
    assert cols["SALEDT"]["date_format"] == "%m/%d/%Y" and cols["PIN"]["date_format"] is None
    assert cols["YEAR"]["type"] == "number" and cols["YEAR"]["samples"] == ["1987", "2003"]  # as written


def test_load_is_written_as_openavmkit_reads_it(client, pid, monkeypatch):
    assert client.put(f"/api/projects/{pid}/files/cama/load", json={"load": LOAD}).status_code == 200
    entry = _settings(pid)["data"]["load"]["cama"]
    assert entry["load"] == LOAD
    files = {f["name"]: f for f in client.get(f"/api/projects/{pid}").json()["files"]}
    assert files["cama"]["fields_loaded"] == 4 and files["cama"]["columns"] == 5

    from openavmkit.data import load_dataframe

    monkeypatch.chdir(projects.project_dir(pid))
    df = load_dataframe(entry, {})
    assert df is not None
    assert {"key", "sale_price", "sale_date", "is_vacant"} <= set(df.columns)  # plus sale_year etc., derived
    assert df["sale_date"].iloc[0] == pd.Timestamp("2025-03-14")
    assert df["is_vacant"].tolist() == [True, False, True]  # "Y"/"N" from a CSV (engine/csv-bool)


def test_a_bare_column_is_written_as_a_string(client, pid):
    assert client.put(f"/api/projects/{pid}/files/cama/load", json={"load": {"key": ["PIN"]}}).status_code == 200
    assert _settings(pid)["data"]["load"]["cama"]["load"] == {"key": "PIN"}


@pytest.mark.parametrize(
    "load",
    [
        {"Sale Price": ["PRICE", "float"]},  # not a valid field name
        {"sale_date": ["SALEDT", "datetime"]},  # a date needs its format
        {"is_vacant": ["VAC", "bool"]},  # yes/no needs blank handling
        {"is_vacant": ["VAC", "bool", "maybe"]},
        {"sale_price": ["PRICE", "money"]},  # not a type OpenAVMKit casts to
        {"sale_price": ["PRICE", "float", "%Y"]},  # only dates and yes/no take a third item
        {"a": ["PIN"], "b": ["PIN"]},  # one column, two fields
    ],
)
def test_incomplete_or_unreadable_loads_are_refused(client, pid, load):
    assert client.put(f"/api/projects/{pid}/files/cama/load", json={"load": load}).status_code == 422
    assert "load" not in _settings(pid)["data"]["load"]["cama"]


def test_date_format_check_reads_like_openavmkit(client):
    r = client.post("/api/date-format", json={"samples": ["03/14/2025", "2025-03-14"], "format": "%m/%d/%Y"})
    assert r.json()["parsed"] == ["2025-03-14", None]


def test_dictionary_offers_openavmkit_fields(client):
    fields = {f["key"]: f for f in client.get("/api/dictionary").json()}
    assert fields["sale_price"]["name"] == "Sale price" and fields["sale_price"]["groups"] == ["sale"]
    assert "land_area_sqft" in fields  # "either": computed only when missing
    assert "model_group" not in fields and "sale_year" not in fields  # "derived": always computed


def test_rename_and_remove_keep_the_load(client, pid):
    client.put(f"/api/projects/{pid}/files/cama/load", json={"load": LOAD})
    client.put(f"/api/projects/{pid}/files/cama/name", json={"name": "cama_2026"})
    assert _settings(pid)["data"]["load"]["cama_2026"]["load"] == LOAD


def test_columns_preview_a_geopackage_layer(client, tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    pid = client.post("/api/projects", json=NEW | {"name": "GIS"}).json()["id"]
    gdf = gpd.GeoDataFrame({"PIN": ["1", "2"], "ACRES": [0.5, 1.0]}, geometry=[box(0, 0, 1, 1)] * 2, crs=4326)
    gdf.to_file(tmp_path / "county.gpkg", layer="parcels")
    gdf.to_file(tmp_path / "county.gpkg", layer="roads")
    body = {"path": str(tmp_path / "county.gpkg"), "mode": "copy", "name": "county", "layer": "parcels"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    r = client.get(f"/api/projects/{pid}/files/county/columns").json()
    assert r["rows"] == 2 and r["geometry"]
    assert [(c["name"], c["type"]) for c in r["columns"]] == [("PIN", "text"), ("ACRES", "number")]

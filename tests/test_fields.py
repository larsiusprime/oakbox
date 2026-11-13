"""Reading a file's columns (their types, samples and date formats), dates as OpenAVMKit reads them, and its data
dictionary: what the Data wizard is built on."""

import pandas as pd
import pytest
from helpers import NEW

from oakbox import fields, projects


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


def _columns(pid, name, layer=None):
    return fields.columns(projects.project_dir(pid) / "in" / name, layer)


def test_columns_preview_types_samples_and_date_formats(pid):
    r = _columns(pid, "cama.csv")
    cols = {c.name: c for c in r.columns}
    assert r.rows is None and not r.geometry  # CSV: no row count without reading it all
    assert cols["PRICE"].type == "number" and cols["PIN"].type == "text"
    assert cols["SALEDT"].samples == ["03/14/2025", "11/02/2024"]  # blanks left out
    assert cols["SALEDT"].date_format == "%m/%d/%Y" and cols["PIN"].date_format is None
    assert cols["YEAR"].type == "number" and cols["YEAR"].samples == ["1987", "2003"]  # as written


def test_date_format_check_reads_like_openavmkit():
    assert fields.check_dates(["03/14/2025", "2025-03-14"], "%m/%d/%Y").parsed == ["2025-03-14", None]


def test_dictionary_offers_openavmkit_fields():
    found = {f.key: f for f in fields.dictionary()}
    assert found["sale_price"].name == "Sale price" and found["sale_price"].groups == ["sale"]
    offered = {k for k, f in found.items() if f.offered}
    assert {"sale_price", "land_area_sqft"} <= offered  # input; either (computed only when missing)
    # derived (always computed), reserved (kept for computed values), and dist_to_* (computed when configured)
    assert not offered & {"model_group", "sale_year", "model_market_value", "osm_is_corner_lot", "dist_to_cbd"}
    assert found["model_group"].source == "derived" and found["model_market_value"].source == "reserved"


def test_columns_preview_a_geopackage_layer(client, tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    pid = client.post("/api/projects", json=NEW | {"name": "GIS"}).json()["id"]
    gdf = gpd.GeoDataFrame({"PIN": ["1", "2"], "ACRES": [0.5, 1.0]}, geometry=[box(0, 0, 1, 1)] * 2, crs=4326)
    gdf.to_file(tmp_path / "county.gpkg", layer="parcels")
    gdf.to_file(tmp_path / "county.gpkg", layer="roads")
    body = {"path": str(tmp_path / "county.gpkg"), "mode": "copy", "name": "county", "layer": "parcels"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    r = _columns(pid, "county.gpkg", "parcels")
    assert r.rows == 2 and r.geometry
    assert [(c.name, c.type) for c in r.columns] == [("PIN", "text"), ("ACRES", "number")]


def test_a_database_timestamp_reads_as_a_date():
    """2020-03-10 00:00:00.000 (a database export's, to the millisecond) reads as a date, by itself."""
    samples = ["2020-03-10 00:00:00.000", "2020-02-28 00:00:00.000"]
    fmt = next(f for f in fields.DATE_FORMATS if fields._reads(samples, f))
    assert fmt == "%Y-%m-%d %H:%M:%S.%f"
    assert fields.check_dates(samples, fmt).parsed == ["2020-03-10", "2020-02-28"]


def test_a_date_no_usual_format_reads_can_still_be_chosen():
    """A text column none of the usual formats reads can still be the date: its own format is picked after."""
    from oakbox.fields import Column
    from oakbox.wizard.checks import field_check
    from oakbox.wizard.files import dictionary_by_key

    d = dictionary_by_key()["sale_date"]
    check, spec = field_check(d, Column(name="WHEN", type="text", samples=["10.03.2020 h0"], date_format=None))
    assert check.ok and check.warn and "pick its format" in check.text
    assert spec == ["WHEN", "datetime", "%Y-%m-%d"]
    check, spec = field_check(d, Column(name="N", type="number", samples=["5"], date_format=None))
    assert not check.ok and spec is None

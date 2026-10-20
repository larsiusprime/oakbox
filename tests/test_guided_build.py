"""Your files and Stitch on synthetic data: a PACS-style export, a parcel map, a sales file."""

import zipfile

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from oakbox import fixedwidth, projects, worker
from oakbox.app import create_app

LAYOUT = "pacs-legacy-8.0.33"


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(worker, "emit", lambda *a, **k: None)
    return tmp_path


def _record(member: str, values: dict[str, str]) -> bytes:
    spec = fixedwidth.layout_file(LAYOUT, member)
    line = bytearray(b" " * spec["record_length"])
    for f in spec["fields"]:
        v = values.get(f["name"])
        if v is not None:
            line[f["start"] - 1 : f["start"] - 1 + f["width"]] = v.ljust(f["width"])[: f["width"]].encode()
    return bytes(line) + b"\r\n"


def make_export(path, n=30):
    """A tiny PACS export: n real properties (one with two owners), 3 personal-property accounts, land segments."""
    prop = b""
    for i in range(1, n + 1):
        prop += _record(
            "PROP.TXT", {"prop_id": f"{i:012d}", "prop_type_cd": "R", "sup_num": "0", "market_value": "100000"}
        )
    prop += _record("PROP.TXT", {"prop_id": f"{1:012d}", "prop_type_cd": "R", "sup_num": "3", "market_value": "150000"})
    for i in range(900, 903):
        prop += _record("PROP.TXT", {"prop_id": f"{i:012d}", "prop_type_cd": "P", "sup_num": "0"})
    land = b"".join(
        _record("LAND_DET.TXT", {"prop_id": f"{i:012d}", "land_seg_id": str(i * 10 + k), "size_acres": "0.5"})
        for i in range(1, n + 1)
        for k in range(2)
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("PROP.TXT", prop)
        z.writestr("LAND_DET.TXT", land)
        z.writestr("APPR_HDR.TXT", _record("APPR_HDR.TXT", {}))
    return path


def make_map(path, n=30, missing=(5, 6)):
    """Map IDs without the export's zero padding; two parcels missing; one ID drawn as two polygons."""
    rows = [{"PID": str(i), "geometry": box(i, 0, i + 1, 1)} for i in range(1, n + 1) if i not in missing]
    rows.append({"PID": "7", "geometry": box(7, 1, 8, 2)})
    rows.append({"PID": "0", "geometry": box(0, 5, 1, 6)})  # a polygon with a zeroed ID
    gpd.GeoDataFrame(rows, crs="EPSG:4326").to_parquet(path)
    return path


def test_pacs_export_is_detected_and_converted(tmp_path):
    z = make_export(tmp_path / "export.zip")
    e = fixedwidth.detect_export(z)
    assert e is not None and e.layout_id == LAYOUT
    assert [m.member for m in e.members if m.used_by_default] == ["PROP.TXT", "LAND_DET.TXT"]
    out = tmp_path / "prop.parquet"
    cols = fixedwidth.default_columns(LAYOUT, "PROP.TXT")
    assert "py_owner_name" not in cols  # owner names are left out by default
    n = fixedwidth.convert(z, "PROP.TXT", LAYOUT, cols, {"prop_id"}, out, block_records=7)
    df = pd.read_parquet(out)
    assert n == len(df) == 34
    assert df["prop_id"].iloc[0] == "000000000001"  # IDs keep their zeros
    assert df["market_value"].iloc[0] == 100000.0  # numbers become numbers


def test_files_and_stitch_through_the_api(tmp_path):
    client = TestClient(create_app())
    pid = client.post("/api/projects", json={"name": "Test County"}).json()["id"]
    basics = {
        "name": "Test County",
        "state": "TX",
        "tax_year": 2026,
        "units": "imperial",
        "valuation_date": "2026-01-01",
    }
    assert client.put(f"/api/projects/{pid}/basics", json=basics).status_code == 200
    assert client.post(f"/api/projects/{pid}/stages/basics/confirm").status_code == 200

    z = make_export(tmp_path / "export.zip")
    insp = client.post("/api/inspect", json={"path": str(z)}).json()
    assert insp["format"] == "fixed_width" and insp["export"]["layout_id"] == LAYOUT
    r = client.post(f"/api/projects/{pid}/exports", json={"path": str(z), "members": ["PROP.TXT", "LAND_DET.TXT"]})
    assert r.status_code == 200
    m = make_map(tmp_path / "map.geoparquet")
    insp = client.post("/api/inspect", json={"path": str(m)}).json()
    assert insp["suggested_uses"] == ["parcel_map"] and insp["suggested_id_column"] == "PID"
    r = client.post(
        f"/api/projects/{pid}/files",
        json={"path": str(m), "name": "map.geoparquet", "uses": ["parcel_map"], "id_columns": ["PID"]},
    )
    project = r.json()
    assert project["setup"]["stitch"]["spine"] == "map"

    worker.run(pid, "check_files")  # what the Check button's job does
    assert client.post(f"/api/projects/{pid}/stages/files/confirm").status_code == 200

    worker.run(pid, "check_stitch")
    rep = client.get(f"/api/projects/{pid}/stages/stitch/check").json()
    assert rep["fresh"]
    prop = next(f for f in rep["stitch"]["files"] if f["file"] == "prop")
    assert prop["filtered_out"] == 3  # personal property left out by the PACS default
    assert prop["matched"] == 0 and prop["suggestion"]["fixes"] == [{"op": "strip_leading_zeros", "width": None}]

    # Apply the suggested fix to every file, as the Stitch screen does.
    stitch = project["setup"]["stitch"] | {
        "id_fixes": {f: [{"op": "strip_leading_zeros"}] for f in ["prop", "land-det", "map"]}
    }
    client.put(f"/api/projects/{pid}/stitch", json=stitch)
    assert not client.get(f"/api/projects/{pid}/stages/stitch/check").json()["fresh"]
    worker.run(pid, "check_stitch")
    rep = client.get(f"/api/projects/{pid}/stages/stitch/check").json()["stitch"]
    assert rep["spine"]["blank_ids"] == 1 and rep["spine"]["polygons_merged"] == 1
    prop = next(f for f in rep["files"] if f["file"] == "prop")
    assert prop["matched"] == 28 and prop["only_here"] == 2 and prop["collapsed_away"] == 1
    land = next(f for f in rep["files"] if f["file"] == "land-det")
    assert land["collapsed_away"] == 30 and rep["parcels"] == 28
    assert client.post(f"/api/projects/{pid}/stages/stitch/confirm").status_code == 200

    # The write path produces exactly what Check predicted, with the latest supplement kept.
    from oakbox import stitcher

    project = projects.load(pid)
    written = stitcher.run(projects.project_dir(pid), project.setup, write=True)
    out = projects.project_dir(pid) / "in" / "stitched"
    parcels = pd.read_parquet(out / "parcels.parquet")
    geo = gpd.read_parquet(out / "geo_parcels.geoparquet")
    assert len(parcels) == len(geo) == written.parcels == 28
    assert parcels.set_index("key").loc["1", "market_value"] == 150000.0
    assert parcels.set_index("key").loc["1", "size_acres"] == 1.0  # two segments summed
    assert geo.set_index("key").loc["7"].geometry.area == 2.0  # two polygons merged
    hood = client.get(f"/api/projects/{pid}/stages/stitch/under-the-hood").json()
    assert hood[0]["content"]["spine"] == "map"

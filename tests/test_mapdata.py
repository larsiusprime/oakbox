"""The map window's data (SPEC §3.15): shapes and centres made from the 🌐 Parcel Universe file, its fields, and a
field's values in the universe's order, joined from another parcel file on the parcel ID."""

import base64
import struct
import time

import numpy as np
import pytest
from helpers import NEW, start_wizard, wizard_files


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    wizard_files(tmp_path)
    for name in ("shapes", "cama", "sales"):
        ext = "parquet" if name == "shapes" else "csv"
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    return pid


def _ready(client, pid) -> dict:
    for _ in range(100):
        m = client.get(f"/api/projects/{pid}/map").json()
        if m["status"] != "making":
            return m
        time.sleep(0.1)
    raise AssertionError("never ready")


def test_no_map_without_a_universe(client, pid):
    assert client.get(f"/api/projects/{pid}/map").json()["status"] == "none"


def test_shapes_centres_and_fields(client, pid):
    assert (
        client.put(
            f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/projects/{pid}/wizard/files/cama", json={"holds": "parcels", "id_column": "PROP_ID"}
        ).status_code
        == 200
    )
    m = _ready(client, pid)
    assert m["status"] == "ready" and m["parcels"] == 6
    assert m["bounds"] == [[0.0, 0.0], [6.0, 1.0]]
    xy = np.frombuffer(client.get(f"/api/projects/{pid}/map/centres").content, dtype="<f4").reshape(-1, 2)
    assert xy.tolist() == [[i + 0.5, 0.5] for i in range(6)]  # each square's middle, in the file's order
    shapes = client.get(f"/api/projects/{pid}/map/shapes").content
    assert shapes[:8] == b"OAKSHP01" and struct.unpack("<4i", shapes[8:24])[0] == 6
    ids = {f["id"] for f in m["fields"]}
    assert {"geo_parcels:ZONE", "cama:LIVING_AREA", "cama:QUALITY"} <= ids
    assert "geo_parcels:PARCEL_ID" not in ids and "cama:PROP_ID" not in ids  # IDs aren't something to colour by


def test_a_number_joined_on_the_parcel_id(client, pid):
    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    client.put(f"/api/projects/{pid}/wizard/files/cama", json={"holds": "parcels", "id_column": "PROP_ID"})
    _ready(client, pid)
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "cama:LIVING_AREA"}).json()
    assert c["kind"] == "number" and c["have"] == 5
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    # CAMA's sixth row is another parcel's: the universe's sixth parcel has no value.
    assert v[:5].tolist() == [1500, 2200, 980, 1750, 3100] and np.isnan(v[5])
    assert c["quantiles"][0] == 980 and c["quantiles"][-1] == 3100 and len(c["auto"]) == 2


def test_a_category(client, pid):
    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    _ready(client, pid)
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "geo_parcels:ZONE"}).json()
    assert c["kind"] == "category" and c["categories"] == ["R1", "R2", "C1"] and c["counts"] == [3, 2, 1]
    codes = np.frombuffer(base64.b64decode(c["values"]), dtype="<u2").tolist()
    assert codes == [0, 0, 1, 2, 0, 1]


def test_unknown_field(client, pid):
    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    _ready(client, pid)
    assert client.get(f"/api/projects/{pid}/map/column", params={"field": "geo_parcels:NOPE"}).status_code == 404


def test_sales_at_their_parcels(client, pid):
    start_wizard(client, pid)  # the universe, and the sales with their price and date found
    m = _ready(client, pid)
    assert {"price", "year"} <= set(m["sales"])
    d = client.get(f"/api/projects/{pid}/map/sales").json()
    assert (d["sales"], d["placed"]) == (4, 4)
    parcel = np.frombuffer(base64.b64decode(d["parcel"]), dtype="<i4").tolist()
    assert parcel == [0, 0, 2, 3]  # each sale at its parcel's place in the universe
    price = np.frombuffer(base64.b64decode(d["price"]), dtype="<f4").tolist()
    assert price == [185000, 210000, 92500, 240000]
    year = np.frombuffer(base64.b64decode(d["year"]), dtype="<f4")
    assert [int(y) for y in year] == [2023, 2024, 2024, 2025] and 2023.19 < year[0] < 2023.21  # 14 March
    valid = np.frombuffer(base64.b64decode(d["valid"]), dtype="i1").tolist()
    assert valid == [-1] * 4  # no valid sale field or rule: unknown


def test_problems_where_they_are(client, pid):
    start_wizard(client, pid)
    _ready(client, pid)
    p = client.get(f"/api/projects/{pid}/map/problems").json()
    # The helper's parcels all have IDs, none repeated: no ID problems to show.
    assert not [x for x in p["items"] if x["id"] in ("pr:blank_ids", "pr:repeated_ids")]
    assert p["unplaced"] == 0
    assert client.get(f"/api/projects/{pid}/map/problem", params={"id": "pr:nope"}).status_code == 404


def test_blank_and_repeated_ids(client, pid, tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    gpd.GeoDataFrame(
        {"PID": ["A", "", "B", "B"]}, geometry=[box(i, 0, i + 1, 1) for i in range(4)], crs="EPSG:4326"
    ).to_parquet(tmp_path / "odd.parquet")
    body = {"path": str(tmp_path / "odd.parquet"), "mode": "copy", "name": "odd"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    client.put(f"/api/projects/{pid}/wizard/files/odd", json={"universe": True, "id_column": "PID"})
    _ready(client, pid)
    items = {x["id"]: x for x in client.get(f"/api/projects/{pid}/map/problems").json()["items"]}
    assert (items["pr:blank_ids"]["count"], items["pr:repeated_ids"]["count"]) == (1, 2)
    d = client.get(f"/api/projects/{pid}/map/problem", params={"id": "pr:repeated_ids"}).json()
    assert d["on"] == "pu" and np.frombuffer(base64.b64decode(d["flags"]), dtype="i1").tolist() == [0, 0, 1, 1]


def test_a_parcels_card(client, pid):
    start_wizard(client, pid)
    client.put(f"/api/projects/{pid}/wizard/files/cama", json={"holds": "parcels", "id_column": "PROP_ID"})
    _ready(client, pid)
    c = client.get(f"/api/projects/{pid}/map/parcel/0").json()
    assert c["index"] == 0 and c["key"]
    assert c["rows"]["cama"] == 1
    columns = {f["column"]: f["value"] for f in c["fields"]}
    assert columns["LIVING_AREA"] == "1500" and columns["ZONE"] == "R1"
    assert "PARCEL_ID" not in columns and "PROP_ID" not in columns  # its IDs are its title
    # Its two sales, the latest first, each with its date as YYYY-MM-DD.
    assert [s["date"] for s in c["sales"]] == ["2024-11-02", "2023-03-14"]
    assert [s["price"] for s in c["sales"]] == ["210000", "185000"]
    assert client.get(f"/api/projects/{pid}/map/parcel/99").status_code == 404


def test_a_column_from_the_steps_outputs(client, pid):
    """The app's own outputs (a nearby average the models' try made), on the parcels by "key"; listed under outs."""
    import pandas as pd
    from helpers import IDS

    from oakbox import projects

    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    _ready(client, pid)
    out = projects.project_dir(pid) / "out" / "models" / "all_model_groups"
    out.mkdir(parents=True)
    lag = [100.0, 200.0, None, 400.0]  # the last two parcels aren't in the output at all
    pd.DataFrame({"key": IDS[:4], "spatial_lag_x": lag, "geometry": ["g"] * 4}).to_parquet(out / "universe.parquet")
    ids = {f["id"] for f in client.get(f"/api/projects/{pid}/map").json()["outs"]}
    assert ids == {"out:modeled:spatial_lag_x"}  # the key and shapes aren't something to colour by
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "out:modeled:spatial_lag_x"}).json()
    assert c["kind"] == "number" and c["have"] == 3
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    assert v[[0, 1, 3]].tolist() == [100, 200, 400] and np.isnan(v[[2, 4, 5]]).all()
    for bad in ("out:modeled:nope", "out:modeled:key", "out:nowhere:spatial_lag_x"):
        assert client.get(f"/api/projects/{pid}/map/column", params={"field": bad}).status_code == 404


def test_permits_on_the_parcels(client, pid, tmp_path):
    """The permits file on the map: how many permits each parcel has (blank: none)."""
    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    body = {"path": str(tmp_path / "permits.csv"), "mode": "copy", "name": "permits"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    r = client.put(f"/api/projects/{pid}/wizard/files/permits", json={"holds": "permits", "id_column": "PROP_ID"})
    assert r.status_code == 200
    m = _ready(client, pid)
    assert "permits:count" in {f["id"] for f in m["fields"]}
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "permits:count"}).json()
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    assert c["kind"] == "number" and v[:2].tolist() == [2, 1] and np.isnan(v[2:]).all()

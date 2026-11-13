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


def test_an_output_column_with_pandas_own_blanks(client, pid):
    """A nullable column (Float64, Int64: blanks are pd.NA, which can't be compared) maps its blanks as blank."""
    import pandas as pd
    from helpers import IDS

    from oakbox import projects

    client.put(f"/api/projects/{pid}/wizard/files/shapes", json={"universe": True, "id_column": "PARCEL_ID"})
    _ready(client, pid)
    out = projects.project_dir(pid) / "out" / "models" / "all_model_groups"
    out.mkdir(parents=True)
    q = pd.array([1.0, None, 2.5, None], dtype="Float64")
    n = pd.array([3, None, 4, 5], dtype="Int64")
    pd.DataFrame({"key": IDS[:4], "bldg_quality_num": q, "rooms": n}).to_parquet(out / "universe.parquet")
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "out:modeled:bldg_quality_num"}).json()
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    assert c["have"] == 2 and v[[0, 2]].tolist() == [1, 2.5] and np.isnan(v[[1, 3, 4, 5]]).all()
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "out:modeled:rooms"}).json()
    assert c["have"] == 3


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


def test_what_bring_in_data_kept(client, pid):
    """Inputs on the map: each parcel brought in or left out, and its sales, from Bring in data's outputs (by key)."""
    import pandas as pd
    from helpers import IDS

    from oakbox import projects

    start_wizard(client, pid)
    _ready(client, pid)
    out = projects.project_dir(pid) / "out" / "oakbox" / "bring_in"
    out.mkdir(parents=True)
    pd.DataFrame({"key": IDS[:5]}).to_parquet(out / "universe.parquet")  # the last parcel left out
    pd.DataFrame({"key": [IDS[0], IDS[3]]}).to_parquet(out / "sales.parquet")  # sales on 0 (two), 2 and 3
    assert {"out:universe:@parcels", "out:universe:@sales"} <= {f["id"] for f in _ready(client, pid)["outs"]}

    def read(field):
        c = client.get(f"/api/projects/{pid}/map/column", params={"field": field}).json()
        codes = np.frombuffer(base64.b64decode(c["values"]), dtype="<u2").tolist()
        return [c["categories"][k] if k < len(c["categories"]) else "" for k in codes]

    assert read("out:universe:@parcels") == ["Brought in"] * 5 + ["Left out"]
    assert read("out:universe:@sales") == ["Some left out", "", "All left out", "All brought in", "", ""]


def test_a_value_per_size(client, pid):
    """A number per each parcel's building size (here the area itself: 1 each), blank where a parcel has none; the
    sales' prices per their parcel's size; the sizes there are listed."""
    start_wizard(client, pid)
    client.put(f"/api/projects/{pid}/wizard/files/cama", json={"holds": "parcels", "id_column": "PROP_ID"})
    r = client.put(
        f"/api/projects/{pid}/wizard/fields/bldg_area_finished_sqft",
        json={"file": "cama", "column": "LIVING_AREA", "area_unit": "sqft"},
    )
    assert r.status_code == 200
    m = _ready(client, pid)
    loaded = {f["field"]: f["id"] for f in m["fields"] if f["field"]}
    assert "bldg" in m["per"] and m["area_unit"] == "sqft"
    area = loaded["bldg_area_finished_sqft"]
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": area, "per": "bldg"}).json()
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    assert v[:5].tolist() == [1.0] * 5 and np.isnan(v[5]) and c["have"] == 5 and c["unsized"] == 0
    d = client.get(f"/api/projects/{pid}/map/sales", params={"per": "bldg"}).json()
    price = np.frombuffer(base64.b64decode(d["price"]), dtype="<f4")
    # Sales on parcels 0, 0, 2, 3: areas 1500, 1500, 980, 1750.
    assert np.allclose(price, [185000 / 1500, 210000 / 1500, 92500 / 980, 240000 / 1750])
    assert client.get(f"/api/projects/{pid}/map/column", params={"field": area, "per": "nope"}).status_code == 404
    # A land size loaded in acres is divided by in square feet (here YR_BLT read as acres, for a number to hand).
    r = client.put(
        f"/api/projects/{pid}/wizard/fields/land_area_sqft",
        json={"file": "cama", "column": "YR_BLT", "area_unit": "acres"},
    )
    assert r.status_code == 200, r.text
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": area, "per": "land"}).json()
    v = np.frombuffer(base64.b64decode(c["values"]), dtype="<f4")
    want = np.array([1500, 2200, 980, 1750, 3100]) / (np.array([1987, 2003, 1954, 1968, 2011]) * 43_560)
    assert np.allclose(v[:5], want)


def test_a_sales_column_by_the_latest_sale(client, pid):
    """The sales as brought in, on the parcels: each parcel by its latest sale's value; one with none, blank."""
    import pandas as pd
    from helpers import IDS

    from oakbox import projects

    start_wizard(client, pid)
    _ready(client, pid)
    out = projects.project_dir(pid) / "out" / "oakbox" / "bring_in"
    out.mkdir(parents=True)
    pd.DataFrame({"key": IDS}).to_parquet(out / "universe.parquet")
    pd.DataFrame(
        {
            "key": [IDS[0], IDS[0], IDS[2]],
            "key_sale": ["a", "b", "c"],
            "sale_date": pd.to_datetime(["2024-05-01", "2021-01-01", "2023-03-03"]),
            "deed_type": ["WD", "QC", "WD"],
        }
    ).to_parquet(out / "sales.parquet")
    ids = {f["id"] for f in _ready(client, pid)["outs"]}
    assert "out:sales:deed_type" in ids and "out:sales:key_sale" not in ids
    c = client.get(f"/api/projects/{pid}/map/column", params={"field": "out:sales:deed_type"}).json()
    codes = np.frombuffer(base64.b64decode(c["values"]), dtype="<u2").tolist()
    got = [c["categories"][k] if k < len(c["categories"]) else "" for k in codes]
    assert got == ["WD", "", "WD", "", "", ""]  # parcel 0's latest sale (2024) was a WD, not the 2021 QC


def test_a_sales_column_each_sale_and_its_twin_in_the_universe(client, pid):
    """The sales record's own columns (sc:<column>) are fields of the map too, a value per sale in /map/sales'
    order; one named as a parcel field is its twin, both ways, so the map can switch between them."""
    import pandas as pd
    from helpers import IDS

    from oakbox import projects

    pd.DataFrame(
        {
            "PROP_ID": [IDS[0], IDS[0], IDS[2], IDS[3]],
            "SALE_PRICE": [185000, 210000, 92500, 240000],
            "SALE_DT": ["03/14/2023", "11/02/2024", "01/09/2024", "06/30/2025"],
            "ZONE": ["R1", "R2", "R2", "C1"],
            "BEDS": [3, 4, 2, 5],
        }
    ).to_csv(projects.inputs_dir(pid) / "sales.csv", index=False)
    start_wizard(client, pid)
    m = _ready(client, pid)
    sc = {f["id"]: f for f in m["sale_fields"]}
    assert set(sc) == {"sc:ZONE", "sc:BEDS"}  # its IDs, price and date aren't columns again
    assert sc["sc:ZONE"]["twin"] == "geo_parcels:ZONE" and sc["sc:BEDS"]["twin"] is None
    assert next(f for f in m["fields"] if f["id"] == "geo_parcels:ZONE")["twin"] == "sc:ZONE"
    c = client.get(f"/api/projects/{pid}/map/sale-column", params={"field": "sc:BEDS"}).json()
    assert c["kind"] == "number" and np.frombuffer(base64.b64decode(c["values"]), dtype="<f4").tolist() == [3, 4, 2, 5]
    z = client.get(f"/api/projects/{pid}/map/sale-column", params={"field": "sc:ZONE"}).json()
    assert z["kind"] == "category" and set(z["categories"]) == {"R1", "R2", "C1"}
    assert client.get(f"/api/projects/{pid}/map/sale-column", params={"field": "sc:NOPE"}).status_code == 404

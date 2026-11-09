"""The map window's data (SPEC §3.15): shapes and centres made from the 🌐 Parcel Universe file, its fields, and a
field's values in the universe's order, joined from another parcel file on the parcel ID."""

import base64
import struct
import time

import numpy as np
import pytest
from helpers import NEW, wizard_files


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    wizard_files(tmp_path)
    for name in ("shapes", "cama"):
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

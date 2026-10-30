"""Fixtures the test files share: each test's own OAK box home, a client on the app, and a project whose data was
brought in. Plain helpers and constants are in helpers.py."""

import sys

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from helpers import NEW, wait
from shapely.geometry import box

from oakbox.app import create_app


@pytest.fixture(autouse=True)
def trash(tmp_path, monkeypatch):
    """Point send2trash at a per-test trash (Linux, where CI runs the tests).

    send2trash reads XDG_DATA_HOME once, when first imported, so setting the variable isn't enough.
    """
    data_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    if sys.platform == "linux":
        import send2trash.plat_other as plat_other

        monkeypatch.setattr(plat_other, "XDG_DATA_HOME", bytes(data_home))
        monkeypatch.setattr(plat_other, "HOMETRASH_B", bytes(data_home / "Trash"))
        monkeypatch.setattr(plat_other, "HOMETRASH", str(data_home / "Trash"))
    return data_home / "Trash" / "files"


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    """Each test's projects and app settings in a folder of its own (a file can override it)."""
    home = tmp_path / "home"
    monkeypatch.setenv("OAKBOX_HOME", str(home))
    return home


@pytest.fixture
def client():
    return TestClient(create_app())


# 40 parcels: houses, duplexes on residential land, condos, shops (one of them a house), and public land.
USES = ["RESIDENTIAL"] * 24 + ["CONDO"] * 8 + ["COMM"] * 6 + ["GOV OWNED"] * 2
TYPES = ["01-SFR"] * 20 + ["08-DUPLEX"] * 4 + ["04-CONDO"] * 8 + ["01-SFR"] + [""] * 5 + [""] * 2
AREAS = [1500.0 + 10 * i for i in range(33)] + [None] * 5 + [None] * 2


@pytest.fixture(scope="module")
def brought_in(tmp_path_factory):
    """A project whose data was brought in (OpenAVMKit's load and join, a few seconds), shared by a file's tests:
    (its folder, its id). Its home is the folder's home/, not each test's own: see brought_in_client."""
    tmp = tmp_path_factory.mktemp("groups")
    mp = pytest.MonkeyPatch()
    mp.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {
            "ID": [str(i) for i in range(40)],
            "LANDUSE": USES,
            "BLDGTYPE": TYPES,
            "AREA": AREAS,
            "SUBDIV": ["OAKS", "PINES"] * 20,
            "VALUE": [180_000 + 2_500 * i for i in range(40)],
        },
        geometry=[box(-79.8 + i * 0.001, 36.0, -79.8 + i * 0.001 + 0.0005, 36.0005) for i in range(40)],
        crs="EPSG:4326",
    ).to_parquet(tmp / "parcels.parquet")
    sold = [*range(20)] * 2 + [24, 25, 26, 27, 32, 33, 20]  # houses twice, condos, a shop, the house on COMM, a duplex
    pd.DataFrame(
        {
            "PID": [str(i) for i in sold],
            "PRICE": [200_000 + 1_000 * i for i in range(len(sold))],
            "DATE": [f"202{3 + i % 2}-0{1 + i % 9}-15" for i in range(len(sold))],
        }
    ).to_csv(tmp / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    client.put(f"/api/projects/{pid}/wizard/files/parcels", json={"universe": True, "id_column": "ID"})
    client.put(f"/api/projects/{pid}/wizard/files/sale", json={"holds": "sales", "id_column": "PID"})
    field = f"/api/projects/{pid}/wizard/fields"
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"{field}/{key}", json={"file": "sale", "column": col})
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"{field}/{key}", json={"assume": True})
    client.put(f"{field}/bldg_area_finished_sqft", json={"file": "geo_parcels", "column": "AREA", "area_unit": "sqft"})
    client.put(f"{field}/assr_market_value", json={"file": "geo_parcels", "column": "VALUE"})
    # The Property type step guesses land use and building type from the column names.
    w = client.post(f"/api/projects/{pid}/wizard/steps/property_type/visit").json()
    used = {f["key"]: f for f in w["fields"]}
    assert used["land_class"]["check"] and used["bldg_type"]["check"]
    # A field of the user's own, classified as about the land.
    body = {"file": "geo_parcels", "column": "SUBDIV", "group": "land", "type": "category"}
    assert client.put(f"/api/projects/{pid}/wizard/custom/subdivision", json=body).status_code == 200
    url = f"/api/projects/{pid}/bring-in"
    assert client.post(f"{url}/run").json()["status"] == "running"
    view = wait(client, url)
    assert view["status"] == "done", view["job"]
    assert client.post(f"{url}/accept").json()["accepted"]  # Looks right: model groups start from it
    yield tmp, pid
    mp.undo()


@pytest.fixture
def brought_in_client(brought_in, oakbox_home, monkeypatch):
    """A client on brought_in's home, in place of the test's own (set by oakbox_home, which runs first)."""
    monkeypatch.setenv("OAKBOX_HOME", str(brought_in[0] / "home"))
    return TestClient(create_app())

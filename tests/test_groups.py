"""Step 2, Model groups (SPEC §3.5): rules on the parcel universe, first match wins, as OpenAVMKit tags them."""

import json
import time
from typing import cast

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


# 40 parcels: houses, duplexes on residential land, condos, shops (one of them a house), and public land.
USES = ["RESIDENTIAL"] * 24 + ["CONDO"] * 8 + ["COMM"] * 6 + ["GOV OWNED"] * 2
TYPES = ["01-SFR"] * 20 + ["08-DUPLEX"] * 4 + ["04-CONDO"] * 8 + ["01-SFR"] + [""] * 5 + [""] * 2
AREAS = [1500.0 + 10 * i for i in range(33)] + [None] * 5 + [None] * 2


@pytest.fixture(scope="module")
def brought_in(tmp_path_factory):
    """A project whose data was brought in (OpenAVMKit's load and join, a few seconds), shared by the tests."""
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
    view: dict = {}
    for _ in range(240):
        view = client.get(url).json()
        if view["status"] != "running":
            break
        time.sleep(0.5)
    assert view["status"] == "done", view["job"]
    yield tmp, pid
    mp.undo()


def _url(pid):
    return f"/api/projects/{pid}/groups"


def _names(view):
    return [g["name"] for g in view["groups"]]


def test_suggested_groups_and_where_parcels_land(brought_in, monkeypatch):
    tmp, pid = brought_in
    monkeypatch.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    view = client.get(_url(pid)).json()
    assert view["ready"] and view["can_suggest"] and view["start"] is None
    assert [f["name"] for f in view["fields"]][:2] == ["land_class", "bldg_type"]  # property type first
    own = next(f for f in view["fields"] if f["name"] == "subdivision")  # the user's own field, to group on
    assert (own["kind"], own["distinct"]) == ("category", 2)

    view = client.post(f"{_url(pid)}/start", json={"how": "suggested"}).json()
    assert _names(view) == [
        "Condos & townhomes",
        "Small multi-family",
        "Commercial & industrial",
        "Public & exempt",
        "Single-family",
    ]
    groups = view["groups"]
    p = client.post(f"{_url(pid)}/preview", json={"groups": groups}).json()
    stats = {s["id"]: s for s in p["stats"]}
    assert [stats[g["id"]]["parcels"] for g in groups] == [8, 4, 6, 2, 20]
    assert stats[""]["parcels"] == 0
    # Sales follow their parcel: 40 house sales, 2 condos, 1 duplex, and 2 on commercial land (one a house).
    assert stats["single_family"]["sales"] == 40 and stats["commercial_industrial"]["sales"] == 2
    checks = {c["level"] for c in stats["public_exempt"]["checks"]}
    assert "bad" in checks  # no sales: too few to model
    assert len(p["assign"]) == p["total"] == 40 and p["moves"] == []

    # Single-family second: the duplexes (on residential land) and the house on commercial land move to it.
    order = [groups[0], groups[4], groups[1], groups[2], groups[3]]
    p = client.post(f"{_url(pid)}/preview", json={"groups": order}).json()
    assert p["moves"] == [
        {"from_id": "small_multi_family", "to_id": "single_family", "parcels": 4, "sold": 1},
        {"from_id": "commercial_industrial", "to_id": "single_family", "parcels": 1, "sold": 1},
    ]

    # A rule left unfinished matches nothing, and says so; its parcels fall to the next group.
    half = [
        {**groups[0], "rule": {"join": "any", "conditions": [{"column": "land_class", "op": "isin", "values": []}]}}
    ]
    p = client.post(f"{_url(pid)}/preview", json={"groups": half + groups[1:]}).json()
    assert p["stats"][0]["checks"][0]["text"].startswith("Its rule isn't finished")
    assert p["stats"][-1]["parcels"] == 8  # the condos: in no group now


def test_inspect_says_why_and_finds_parcels_like_it(brought_in, monkeypatch):
    tmp, pid = brought_in
    monkeypatch.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    groups = client.post(f"{_url(pid)}/start", json={"how": "suggested"}).json()["groups"]
    u = pd.read_parquet(projects.project_dir(pid) / "out" / "oakbox" / "bring_in" / "universe.parquet")
    house_on_comm = int(u.index[u["key"] == "32"].tolist()[0])
    v = client.post(f"{_url(pid)}/inspect", json={"groups": groups, "index": house_on_comm}).json()
    assert v["key"] == "32" and v["group"] == "commercial_industrial"
    why = {w["group"]: w for w in v["why"]}
    assert why["commercial_industrial"]["met"] and why["commercial_industrial"]["text"] == "land use is COMM"
    assert not why["condos_townhomes"]["met"]
    assert why["single_family"]["met"]  # it meets a later group's rule too
    assert len(v["like"]) == 1 and v["like_sold"] == 1  # the only house on commercial land
    assert [s["price"] for s in v["sales"]] == [244_000.0]
    values = client.get(f"{_url(pid)}/values/land_class").json()["rows"]
    assert values[0] == {"value": "RESIDENTIAL", "parcels": 24, "vacant": 0, "sales": 41}


def test_saved_groups_are_what_openavmkit_tags(brought_in, monkeypatch):
    """The settings OAK box writes, run through OpenAVMKit's own model-group tagging, give the preview's counts."""
    tmp, pid = brought_in
    monkeypatch.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    groups = client.post(f"{_url(pid)}/start", json={"how": "suggested"}).json()["groups"]
    groups[0]["name"] = "  Condos  "
    view = client.put(_url(pid), json={"groups": groups}).json()
    assert view["groups"][0]["name"] == "Condos"
    pdir = projects.project_dir(pid)
    settings = json.loads((pdir / "in" / "settings.json").read_text(encoding="utf-8"))
    mg = settings["modeling"]["model_groups"]
    assert list(mg) == [g["id"] for g in groups] and mg["condos_townhomes"]["name"] == "Condos"
    p = client.post(f"{_url(pid)}/preview", json={"groups": view["groups"]}).json()
    assert p["moves"] == []  # saved: nothing differs

    from openavmkit.data import SalesUniversePair, _tag_model_groups_sup

    sup = cast(SalesUniversePair, pd.read_pickle(pdir / "out" / "oakbox" / "bring_in" / "sup.pickle"))
    monkeypatch.chdir(tmp)  # it writes out/look/
    tagged = _tag_model_groups_sup(sup, settings)
    counts = tagged.universe["model_group"].value_counts().to_dict()
    assert counts == {s["id"]: s["parcels"] for s in p["stats"] if s["id"] and s["parcels"]}

    # The map's shapes: one per parcel, in the preview's order.
    shapes = client.get(f"{_url(pid)}/shapes").json()
    assert len(shapes["features"]) == len(p["assign"]) and shapes["features"][3]["id"] == 3


def test_from_scratch_starts_empty_and_needs_data_first(client):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    assert client.get(_url(pid)).json()["ready"] is False
    assert client.post(f"{_url(pid)}/start", json={"how": "suggested"}).status_code == 409
    view = client.post(f"{_url(pid)}/start", json={"how": "scratch"}).json()
    assert view["start"] == "scratch" and view["groups"] == []


def _wait(client, url):
    view: dict = {}
    for _ in range(240):
        view = client.get(url).json()
        if view["status"] != "running":
            return view
        time.sleep(0.5)
    raise AssertionError("still running")


def test_tag_and_write_notebook_1s_output(brought_in, monkeypatch):
    """OpenAVMKit tags the parcels and writes 1-assemble; the receipt counts each group and matches the preview."""
    tmp, pid = brought_in
    monkeypatch.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    groups = client.post(f"{_url(pid)}/start", json={"how": "suggested"}).json()["groups"]
    groups = [g for g in groups if g["id"] != "public_exempt"]  # the public land ends up in no group
    client.put(_url(pid), json={"groups": groups})
    url = f"/api/projects/{pid}/assemble"
    view = client.get(url).json()
    assert (view["status"], view["blocked"]) == ("never", [])
    client.put(f"{url}/exports", json={"exports": ["gpkg"]})

    assert client.post(f"{url}/run").json()["status"] == "running"
    view = _wait(client, url)
    assert view["status"] == "done", view["job"]
    r = view["receipt"]
    counts = {g["id"]: g for g in r["groups"]}
    assert counts["single_family"]["parcels"] == 20 and counts["single_family"]["sales"] == 40
    assert counts["UNKNOWN"]["parcels"] == 2  # the two public parcels
    assert r["matches_preview"] and r["parcels"] == 40
    paths = {w["path"] for w in r["written"]}
    assert {
        "out/1-assemble-sup.pickle",
        "out/look/1-assemble-universe.parquet",
        "out/look/1-assemble-universe.gpkg",
    } <= paths

    # What's written is what notebook 2 reads: the parcels carry their model group.
    sup = pd.read_pickle(projects.project_dir(pid) / "out" / "1-assemble-sup.pickle")
    assert sup.universe["model_group"].value_counts()["condos_townhomes"] == 8

    assert client.post(f"{url}/accept").json()["accepted"]
    # A change to the groups puts it out of date, and Looks right with it.
    client.put(_url(pid), json={"groups": groups[:-1]})
    view = client.get(url).json()
    assert view["stale"] and not view["accepted"]
    assert client.post(f"{url}/accept").status_code == 409

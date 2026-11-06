"""Step 2, Model groups (SPEC §3.5): rules on the parcel universe, first match wins, as OpenAVMKit tags them."""

import json
from typing import cast

import numpy as np
import pandas as pd
from helpers import NEW, wait

from oakbox import projects


def _url(pid):
    return f"/api/projects/{pid}/groups"


def _names(view):
    return [g["name"] for g in view["groups"]]


def test_suggested_groups_and_where_parcels_land(brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
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


def test_inspect_says_why_and_finds_parcels_like_it(brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
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


def test_saved_groups_are_what_openavmkit_tags(brought_in_client, brought_in, monkeypatch):
    """The settings OAK box writes, run through OpenAVMKit's own model-group tagging, give the preview's counts."""
    client, (tmp, pid) = brought_in_client, brought_in
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
    shapes = client.get(f"{_url(pid)}/shapes")
    assert shapes.headers["content-type"] == "application/octet-stream"
    head, parcels, *_ = _read_shapes(shapes.content)
    assert head[0] == len(p["assign"]) and (np.diff(parcels) == 1).all()  # a polygon each


def test_from_scratch_starts_empty_and_needs_data_first(client):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    assert client.get(_url(pid)).json()["ready"] is False
    assert client.post(f"{_url(pid)}/start", json={"how": "suggested"}).status_code == 409
    view = client.post(f"{_url(pid)}/start", json={"how": "scratch"}).json()
    assert view["start"] == "scratch" and view["groups"] == []


def test_tag_and_write_notebook_1s_output(brought_in_client, brought_in):
    """OpenAVMKit tags the parcels and writes 1-assemble; the receipt counts each group and matches the preview."""
    client, pid = brought_in_client, brought_in[1]
    groups = client.post(f"{_url(pid)}/start", json={"how": "suggested"}).json()["groups"]
    groups = [g for g in groups if g["id"] != "public_exempt"]  # the public land ends up in no group
    client.put(_url(pid), json={"groups": groups})
    url = f"/api/projects/{pid}/assemble"
    view = client.get(url).json()
    assert (view["status"], view["blocked"]) == ("never", [])
    client.put(f"{url}/exports", json={"exports": ["gpkg"]})

    assert client.post(f"{url}/run").json()["status"] == "running"
    view = wait(client, url)
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


def _read_shapes(b: bytes):
    """shapes.bin (groups._binary): its four counts, then each offset array, then the corners as (x, y) in degrees."""
    assert b[:8] == b"OAKSHP01"
    a = np.frombuffer(b[8:], dtype="<i4")
    n, p, r, c = (int(x) for x in a[:4])
    at = 4
    out = []
    for k in (n + 1, p + 1, r + 1, 2 * c):
        out.append(a[at : at + k])
        at += k
    return [n, p, r, c], out[0], out[1], out[2], out[3].reshape(-1, 2) / 1e6


def test_shapes_for_the_map_are_flat_arrays():
    """The map's shapes: a parcel's polygons, their rings and corners. Flat: a parcel with a height on each corner
    (PolygonZ, even a huge "no data") is drawn flat. No shape, or a point, is a parcel with no polygon; a hole is a
    ring of its polygon; a multipolygon's parts are polygons of the one parcel."""
    from shapely.geometry import MultiPolygon, Point, Polygon

    from oakbox.groups import _binary

    z = Polygon([(0, 0, -1.7e308), (1, 0, -1.7e308), (1, 1, -1.7e308)])
    holed = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)], [[(1, 1), (2, 1), (2, 2), (1, 1)]])
    head, parcels, polygons, rings, xy = _read_shapes(
        _binary(np.array([z, None, Point(3, 3), MultiPolygon([holed, z])], dtype=object))
    )
    assert head == [4, 3, 4, 17]
    assert parcels.tolist() == [0, 1, 1, 1, 3]  # z; nothing; nothing; two polygons
    assert polygons.tolist() == [0, 1, 3, 4]  # the holed polygon: two rings
    assert rings.tolist() == [0, 4, 9, 13, 17]
    assert xy[:4].tolist() == [[0, 0], [1, 0], [1, 1], [0, 0]]
    assert _read_shapes(_binary(np.array([None, None], dtype=object)))[0] == [2, 0, 0, 0]

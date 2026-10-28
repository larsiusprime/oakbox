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
    return json.loads((projects.project_dir(pid) / "in" / "settings.json").read_text(encoding="utf-8"))


def _step(w, key):
    return next(s for s in w["steps"] if s["key"] == key)


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
    assert base["id_check"] == {
        "ok": True,
        "text": "✓ 6 parcels, all different",
        "warn": False,
        "issues": [],
        "share": None,
    }
    sales = _file(w, "sales")
    assert (sales["holds"], sales["match"], sales["id_column"]) == ("sales", "key", "PROP_ID")
    assert sales["id_check"]["text"] == "100% of sales match a parcel"
    assert w["sale_id"]["made"] and w["sale_id"]["check"] == {
        "ok": True,
        "text": "from parcel ID + sale date",
        "warn": False,
        "issues": [],
        "share": None,
    }
    assert _field(w, "sale_price")["sources"] == [{"file": "sales", "column": "SALE_PRICE"}]
    assert _field(w, "sale_date")["check"] == {
        "ok": True,
        "text": "✓ reads as month/day/year",
        "warn": False,
        "issues": [],
        "share": None,
    }
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
    # Big five not visited yet, so nothing guessed; only age is flagged (quality and condition are nice to have)
    assert w["warnings"] == ["No building year built: recommended for a good model."]
    # Many repeats (several rows per parcel): it joins only once you say what to do with them.
    w = _put_file(client, pid, "permits", holds="parcels", id_column="PROP_ID").json()
    check = _file(w, "permits")["id_check"]
    assert not check["ok"] and check["text"] == "1 repeated ID (1 extra row): choose what to do"
    assert "permits: 1 repeated ID (1 extra row): choose what to do." in w["problems"]
    w = _put_file(client, pid, "permits", dupes="all").json()
    assert _file(w, "permits")["id_check"]["ok"]
    assert _settings(pid)["data"]["load"]["permits"]["dupes"] == {
        "subset": ["key"],
        "sort_by": ["key", "asc"],
        "drop": "all",
    }
    _put_file(client, pid, "permits", holds="unused")
    assert _settings(pid)["data"]["process"]["merge"]["universe"] == ["geo_parcels", "cama"]


def test_guesses_once_and_type_checks(client, pid):
    _start(client, pid)
    _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID")
    w = client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit").json()
    assert _field(w, "bldg_year_built")["sources"] == [{"file": "cama", "column": "YR_BLT"}]
    assert _field(w, "bldg_year_built")["check"] == {
        "ok": True,
        "text": "✓ years 1954–2011",
        "warn": False,
        "issues": [],
        "share": None,
    }
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
    for step in ("big_five", "assessed"):
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
    assert _put_file(client, pid, "shapes", universe=True, extra_field="key2", extra_column="MAP_NO").status_code == 200
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


def test_a_few_repeated_or_blank_ids_are_handled_and_flagged(client, tmp_path):
    """Guilford: 1 repeated ID and some parcels with none, in a big file. Keep the first; say so."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    ids: list[str | None] = [str(100000 + n) for n in range(1500)]
    ids[10] = ids[11]  # one ID on two rows
    ids[20] = ids[21] = ids[22] = None  # three with no ID
    gpd.GeoDataFrame(
        {"REID": ids, "PIN": [f"P{n}" for n in range(1500)]},
        geometry=[box(n, 0, n + 1, 1) for n in range(1500)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "big.parquet")
    body = {"path": str(tmp_path / "big.parquet"), "mode": "copy", "name": "big"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    w = _put_file(client, pid, "big", universe=True, id_column="REID").json()
    base = _file(w, "geo_parcels")
    assert base["id_check"] == {  # nothing chosen yet: repeats a warning, blank IDs a blocker
        "ok": False,
        "text": "1,496 parcels",
        "warn": True,
        "issues": [
            {"text": "1 repeated ID", "resolved": False, "blocking": False, "todo": "1 repeated ID to decide"},
            {"text": "3 blank IDs, dropped", "resolved": False, "blocking": True, "todo": "3 blank IDs to confirm"},
        ],
        "share": None,
    }
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    universe = _step(client.get(f"/api/projects/{pid}/wizard").json(), "universe")
    assert universe["status"] == "blocked"  # Next is greyed, and the skip dialog lists these, worst first
    assert universe["left"] == [
        {"text": "3 blank IDs to confirm", "blocking": True},
        {"text": "1 repeated ID to decide", "blocking": False},
    ]
    r = base["repeats"]
    assert (r["rows"], r["blank"], r["distinct"], r["repeated"], r["extra"], r["few"]) == (1500, 3, 1496, 1, 1, True)
    assert "Parcel universe: 3 blank IDs. Resolve them on its step to drop those rows." in w["problems"]
    assert (
        "Parcel universe: 1 ID repeats. Resolve it on its step; until then OpenAVMKit keeps the first row of each."
        in w["warnings"]
    )
    assert _settings(pid)["data"]["load"]["geo_parcels"]["dupes"] == {
        "subset": ["key"],
        "sort_by": ["key", "asc"],
        "drop": True,
    }
    rows = client.get(f"/api/projects/{pid}/wizard/files/geo_parcels/repeats").json()
    assert rows["columns"][:2] == ["REID", "PIN"]
    assert [r[:2] for r in rows["rows"]] == [["100011", "P10"], ["100011", "P11"]]
    # Keep the first by another field, descending.
    _put_file(client, pid, "geo_parcels", extra_field="key2", extra_column="PIN")
    w = _put_file(client, pid, "geo_parcels", dupes="first", dupes_sort="key2", dupes_desc=True).json()
    assert _settings(pid)["data"]["load"]["geo_parcels"]["dupes"]["sort_by"] == ["key2", "desc"]
    issues = _file(w, "geo_parcels")["id_check"]["issues"]
    assert issues[0] == {"text": "1 repeated ID, first kept", "resolved": True, "blocking": False, "todo": ""}
    assert not any("repeat" in x for x in w["warnings"])
    assert _file(w, "geo_parcels")["id_check"]["warn"]  # the blank IDs are still to acknowledge
    w = _put_file(client, pid, "geo_parcels", blank_ok=True).json()
    check = _file(w, "geo_parcels")["id_check"]
    assert check["issues"][1] == {
        "text": "3 blank IDs, dropped",
        "resolved": True,
        "blocking": False,
        "todo": "3 blank IDs to confirm",
    }
    assert check["ok"] and not any("geo_parcels" in p for p in w["problems"])
    assert not check["warn"] and check["text"] == "✓ 1,496 parcels"  # everything decided: all green
    assert not any("geo_parcels" in x for x in w["warnings"])
    assert _step(w, "universe")["status"] == "done" and _step(w, "universe")["left"] == []


def test_extra_ids_are_added_removed_and_joined_on(client, tmp_path, monkeypatch):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {"ID": ["a", "b", "c", "d"], "MAP": ["m1", "m1", None, "m4"], "OLD": ["o1", "o2", "o3", "o4"]},
        geometry=[box(n, 0, n + 1, 1) for n in range(4)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "u.parquet")
    pd.DataFrame({"OLD_ID": ["o1", "o3"], "STORIES": [1, 2]}).to_csv(tmp_path / "x.csv", index=False)
    for name, fn in (("u", "u.parquet"), ("x", "x.csv")):
        client.post(f"/api/projects/{pid}/files", json={"path": str(tmp_path / fn), "mode": "copy", "name": name})
    _put_file(client, pid, "u", universe=True, id_column="ID")
    r = _put_file(client, pid, "geo_parcels", extra_field="key3", extra_column="OLD")
    assert r.status_code == 422 and "2nd ID first" in r.json()["detail"]
    w = _put_file(client, pid, "geo_parcels", extra_field="key2", extra_column="MAP").json()
    assert _file(w, "geo_parcels")["extra_ids"] == [{"field": "key2", "column": "MAP"}]  # not checked
    w = _put_file(client, pid, "geo_parcels", extra_field="key3", extra_column="OLD").json()
    assert [e["field"] for e in _file(w, "geo_parcels")["extra_ids"]] == ["key2", "key3"]
    # Another file joins on the 3rd ID.
    w = _put_file(client, pid, "x", holds="parcels", match="key3", id_column="OLD_ID").json()
    assert _file(w, "x")["id_check"]["text"] == "✓ one row per parcel · 100% match parcels"
    assert _settings(pid)["data"]["process"]["merge"]["universe"] == ["geo_parcels", {"id": "x", "on": "key3"}]
    # Removing the 2nd ID moves the 3rd up.
    w = _put_file(client, pid, "geo_parcels", extra_field="key2").json()
    assert [(e["field"], e["column"]) for e in _file(w, "geo_parcels")["extra_ids"]] == [("key2", "OLD")]
    assert (_file(w, "x")["match"], _file(w, "x")["id_column"]) == ("key2", "OLD_ID")


def test_step_marks_come_from_what_is_on_each_step(client, pid):
    def marks():
        w = client.get(f"/api/projects/{pid}/wizard").json()
        return {s["key"]: s["status"] for s in w["steps"]}

    assert set(marks().values()) == {"blank"}  # nothing visited: nothing shown, not even what's missing
    client.post(f"/api/projects/{pid}/wizard/steps/welcome/visit")
    assert marks()["welcome"] == "blank"
    client.post(f"/api/projects/{pid}/wizard/steps/welcome/confirm")  # Start
    assert marks()["welcome"] == "done"
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    assert marks()["universe"] == "blocked"  # visited, no file yet
    _put_file(client, pid, "shapes", universe=True)
    assert marks()["universe"] == "done"
    client.post(f"/api/projects/{pid}/wizard/steps/sales/visit")
    assert marks()["sales"] == "blocked"  # no sales file
    _put_file(client, pid, "sales", holds="sales")
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True})
    assert marks()["sales"] == "done"
    client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit")
    assert marks()["big_five"] == "blocked"  # no building size
    _put_file(client, pid, "cama", holds="parcels", id_column="PROP_ID")  # guesses year built, area too
    client.put(
        f"/api/projects/{pid}/wizard/fields/bldg_area_finished_sqft", json={"file": "cama", "column": "LIVING_AREA"}
    )
    assert marks()["big_five"] == "done"
    client.put(f"/api/projects/{pid}/wizard/fields/bldg_year_built", json={})
    assert marks()["big_five"] == "attention"  # no age
    # Optional steps: blank when only seen, done once moved on from (Next) or skipped.
    client.post(f"/api/projects/{pid}/wizard/steps/location/visit")
    assert marks()["location"] == "blank"
    client.post(f"/api/projects/{pid}/wizard/steps/location/confirm")
    client.post(f"/api/projects/{pid}/wizard/steps/assessed/skip")
    m = marks()
    assert (m["location"], m["assessed"], m["details"]) == ("done", "done", "attention")  # worst of its parts
    assert "land" not in m and "building" not in m and "rooms_features" not in m


def test_reconcile_cleans_ids_so_sales_find_their_parcels(client, tmp_path, monkeypatch):
    """Parcel IDs zero-padded, sales IDs not (one with a stray space): clean both sides, OpenAVMKit joins them."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    reids: list[str | None] = [f"{118000 + n:010d}" for n in range(20)] + [None]  # and one sliver with no ID
    gpd.GeoDataFrame(
        {"GDV_REID": reids}, geometry=[box(n, 0, n + 1, 1) for n in range(21)], crs="EPSG:4326"
    ).to_parquet(tmp_path / "parcels.parquet")
    sale_ids = [str(118000 + n) for n in (1, 2, 2, 5, 7)] + ["118009 ", "999999"]
    pd.DataFrame(
        {"REID": sale_ids, "PRICE": [100_000 + n for n in range(7)], "DATE": [f"2024-01-{n + 1:02d}" for n in range(7)]}
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="GDV_REID", blank_ok=True)
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    _put_file(client, pid, "sale", holds="sales", id_column="REID")
    w = client.post(f"/api/projects/{pid}/wizard/steps/sales/visit").json()
    check = _file(w, "sale")["id_check"]
    assert (check["share"], check["ok"]) == (0, False)  # nothing matches as is: a blocker
    assert _step(w, "sales")["left"][0] == {"text": "Reconcile the IDs: 0% of sales match a parcel", "blocking": True}

    url = f"/api/projects/{pid}/wizard/files/sale/reconcile"
    view = client.post(url, json={"suggest": True}).json()
    assert (view["matched"], view["total"], view["field"]) == (0, 7, "key")
    assert {s["raw"] for s in view["file_samples"]} == {"118001", "118002", "118005", "118007", "118009 ", "999999"}
    assert view["suggestion"]["base_steps"] == [{"kind": "zeros", "text": "", "to": "", "n": 0}]
    assert view["suggestion"]["file_steps"] == [{"kind": "trim", "text": "", "to": "", "n": 0}]
    assert view["suggestion"]["text"] == "Remove leading zeros from the parcel IDs; trim spaces from the sales IDs"
    zeros, trim = [{"kind": "zeros"}], [{"kind": "trim"}]
    view = client.post(url, json={"base_steps": zeros, "view": "random"}).json()
    assert view["matched"] == 5  # the spaced one still misses, and 999999 has no parcel
    sold = {"118001", "118002", "118005", "118007"}
    for sample in view["base_samples"]:  # parcels: cleaned, and whether a sale finds them
        assert sample["clean"] == sample["raw"].lstrip("0") and sample["hit"] == (sample["clean"] in sold)
    view = client.post(url, json={"base_steps": zeros, "file_steps": trim}).json()
    assert (view["matched"], view["saved_share"]) == (6, 0)
    assert [s["raw"] for s in view["file_samples"]] == ["999999"]  # unmatched only
    assert view["writes"] == {
        "geo_parcels": ["where", ["isempty", "key"], None, ["striplzero", "key"]],
        "sale": ["where", ["isempty", "key"], None, ["strip", "key"]],
    }

    w = client.put(url, json={"base_steps": zeros, "file_steps": trim}).json()
    check = _file(w, "sale")["id_check"]
    assert check["text"] == "86% of sales match a parcel" and check["ok"] and check["warn"]
    assert _file(w, "geo_parcels")["clean"] == {"key": [{"kind": "zeros", "text": "", "to": "", "n": 0}]}
    load = _settings(pid)["data"]["load"]
    assert load["geo_parcels"]["calc"]["key"] == ["where", ["isempty", "key"], None, ["striplzero", "key"]]
    assert list(load["sale"]["calc"])[0] == "key"  # cleaned before the sale ID is made from it
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"file": "sale", "column": col})
    univ, sales = _engine(pid, monkeypatch)
    assert len(univ) == 20 and univ["key"].iloc[0] == "118000"  # the blank one dropped, not kept as "<NA>"
    assert set(sales["key"]) >= {"118001", "118002", "118005", "118007", "118009"}
    assert "118002-2024-01-02" in set(sales["key_sale"])


def test_valid_and_vacant_sale_rules_and_date_formats(client, tmp_path, monkeypatch):
    """Codes, not yes/no (Q/U, Y/blank): a rule picks which values mean yes; OpenAVMKit works it out the same."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {"ID": [str(n) for n in range(6)]}, geometry=[box(n, 0, n + 1, 1) for n in range(6)], crs="EPSG:4326"
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame(
        {
            "PID": ["0", "1", "2", "3", "4", "5"],
            "PRICE": [250_000, 10, 180_000, 90_000, 300_000, 120_000],
            "DATE": ["03/04/2024", "05/06/2024", "07/08/2024", "09/10/2024", "11/12/2024", "01/02/2025"],
            "QUALIFIED": ["Q", "Q", "U", "Q", "Q", "U"],
            "VACANT_LOT": ["", "Y", "", "", "Y", ""],
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    client.post(f"/api/projects/{pid}/wizard/steps/sales/visit")
    field = f"/api/projects/{pid}/wizard/fields"
    client.put(f"{field}/sale_price", json={"file": "sale", "column": "PRICE"})

    # A date that reads both ways: flagged, and another format can be previewed and chosen.
    w = client.put(f"{field}/sale_date", json={"file": "sale", "column": "DATE"}).json()
    assert _field(w, "sale_date")["check"]["warn"]
    assert _field(w, "sale_date")["check"]["text"] == "reads as month/day/year, or as day/month/year?"
    dates = f"/api/projects/{pid}/wizard/files/sale/dates"
    view = client.post(dates, json={"column": "DATE", "format": "%d/%m/%Y"}).json()
    assert (view["read"], view["failed"], view["first"], view["last"]) == (6, 0, "2024-04-03", "2025-02-01")
    assert view["also"] == [{"format": "%m/%d/%Y", "words": "month/day/year"}]
    assert client.post(dates, json={"column": "DATE", "format": "%Y-%m-%d"}).json()["failed"] == 6
    w = client.put(f"{field}/sale_date", json={"file": "sale", "column": "DATE", "date_format": "%d/%m/%Y"}).json()
    assert _field(w, "sale_date")["date_format"] == "%d/%m/%Y"
    assert _settings(pid)["data"]["load"]["sale"]["load"]["sale_date"] == ["DATE", "datetime", "%d/%m/%Y"]

    # Q/U isn't yes/no: picking it starts a rule with nothing chosen yet.
    w = client.put(f"{field}/valid_sale", json={"file": "sale", "column": "QUALIFIED"}).json()
    valid = _field(w, "valid_sale")
    assert valid["rule"] == {"join": "all", "conditions": [{"column": "QUALIFIED", "op": "isin", "values": []}]}
    assert (valid["check"]["ok"], valid["check"]["text"]) == (False, "choose which values mean yes")
    assert valid["sources"] == [{"file": "sale", "column": "QUALIFIED"}]

    rule = {"join": "all", "conditions": [{"column": "QUALIFIED", "op": "isin", "values": ["Q"]}]}
    view = client.post(f"{field}/valid_sale/rule", json=rule).json()
    assert (view["yes"], view["total"]) == (4, 6)
    assert view["values"]["QUALIFIED"] == [{"value": "Q", "count": 4}, {"value": "U", "count": 2}]
    assert view["calc"] == ["?", ["isin", "qualified", ["str:Q"]]]
    assert view["load"] == {"qualified": ["QUALIFIED", "string"]}
    # ...and not the $10 deed: a second test on a column already loaded (as sale_price) reuses it.
    rule["conditions"].append({"column": "PRICE", "op": ">", "values": ["1000"]})
    view = client.post(f"{field}/valid_sale/rule", json=rule).json()
    assert view["yes"] == 3 and view["calc"] == [
        "?",
        ["and", ["isin", "qualified", ["str:Q"]], [">", "sale_price", 1000.0]],
    ]
    w = client.put(f"{field}/valid_sale/rule", json=rule).json()
    assert _field(w, "valid_sale")["check"] == {
        "ok": True,
        "text": "✓ 3 of 6 valid (50%)",
        "warn": False,
        "issues": [],
        "share": None,
    }
    vacant = {"join": "all", "conditions": [{"column": "VACANT_LOT", "op": "isin", "values": ["Y"]}]}
    w = client.put(f"{field}/vacant_sale/rule", json=vacant).json()
    assert _field(w, "vacant_sale")["check"]["text"] == "✓ 2 of 6 vacant (33%)"
    entry = _settings(pid)["data"]["load"]["sale"]
    assert entry["load"]["qualified"] == ["QUALIFIED", "string"]
    assert entry["load"]["sale_price"] == ["PRICE", "float"]
    assert entry["calc"]["vacant_sale"] == ["?", ["isin", "vacant_lot", ["str:Y"]]]
    assert "valid_sale" not in entry["load"] and "vacant_sale" not in entry["load"]

    _, sales = _engine(pid, monkeypatch)
    sales = sales.sort_values("key")
    assert sales["valid_sale"].tolist() == [True, False, False, True, True, False]
    assert sales["vacant_sale"].tolist() == [False, True, False, False, True, False]
    assert str(sales["sale_date"].iloc[0].date()) == "2024-04-03"

    # Back to a plain column (or an assumption): the rule goes.
    w = client.put(f"{field}/valid_sale", json={"assume": True}).json()
    assert _field(w, "valid_sale")["rule"] is None and _field(w, "valid_sale")["assumed"]


@pytest.mark.parametrize("units", ["imperial", "metric"])
def test_area_columns_are_converted_to_the_projects_small_unit(client, tmp_path, monkeypatch, units):
    """Land in acres, building in square feet: labelled, converted as OpenAVMKit loads them."""
    pid = client.post("/api/projects", json={**NEW, "units": units}).json()["id"]
    gpd.GeoDataFrame(
        {"ID": ["1", "2", "3"], "ACRES": [0.25, 1.0, 0.1], "HEATED_SF": [1500, 2400, 980]},
        geometry=[box(n, 0, n + 1, 1) for n in range(3)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame({"PID": ["1", "3"], "PRICE": [200_000, 150_000], "DATE": ["2024-01-02", "2024-05-06"]}).to_csv(
        tmp_path / "sale.csv", index=False
    )
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    field = f"/api/projects/{pid}/wizard/fields"
    client.put(f"{field}/sale_price", json={"file": "sale", "column": "PRICE"})
    client.put(f"{field}/sale_date", json={"file": "sale", "column": "DATE"})
    w = client.put(f"{field}/land_area_sqft", json={"file": "geo_parcels", "column": "ACRES"}).json()
    land = _field(w, "land_area_sqft")
    small = "sq ft" if units == "imperial" else "m²"
    assert land["area_unit"] == "acres"  # from the column's name
    assert land["check"]["text"] == f"✓ 0.25 acres → {'10,890' if units == 'imperial' else '1,012'} {small}"
    assert land["name"] == ("Land area in square feet" if units == "imperial" else "Land area in square metres")
    # Square feet in a metric project: said so, and converted.
    w = client.put(
        f"{field}/bldg_area_finished_sqft", json={"file": "geo_parcels", "column": "HEATED_SF", "area_unit": "sqft"}
    ).json()
    assert _field(w, "bldg_area_finished_sqft")["area_unit"] == "sqft"
    # The wrong unit for its size: flagged.
    w = client.put(
        f"{field}/land_area_sqft", json={"file": "geo_parcels", "column": "ACRES", "area_unit": "sqft"}
    ).json()
    assert _field(w, "land_area_sqft")["check"]["warn"]
    client.put(f"{field}/land_area_sqft", json={"file": "geo_parcels", "column": "ACRES", "area_unit": "acres"})

    load = _settings(pid)["data"]["load"]["geo_parcels"]
    unit = "sqft" if units == "imperial" else "sqm"
    assert load["load"][f"land_area_{unit}_in_acres"] == ["ACRES", "float"]
    assert load["calc"][f"land_area_{unit}"][:2] == ["*", f"land_area_{unit}_in_acres"]
    univ, _ = _engine(pid, monkeypatch)
    univ = univ.sort_values("key")
    land = univ[f"land_area_{unit}"].tolist()
    bldg = univ[f"bldg_area_finished_{unit}"].tolist()
    if units == "imperial":
        assert land == pytest.approx([10_890, 43_560, 4_356]) and bldg == [1500, 2400, 980]
    else:
        assert land == pytest.approx([1011.71, 4046.86, 404.686], rel=1e-4)
        assert bldg == pytest.approx([139.355, 222.967, 91.0451], rel=1e-4)


def test_more_files_join_the_parcels_or_the_sales(client, tmp_path, monkeypatch):
    """CAMA joins the parcels (after Reconcile and picking a card); deed details join the sales on the sale ID."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {"GDV_REID": [f"{n:010d}" for n in range(1, 6)]},
        geometry=[box(n, 0, n + 1, 1) for n in range(5)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame(
        {"REID": ["1", "2", "2", "3", "4", "5"], "CARD": [1, 1, 2, 1, 1, 1], "AREA": [1500, 2000, 400, 900, 1200, 1800]}
    ).to_csv(tmp_path / "cama.csv", index=False)
    pd.DataFrame(
        {
            "SALE_ID": ["S1", "S2", "S3"],
            "PARCEL": ["0000000001", "0000000003", "0000000003"],
            "PRICE": [200_000, 150_000, 175_000],
            "DATE": ["2024-01-02", "2023-05-06", "2025-02-03"],
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    pd.DataFrame({"SALE_ID": ["S1", "S2", "S3"], "DEED_TYPE": ["WD", "QC", "WD"]}).to_csv(
        tmp_path / "deeds.csv", index=False
    )
    for name, ext in (("parcels", "parquet"), ("cama", "csv"), ("sale", "csv"), ("deeds", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="GDV_REID")
    _put_file(client, pid, "sale", holds="sales", id_column="PARCEL")
    client.put(f"/api/projects/{pid}/wizard/sale-id", json={"column": "SALE_ID", "make": False})
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"file": "sale", "column": col})
    client.post(f"/api/projects/{pid}/wizard/steps/more_files/visit")

    # Not said yet what they join to: listed as to-dos, not blockers.
    w = client.get(f"/api/projects/{pid}/wizard").json()
    step = _step(w, "more_files")
    assert {"text": "cama: say what it joins to", "blocking": False} in step["left"]

    # CAMA: one row per parcel, joined on REID; padded IDs on one side only.
    w = _put_file(client, pid, "cama", holds="parcels", id_column="REID").json()
    check = _file(w, "cama")["id_check"]
    assert (check["ok"], check["share"]) == (False, 0)
    url = f"/api/projects/{pid}/wizard/files/cama/reconcile"
    view = client.post(url, json={"suggest": True}).json()
    assert (view["kind"], view["base"]) == ("parcels", "geo_parcels")
    assert view["suggestion"]["text"] == "Remove leading zeros from the parcel IDs"
    w = client.put(url, json={"base_steps": [{"kind": "zeros"}], "file_steps": []}).json()
    check = _file(w, "cama")["id_check"]
    assert check["text"] == "1 repeated ID (1 extra row): choose what to do"
    w = _put_file(client, pid, "cama", dupes="first", dupes_sort="key", dupes_desc=False).json()
    assert _file(w, "cama")["id_check"]["ok"] and _file(w, "cama")["id_check"]["share"] == 1
    # The sales still find their parcels: the parcel side's clean-up applies to every join on it.
    assert _file(w, "sale")["id_check"]["share"] == 0
    client.put(
        f"/api/projects/{pid}/wizard/files/sale/reconcile",
        json={"base_steps": [{"kind": "zeros"}], "file_steps": [{"kind": "zeros"}]},
    )

    # Deed details: more sales, joined on the sale ID, which it guesses from the main file's column.
    w = _put_file(client, pid, "deeds", holds="sales", match="key_sale").json()
    deeds = _file(w, "deeds")
    assert (deeds["match"], deeds["id_column"], deeds["id_check"]["text"]) == (
        "key_sale",
        "SALE_ID",
        "100% match a sale",
    )
    assert _file(w, "sale")["holds"] == "sales"  # still the main sales file
    assert w["sale_id"]["file"] == "sale"
    client.put(f"/api/projects/{pid}/wizard/fields/bldg_area_finished_sqft", json={"file": "cama", "column": "AREA"})
    w = client.post(f"/api/projects/{pid}/wizard/steps/more_files/confirm").json()
    assert _step(w, "more_files")["status"] == "done"

    process = _settings(pid)["data"]["process"]
    assert process["merge"]["universe"] == ["geo_parcels", "cama"]
    assert process["merge"]["sales"] == ["sale", "deeds"]
    assert "enrich" not in process
    load = _settings(pid)["data"]["load"]
    assert load["deeds"]["load"] == {"key_sale": ["SALE_ID", "string"]}
    assert load["deeds"]["dupes"]["subset"] == ["key_sale"]
    assert load["cama"]["dupes"] == {"subset": ["key"], "sort_by": ["key", "asc"], "drop": True}

    client.put(f"/api/projects/{pid}/wizard/fields/valid_sale", json={"assume": True})
    client.put(f"/api/projects/{pid}/wizard/fields/vacant_sale", json={"assume": True})
    univ, sales = _engine(pid, monkeypatch)
    univ = univ.sort_values("key")
    assert univ["key"].tolist() == ["1", "2", "3", "4", "5"]
    assert univ["bldg_area_finished_sqft"].tolist() == [1500, 2000, 900, 1200, 1800]  # card 1 of parcel 2
    assert sorted(sales["key_sale"]) == ["S1", "S2", "S3"] and set(sales["key"]) == {"1", "3"}


def test_location_fields_the_user_names_and_the_polar_centre(client, tmp_path, monkeypatch):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {
            "ID": [str(n) for n in range(6)],
            "PHYADDR": [f"{n} MAIN ST" for n in range(6)],
            "MAIL_ADDR": [f"PO BOX {n}" for n in range(6)],
            "NBHD": ["A", "A", "B", "B", "C", "C"],
        },
        geometry=[box(-79.8 + n * 0.01, 36.1, -79.79 + n * 0.01, 36.11) for n in range(6)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame({"PID": ["1", "3"], "PRICE": [200_000, 150_000], "DATE": ["2024-01-02", "2024-05-06"]}).to_csv(
        tmp_path / "sale.csv", index=False
    )
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"file": "sale", "column": col})
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True})

    # Only the situs address is asked, and its guess is the physical address, not the mailing one.
    w = client.post(f"/api/projects/{pid}/wizard/steps/location/visit").json()
    assert [f["key"] for f in w["fields"] if f["step"] == "location"] == ["address"]
    address = _field(w, "address")
    assert address["name"] == "Situs address" and "not where the owner gets mail" in address["description"]
    assert address["sources"] == [{"file": "geo_parcels", "column": "PHYADDR"}]

    url = f"/api/projects/{pid}/wizard/locations"
    w = client.put(f"{url}/market_area", json={"file": "geo_parcels", "column": "NBHD"}).json()
    assert [(x["name"], x["column"], x["check"]["text"]) for x in w["locations"]] == [("market_area", "NBHD", "✓")]
    assert client.put(f"{url}/Bad Name", json={"file": "geo_parcels", "column": "NBHD"}).status_code == 422
    assert client.put(f"{url}/latitude", json={"file": "geo_parcels", "column": "NBHD"}).status_code == 422
    assert client.put(f"{url}/sale_price", json={"file": "geo_parcels", "column": "MAIL_ADDR"}).status_code == 422
    settings = _settings(pid)
    assert settings["data"]["load"]["geo_parcels"]["load"]["market_area"] == ["NBHD", "string"]
    assert settings["field_classification"] == {
        "important": {"locations": ["market_area"]},
        "other": {"categorical": ["market_area"]},
    }

    view = client.get(f"/api/projects/{pid}/wizard/map").json()
    assert view["parcels"] == 6 and len(view["points"]) == 6 and view["center"] is None
    lat, lon = view["middle"]
    assert 36.1 < lat < 36.11 and -79.8 < lon < -79.7
    view = client.put(f"/api/projects/{pid}/center", json={"latitude": 36.0, "longitude": -79.9}).json()
    assert view["center"] == [36.0, -79.9]
    assert _settings(pid)["locality"]["center"] == {"latitude": 36.0, "longitude": -79.9}
    client.put(f"/api/projects/{pid}/center")
    assert "center" not in _settings(pid)["locality"]

    univ, _ = _engine(pid, monkeypatch)
    assert sorted(set(univ["market_area"])) == ["A", "B", "C"]

    w = client.put(f"{url}/market_area", json={}).json()
    assert w["locations"] == [] and "field_classification" not in _settings(pid)


def test_map_layers_stamped_onto_parcels_or_measured_to(client, tmp_path, monkeypatch):
    """Zoning polygons (GeoJSON, in degrees) stamped onto parcels (State Plane feet); schools (points, a
    shapefile) measured to. OpenAVMKit's own spatial join and distances produce the fields."""
    from shapely.geometry import Point

    pid = client.post("/api/projects", json=NEW).json()["id"]
    lots = gpd.GeoDataFrame(
        {"ID": [str(n) for n in range(6)]},
        geometry=[box(1_760_000 + n * 200, 850_000, 1_760_150 + n * 200, 850_150) for n in range(6)],
        crs="EPSG:2264",
    )
    lots.to_parquet(tmp_path / "parcels.parquet")
    zoning = gpd.GeoDataFrame(
        {"ZONE_CODE": ["R-3", "C-M"], "OBJECTID": [1, 2]},
        geometry=[box(1_759_900, 849_900, 1_760_500, 850_300), box(1_760_500, 849_900, 1_761_300, 850_300)],
        crs="EPSG:2264",
    ).to_crs(4326)
    zoning.to_file(tmp_path / "zoning.geojson", driver="GeoJSON")
    gpd.GeoDataFrame({"SCHOOL": ["A"]}, geometry=[Point(1_759_000, 850_075)], crs="EPSG:2264").to_file(
        tmp_path / "schools.shp"
    )
    pd.DataFrame({"PID": ["1", "3"], "PRICE": [200_000, 150_000], "DATE": ["2024-01-02", "2024-05-06"]}).to_csv(
        tmp_path / "sale.csv", index=False
    )
    for name, fn in (
        ("parcels", "parcels.parquet"),
        ("sale", "sale.csv"),
        ("zoning", "zoning.geojson"),
        ("schools", "schools.shp"),
    ):
        body = {"path": str(tmp_path / fn), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200, fn
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"file": "sale", "column": col})
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"/api/projects/{pid}/wizard/fields/{key}", json={"assume": True})
    client.post(f"/api/projects/{pid}/wizard/steps/shapefiles/visit")
    layer = f"/api/projects/{pid}/wizard/layers"

    # Added but not said how to use: listed, nothing written yet.
    w = client.put(f"{layer}/zoning", json={}).json()
    z = next(x for x in w["layers"] if x["name"] == "zoning")
    assert (z["polygons"], z["points"], z["projected"]) == (2, 0, True)
    assert {"text": "zoning: say how to use it", "blocking": False} in _step(w, "shapefiles")["left"]

    stamp = {"use": "stamp", "fields": [{"column": "ZONE_CODE", "name": "zoning_district", "kind": "location"}]}
    w = client.put(f"{layer}/zoning", json=stamp).json()
    z = next(x for x in w["layers"] if x["name"] == "zoning")
    assert z["check"]["text"] == "✓ every parcel in one shape"
    # Points can only be measured to; names OpenAVMKit computes are refused.
    bad = {"use": "stamp", "fields": [{"column": "SCHOOL", "name": "school", "kind": "location"}]}
    w = client.put(f"{layer}/schools", json=bad).json()
    s = next(x for x in w["layers"] if x["name"] == "schools")
    assert {"text": "schools: has no shapes to fall in: use it for distances", "blocking": True} in _step(
        w, "shapefiles"
    )["left"]
    assert (s["points"], s["polygons"]) == (1, 0)
    assert (
        client.put(f"{layer}/schools", json={**bad, "fields": [{**bad["fields"][0], "name": "latitude"}]}).status_code
        == 422
    )
    dist = {"use": "distance", "feature": "schools", "max_distance": 2, "unit": "mile", "name_column": "SCHOOL"}
    w = client.put(f"{layer}/schools", json=dist).json()
    assert _step(w, "shapefiles")["left"] == []
    # Map layers aren't More files: they don't join on an ID, so they're nothing to do there.
    w = client.post(f"/api/projects/{pid}/wizard/steps/more_files/visit").json()
    assert _step(w, "more_files")["left"] == []

    settings = _settings(pid)
    enrich = settings["data"]["process"]["enrich"]
    assert enrich["geometry"] == [{"id": "zoning", "predicate": "contains_centroid", "fields": ["zoning_district"]}]
    assert enrich["distances"] == {
        "enabled": True,
        "schools": {"enabled": True, "source": "schools", "unit": "mile", "max_distance": 2.0},
    }
    load = settings["data"]["load"]
    assert load["zoning"] == {
        "filename": "zoning.geojson",
        "load": {"zoning_district": ["ZONE_CODE", "string"]},
        "dupes": "allow",
    }
    assert load["schools"]["load"] == {"name": ["SCHOOL", "string"]}
    assert settings["field_classification"]["important"]["locations"] == ["zoning_district"]
    assert "zoning" not in settings["data"]["process"]["merge"]["universe"]

    view = client.get(f"{layer}/zoning/map").json()
    assert len(view["shapes"]["features"]) == 2 and len(view["points"]) == 6

    from openavmkit.data import _basic_geo_enrichment, _enrich_df_distances, _enrich_df_spatial_joins
    from openavmkit.pipeline import load_dataframes, load_settings

    monkeypatch.chdir(projects.project_dir(pid))
    s = load_settings("in/settings.json")
    dfs = load_dataframes(s)
    univ = dfs["geo_parcels"]
    e = s["data"]["process"]["enrich"]
    univ = _enrich_df_spatial_joins(univ, e, dfs, s)
    univ = _basic_geo_enrichment(univ, e, s)
    univ = _enrich_df_distances(univ, e["distances"], dfs).sort_values("key")
    assert univ["zoning_district"].tolist() == ["R-3", "R-3", "R-3", "C-M", "C-M", "C-M"]
    d = univ["dist_to_schools"].tolist()
    assert d == sorted(d) and 0.1 < d[0] < 0.3  # miles, growing east from the school

    w = client.put(f"{layer}/schools").json()
    assert all(x["name"] != "schools" for x in w["layers"])
    assert "distances" not in _settings(pid)["data"]["process"]["enrich"]
    # Nothing taken from it now, but still listed: OpenAVMKit loads it without tripping on its missing columns.
    assert _settings(pid)["data"]["load"]["schools"] == {"filename": "schools.shp", "dupes": "allow"}
    assert len(load_dataframes(load_settings("in/settings.json"))["schools"]) == 1


def test_prices_written_as_text_are_read_and_their_scale_checked(client, tmp_path, monkeypatch):
    """$250,000.00, (10), N/A: read by a calc OpenAVMKit runs; a price in thousands is caught by the assessed values."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    n = 30
    assessed = [200_000 + 5_000 * i for i in range(n)]
    gpd.GeoDataFrame(
        {"ID": [str(i) for i in range(n)], "VALUE": assessed},
        geometry=[box(i, 0, i + 1, 1) for i in range(n)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    prices = [int(a * 1.1) for a in assessed]
    written = [f"${p:,.2f}" for p in prices]
    written[1], written[2], written[3] = "(10)", "N/A", ""
    pd.DataFrame(
        {
            "PID": [str(i) for i in range(n)],
            "PRICE": written,
            "IN_THOUSANDS": [f"{p / 1000:g}" for p in prices],
            "DATE": ["2024-01-02"] * n,
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    field = f"/api/projects/{pid}/wizard/fields"
    client.put(f"{field}/assr_market_value", json={"file": "geo_parcels", "column": "VALUE"})
    client.put(f"{field}/sale_date", json={"file": "sale", "column": "DATE"})

    # Not plain numbers: read as text with a format worked out from the whole column, not refused.
    w = client.put(f"{field}/sale_price", json={"file": "sale", "column": "PRICE"}).json()
    price = _field(w, "sale_price")
    assert price["number_format"] == {"decimal": ".", "suffixes": False, "scale": 1.0}
    assert price["check"] == {
        "ok": True,
        "text": "✓ median $308K",
        "warn": False,
        "issues": [],
        "share": None,
    }
    numbers = f"/api/projects/{pid}/wizard/files/sale/numbers"
    view = client.post(numbers, json={"key": "sale_price", "column": "PRICE"}).json()
    assert (view["read"], view["blank"], view["failed"], view["negative"]) == (28, 2, 0, 1)
    assert view["hint"] is None and 1.05 < view["assessed"] < 1.15
    assert {"raw": "(10)", "read": -10.0} in view["samples"]
    entry = _settings(pid)["data"]["load"]["sale"]
    assert entry["load"]["sale_price_text"] == ["PRICE", "string"] and "sale_price" not in entry["load"]

    # Plain numbers, but in thousands: the assessed values give it away, and say what to read them as.
    w = client.put(f"{field}/sale_price", json={"file": "sale", "column": "IN_THOUSANDS"}).json()
    assert _field(w, "sale_price")["check"]["text"] == "median $299.75 · in thousands?"
    assert _field(w, "sale_price")["number_format"] is None  # read as a plain float column until told otherwise
    view = client.post(numbers, json={"key": "sale_price", "column": "IN_THOUSANDS"}).json()
    assert view["hint"]["scale"] == 1000 and view["nominal"] == 30
    fmt = {"decimal": ".", "suffixes": False, "scale": 1000}
    w = client.put(f"{field}/sale_price", json={"file": "sale", "column": "IN_THOUSANDS", "number_format": fmt}).json()
    assert _field(w, "sale_price")["check"]["text"] == "✓ median $300K"

    # Back to the formatted column, and the $10 deed left out of valid sales by a price test the rule reads as read.
    client.put(f"{field}/sale_price", json={"file": "sale", "column": "PRICE"})
    rule = {"join": "all", "conditions": [{"column": "PRICE", "op": ">=", "values": ["1000"]}]}
    view = client.post(f"{field}/valid_sale/rule", json=rule).json()
    assert view["as_read"] == ["PRICE"] and {"cells": ["-10"], "yes": False} in view["rows"]
    w = client.put(f"{field}/valid_sale/rule", json=rule).json()
    assert _field(w, "valid_sale")["check"]["text"] == "✓ 27 of 30 valid (90%)"
    client.put(f"{field}/vacant_sale", json={"assume": True})
    entry = _settings(pid)["data"]["load"]["sale"]
    # Its own copy of the price: OpenAVMKit drops a calculated field another calc uses.
    assert entry["calc"]["valid_sale"] == ["?", [">=", "sale_price_num", 1000.0]]
    assert entry["calc"]["sale_price_num"] == entry["calc"]["sale_price"]
    assert list(entry["calc"]).index("sale_price_num") < list(entry["calc"]).index("valid_sale")

    _, sales = _engine(pid, monkeypatch)
    sales = sales.sort_values("key", key=lambda s: s.astype(int))
    got = sales["sale_price"].tolist()
    assert got[0] == prices[0] and got[1] == -10 and pd.isna(got[2]) and pd.isna(got[3])
    assert sales["valid_sale"].tolist() == [True, False, False, False] + [True] * (n - 4)


def test_tier_names_put_in_order_worst_to_best():
    from oakbox.wizard import tier_order

    order, name, unknown = tier_order(["B", "AA", "C+", "A", "C", "D-"])
    assert [v for v, _ in order] == ["D-", "C", "C+", "B", "A", "AA"] and name == "letter grades, AA best"
    order, name, _ = tier_order(["Good", "Poor", "AVERAGE", "Excellent", "VG", "Very Good"])
    assert [v for v, _ in order] == ["Poor", "AVERAGE", "Good", "VG", "Very Good", "Excellent"]
    assert dict(order)["VG"] == dict(order)["Very Good"] == 4  # the same tier written two ways: one number
    order, name, _ = tier_order(["C1", "C3", "C6"])
    assert [v for v, _ in order] == ["C6", "C3", "C1"] and name == "Q1–Q6 or C1–C6, 1 best"
    order, name, unknown = tier_order(["Good", "Poor", "Shiny"])
    assert [v for v, _ in order] == ["Poor", "Good", "Shiny"] and unknown == ["Shiny"]
    # Grade adjustments (B+5, A-10) order within their letter; a stray match doesn't make a column known.
    order, name, _ = tier_order(["B+5", "A-10", "C", "B"])
    assert [v for v, _ in order] == ["C", "B", "B+5", "A-10"] and name == "letter grades, AA best"
    order, name, unknown = tier_order(["D-4", "Q1", "S-3", "X-2"])
    assert name is None and unknown == ["D-4", "Q1", "S-3", "X-2"]


def test_quality_and_condition_become_numbers_where_higher_is_better(client, tmp_path, monkeypatch):
    """A number is preferred; nothing is written until its meaning is said; a category is ranked into tiers."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    n = 40
    ids = [str(i) for i in range(n)]
    gpd.GeoDataFrame({"ID": ids}, geometry=[box(i, 0, i + 1, 1) for i in range(n)], crs="EPSG:4326").to_parquet(
        tmp_path / "parcels.parquet"
    )
    grades = ["C", "B", "A", "AA"]
    eff = [1960 + i for i in range(n)]
    pd.DataFrame(
        {
            "PID": ids,
            "AREA": [1000 + 10 * i for i in range(n)],
            "EFF_YEAR": eff,
            "GRADE": [grades[i % 4] for i in range(n)],
            "QUALITY_SCORE": [1 + i % 4 for i in range(n)],
            # % depreciation as a fraction: more for older buildings
            "COND_SCORE": [round((2026 - y) / 100, 2) for y in eff],
            "COND_CODE": ["A"] * n,
        }
    ).to_csv(tmp_path / "cama.csv", index=False)
    pd.DataFrame(
        {
            "PID": ids,
            "PRICE": [100_000 * (1 + i % 4) + 1_000 * i for i in range(n)],
            "DATE": ["2024-01-02"] * n,
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("cama", "csv"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    _put_file(client, pid, "cama", holds="parcels", id_column="PID")
    field = f"/api/projects/{pid}/wizard/fields"
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"{field}/{key}", json={"file": "sale", "column": col})
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"{field}/{key}", json={"assume": True})
    w = client.post(f"/api/projects/{pid}/wizard/steps/big_five/visit").json()

    # The numbers are guessed, but which way they run isn't: a to-do, and nothing written yet.
    quality, condition = _field(w, "bldg_quality_num"), _field(w, "bldg_condition_num")
    assert quality["sources"] == [{"file": "cama", "column": "QUALITY_SCORE"}]
    assert quality["check"]["text"] == "say which way is better" and quality["scale"]["kind"] is None
    assert condition["scale"]["fraction"] and condition["check"]["text"] == "say what the numbers mean"
    assert _field(w, "bldg_quality_txt")["sources"] == []  # the number's there: the category isn't loaded
    assert {"text": "Building condition (numeric): say what the numbers mean", "blocking": False} in _step(
        w, "big_five"
    )["left"]
    load = _settings(pid)["data"]["load"]["cama"]["load"]
    assert "bldg_quality_num" not in load and "bldg_condition_num_src" not in load

    # Side by side: the code that's the same everywhere, and the score that rises with age.
    found = {c["column"]: c for c in client.get(f"{field}/bldg_condition_num/candidates").json()}
    assert found["COND_CODE"]["notes"] == ["One value on every row: tells nothing apart"] and found["COND_CODE"]["warn"]
    assert "Rises with effective age: % depreciation, or lower is better" in found["COND_SCORE"]["notes"]
    assert found["COND_SCORE"]["loaded_as"] == "number"

    # What it means, checked against age (newer should be better) and price: per sq ft once there's a size.
    depr = {"kind": "pct_depr", "fraction": True, "low": None, "high": None, "tiers": {}}
    scale = {"file": "cama", "column": "COND_SCORE", "scale": depr}
    view = client.post(f"{field}/bldg_condition_num/scale", json=scale).json()
    assert view["price_basis"] == "sale price"
    assert "no building size: choose it on this step for a fairer comparison" in view["notes"]
    client.put(f"{field}/bldg_area_finished_sqft", json={"file": "cama", "column": "AREA", "area_unit": "sqft"})
    view = client.post(
        f"{field}/bldg_condition_num/scale", json={"file": "cama", "column": "COND_SCORE", "scale": depr}
    ).json()
    assert view["fits"] == ["pct_depr", "lower"] and view["age_basis"] == "effective age"
    values = [b["value"] for b in view["by_age"]]
    assert values == sorted(values, reverse=True)  # as read, newer buildings are in better condition
    assert view["price_basis"] == "price per sq ft" and view["calc"] == ["-", 100, ["*", "bldg_condition_num_src", 100]]
    w = client.put(f"{field}/bldg_condition_num", json={"file": "cama", "column": "COND_SCORE", "scale": depr}).json()
    assert _field(w, "bldg_condition_num")["check"]["text"].startswith("✓ as % good: 0.66 → 34")
    w = client.put(
        f"{field}/bldg_quality_num",
        json={"file": "cama", "column": "QUALITY_SCORE", "scale": {**depr, "kind": "lower", "fraction": False}},
    ).json()
    assert _field(w, "bldg_quality_num")["check"]["text"] == "✓ 1–4 · flipped, so higher is better"
    assert _settings(pid)["data"]["load"]["cama"]["calc"]["bldg_quality_num"] == ["-", 5.0, "bldg_quality_num_src"]

    # A category instead: its tiers in a known order, with what each sells for; then ranked, and kept as text too.
    tiers = client.post(f"{field}/bldg_quality_num/tiers", json={"file": "cama", "column": "GRADE"}).json()
    assert tiers["recognised"] == "letter grades, AA best" and tiers["basis"] == "price per sq ft"
    assert [(t["value"], t["number"]) for t in tiers["tiers"]] == [("C", 1), ("B", 2), ("A", 3), ("AA", 4)]
    medians = [t["median"] for t in tiers["tiers"]]
    assert medians == sorted(medians) and tiers["notes"] == ["all sales: no valid-sale rule yet"]
    w = client.put(f"{field}/bldg_quality_num", json={"file": "cama", "column": "GRADE"}).json()
    assert _field(w, "bldg_quality_num")["check"]["text"] == "rank its 4 tiers"
    ranked = {**depr, "kind": "tiers", "fraction": False, "tiers": {"C": 1, "B": 2, "A": 3, "AA": 5}}
    client.put(f"{field}/bldg_quality_txt", json={"file": "cama", "column": "GRADE"})
    w = client.put(f"{field}/bldg_quality_num", json={"file": "cama", "column": "GRADE", "scale": ranked}).json()
    assert _field(w, "bldg_quality_num")["check"]["text"] == "✓ 4 tiers ranked, 1–5"
    entry = _settings(pid)["data"]["load"]["cama"]
    # One column, two fields: loaded once, as text; the category is it, the number is it ranked.
    assert entry["load"]["grade_raw"] == ["GRADE", "string"] and "bldg_quality_txt" not in entry["load"]
    assert entry["calc"]["bldg_quality_txt"] == ["set", "grade_raw"]
    assert entry["calc"]["bldg_quality_num"][1][1] == [
        "map",
        ["strip", "grade_raw"],
        {"C": "1", "B": "2", "A": "3", "AA": "5"},
    ]

    univ, _ = _engine(pid, monkeypatch)
    univ = univ.sort_values("key", key=lambda s: s.astype(int))
    assert univ["bldg_quality_num"].tolist()[:4] == [1, 2, 3, 5] and univ["bldg_quality_txt"].tolist()[:2] == ["C", "B"]
    assert univ["bldg_condition_num"].tolist()[:2] == [34, 35]  # 100 - 66, 100 - 65: % good

    # No condition at all: said, not left blank; nothing loaded.
    w = client.put(f"{field}/bldg_condition_num", json={"absent": True}).json()
    assert _field(w, "bldg_condition_num")["absent"] and _field(w, "bldg_condition_num")["sources"] == []
    assert "bldg_condition_num_src" not in _settings(pid)["data"]["load"]["cama"]["load"]


def test_ranked_tiers_still_match_values_padded_with_spaces():
    """A ranked tier written with spaces around it (fixed-width exports) still finds its number."""
    from openavmkit.calculations import perform_calculations

    from oakbox.datafiles import Scale, scale_calc

    padded = pd.DataFrame({"t": pd.Series([" Good ", "Poor", None], dtype="string")})
    tiers = Scale(kind="tiers", tiers={"Poor": 1, "Good": 2})
    out = perform_calculations(padded, {"n": scale_calc("t", tiers)})["n"].tolist()
    assert out[:2] == [2.0, 1.0] and pd.isna(out[2])


def test_bring_in_data_runs_openavmkit_and_writes_a_receipt(client, tmp_path):
    """Load and join in a process of its own; the receipt counts what came out, the rows behind it page."""
    import time

    pid = client.post("/api/projects", json=NEW).json()["id"]
    ids = [str(i) for i in range(30)] + [None]
    gpd.GeoDataFrame(
        {"ID": ids, "AREA": [1000 + i for i in range(31)]},
        geometry=[box(-79.8 + i * 0.001, 36.0, -79.8 + i * 0.001 + 0.0005, 36.0005) for i in range(31)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame(
        {
            "PID": [str(i % 30) for i in range(40)] + ["999"],
            "PRICE": [100_000 + i for i in range(41)],
            "DATE": [f"2024-01-{1 + i % 28:02d}" for i in range(41)],
            "OK": ["Q"] * 35 + ["U"] * 6,
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    url = f"/api/projects/{pid}/bring-in"
    blocked = client.get(url).json()["blocked"]
    assert blocked[0] == "Parcel universe: 1 blank ID. Resolve them on its step to drop those rows."
    assert client.post(f"{url}/run").status_code == 422  # not while Data has a problem
    _put_file(client, pid, "geo_parcels", blank_ok=True)
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    field = f"/api/projects/{pid}/wizard/fields"
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"{field}/{key}", json={"file": "sale", "column": col})
    client.put(
        f"{field}/valid_sale/rule",
        json={"join": "all", "conditions": [{"column": "OK", "op": "isin", "values": ["Q"]}]},
    )
    client.put(f"{field}/vacant_sale", json={"assume": True})
    area = {"file": "geo_parcels", "column": "AREA", "area_unit": "sqft"}
    client.put(f"{field}/bldg_area_finished_sqft", json=area)
    view = client.get(url).json()
    assert (view["status"], view["blocked"], view["receipt"]) == ("never", [], None)

    assert client.post(f"{url}/run").json()["status"] == "running"
    view: dict = {}
    for _ in range(240):
        view = client.get(url).json()
        if view["status"] != "running":
            break
        time.sleep(0.5)
    assert view["status"] == "done", view["job"]
    r = view["receipt"]
    assert (r["universe"]["rows"], r["sales"]["rows"]) == (30, 35)
    lines = {line["text"]: line for line in r["universe"]["funnels"][0]["lines"]}
    assert lines["without a parcel ID: dropped"]["n"] == 1 and lines["parcels in the parcel universe"]["n"] == 30
    sales = {line["text"]: line for line in r["sales"]["funnels"][0]["lines"]}
    invalid = sales["not valid by your valid-sale rule: left out as they load"]
    assert invalid["n"] == 6 and invalid["rows"] == "sales_invalid"
    assert all(c["ok"] for c in r["checks"])
    assert {f["field"] for f in r["sales"]["fields"]} >= {"sale_price", "sale_date", "valid_sale", "key_sale"}
    assert (
        next(f for f in r["sales"]["fields"] if f["field"] == "valid_sale")["source"] == "sale · your valid-sale rule"
    )

    # The rows behind a count, a page at a time; and all of them as CSV.
    page = client.get(f"{url}/rows/sales_invalid", params={"offset": 4, "limit": 10}).json()
    assert (page["total"], page["offset"], len(page["rows"])) == (6, 4, 2) and page["columns"][:2] == ["PID", "PRICE"]
    csv = client.get(f"{url}/rows/universe/csv").text.splitlines()
    assert len(csv) == 31 and csv[0].startswith("key")
    assert client.get(f"{url}/rows/nope").status_code == 404

    # One field in detail: a number's statistics; a category's values, searchable.
    area = client.get(f"{url}/fields/universe/bldg_area_finished_sqft").json()
    assert area["kind"] == "number" and area["rows"] == 30
    stats = {x["label"]: x["value"] for x in area["stats"]}
    assert (stats["lowest"], stats["highest"], stats["filled"]) == ("1,000", "1,029", "30")
    key = client.get(f"{url}/fields/sales/key", params={"search": "2"}).json()
    assert key["kind"] == "category" and key["distinct"] == 30 and all("2" in v["value"] for v in key["values"])
    assert client.get(f"{url}/fields/universe/nope").status_code == 404

    # Looks right, then Data changes: out of date, and no longer accepted.
    assert client.post(f"{url}/accept").json()["accepted"]
    client.put(f"{field}/vacant_sale", json={"assume": False})
    client.put(f"{field}/vacant_sale", json={"file": "sale", "column": "OK"})
    view = client.get(url).json()
    assert view["stale"] and not view["accepted"] and "how sale is read" in view["changed"]
    assert client.post(f"{url}/accept").status_code == 409


def test_own_fields_named_and_classified_as_land_building_or_other(client, pid):
    """Any parcel column under the user's name, in OpenAVMKit's land / impr / other field classification."""
    from oakbox import bring_in

    _start(client, pid)
    url = f"/api/projects/{pid}/wizard/custom"
    w = client.put(f"{url}/zone_class", json={"file": "geo_parcels", "column": "ZONE", "group": "land"}).json()
    own = {x["name"]: x for x in w["custom"]}
    assert own["zone_class"]["column"] == "ZONE" and own["zone_class"]["distinct"] == 3
    # Its values, most common first, behind the "3 values" button; searchable.
    vals = client.get(f"/api/projects/{pid}/wizard/files/geo_parcels/values", params={"column": "ZONE"}).json()
    assert (vals["rows"], vals["distinct"], vals["blank"], vals["more"]) == (6, 3, 0, 0)
    assert [(v["value"], v["count"]) for v in vals["values"]] == [("R1", 3), ("R2", 2), ("C1", 1)]
    vals = client.get(
        f"/api/projects/{pid}/wizard/files/geo_parcels/values", params={"column": "ZONE", "search": "r"}
    ).json()
    assert [v["value"] for v in vals["values"]] == ["R1", "R2"] and vals["distinct"] == 3
    s = _settings(pid)
    assert s["data"]["load"]["geo_parcels"]["load"]["zone_class"] == ["ZONE", "string"]
    assert s["field_classification"]["land"] == {"categorical": ["zone_class"]}
    before = s

    # Reclassified as a number about the building: the column reads as one, and no text value is a number.
    w = client.put(
        f"{url}/zone_class", json={"file": "geo_parcels", "column": "ZONE", "group": "building", "type": "number"}
    ).json()
    assert next(x for x in w["custom"] if x["name"] == "zone_class")["check"]["warn"]
    s = _settings(pid)
    assert s["field_classification"]["impr"] == {"numeric": ["zone_class"]} and "land" not in s["field_classification"]
    assert "your own fields" in bring_in.changes(before, s)

    # OpenAVMKit's own names, and bad ones, are refused.
    body = {"file": "geo_parcels", "column": "MAP_NO"}
    assert client.put(f"{url}/land_class", json=body).status_code == 422
    assert client.put(f"{url}/Map%20No", json=body).status_code == 422
    assert client.put(f"{url}/other_zone", json={"file": "geo_parcels", "column": "ZONE"}).status_code == 422

    w = client.put(f"{url}/zone_class", json={"file": None, "column": None}).json()
    assert w["custom"] == [] and "zone_class" not in _settings(pid)["data"]["load"]["geo_parcels"]["load"]
    assert "field_classification" not in _settings(pid)


def test_a_column_already_loaded_is_named_by_its_field(client, pid):
    _start(client, pid)
    field = f"/api/projects/{pid}/wizard/fields"
    assert client.put(f"{field}/bldg_type", json={"file": "geo_parcels", "column": "MAP_NO"}).status_code == 200
    r = client.put(f"/api/projects/{pid}/wizard/custom/map_no", json={"file": "geo_parcels", "column": "MAP_NO"})
    assert r.status_code == 422 and r.json()["detail"] == "MAP_NO is already loaded as Building type."


def test_true_values_are_not_asked(client, pid):
    """OpenAVMKit's true_* values are synthetic data's answer key: the wizard never shows or guesses them."""
    w = client.get(f"/api/projects/{pid}/wizard").json()
    assert not [f["key"] for f in w["fields"] if f["key"].startswith("true_")]
    assert _step(w, "assessed")["more"] == []


def test_condo_units_without_a_shape_borrow_their_buildings(client, tmp_path):
    """Units on the roll, not on the map: each finds its building by the start of its PIN, borrows its shape, and
    comes in with its own fields and land size (OpenAVMKit's data.process.condos)."""
    import time

    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {
            "ID": ["1", "2", "3"],
            "PIN": ["100-000", "200-000", "300-000"],
            "USE": ["COMMON", "COMMON", "RESIDENTIAL"],
            "ACRES": [2.0, 1.0, 0.25],
            "AREA": [None, None, 1500.0],
        },
        geometry=[box(-79.8 + i * 0.01, 36.0, -79.8 + i * 0.01 + 0.005, 36.005) for i in range(3)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame(
        {
            "ID": ["11", "12", "21", "22", "91", "3"],
            "PIN": ["100-001", "100-002", "200-001", "200-002", "999-001", "300-000"],
            "USE": ["CONDO", "CONDO", "CONDO", "CONDO", "CONDO", "RESIDENTIAL"],
            "ACRES": [0.01, 0.02, 0.01, 0.01, 0.01, 0.25],
            "AREA": [900.0, 1100.0, 800.0, 850.0, 700.0, 1500.0],
        }
    ).to_csv(tmp_path / "units.csv", index=False)
    pd.DataFrame({"PID": ["11", "21", "3"], "PRICE": [150_000, 140_000, 300_000], "DATE": ["2024-01-02"] * 3}).to_csv(
        tmp_path / "sale.csv", index=False
    )
    for name, ext in (("parcels", "parquet"), ("units", "csv"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _put_file(client, pid, "parcels", universe=True, id_column="ID")
    _put_file(client, pid, "sale", holds="sales", id_column="PID")
    field = f"/api/projects/{pid}/wizard/fields"
    for key, col in (("sale_price", "PRICE"), ("sale_date", "DATE")):
        client.put(f"{field}/{key}", json={"file": "sale", "column": col})
    for key in ("valid_sale", "vacant_sale"):
        client.put(f"{field}/{key}", json={"assume": True})
    for key, col in (("land_class", "USE"), ("bldg_area_finished_sqft", "AREA")):
        client.put(f"{field}/{key}", json={"file": "geo_parcels", "column": col})
    client.put(f"{field}/land_area_sqft", json={"file": "geo_parcels", "column": "ACRES", "area_unit": "acres"})
    w = _put_file(client, pid, "units", holds="parcels", id_column="ID").json()
    assert _file(w, "units")["unshaped"] == 5  # all but the house
    # Rows without a shape are Condo units' to set up: a pointer there from More files, never a stop.
    w = client.post(f"/api/projects/{pid}/wizard/steps/more_files/visit").json()
    pointer = [x for x in _step(w, "more_files")["left"] if "Condo units" in x["text"]]
    assert pointer and not pointer[0]["blocking"]
    assert not any("units:" in p for p in w["problems"])
    # Condo units asks first, worth deciding before it's reached since the files suggest units; its parts wait.
    assert _step(w, "condo_ask")["status"] == "attention" and _step(w, "condos")["status"] == "attention"
    assert not any(st["key"] == "condo_file" for st in w["steps"])
    assert "units.csv: 5 of 6 rows have a parcel ID but no shape in the parcel universe." in w["condos"]["evidence"]
    w = client.put(f"/api/projects/{pid}/wizard/condos", json={"has": True}).json()
    assert w["condos"]["answer"] is True and _step(w, "condo_ask")["status"] == "done"
    assert [f["name"] for f in w["condos"]["files"]] == ["units"] and w["condos"]["file"] is None
    w = client.post(f"/api/projects/{pid}/wizard/steps/condo_file/visit").json()
    assert _step(w, "condo_file")["status"] == "blocked"

    w = client.put(f"/api/projects/{pid}/wizard/files/units/units", json={"units": {}}).json()
    assert w["condos"]["file"] == "units" and _step(w, "condo_file")["status"] != "blocked"
    u = _file(w, "units")["units"]
    assert (u["settings"]["link"], u["settings"]["column"], u["settings"]["prefix_len"]) == ("prefix", "PIN", 3)
    assert (u["units"], u["linked"], u["buildings"]) == (5, 4, 2)
    assert u["check"]["text"] == "4 of 5 units find the parcel they're on (2 parcels) · 1 finds none: left out"
    assert u["settings"]["guessed"] and u["basis"].startswith(
        "Guessed: PIN is in both files, and its first 3 characters"
    )
    # Nothing is copied unasked: the same-named fields are offered, and given when asked.
    assert u["fields"] == []
    # Land size isn't offered while the units' land is a share of their building's.
    assert {f["field"] for f in u["offers"]} >= {"land_class", "bldg_area_finished_sqft"}
    assert "land_area_sqft" not in {f["field"] for f in u["offers"]}
    w = client.post(f"/api/projects/{pid}/wizard/steps/condo_fields/visit").json()
    assert any("could be given to the units" in x["text"] for x in _step(w, "condo_fields")["left"])
    give = {f["field"]: f["column"] for f in u["offers"]}
    w = client.put(f"/api/projects/{pid}/wizard/files/units/units/fields", json={"fields": give}).json()
    u = _file(w, "units")["units"]
    assert {f["field"] for f in u["fields"]} >= {"land_class", "bldg_area_finished_sqft"} and u["offers"] == []
    # Land: equal shares to start with (needs nothing); each unit's own land size, once there's a column for it.
    assert u["settings"]["land"] == "equal" and u["land"]["ok"]
    assert u["examples"][0]["share"].startswith("1/2 of ")
    w = client.put(
        f"/api/projects/{pid}/wizard/files/units/units", json={"units": {**u["settings"], "land": "field"}}
    ).json()
    u = _file(w, "units")["units"]
    assert not u["land"]["ok"] and any("Condo units › Land" in p for p in w["problems"])  # OpenAVMKit would stop
    assert [f["field"] for f in u["offers"]] == ["land_area_sqft"]
    w = client.put(
        f"/api/projects/{pid}/wizard/files/units/units/fields", json={"fields": {"land_area_sqft": "ACRES"}}
    ).json()
    u = _file(w, "units")["units"]
    assert u["land"]["ok"], u["land"]
    assert u["settings"]["guessed"]  # the link wasn't changed: still a guess
    # Its fields are the units' own, not a second source of the parcel universe's.
    assert _field(w, "land_class")["sources"] == [{"file": "geo_parcels", "column": "USE"}]
    assert _file(w, "units")["id_check"]["ok"]

    s = _settings(pid)
    condos = s["data"]["process"]["condos"]
    assert condos["link"] == {"method": "id_prefix", "id_field": "condo_link", "prefix_len": 3, "from": "geo_parcels"}
    assert condos["select"] == ["==", "condo_unit", True]
    assert s["data"]["load"]["geo_parcels"]["calc"]["condo_unit"] == ["?", ["isempty", "key"]]
    assert "condo_group" in s["field_classification"]["important"]["locations"]

    url = f"/api/projects/{pid}/bring-in"
    r = client.post(f"{url}/run").json()
    assert r.get("status") == "running", r
    view: dict = {}
    for _ in range(240):
        view = client.get(url).json()
        if view["status"] != "running":
            break
        time.sleep(0.5)
    assert view["status"] == "done", view["job"]
    out = projects.project_dir(pid) / "out" / "oakbox" / "bring_in"
    uni = pd.read_parquet(out / "universe.parquet").set_index("key")
    assert set(uni.index) == {"1", "2", "3", "11", "12", "21", "22"}  # 91's building isn't on the map
    assert uni.loc["11", "condo_group"] == "100" and uni.loc["22", "condo_group"] == "200"
    assert uni.loc["12", "land_class"] == "CONDO" and round(uni.loc["12", "land_area_sqft"]) == round(0.02 * 43560)
    assert uni.loc["21", "bldg_area_finished_sqft"] == 800.0
    assert view["receipt"]["sales"]["rows"] == 3  # the units' sales find them
    lines = {line["text"]: line for line in view["receipt"]["universe"]["funnels"][0]["lines"]}
    assert lines["units from units.csv, with their building's shape"]["n"] == 4
    assert all(c["ok"] for c in view["receipt"]["checks"]), view["receipt"]["checks"]
    unit_lines = {line["text"] for f in view["receipt"]["universe"]["funnels"][1:] for line in f["lines"]}
    assert "units that find no building: left out" in unit_lines

    # No land of their own (a mobile-home park, leased land): the land is the shared parcel's.
    w = client.put(
        f"/api/projects/{pid}/wizard/files/units/units", json={"units": {**u["settings"], "land": "none"}}
    ).json()
    assert _file(w, "units")["units"]["land"]["ok"]
    assert _settings(pid)["data"]["process"]["condos"]["land_share"] == {"method": "none"}
    # No condos after all: the units and the fields given them go, and so do the step's parts.
    w = client.put(f"/api/projects/{pid}/wizard/condos", json={"has": False}).json()
    assert _file(w, "units")["units"] is None and w["condos"]["file"] is None
    assert [st["key"] for st in w["steps"] if st["parent"] == "condos"] == ["condo_ask"]
    assert "condos" not in _settings(pid)["data"]["process"]
    assert any("no units, you said" in x["text"] for x in _step(w, "more_files")["left"])


def test_sales_of_parcels_missing_from_the_universe_are_a_note_not_a_reconcile(client, tmp_path):
    """IDs written like the parcel universe's that it simply lacks (condo units kept off the map, say): cleaning
    won't help, so the step says why and where they are, without holding up Next; Reconcile stays for IDs written
    differently."""
    pid = client.post("/api/projects", json={**NEW, "name": "Missing"}).json()["id"]
    gpd.GeoDataFrame(
        {"PID": [f"0012-{n:03d}" for n in range(1, 21)]}, geometry=[box(i, 0, i + 1, 1) for i in range(20)], crs=4326
    ).to_parquet(tmp_path / "shapes.parquet")
    # 20 sales on the map, 12 of units that aren't: 62% find a parcel.
    sold = [f"0012-{n:03d}" for n in range(1, 21)] + [f"0012-{n:03d}" for n in range(101, 113)]
    pd.DataFrame({"PID": sold, "SALE_PRICE": [100_000] * 32, "SALE_DATE": ["2024-01-02"] * 32}).to_csv(
        tmp_path / "sales.csv", index=False
    )
    pd.DataFrame({"PID": [f"0012-{n:03d}" for n in range(101, 131)], "AREA": [900] * 30}).to_csv(
        tmp_path / "units.csv", index=False
    )
    for name, ext in (("shapes", "parquet"), ("sales", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    w = _start(client, pid)
    sales = _file(w, "sales")
    assert sales["id_check"]["text"] == "62% of sales match a parcel"
    lines = sales["not_in_universe"]["lines"]
    assert lines[0].startswith("12 sales are for parcels that aren't in the parcel universe.")
    assert "Add it on More files" in lines[1]
    assert not any("Reconcile" in x["text"] for x in _step(w, "sales")["left"])
    assert any("12 sales are for parcels" in x for x in w["warnings"])

    # The file that has them, once it's in the project.
    body = {"path": str(tmp_path / "units.csv"), "mode": "copy", "name": "units"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    w = client.get(f"/api/projects/{pid}/wizard").json()
    assert _file(w, "sales")["not_in_universe"]["lines"][1].startswith("12 of them are in units (PID).")

    # IDs written differently are still for Reconcile.
    pd.DataFrame(
        {"PID": [v.replace("-", "") for v in sold[:20]], "SALE_PRICE": [1] * 20, "SALE_DATE": ["2024-01-02"] * 20}
    ).to_csv(tmp_path / "sales2.csv", index=False)
    body = {"path": str(tmp_path / "sales2.csv"), "mode": "copy", "name": "sales2"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    w = _put_file(client, pid, "sales2", holds="sales").json()
    assert _file(w, "sales2")["not_in_universe"] is None


def _sales_against(client, tmp_path, name, parcel_ids, sale_ids):
    pid = client.post("/api/projects", json={**NEW, "name": name}).json()["id"]
    gpd.GeoDataFrame(
        {"PID": parcel_ids},
        geometry=[box(i % 100, i // 100, i % 100 + 1, i // 100 + 1) for i in range(len(parcel_ids))],
    ).set_crs(4326).to_parquet(tmp_path / f"{name}.parquet")
    n = len(sale_ids)
    pd.DataFrame({"PID": sale_ids, "SALE_PRICE": [1] * n, "SALE_DATE": ["2024-01-02"] * n}).to_csv(
        tmp_path / f"{name}.csv", index=False
    )
    for f in (f"{name}.parquet", f"{name}.csv"):
        body = {"path": str(tmp_path / f), "mode": "copy", "name": f.replace(".", "_")}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    assert _put_file(client, pid, f"{name}_parquet", universe=True, id_column="PID").status_code == 200
    w = _put_file(client, pid, f"{name}_csv", holds="sales", id_column="PID").json()
    return pid, _file(w, f"{name}_csv")


def test_another_numbering_lower_case_and_keying_slips(client, tmp_path):
    import random

    r = random.Random(3)
    ids = sorted({f"R{r.randint(0, 9_999_999):07d}" for _ in range(2_000)})
    # Another numbering written the same way: none match. Not "missing parcels": check the ID column.
    other = [f"R{r.randint(0, 9_999_999):07d}" for _ in range(600)]
    _, sales = _sales_against(client, tmp_path, "other", ids, [v for v in other if v not in ids])
    assert sales["not_in_universe"]["kind"] == "other_id"
    assert sales["not_in_universe"]["lines"][0].startswith("Fewer than half find a parcel: is PID the parcel ID")
    # Written in small letters: a clean-up, for Reconcile.
    pid, sales = _sales_against(client, tmp_path, "lower", ids, [v.lower() for v in ids[:600]])
    assert sales["not_in_universe"] is None
    body = {"file_steps": [], "base_steps": [], "view": "unmatched", "seed": 0, "suggest": True}
    s = client.post(f"/api/projects/{pid}/wizard/files/lower_csv/reconcile", json=body).json()["suggestion"]
    assert s["text"] == "Make letters capitals in the sales IDs" and s["share"] == 1.0

    # 15% one digit off: keying slips.
    def slip(v):
        return v[:-1] + str((int(v[-1]) + 1) % 10)

    sold = [slip(v) if i % 7 == 0 else v for i, v in enumerate(ids[:700])]
    _, sales = _sales_against(client, tmp_path, "slips", ids, sold)
    lines = sales["not_in_universe"]["lines"]
    assert any(x.startswith("About ") and "keying slips" in x for x in lines)
    assert not any("Add it on More files" in x for x in lines)  # nearly all slips: no talk of missing parcels

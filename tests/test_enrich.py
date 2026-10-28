"""F3e Enrichments, F3f Deeds and F3g Permits: what each writes for OpenAVMKit, and how a failed download is
skipped rather than stopping Bring in data."""

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box
from test_data_files import NEW
from test_wizard import _files, _put_file, _settings, _start, _step

from oakbox import enrichments, projects
from oakbox.app import create_app


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def pid(client, tmp_path):
    """test_wizard's project: a parcel file with shapes, CAMA, sales and more."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    _files(tmp_path)
    for name in ("shapes", "cama", "sales"):
        ext = "parquet" if name == "shapes" else "csv"
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    return pid


def _visit(client, pid, step):
    return client.post(f"/api/projects/{pid}/wizard/steps/{step}/visit").json()


# ---------- Enrichments ----------


def test_enrichments_start_on_and_write_openavmkit_settings(client, pid):
    _start(client, pid)
    before = _settings(pid)["data"].get("process", {}).get("enrich", {})
    assert "overture" not in before and "dem" not in before  # nothing until the step is shown
    _visit(client, pid, "enrich")
    v = client.get(f"/api/projects/{pid}/wizard/enrich").json()
    s = v["settings"]
    assert (s["distances"], s["footprints"], s["census"], s["elevation"]) == (True, True, False, True)
    assert s["features"]["parks"] == {"on": True, "max_distance": 1.0, "top_n": 3}
    assert s["features"]["coastline"]["on"] is False
    # The fixture's parcels are degree-sized: a big area, so coarse elevation tiles.
    assert v["area"]["km2"] > 8_000 and v["resolution"] == 60 and s["resolution_m"] == 60
    enrich = _settings(pid)["data"]["process"]["enrich"]
    assert enrich["overture"]["footprint"] == {"units": "sqft", "field": "bldg_area_footprint_sqft"}
    assert enrich["dem"] == {"enabled": True, "resolution_m": 60}
    assert enrich["distances"]["parks"] == {
        "osm": True,
        "max_distance": 1.0,
        "unit": "mile",
        "store_top": True,
        "top_n": 3,
    }
    assert "coastline" not in enrich["distances"] and "census" not in enrich

    # Census: needs the county and the user's key, kept on this computer, never in the project.
    s |= {"census": True, "fips": "48453", "census_year": 2021}
    v = client.put(f"/api/projects/{pid}/wizard/enrich", json=s).json()
    assert _settings(pid)["data"]["process"]["enrich"]["census"] == {"enabled": True, "fips": "48453", "year": 2021}
    left = _step(client.get(f"/api/projects/{pid}/wizard").json(), "enrich")["left"]
    assert [x["text"] for x in left] == ["Census: add your API key"]
    assert client.put("/api/census-key", json={"key": "abcdef123456"}).status_code == 200
    v = client.get(f"/api/projects/{pid}/wizard/enrich").json()
    assert v["key_saved"] and v["key_end"] == "3456"
    assert "abcdef" not in client.get("/api/app-settings").text
    assert "abcdef" not in (projects.project_dir(pid) / "in" / "settings.json").read_text(encoding="utf-8")
    assert _step(client.get(f"/api/projects/{pid}/wizard").json(), "enrich")["left"] == []

    bad = client.put(f"/api/projects/{pid}/wizard/enrich", json=s | {"fips": "99999"})
    assert bad.status_code == 422
    assert "drop_fields" not in _settings(pid)["data"]["process"]["enrich"]  # every field, to start with


def test_the_fields_each_enrichment_adds_can_be_chosen(client, pid):
    """Each field ticked or not: unticked ones are dropped as the run ends (the largest features' distances by a
    pattern); an enrichment with none ticked isn't downloaded."""
    _start(client, pid)
    _visit(client, pid, "enrich")
    v = client.get(f"/api/projects/{pid}/wizard/enrich").json()
    adds = {a["enrichment"]: a["fields"] for a in v["adds"]}
    assert [f["key"] for f in adds["distances"]] == ["dist_to", "within", "proximity_to"]
    assert adds["distances"][1]["name"] == "within_osm_<feature>" and adds["distances"][1]["what"]
    assert [f["name"] for f in adds["elevation"]] == ["elevation_mean_ft", "elevation_stdev_ft", "slope_mean_deg"]
    assert all(f["on"] for a in adds.values() for f in a)

    s = v["settings"] | {"kinds": ["dist_to"], "off": ["bldg_height_ft", "elevation_stdev_ft"]}
    v = client.put(f"/api/projects/{pid}/wizard/enrich", json=s).json()
    adds = {a["enrichment"]: {f["key"]: f["on"] for f in a["fields"]} for a in v["adds"]}
    assert adds["distances"] == {"dist_to": True, "within": False, "proximity_to": False}
    assert not adds["footprints"]["bldg_height_ft"] and adds["footprints"]["bldg_area_footprint_sqft"]
    enrich = _settings(pid)["data"]["process"]["enrich"]
    drop = enrich["drop_fields"]["universe"]
    assert {"bldg_height_ft", "elevation_stdev_ft", "within_osm_parks", "within_osm_parks_*"} <= set(drop)
    assert "dist_to_osm_parks" not in drop and enrich["drop_fields"]["sales"] == drop
    assert "overture" in enrich and "dem" in enrich

    # Every field of one unticked: not downloaded at all, and the step says so.
    s |= {"off": ["elevation_mean_ft", "elevation_stdev_ft", "slope_mean_deg"]}
    client.put(f"/api/projects/{pid}/wizard/enrich", json=s)
    enrich = _settings(pid)["data"]["process"]["enrich"]
    assert "dem" not in enrich and not any(f.startswith("elevation") for f in enrich["drop_fields"]["universe"])
    left = _step(client.get(f"/api/projects/{pid}/wizard").json(), "enrich")["left"]
    assert "Elevation: every field is unticked, so nothing is downloaded" in [x["text"] for x in left]
    assert client.put(f"/api/projects/{pid}/wizard/enrich", json=s | {"off": ["nope"]}).status_code == 422


def test_the_county_comes_from_the_projects_place():
    assert enrichments.guess_county("NC", "Guilford County") == "37081"
    assert enrichments.guess_county("NC", "Guilford") == "37081"
    assert enrichments.guess_county("LA", "Orleans Parish") == "22071"
    assert enrichments.guess_county("NC", "Nowhere") is None


def _parcels():
    return gpd.GeoDataFrame({"key": ["a", "b", "c"]}, geometry=[box(i, 0, i + 1, 1) for i in range(3)], crs=4326)


@pytest.fixture
def engine(monkeypatch, tmp_path):
    """OpenAVMKit's enrichment functions, replaced by fakes before OAK box wraps them."""
    from openavmkit import data

    monkeypatch.chdir(tmp_path)
    for name in enrichments.STEPS:
        monkeypatch.setattr(data, name, getattr(data, name))  # put back afterwards
    monkeypatch.setattr(enrichments, "reachable", lambda url, timeout=10: None)
    return data


SETTINGS = {
    "data": {
        "process": {
            "enrich": {
                "overture": {"enabled": True},
                "dem": {"enabled": True},
                "distances": {
                    "enabled": True,
                    "lakes": {"source": "lakes"},  # a map layer of the user's: not an enrichment
                    "water_bodies": {"osm": True},
                    "parks": {"osm": True},
                    "coastline": {"osm": True},
                },
            }
        }
    }
}


def test_a_failed_enrichment_is_skipped_and_says_why(engine, monkeypatch):
    def overture(df, s, *a, **k):
        raise OSError("S3 said no")

    def distances(df, s, *a, **k):
        print("Getting water_bodies from OSM...")
        print("Getting parks from OSM...")
        print("ERROR in _get_thing: 504 Gateway Timeout")
        print("Getting coastline from OSM...")
        return df.assign(dist_to_osm_water_bodies=[1.0, None, 2.0], dist_to_lakes=1.0)

    monkeypatch.setattr(engine, "_enrich_df_overture", overture)
    monkeypatch.setattr(engine, "_enrich_df_distances", distances)
    monkeypatch.setattr(engine, "_enrich_df_dem", lambda df, s, *a, **k: df.assign(elevation_mean_ft=[1.0, 2.0, 3.0]))
    lines = []
    results = enrichments.instrument(SETTINGS, lambda **kw: lines.append(kw["step"]))
    df = _parcels()
    df = engine._enrich_df_overture(df, {}, {}, {})
    df = engine._enrich_df_distances(df, {"enabled": True}, {})
    df = engine._enrich_df_dem(df, {"enabled": True}, {})
    assert lines == ["footprints", "distances", "elevation"]
    by = {r.key: r for r in results}
    assert by["footprints"].status == "skipped" and by["footprints"].text == "Skipped: OSError: S3 said no"
    d = by["distances"]
    assert d.status == "partial" and d.fields == ["dist_to_osm_water_bodies"]  # not the layer's own
    assert [(f.key, f.status) for f in d.features] == [
        ("water_bodies", "ok"),
        ("parks", "failed"),
        ("coastline", "none"),
    ]
    assert d.features[1].text == "504 Gateway Timeout"
    assert by["elevation"].status == "ok" and by["elevation"].text == "every parcel"


def test_a_service_that_cant_be_reached_is_skipped_at_once(engine, monkeypatch):
    called = []
    monkeypatch.setattr(engine, "_enrich_df_overture", lambda df, *a, **k: called.append(1) or df)
    monkeypatch.setattr(
        enrichments, "reachable", lambda url, timeout=10: "overturemaps-us-west-2.s3.amazonaws.com didn't answer"
    )
    results = enrichments.instrument(SETTINGS, lambda **kw: None)
    df = engine._enrich_df_overture(_parcels(), {}, {}, {})
    assert called == [] and len(df) == 3
    assert results[0].status == "skipped" and "didn't answer" in results[0].text


# ---------- Deeds ----------


def test_deed_book_and_page_become_the_deed_id_sales_scrutiny_reads(client, tmp_path, monkeypatch):
    pid = client.post("/api/projects", json={**NEW, "name": "Deeds"}).json()["id"]
    gpd.GeoDataFrame({"PID": list("abcd")}, geometry=[box(i, 0, i + 1, 1) for i in range(4)], crs=4326).to_parquet(
        tmp_path / "shapes.parquet"
    )
    pd.DataFrame(
        {
            "PID": list("abcd"),
            "PRICE": [500_000, 500_000, 210_000, 99_000],
            "SALE_DATE": ["2024-05-01", "2024-05-01", "2024-06-01", "2024-07-01"],
            # a and b on one deed the same day; d has no deed.
            "BOOK": ["123", "123", "124", ""],
            "PAGE": ["45", "45", "9", ""],
        }
    ).to_csv(tmp_path / "sales.csv", index=False)
    for name, ext in (("shapes", "parquet"), ("sales", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _start(client, pid)
    w = _visit(client, pid, "deeds")
    assert {f["key"]: f["sources"] for f in w["fields"] if f["step"] == "deeds" and f["sources"]} == {
        "deed_book": [{"file": "sales", "column": "BOOK"}],
        "deed_page": [{"file": "sales", "column": "PAGE"}],
    }
    assert (w["deeds"]["deeds"], w["deeds"]["sales"], w["deeds"]["blank"]) == (1, 2, 1)
    s = _settings(pid)
    assert s["analysis"]["sales_scrutiny"]["deed_id"] == "deed_book_and_page"

    from openavmkit.pipeline import load_dataframes, load_settings

    monkeypatch.chdir(projects.project_dir(pid))
    sales = load_dataframes(load_settings("in/settings.json"))["sales"]
    assert sales["deed_book_and_page"].tolist()[:3] == ["123-45", "123-45", "124-9"]
    assert pd.isna(sales["deed_book_and_page"].iloc[3])

    # A deed ID column wins over book and page; "I don't have these" leaves the heuristic off.
    assert client.post(f"/api/projects/{pid}/wizard/steps/deeds/skip").status_code == 200
    assert "analysis" not in _settings(pid)


# ---------- Permits ----------


def test_permits_are_guessed_and_written_for_openavmkit(client, tmp_path, monkeypatch):
    pid = client.post("/api/projects", json={**NEW, "name": "Permits"}).json()["id"]
    gpd.GeoDataFrame({"PID": list("abc")}, geometry=[box(i, 0, i + 1, 1) for i in range(3)], crs=4326).to_parquet(
        tmp_path / "shapes.parquet"
    )
    pd.DataFrame({"PID": list("abc"), "SALE_PRICE": [1, 2, 3], "SALE_DATE": ["2024-05-01"] * 3}).to_csv(
        tmp_path / "sales.csv", index=False
    )
    pd.DataFrame(
        {
            "PERMIT_NO": ["P1", "P2", "P3", "P4"],
            "PID": ["a", "a", "b", "zz"],
            "ISSUED": ["2024-06-01", "2019-03-01", "2020-01-01", "2020-01-01"],
            "WORK_TYPE": ["DEMOLITION", "ADDITION", "REROOF", "INTERIOR REMODEL"],
        }
    ).to_csv(tmp_path / "permits.csv", index=False)
    for name, ext in (("shapes", "parquet"), ("sales", "csv"), ("permits", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    _start(client, pid)
    w = _put_file(client, pid, "permits", holds="permits").json()
    p = w["permits"]
    assert (p["settings"]["date"], p["settings"]["date_format"], p["settings"]["type"]) == (
        "ISSUED",
        "%Y-%m-%d",
        "WORK_TYPE",
    )
    assert {k["value"]: k["means"] for k in p["kinds"]} == {
        "DEMOLITION": "teardown",
        "ADDITION": "major",
        "REROOF": "none",
        "INTERIOR REMODEL": "major",
    }
    permits = next(f for f in w["files"] if f["name"] == "permits")
    assert permits["id_check"]["text"] == "4 permits · 75% find a parcel"
    s = _settings(pid)["data"]
    assert s["process"]["enrich"]["permits"] == {
        "sources": ["permits"],
        "max_days_to_demo": 365,
        "calc_effective_age": False,  # no year built loaded
    }
    assert "permits" not in s["process"]["merge"]["universe"]

    # Saying what one kind means; the rest stay as shown.
    settings = p["settings"] | {"means": {**p["settings"]["means"], "INTERIOR REMODEL": "minor"}, "max_days": 180}
    r = client.put(f"/api/projects/{pid}/wizard/files/permits/permits", json={"permits": settings})
    assert r.status_code == 200

    from openavmkit.pipeline import load_dataframes, load_settings

    monkeypatch.chdir(projects.project_dir(pid))
    df = load_dataframes(load_settings("in/settings.json"))["permits"]
    assert df["is_teardown"].tolist() == [True, False, False, False]
    assert df["is_renovation"].tolist() == [False, True, False, True]
    assert df["renovation_num"].tolist() == [0, 3, 0, 1]
    assert pd.api.types.is_datetime64_any_dtype(df["date"])

    r = client.put(f"/api/projects/{pid}/wizard/files/permits/permits", json={"permits": None})
    assert "permits" not in _settings(pid)["data"]["process"].get("enrich", {})

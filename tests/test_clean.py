"""Step 3, Check sales (SPEC F6): the calls written as OpenAVMKit's settings, the run's receipt, and the review of the
sales set aside."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_groups import brought_in  # noqa: F401 - the shared project, data brought in

from oakbox import bring_in, clean, projects
from oakbox.app import create_app


def _wait(client, url):
    view: dict = {}
    for _ in range(360):
        view = client.get(url).json()
        if view["status"] != "running":
            return view
        time.sleep(0.5)
    raise AssertionError("still running")


def _settings(pid):
    return json.loads((projects.project_dir(pid) / "in" / "settings.json").read_text(encoding="utf-8"))


def test_the_calls_are_openavmkit_settings():
    p = projects.Project.model_validate(
        {"id": "x", "name": "x", "created_at": "2026-01-01T00:00:00", "tax_year": 2026, "valuation_date": "2026-01-01"}
    )
    assert clean.settings(p) == {}  # nothing until the step is used
    p.clean.location = "neighborhood"
    s = clean.settings(p)
    assert s["modeling"]["metadata"]["use_sales_from"] == {"improved": 2021, "vacant": 2021}
    assert s["data"]["process"]["time_adjustment"] == {"use": True, "period": "Q"}
    ss = s["analysis"]["sales_scrutiny"]
    # Nothing reaches modeling unseen: drops on, the user's keeps exempt, a second pass for hidden outliers.
    assert ss["drop"] == {"clusters": True, "heuristics": True} and ss["passes"] == 2
    # Nominal prices (a $10 deed) are set aside, under 1,000 unless changed.
    assert ss["heuristics"]["nominal_price"] and ss["nominal_price"] == {"below": 1000}
    assert (ss["keep_file"], ss["invalid_key_file"], ss["location"]) == (
        clean.KEEP_FILE,
        clean.EXCLUDE_FILE,
        "neighborhood",
    )

    p.clean.sales_from, p.clean.vacant_from = 2023, 2019
    p.clean.fills = {"slope": clean.Fill(method="median"), "lot": clean.Fill(method="zero", scope="vacant")}
    p.clean.fills["skip"] = clean.Fill(method="leave")
    p.clean.location, p.clean.checks = "", {"dupe_date_price": False}
    s = clean.settings(p)
    assert s["modeling"]["metadata"]["use_sales_from"] == {"improved": 2023, "vacant": 2019}
    # Added to OpenAVMKit's own fill lists ("+"), not replacing them.
    assert s["data"]["process"]["fill"] == {"+median": ["slope"], "+zero_vacant": ["lot"]}
    assert s["analysis"]["sales_scrutiny"]["location"] is None
    assert s["analysis"]["horizontal_equity"] == {"location": None}
    assert s["analysis"]["sales_scrutiny"]["heuristics"]["dupe_date_price"] is False
    # Merged into the rest, dicts all the way down.
    merged = clean.merge({"analysis": {"sales_scrutiny": {"deed_id": "deed_id"}}}, s)
    assert merged["analysis"]["sales_scrutiny"]["deed_id"] == "deed_id"


def test_its_calls_dont_put_bring_in_data_out_of_date():
    before = {"data": {"load": {"a": {}}, "process": {"merge": {"universe": ["a"]}}}}
    after = clean.merge(before, {"data": {"process": {"fill": {"+median": ["x"]}, "time_adjustment": {"use": False}}}})
    assert bring_in.settings_hash(before) == bring_in.settings_hash(after)


def test_check_sales_and_review_them(brought_in, monkeypatch):  # noqa: F811
    tmp, pid = brought_in
    monkeypatch.setenv("OAKBOX_HOME", str(tmp / "home"))
    client = TestClient(create_app())
    url = f"/api/projects/{pid}/clean"
    assert client.get(url).json()["blocked"]  # step 2 first
    assert client.get(f"{url}/setup").status_code == 409
    groups = client.post(f"/api/projects/{pid}/groups/start", json={"how": "suggested"}).json()["groups"]
    client.put(f"/api/projects/{pid}/groups", json={"groups": groups})
    assert client.post(f"/api/projects/{pid}/assemble/run").status_code == 200
    assert _wait(client, f"/api/projects/{pid}/assemble")["status"] == "done"

    setup = client.get(f"{url}/setup").json()
    assert (setup["valuation_year"], setup["sales_from"], setup["total"]) == (2026, 2021, 47)
    assert {y["year"] for y in setup["years"]} == {2023, 2024}
    assert setup["in_window"] == 47
    # Finished area is blank on some parcels, but 0 means no building: never proposed a fill.
    area = next((f for f in setup["fills"] if f["field"] == "bldg_area_finished_sqft"), None)
    assert area is None or area["proposed"]["method"] == "leave"

    setup = client.patch(f"{url}/setup", json={"sales_from": 2024, "vacant_from": 2024}).json()
    assert setup["sales_from"] == 2024 and 0 < setup["in_window"] < 47
    assert _settings(pid)["modeling"]["metadata"]["use_sales_from"] == {"improved": 2024, "vacant": 2024}
    setup = client.patch(f"{url}/setup", json={"sales_from": None, "vacant_from": None}).json()
    assert setup["sales_from"] == 2021
    assert _settings(pid)["analysis"]["sales_scrutiny"]["passes"] == 2

    assert client.post(f"{url}/run").json()["status"] == "running"
    view = _wait(client, url)
    assert view["status"] == "done", view["job"]
    r = view["receipt"]
    # The funnel adds up: from the valid sales to the sales for modeling.
    total = sum(-x["count"] if x["sign"] == "-" else x["count"] for x in r["funnel"] if x["sign"] in ("", "-", "+"))
    assert r["funnel"][0]["count"] == 47 and r["funnel"][-1]["count"] == r["used"] == total
    assert sum(g["used"] for g in r["groups"]) == r["used"]
    assert any(w["path"] == "out/2-clean-sup.pickle" for w in r["written"])
    # The five-pattern table: all groups first; each sale far from its group counted once, by its pattern.
    assert r["patterns"][0]["group"] == "" and set(r["patterns"][0]["counts"]) == {"1", "2", "3", "4", "5", "other"}
    assert _settings(pid)["analysis"]["sales_scrutiny"]["patterns"] == "strict"

    page = client.get(f"{url}/review").json()
    assert page["all"] == r["set_aside"] and page["undecided"] == page["all"]
    if page["items"]:
        key = page["items"][0]["key_sale"]
        sale = client.get(f"{url}/review/{key}").json()
        assert sale["item"]["key_sale"] == key and isinstance(sale["related"], list)
        first = page["items"][0]
        if "cluster" in first["checks"]:
            assert first["per_area_rating"] in ("low", "in", "high") and first["pattern"]
            only = client.get(f"{url}/review", params={"pattern": first["pattern"].split(",")[0]}).json()
            assert only["total"] >= 1
        # Keeping needs a note: why it's a market sale.
        assert client.put(f"{url}/marks/{key}", json={"action": "keep", "note": " "}).status_code == 422
        view = client.put(f"{url}/marks/{key}", json={"action": "keep", "note": "Arm's length"}).json()
        assert view["stale"]
        keep = (projects.project_dir(pid) / "in" / "oakbox" / "keep.csv").read_text(encoding="utf-8")
        assert f"{key},Arm's length" in keep
        assert client.get(f"{url}/review", params={"status": "kept"}).json()["total"] == 1
        assert client.post(f"{url}/accept").status_code == 409  # run again first
        client.put(f"{url}/marks/{key}", json={"action": None})
    assert client.post(f"{url}/accept").json()["accepted"]

    # The time adjustment, worked out alone before a run.
    assert client.post(f"{url}/time/run").json()["status"] == "running"
    time_view = _wait(client, f"{url}/time")
    assert time_view["status"] == "done", time_view["job"]
    assert {g["id"] for g in time_view["result"]["groups"]} == {g["id"] for g in groups}

    # A group's own time adjustment file: OpenAVMKit reads it, and every problem is said.
    sample = Path(__file__).parents[1] / "sample" / "us-nc-guilford-synth" / "in"
    a, b = groups[0]["id"], groups[1]["id"]
    check = client.post(f"{url}/time/file/{a}", json={"path": str(sample / "time_adjustment_index_broken.csv")}).json()
    assert not check["ok"] and len(check["problems"]) >= 3
    assert "spring 2015" in " ".join(check["problems"])
    check = client.post(f"{url}/time/file/{a}", json={"path": str(sample / "time_adjustment_index.csv")}).json()
    assert check["ok"] and check["file"]["periods"] == 40, check
    assert client.post(f"{url}/time/file/nope", json={"path": "x.csv"}).status_code == 404
    ta = _settings(pid)["data"]["process"]["time_adjustment"]
    assert ta["from_file"] == {a: f"in/oakbox/time_adjustment/{a}.csv"} and a in ta["__file_digests"]
    assert (projects.project_dir(pid) / ta["from_file"][a]).is_file()
    # Another group borrows it; a group can't borrow from itself.
    assert client.put(f"{url}/time/borrow", json={"group": b, "source": b}).status_code == 422
    setup = client.put(f"{url}/time/borrow", json={"group": b, "source": a}).json()
    mine = {g["id"]: g for g in setup["groups"]}
    assert mine[a]["file"]["name"] == "time_adjustment_index.csv" and mine[b]["borrow"] == a
    assert _settings(pid)["data"]["process"]["time_adjustment"]["borrow"] == {b: a}
    assert client.get(url).json()["stale"]  # the time adjustment changed since Check sales ran
    assert client.get(f"{url}/time").json()["stale"]
    client.post(f"{url}/time/run")
    time_view = _wait(client, f"{url}/time")
    assert time_view["status"] == "done", time_view["job"]
    curves = {g["id"]: g for g in time_view["result"]["groups"]}
    assert curves[a]["per_year"] == curves[b]["per_year"] and curves[a]["per_year"] > 0
    client.post(f"{url}/run")  # and Check sales itself, which runs in the project folder
    view = _wait(client, url)
    assert view["status"] == "done", view["job"]
    ran = {g["id"]: g for g in view["receipt"]["groups"]}
    assert ran[a]["per_year"] == ran[b]["per_year"] == curves[a]["per_year"]
    # Back to their own sales: the file is set aside, the borrowing undone.
    client.put(f"{url}/time/borrow", json={"group": a, "source": None})
    setup = client.put(f"{url}/time/borrow", json={"group": b, "source": None}).json()
    assert all(g["file"] is None and g["borrow"] is None for g in setup["groups"])
    ta = _settings(pid)["data"]["process"]["time_adjustment"]
    assert "borrow" not in ta and not ta.get("from_file")
    client.post(f"{url}/run")
    assert _wait(client, url)["status"] == "done"
    assert client.post(f"{url}/accept").json()["accepted"]

    # Step 4: the values checked against the sales Check sales kept.
    rv = f"/api/projects/{pid}/ratio"
    setup = client.get(f"{rv}/setup").json()
    assert [f["field"] for f in setup["fields"] if f["chosen"]] == ["assr_market_value"]
    if setup["fields"]:
        client.patch(f"{rv}/setup", json={"start": "2020-01-01"})
        assert client.post(f"{rv}/run").json()["status"] == "running"
        view = _wait(client, rv)
        assert view["status"] == "done", view["job"]
        result = view["receipt"]["results"][0]
        assert {g["id"] for g in result["groups"]} == {g["id"] for g in groups}
        assert result["overall"]["sales"] == sum(g["sales"] for g in result["groups"])
        points = client.get(f"{rv}/map", params={"field": "assr_market_value"}).json()
        assert len(points) == result["overall"]["sales"] + result["overall"]["trimmed"]
        assert all({"lat", "lon", "ratio"} <= set(x) for x in points)
        assert client.post(f"{rv}/accept").json()["accepted"]
        client.patch(f"{rv}/setup", json={"price": "sold", "targets": {**setup["targets"], "level_low": 0.5}})
        assert client.get(rv).json()["stale"]

    # Step 5 begins: the fills and folding Check sales left out, on what it wrote.
    client.patch(f"{url}/setup", json={"collapse": True, "collapse_sales_min": 2, "collapse_univ_min": 2})
    assert not client.get(url).json()["stale"]  # the fields' preparation doesn't put Check sales out of date
    prep = f"/api/projects/{pid}/prepare"
    assert client.get(prep).json()["blocked"] == []
    assert client.post(f"{prep}/run").json()["status"] == "running"
    view = _wait(client, prep)
    assert view["status"] == "done", view["job"]
    assert any(w["path"] == "out/2-clean-sup.pickle" for w in view["receipt"]["written"])
    assert client.post(f"{prep}/accept").json()["accepted"]
    client.patch(f"{url}/setup", json={"collapse_sales_min": 3})
    assert client.get(prep).json()["stale"]


@pytest.mark.parametrize("value", ["", "None", "nan", None])
def test_a_sale_with_no_parcel_has_no_group(value):
    assert clean._group(value) == clean.NO_PARCEL


@pytest.mark.parametrize(
    ("field", "method"),
    [
        ("renovation_num", "zero"),  # blank: no renovation permit
        ("days_to_reno", "leave"),  # blank: no date to count from
        ("land_area_alloc_sqft", "leave"),  # only condo units have a share of land
        ("median_income", "median"),
        ("bldg_area_finished_sqft", "leave"),  # blank: no building
    ],
)
def test_fills_proposed_from_what_a_blank_means(field, method):
    fill, why = clean.propose(field)
    assert fill.method == method and why


def test_a_failed_write_fails_the_run():
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn("Failed to output sup: Conversion failed for column demo_date with type object", stacklevel=1)
    with pytest.raises(
        RuntimeError, match="couldn't write notebook 2's output: Conversion failed for column demo_date"
    ):
        bring_in.written(caught, "notebook 2's output")
    bring_in.written([], "notebook 2's output")  # nothing said: written

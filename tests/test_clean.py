"""Step 3, Check sales (SPEC F6): the calls written as OpenAVMKit's settings, the run's receipt, and the review of the
sales set aside."""

from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import read_settings, wait

from oakbox import bring_in, clean, projects, steps
from oakbox.app import create_app


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


# ---------- Steps 2 to 5 through the API, on the project brought in (conftest.brought_in) ----------
# Each fixture below runs one step and accepts it, building on the one before; a test checks what that step did. A
# test that changes the project puts it back as it was, so the next fixtures and tests find it as they expect.

SAMPLE = Path(__file__).parents[1] / "sample" / "us-nc-guilford-synth" / "in"


@contextmanager
def _api(brought_in):
    """A client on the shared project, for the module's fixtures (each test's own home isn't set yet)."""
    tmp, pid = brought_in
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OAKBOX_HOME", str(tmp / "home"))
        yield TestClient(create_app()), pid


def _urls(pid):
    return f"/api/projects/{pid}/clean", f"/api/projects/{pid}/prepare"


@pytest.fixture(scope="module")
def before_groups(brought_in):
    """Check sales before Model groups is run and accepted: its view, and its setup's status code."""
    with _api(brought_in) as (client, pid):
        url = _urls(pid)[0]
        return client.get(url).json(), client.get(f"{url}/setup").status_code


@pytest.fixture(scope="module")
def assembled(before_groups, brought_in):
    """Model groups (the suggested ones) run and accepted: the groups."""
    with _api(brought_in) as (client, pid):
        groups = client.post(f"/api/projects/{pid}/groups/start", json={"how": "suggested"}).json()["groups"]
        # The sample's groups are small: each is ticked to be modeled, so every step after has them all.
        groups = [g | {"modeled": True} for g in groups]
        client.put(f"/api/projects/{pid}/groups", json={"groups": groups})
        assert client.post(f"/api/projects/{pid}/assemble/run").status_code == 200
        assert wait(client, f"/api/projects/{pid}/assemble")["status"] == "done"
        assert client.post(f"/api/projects/{pid}/assemble/accept").json()["accepted"]
    return groups


@pytest.fixture(scope="module")
def checked(assembled, brought_in):
    """Check sales run on the calls it proposes: its view."""
    with _api(brought_in) as (client, pid):
        url = _urls(pid)[0]
        assert client.post(f"{url}/run").json()["status"] == "running"
        view = wait(client, url)
        assert view["status"] == "done", view["job"]
    return view


@pytest.fixture(scope="module")
def checked_accepted(checked, brought_in):
    """That run accepted (Looks right)."""
    with _api(brought_in) as (client, pid):
        assert client.post(f"{_urls(pid)[0]}/accept").json()["accepted"]


@pytest.fixture(scope="module")
def time_worked_out(checked_accepted, brought_in):
    """The time adjustment worked out alone, before a run: its view."""
    with _api(brought_in) as (client, pid):
        url = _urls(pid)[0]
        assert client.post(f"{url}/time/run").json()["status"] == "running"
        time_view = wait(client, f"{url}/time")
        assert time_view["status"] == "done", time_view["job"]
    return time_view


@pytest.fixture(scope="module")
def own_time_files(time_worked_out, assembled, brought_in):
    """A group's own time adjustment file and another group borrowing it, the time adjustment and Check sales run on
    them, then both undone and Check sales run and accepted again: what was said along the way, for its test.

    A fixture, not a test, because Check sales runs again: Prepare and the steps after it start from this run."""
    a, b = assembled[0]["id"], assembled[1]["id"]
    said: dict = {"a": a, "b": b}
    with _api(brought_in) as (client, pid):
        url = _urls(pid)[0]
        pdir = projects.project_dir(pid)

        def check(name, group=a):
            return client.post(f"{url}/time/file/{group}", json={"path": str(SAMPLE / name)})

        said["broken"] = check("time_adjustment_index_broken.csv").json()
        said["file"] = check("time_adjustment_index.csv").json()
        said["no_group"] = client.post(f"{url}/time/file/nope", json={"path": "x.csv"}).status_code
        said["file_settings"] = read_settings(pid)["data"]["process"]["time_adjustment"]
        copied = said["file_settings"].get("from_file", {}).get(a)
        said["copied"] = bool(copied) and (pdir / copied).is_file()
        said["own"] = client.put(f"{url}/time/borrow", json={"group": b, "source": b}).status_code
        said["borrowed"] = client.put(f"{url}/time/borrow", json={"group": b, "source": a}).json()
        said["borrow_settings"] = read_settings(pid)["data"]["process"]["time_adjustment"]
        said["check_stale"] = client.get(url).json()["stale"]
        said["time_stale"] = client.get(f"{url}/time").json()["stale"]
        client.post(f"{url}/time/run")
        said["time"] = wait(client, f"{url}/time")
        client.post(f"{url}/run")  # and Check sales itself, which runs in the project folder
        said["checked"] = wait(client, url)
        # Back to their own sales.
        client.put(f"{url}/time/borrow", json={"group": a, "source": None})
        said["undone"] = client.put(f"{url}/time/borrow", json={"group": b, "source": None}).json()
        said["undone_settings"] = read_settings(pid)["data"]["process"]["time_adjustment"]
        client.post(f"{url}/run")
        assert wait(client, url)["status"] == "done"
        assert client.post(f"{url}/accept").json()["accepted"]
    return said


@pytest.fixture(scope="module")
def prepared(own_time_files, brought_in):
    """Step 5 begins: Prepare, with folding on, run and accepted: its view."""
    with _api(brought_in) as (client, pid):
        url, prep = _urls(pid)
        client.patch(f"{url}/setup", json={"collapse": True, "collapse_sales_min": 2, "collapse_univ_min": 2})
        assert client.post(f"{prep}/run").json()["status"] == "running"
        view = wait(client, prep)
        assert view["status"] == "done", view["job"]
        assert client.post(f"{prep}/accept").json()["accepted"]
    return view


def test_check_sales_waits_for_model_groups(before_groups):
    view, setup = before_groups
    assert view["blocked"]  # step 2 first
    assert setup == 409


def test_the_sales_window_and_fills_proposed(assembled, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    url = _urls(pid)[0]
    setup = client.get(f"{url}/setup").json()
    assert (setup["valuation_year"], setup["sales_from"], setup["total"]) == (2026, 2021, 47)
    assert {y["year"] for y in setup["years"]} == {2023, 2024}
    assert setup["in_window"] == 47
    # Finished area is blank on some parcels, but 0 means no building: never proposed a fill.
    area = next((f for f in setup["fills"] if f["field"] == "bldg_area_finished_sqft"), None)
    assert area is None or area["proposed"]["method"] == "leave"

    try:
        setup = client.patch(f"{url}/setup", json={"sales_from": 2024, "vacant_from": 2024}).json()
        assert setup["sales_from"] == 2024 and 0 < setup["in_window"] < 47
        assert read_settings(pid)["modeling"]["metadata"]["use_sales_from"] == {"improved": 2024, "vacant": 2024}
    finally:
        setup = client.patch(f"{url}/setup", json={"sales_from": None, "vacant_from": None}).json()
    assert setup["sales_from"] == 2021
    assert read_settings(pid)["analysis"]["sales_scrutiny"]["passes"] == 2


@pytest.mark.usefixtures("brought_in_client")  # the project's home, for its settings
def test_the_runs_funnel_adds_up(checked, brought_in):
    r = checked["receipt"]
    # The funnel adds up: from the valid sales to the sales for modeling.
    total = sum(-x["count"] if x["sign"] == "-" else x["count"] for x in r["funnel"] if x["sign"] in ("", "-", "+"))
    assert r["funnel"][0]["count"] == 47 and r["funnel"][-1]["count"] == r["used"] == total
    assert sum(g["used"] for g in r["groups"]) == r["used"]
    assert any(w["path"] == "out/2-clean-sup.pickle" for w in r["written"])
    # The five-pattern table: all groups first; each sale far from its group counted once, by its pattern.
    assert r["patterns"][0]["group"] == "" and set(r["patterns"][0]["counts"]) == {"1", "2", "3", "4", "5", "other"}
    assert read_settings(brought_in[1])["analysis"]["sales_scrutiny"]["patterns"] == "strict"


def test_review_the_sales_set_aside(checked, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    url = _urls(pid)[0]
    r = client.get(url).json()["receipt"]
    page = client.get(f"{url}/review").json()
    assert page["all"] == r["set_aside"] and page["undecided"] == page["all"]
    if page["items"]:
        key = page["items"][0]["key_sale"]
        sale = client.get(f"{url}/review/{key}").json()
        assert sale["item"]["key_sale"] == key and isinstance(sale["related"], list)
        # The sales recorded with it (its deed or, without one, the same day at the same price), itself first.
        if sale["together"]:
            assert sale["together"][0]["this"] and sale["together"][0]["key_sale"] == key
        first = page["items"][0]
        if "cluster" in first["checks"]:
            assert first["per_area_rating"] in ("low", "in", "high") and first["pattern"]
            only = client.get(f"{url}/review", params={"pattern": first["pattern"].split(",")[0]}).json()
            assert only["total"] >= 1
        # Keeping needs a note: why it's a market sale.
        assert client.put(f"{url}/marks/{key}", json={"action": "keep", "note": " "}).status_code == 422
        try:
            view = client.put(f"{url}/marks/{key}", json={"action": "keep", "note": "Arm's length"}).json()
            assert view["stale"]
            keep = (projects.project_dir(pid) / "in" / "oakbox" / "keep.csv").read_text(encoding="utf-8")
            assert f"{key},Arm's length" in keep
            assert client.get(f"{url}/review", params={"status": "kept"}).json()["total"] == 1
            assert client.post(f"{url}/accept").status_code == 409  # run again first
        finally:
            client.put(f"{url}/marks/{key}", json={"action": None})


def test_the_time_adjustment_worked_out_alone(time_worked_out, assembled):
    assert {g["id"] for g in time_worked_out["result"]["groups"]} == {g["id"] for g in assembled}


def test_a_groups_own_time_adjustment_file_and_borrowing_it(own_time_files):
    said = own_time_files
    a, b = said["a"], said["b"]
    # A group's own time adjustment file: OpenAVMKit reads it, and every problem is said.
    check = said["broken"]
    assert not check["ok"] and len(check["problems"]) >= 3
    assert "spring 2015" in " ".join(check["problems"])
    check = said["file"]
    assert check["ok"] and check["file"]["periods"] == 40, check
    assert said["no_group"] == 404
    ta = said["file_settings"]
    assert ta["from_file"] == {a: f"in/oakbox/time_adjustment/{a}.csv"} and a in ta["__file_digests"]
    assert said["copied"]
    # Another group borrows it; a group can't borrow from itself.
    assert said["own"] == 422
    mine = {g["id"]: g for g in said["borrowed"]["groups"]}
    assert mine[a]["file"]["name"] == "time_adjustment_index.csv" and mine[b]["borrow"] == a
    assert said["borrow_settings"]["borrow"] == {b: a}
    assert said["check_stale"]  # the time adjustment changed since Check sales ran
    assert said["time_stale"]
    time_view = said["time"]
    assert time_view["status"] == "done", time_view["job"]
    curves = {g["id"]: g for g in time_view["result"]["groups"]}
    assert curves[a]["per_year"] == curves[b]["per_year"] and curves[a]["per_year"] > 0
    view = said["checked"]  # and Check sales itself, which runs in the project folder
    assert view["status"] == "done", view["job"]
    ran = {g["id"]: g for g in view["receipt"]["groups"]}
    assert ran[a]["per_year"] == ran[b]["per_year"] == curves[a]["per_year"]
    # Back to their own sales: the file is set aside, the borrowing undone.
    assert all(g["file"] is None and g["borrow"] is None for g in said["undone"]["groups"])
    ta = said["undone_settings"]
    assert "borrow" not in ta and not ta.get("from_file")


def test_step_4_checks_the_values_against_the_sales_kept(own_time_files, assembled, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    rv = f"/api/projects/{pid}/ratio"
    setup = client.get(f"{rv}/setup").json()
    if setup["parcels"]:  # Only the market value is checked.
        client.patch(f"{rv}/setup", json={"start": "2020-01-01"})
        assert client.post(f"{rv}/run").json()["status"] == "running"
        view = wait(client, rv)
        assert view["status"] == "done", view["job"]
        result = view["receipt"]["results"][0]
        assert {g["id"] for g in result["groups"]} == {g["id"] for g in assembled}
        assert result["overall"]["sales"] == sum(g["sales"] for g in result["groups"])
        points = client.get(f"{rv}/map", params={"field": "assr_market_value"}).json()
        assert len(points) == result["overall"]["sales"] + result["overall"]["trimmed"]
        assert all({"lat", "lon", "ratio"} <= set(x) for x in points)
        assert client.post(f"{rv}/accept").json()["accepted"]
        client.patch(f"{rv}/setup", json={"price": "sold", "targets": {**setup["targets"], "level_low": 0.5}})
        assert client.get(rv).json()["stale"]


def test_prepare_fills_and_folds_on_what_check_sales_wrote(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    url, prep = _urls(pid)
    assert not client.get(url).json()["stale"]  # the fields' preparation doesn't put Check sales out of date
    assert client.get(prep).json()["blocked"] == []
    assert any(w["path"] == "out/2-clean-sup.pickle" for w in prepared["receipt"]["written"])
    # A change to the folding puts it out of date.
    try:
        client.patch(f"{url}/setup", json={"collapse_sales_min": 3})
        assert client.get(prep).json()["stale"]
    finally:
        client.patch(f"{url}/setup", json={"collapse_sales_min": 2})
    assert not client.get(prep).json()["stale"]  # and back as it was


def test_the_models_variables_found_and_choose_for_me(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    # Step 5 continues: the models (F9). The variables found, Choose for me.
    ms = client.get(f"/api/projects/{pid}/model/setup").json()
    assert ms["choose_for_me"] and [e["key"] for e in ms["engines"] if e["chosen"]] == ["lightgbm", "mra", "local_area"]
    assert any(v["field"].startswith("bldg_area_finished") for v in ms["variables"])


def test_the_variables_tested_one_test_at_a_time(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    mdl, vt = f"/api/projects/{pid}/model", f"/api/projects/{pid}/vartest"
    # Every test's result for every variable, per model group.
    assert client.post(f"{vt}/run").json()["status"] == "running"
    tv = wait(client, vt)
    assert tv["status"] == "done", tv["job"]
    tested = [g for g in tv["receipt"]["groups"] if g["tests"]]
    assert tested and {"represented", "corr", "p_value", "vif"} <= set(tested[0]["tests"])
    assert all(row["variable"] in tv["receipt"]["variables"] for row in tested[0]["tests"]["corr"])
    # Each correlation failure says why, and each column's correlation is there in detail (strength, clarity, overlaps).
    assert all(row["reason"] for row in tested[0]["tests"]["corr"] if row["passed"] is False)
    assert all("to_price" in d and "overlaps" in d for d in tested[0]["corr"].values())
    assert not tv["stale"] and tv["receipt"]["tests"] == ["corr", "p_value", "vif"]
    # Only the tests picked run; a change of tests makes the results out of date.
    assert client.patch(f"{mdl}/setup", json={"tests": []}).status_code == 422
    assert client.patch(f"{mdl}/setup", json={"tests": ["vif", "corr"]}).json()["tests"] == ["corr", "vif"]
    assert client.get(vt).json()["stale"]
    client.post(f"{vt}/run")
    tv = wait(client, vt)
    assert tv["status"] == "done", tv["job"]
    tested = [g for g in tv["receipt"]["groups"] if g["tests"]]
    assert tested and set(tested[0]["tests"]) == {"represented", "corr", "vif"} and not tv["stale"]


def test_a_try_of_one_model(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    mdl = f"/api/projects/{pid}/model"
    client.patch(f"{mdl}/setup", json={"models": ["lightgbm"]})
    assert client.post(f"{mdl}/run").json()["status"] == "running"
    view = wait(client, mdl)
    assert view["status"] == "done", view["job"]
    r = view["receipt"]
    assert r["models"] == ["lightgbm"]
    modeled = [g for g in r["groups"] if g["sets"]]
    assert modeled and all(g["skipped"] for g in r["groups"] if not g["sets"])
    sets = {s["key"]: s for s in modeled[0]["sets"]}
    assert {f["model"] for f in sets["holdout"]["rows"]} <= {"lightgbm", "ensemble"}
    # The roll ran too, as OpenAVMKit's assessor model: on the study set only, never in the academic figures.
    assert "assessor" in {f["model"] for f in sets["study"]["rows"]}
    assert "assessor" not in {f["model"] for f in modeled[0]["academic"]}
    assert modeled[0]["timings"] and modeled[0]["academic_trimmed"]
    assert "vei" not in modeled[0]["academic"][0]["values"]  # the IAAO view has it
    assert not client.get(mdl).json()["stale"]
    client.patch(f"{mdl}/setup", json={"choose_for_me": True})
    assert client.get(mdl).json()["stale"]


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
        steps.written(caught, "notebook 2's output")
    steps.written([], "notebook 2's output")  # nothing said: written


def test_the_models_study_set_setting_leaves_check_sales_as_it_was(tmp_path):
    project = projects.Project.model_validate(
        {"id": "x", "name": "x", "created_at": "2026-01-01T00:00:00", "tax_year": 2026, "valuation_date": "2026-01-01"}
    )
    base = {"analysis": {"ratio_study": {"look_back_years": 1}}}
    more = {"analysis": {"ratio_study": {"look_back_years": 1, "study_set_predictions": "holdout"}}}
    assert clean.settings_key(base, project, tmp_path) == clean.settings_key(more, project, tmp_path)
    other = {"analysis": {"ratio_study": {"look_back_years": 2}}}
    assert clean.settings_key(base, project, tmp_path) != clean.settings_key(other, project, tmp_path)

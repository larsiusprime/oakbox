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

    p.clean.sales_from = 2023
    p.clean.per = {"condos": "impr"}  # condos indexed on finished area, whatever OpenAVMKit would choose
    p.clean.fills = {
        "slope": clean.Fill(method="median"),
        # From before: a split, improved parcels left blank.
        "lot": clean.Fill.model_validate({"method": "zero", "scope": "vacant"}),
        "skip": clean.Fill(method="leave"),
        "renovation_num": clean.Fill(),  # auto: zero (blank means no permit)
        "quality": clean.Fill(method="auto", split=True, kind="building"),  # a building's: improved parcels only
        "income": clean.Fill(method="mean", split=True, vacant="zero", kind="land"),  # land: every parcel alike
        "deck": clean.Fill(method="median", split=True, vacant="zero"),
    }
    p.clean.location, p.clean.checks = "", {"dupe_date_price": False}
    s = clean.settings(p)
    # Vacant land has no window of its own: it follows the sales window.
    assert s["modeling"]["metadata"]["use_sales_from"] == {"improved": 2023, "vacant": 2023}
    assert s["data"]["process"]["time_adjustment"]["per"] == {"condos": "impr"}
    # Added to OpenAVMKit's own fill lists ("+"), not replacing them.
    assert s["data"]["process"]["fill"] == {
        "+mean": ["income"],
        "+median": ["slope"],
        "+zero": ["renovation_num"],
        "+median_impr": ["deck", "quality"],
        "+zero_vacant": ["deck", "lot"],
    }
    assert clean.fill_words("deck", p.clean.fills["deck"]) == "median (improved), zero (vacant)"
    assert s["analysis"]["sales_scrutiny"]["location"] is None
    assert s["analysis"]["horizontal_equity"] == {"location": None}
    assert s["analysis"]["sales_scrutiny"]["heuristics"]["dupe_date_price"] is False
    # OpenAVMKit's bulk-deed check (a deed for several parcels, the others' sales not valid) is on unless turned off.
    assert s["analysis"]["sales_scrutiny"]["heuristics"]["bulk_deed"] is True
    assert "bulk_deed" in clean.CHECK_WORDS
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
        shown = next((g for g in time_view["result"]["groups"] if g["curve"]), None)
        time_view["detail"] = client.get(f"{url}/time/{shown['id']}").json() if shown else None
        time_view["missing"] = client.get(f"{url}/time/no_such_group").status_code
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
        setup = client.patch(f"{url}/setup", json={"sales_from": 2024}).json()
        assert setup["sales_from"] == 2024 and 0 < setup["in_window"] < 47
        assert read_settings(pid)["modeling"]["metadata"]["use_sales_from"] == {"improved": 2024, "vacant": 2024}
    finally:
        setup = client.patch(f"{url}/setup", json={"sales_from": None}).json()
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
    # Each group says what its index is of; a group without one says why, in OpenAVMKit's own terms.
    for g in time_worked_out["result"]["groups"]:
        if g["sales"]:
            assert g["per"] in ("impr", "land")
        if g["per_year"] is None:
            assert g["why"], g
    # The expanded chart: the index over time and every sale drawn, each with its price per area.
    d = time_worked_out["detail"]
    assert d and d["index"] and d["sales"] and all(x["per_area"] > 0 for x in d["sales"])
    assert time_worked_out["missing"] == 404


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
        stds = [x | {"level_low": 0.5} if i == 0 else x for i, x in enumerate(setup["standards"])]
        client.patch(f"{rv}/setup", json={"price": "sold", "standards": stds})
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


def test_check_my_values_starts_from_check_sales_not_from_what_prepare_wrote(prepared, brought_in_client, brought_in):
    """Prepare the fields (step 5) writes out/2-clean-* again, filled and folded: Check my values (step 4) reads
    Check sales' own copies, so it's the same whether step 5 has run or not."""
    client, pid = brought_in_client, brought_in[1]
    pdir = projects.project_dir(pid)
    rv = f"/api/projects/{pid}/ratio"
    before = client.get(f"{rv}/setup").json()
    shared = [pdir / "out" / "2-clean-sup.pickle", *(pdir / "out" / "look").glob("2-clean-*")]
    aside = pdir / "aside"
    aside.mkdir()
    try:
        for f in shared:
            f.rename(aside / f.name)
        assert client.get(rv).json()["blocked"] == []
        assert client.get(f"{rv}/setup").json() == before
    finally:
        for f in shared:
            (aside / f.name).rename(f)


def test_the_variable_lists_and_each_groups_models(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    # Variables › Variable lists (F9): none to start (the user makes them); each variable judged per group and type.
    vl = client.get(f"/api/projects/{pid}/varlists").json()
    assert vl["lists"] == []
    assert any(v["field"].startswith("bldg_area_finished") for v in vl["variables"])
    group = next(g["id"] for g in vl["groups"] if g["modeled"])
    assert set(vl["recommend"][group]) == {"regression", "ml"}
    # Before any list, a group's models have none: said, and a try is stopped.
    ms = client.get(f"/api/projects/{pid}/model/setup").json()
    first = next(x for x in ms["groups"] if x["id"] == group)["models"][0]
    assert first["list_id"] is None and [w["code"] for w in first["warnings"]] == ["no_list"]
    # Every list at once: a new one gets an id from its name; one with no name is refused.
    fields = [v["field"] for v in vl["variables"]]
    lists = [
        {"id": "", "name": "Trees", "kind": "ml", "groups": [group], "variables": fields},
        {"id": "", "name": "Regression", "kind": "regression", "groups": [group], "variables": fields[:3]},
        {"id": "", "name": "Short list", "kind": "regression", "groups": [group], "variables": []},
    ]
    vl = client.put(f"/api/projects/{pid}/varlists", json={"lists": lists}).json()
    assert [x["id"] for x in vl["lists"]] == ["trees", "regression", "short_list"]
    bad = [*lists[:2], {"id": "", "name": " ", "kind": "ml", "groups": [], "variables": []}]
    assert client.put(f"/api/projects/{pid}/varlists", json={"lists": bad}).status_code == 422
    # Model values › Models: every modeled group starts with LightGBM, MRA and Multi-MRA, each taking the group's
    # first list of its type.
    ms = client.get(f"/api/projects/{pid}/model/setup").json()
    g = next(x for x in ms["groups"] if x["id"] == group)
    assert [(e["engine"], e["list_id"]) for e in g["models"]] == [
        ("lightgbm", "trees"),
        ("mra", "regression"),
        ("multi_mra", "regression"),
    ]
    # A model on an empty list is said, and stops a try.
    url = f"/api/projects/{pid}/model/groups/{group}"
    ms = client.put(url, json={"models": [{"engine": "mra", "name": "Short", "list_id": "short_list"}]}).json()
    short = next(x for x in ms["groups"] if x["id"] == group)["models"][0]
    assert short["key"] == "short" and [w["code"] for w in short["warnings"]] == ["list_empty"]
    assert any(
        "Short: its variable list has no variables" in b
        for b in client.get(f"/api/projects/{pid}/model").json()["blocked"]
    )
    assert client.put(url, json={"models": [{"engine": "nope"}]}).status_code == 422
    # Every model removed: none, not the defaults back (only None is the defaults).
    ms = client.put(url, json={"models": []}).json()
    assert next(x for x in ms["groups"] if x["id"] == group)["models"] == []
    client.put(url, json={"models": None})
    # Not modeled, chosen here: left unvalued, said, and not asked for models; then modeled again.
    ms = client.put(f"{url}/skip", json={"skip": True}).json()
    assert next(x for x in ms["groups"] if x["id"] == group)["skipped"] is True
    client.put(url, json={"models": []})
    name = next(x for x in ms["groups"] if x["id"] == group)["name"]
    blocked = client.get(f"/api/projects/{pid}/model").json()["blocked"]
    assert not any(b.startswith(f"{name} has no models") for b in blocked)
    ms = client.put(f"{url}/skip", json={"skip": False}).json()
    assert next(x for x in ms["groups"] if x["id"] == group)["skipped"] is False
    client.put(url, json={"models": None})
    client.put(f"/api/projects/{pid}/varlists", json={"lists": []})
    # A location stack's preview: whatever location fields there are, broadest first.
    fields = [x["field"] for x in ms["locations"]]
    stack = client.get(f"/api/projects/{pid}/model/stack/{group}", params={"fields": fields}).json()
    assert [x["field"] for x in stack["levels"]] == fields and stack["sales"] >= 0


def test_the_variables_tested_one_test_at_a_time(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    mdl, vt = f"/api/projects/{pid}/model", f"/api/projects/{pid}/vartest"
    # Every test's result for every variable, per model group.
    assert client.post(f"{vt}/run").json()["status"] == "running"
    tv = wait(client, vt)
    assert tv["status"] == "done", tv["job"]
    tested = [g for g in tv["receipt"]["groups"] if g["tests"]]
    assert tested and {"represented", "corr", "vif"} <= set(tested[0]["tests"])
    assert all(row["variable"] in tv["receipt"]["variables"] for row in tested[0]["tests"]["corr"])
    # The correlation test judges the relation to price alone (overlap is VIF's): a failure is too weak a
    # correlation, a pass a strong enough one, whatever it overlaps; each column's correlation is there in detail.
    floor = tv["receipt"]["thresholds"].get("correlation", 0.1)
    for row in tested[0]["tests"]["corr"]:
        assert row["passed"] == ((row["value"] or 0) >= floor), row
        assert row["reason"] == (None if row["passed"] else "no_correlation")
    assert all("to_price" in d and "overlaps" in d for d in tested[0]["corr"].values())
    assert not tv["stale"] and tv["receipt"]["tests"] == ["corr", "vif"]
    # Only the tests picked run; a change of tests makes the results out of date.
    assert client.patch(f"{mdl}/setup", json={"tests": []}).status_code == 422
    assert client.patch(f"{mdl}/setup", json={"tests": ["vif"]}).json()["tests"] == ["vif"]
    assert client.get(vt).json()["stale"]
    client.post(f"{vt}/run")
    tv = wait(client, vt)
    assert tv["status"] == "done", tv["job"]
    tested = [g for g in tv["receipt"]["groups"] if g["tests"]]
    assert tested and set(tested[0]["tests"]) == {"represented", "vif"} and not tv["stale"]


def test_a_try_of_one_model(prepared, brought_in_client, brought_in):
    client, pid = brought_in_client, brought_in[1]
    mdl = f"/api/projects/{pid}/model"
    groups = [g["id"] for g in client.get(f"{mdl}/setup").json()["groups"] if g["modeled"]]
    fields = [v["field"] for v in client.get(f"/api/projects/{pid}/varlists").json()["variables"]]
    trees = {"id": "", "name": "Trees", "kind": "ml", "groups": groups, "variables": fields}
    client.put(f"/api/projects/{pid}/varlists", json={"lists": [trees]})
    for g in groups:
        client.put(f"{mdl}/groups/{g}", json={"models": [{"engine": "lightgbm", "name": "Trees"}]})
    assert client.post(f"{mdl}/run").json()["status"] == "running"
    view = wait(client, mdl)
    assert view["status"] == "done", view["job"]
    r = view["receipt"]
    assert r["models"] == ["trees"]
    modeled = [g for g in r["groups"] if g["sets"]]
    assert modeled and all(g["skipped"] for g in r["groups"] if not g["sets"])
    sets = {s["key"]: s for s in modeled[0]["sets"]}
    assert {f["model"] for f in sets["holdout"]["rows"]} <= {"trees", "ensemble"}
    # Each model by the name the user gave it.
    assert "Trees" in {f["name"] for f in sets["holdout"]["rows"]}
    # The roll ran too, as OpenAVMKit's assessor model: on the study set only, never in the academic figures.
    assert "assessor" in {f["model"] for f in sets["study"]["rows"]}
    assert "assessor" not in {f["model"] for f in modeled[0]["academic"]}
    assert modeled[0]["timings"] and modeled[0]["academic_trimmed"]
    assert "vei" not in modeled[0]["academic"][0]["values"]  # the IAAO view has it
    assert not client.get(mdl).json()["stale"]
    for g in groups:
        client.put(f"{mdl}/groups/{g}", json={"models": None})
    assert client.get(mdl).json()["stale"]


def test_a_project_from_before_has_its_proposals_made_auto(assembled, brought_in_client, brought_in):
    """Proposals were written down as if chosen: each still as proposed becomes auto, once (a building's field's
    split from only improved too); a choice stays; after that, the proposal's method is a choice like any."""
    pid = brought_in[1]
    project, pdir = projects.load(pid), projects.project_dir(pid)
    universe, _ = clean._data(pdir)
    universe = universe.copy()
    improved = universe.index[~universe["is_vacant"].astype(bool)]
    universe.loc[improved[:5], ["bldg_quality_num", "bldg_condition_num"]] = None
    project.clean.fills_auto = False  # as a project from before (the file's other tests may have run decide)
    project.clean.fills = {
        "bldg_quality_num": clean.Fill.model_validate({"method": "median", "scope": "impr"}),
        "bldg_condition_num": clean.Fill(method="mean"),
    }

    rows = {r.field: r for r in clean._fill_rows(project, pdir, universe)}
    q = rows["bldg_quality_num"]
    assert (q.kind, q.auto, q.fill.method, q.fill.kind) == ("building", "median", "auto", "building")
    assert rows["bldg_condition_num"].fill.method == "mean"  # a choice: stays

    project.clean.fills_auto = True  # made auto already: median is a choice now
    project.clean.fills["bldg_quality_num"] = clean.Fill(method="median")
    assert {r.field: r for r in clean._fill_rows(project, pdir, universe)}["bldg_quality_num"].fill.method == "median"


@pytest.mark.parametrize("value", ["", "None", "nan", None])
def test_a_sale_with_no_parcel_has_no_group(value):
    assert clean.group_of(value) == clean.NO_PARCEL


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
def test_auto_is_proposed_from_what_a_blank_means(field, method):
    assert clean.propose(field) == method


def test_what_each_group_gets_is_worked_out_as_openavmkit_fills():
    """Each model group from its own parcels' values; a building's field from improved parcels only (vacant ones'
    0s don't count); a group with blanks and nothing to take a median from stays blank; split: each its own."""
    import pandas as pd

    p = projects.Project.model_validate(
        {"id": "x", "name": "x", "created_at": "2026-01-01T00:00:00", "tax_year": 2026, "valuation_date": "2026-01-01"}
    )
    p.groups = [
        projects.ModelGroup(id="sf", name="Single-family", color="#c55"),
        projects.ModelGroup(id="condo", name="Condos", color="#58c"),
    ]
    # Single-family: an improved 4, two improved blanks, two vacant 0s and a vacant blank; a condo with a blank.
    u = pd.DataFrame(
        {
            "model_group": ["sf"] * 6 + ["condo"],
            "is_vacant": [False, False, False, True, True, True, False],
            "q": [4.0, None, None, 0.0, 0.0, None, None],
        }
    )

    def cells(**fill):
        row = clean.FillRow(field="q", name="Q", blanks=4, kind="other", fill=clean.Fill(**fill), auto="median")
        prev = clean.fill_preview(p, u, [row])
        assert [g.label for g in prev.groups] == ["Single-family", "Condos"]
        return prev.rows[0].cells

    sf, condo = cells()  # every parcel: the vacant 0s count
    assert sf.main and (sf.main.blanks, sf.main.value) == (3, 0.0) and sf.vacant is None
    assert condo.main and (condo.main.blanks, condo.main.value) == (1, None)  # nothing to take: stays blank
    sf, _ = cells(kind="building")  # improved parcels only
    assert sf.main and (sf.main.blanks, sf.main.value) == (2, 4.0)
    sf, _ = cells(split=True, method="median", vacant="leave")
    assert sf.main and sf.main.value == 4.0 and sf.vacant and sf.vacant.left and sf.vacant.blanks == 1
    sf, _ = cells(split=True, method="median", vacant="leave", kind="land")  # land: never split
    assert sf.main and (sf.main.blanks, sf.main.value) == (3, 0.0) and sf.vacant is None
    sf, _ = cells(method="mode")
    assert sf.main and sf.main.value == 0.0


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
    # No ratio study settings of its own at first, then the models' alone: still as it was (Prepare runs).
    none = {"analysis": {}}
    only_models = {"analysis": {"ratio_study": {"study_set_predictions": "holdout"}}}
    assert clean.settings_key(none, project, tmp_path) == clean.settings_key(only_models, project, tmp_path)


def test_a_deed_name_format_this_oak_box_doesnt_know_reads_as_not_decided():
    """A format renamed since it was saved: the guess is shown again, not an error on Data › Deeds or the project."""
    assert clean.CleanState(name_format="last_word").name_format == "last_word"
    assert clean.CleanState.model_validate({"name_format": "surname_first"}).name_format is None

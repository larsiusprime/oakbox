"""Existing values (Data › Existing values): named sets, the roll's in OpenAVMKit's assr_* fields and the others in
slots of their own; making another set the roll moves the columns; the models compare them as pass_through models,
judged like the roll."""

import geopandas as gpd
import pytest
from helpers import NEW, put_file
from shapely.geometry import box

from oakbox import model, projects


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {"ID": ["1", "2", "3"], "ROLL": [100_000, 200_000, 300_000], "AVM": [110_000, 190_000, 310_000]},
        geometry=[box(i, 0, i + 1, 1) for i in range(3)],
        crs=4326,
    ).to_parquet(tmp_path / "parcels.parquet")
    body = {"path": str(tmp_path / "parcels.parquet"), "mode": "copy", "name": "parcels"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    put_file(client, pid, "parcels", universe=True, id_column="ID")
    return pid


def _field(w, key):
    return next(f for f in w["fields"] if f["key"] == key)


def test_value_sets_named_moved_and_removed(client, pid):
    url = f"/api/projects/{pid}/wizard"
    w = client.get(url).json()
    assert [(s["id"], s["roll"]) for s in w["value_sets"]] == [("assr", True)]  # the roll, as first proposed
    client.put(f"{url}/fields/assr_market_value", json={"file": "geo_parcels", "column": "ROLL"})
    w = client.post(f"{url}/value-sets", json={"name": "Acme AVM"}).json()
    assert [(s["id"], s["name"]) for s in w["value_sets"]][1] == ("vset1", "Acme AVM")
    assert client.post(f"{url}/value-sets", json={"name": "Acme AVM"}).status_code == 422  # one name each
    w = client.put(f"{url}/fields/vset1_market_value", json={"file": "geo_parcels", "column": "AVM"}).json()
    assert _field(w, "vset1_market_value")["name"] == "Acme AVM market value"
    assert _field(w, "vset1_market_value")["check"]["ok"]  # read and checked like the roll's
    # Making the AVM the roll swaps the columns: assr_* is always the roll.
    w = client.patch(f"{url}/value-sets/vset1", json={"roll": True}).json()
    sets = {s["name"]: (s["id"], s["roll"]) for s in w["value_sets"]}
    assert sets == {"Acme AVM": ("assr", True), f"{NEW['jurisdiction']} roll": ("vset1", False)}
    assert _field(w, "assr_market_value")["sources"] == [{"file": "geo_parcels", "column": "AVM"}]
    assert _field(w, "vset1_market_value")["sources"] == [{"file": "geo_parcels", "column": "ROLL"}]
    w = client.patch(f"{url}/value-sets/vset1", json={"name": "Last year"}).json()
    assert _field(w, "vset1_market_value")["name"] == "Last year market value"
    w = client.delete(f"{url}/value-sets/vset1").json()
    assert [s["name"] for s in w["value_sets"]] == ["Acme AVM"]
    assert _field(w, "vset1_market_value")["sources"] == []
    load = projects.load(pid).files[0].load
    assert "vset1_market_value" not in load and load["assr_market_value"][0] == "AVM"


def test_other_values_are_pass_through_models_judged_like_the_roll(client, pid, monkeypatch):
    url = f"/api/projects/{pid}/wizard"
    client.post(f"{url}/value-sets", json={"name": "Acme AVM"})
    client.put(f"{url}/fields/vset1_market_value", json={"file": "geo_parcels", "column": "AVM"})
    project = projects.load(pid)
    project.model.models = ["lightgbm"]
    monkeypatch.setattr(
        model,
        "variables",
        lambda p, d: [
            model.Variable(
                field="x", name="x", kind="building", numeric=True, parcels=3, blanks=0, chosen=True, trees_only=False
            )
        ],
    )
    monkeypatch.setattr(model, "_universe_fields", lambda d: ["vset1_market_value"])
    monkeypatch.setattr(model, "_has_roll", lambda d: False)
    s = model.settings(project, projects.project_dir(pid))
    main = s["modeling"]["instructions"]["main"]
    assert main["run"] == ["lightgbm", "vset1"] and main["ensemble"]["models"] == ["lightgbm"]
    assert s["modeling"]["models"]["main"]["vset1"] == {"model": "pass_through", "field": "vset1_market_value"}
    assert s["analysis"]["ratio_study"]["outside_models"] == ["vset1"]

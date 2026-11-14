"""A parcel file whose rows each say something about the parcel (one per amenity), combined into one row per parcel
(wizard/combine.py): a yes/no field per group of values, a number per number column, the main value by priority."""

import pandas as pd
import pytest
from helpers import IDS, NEW, put_file, read_settings, start_wizard, wizard_files

from oakbox import projects
from oakbox.datafiles import Combine, CombineGroup
from oakbox.wizard import combine


def test_to_start_a_group_per_value():
    groups = combine.suggest_groups(["LAKE", "GOLF COURSE", "RAIL-ROAD", "RAIL ROAD"])
    assert [(g.name, g.values) for g in groups] == [
        ("Lake", ["LAKE"]),
        ("Golf Course", ["GOLF COURSE"]),
        ("Rail-Road", ["RAIL-ROAD"]),
        ("Rail Road 2", ["RAIL ROAD"]),  # the same field otherwise (has_rail_road)
    ]


def test_one_row_per_parcel_with_its_groups_numbers_and_main_value():
    ids = pd.Series(["1", "1", "1", "2", "3", ""], dtype=object)
    about = pd.Series(["Golf Course", "BAY", "gulf ", "LAKE", "NULL", "BAY"], dtype=object)
    length = pd.Series(["800", "2534.5", "", "1259", "", "5"], dtype=object)
    c = Combine(
        source="a.csv",
        about="Amenity",
        groups=[
            CombineGroup(name="Open water", values=["GULF", "BAY"]),
            CombineGroup(name="Golf", values=["GOLF COURSE"]),
        ],
        measures={"Water_Length": "max"},
        main=["GULF", "BAY", "LAKE", "GOLF COURSE"],
    )
    out = combine.build(ids, about, {"Water_Length": length}, c)
    assert list(out.index) == ["1", "2", "3"]  # a row with no ID is left out
    assert out["has_open_water"].tolist() == [1, 0, 0] and out["has_golf"].tolist() == [1, 0, 0]
    assert out["water_length"].tolist()[:2] == [2534.5, 1259.0] and pd.isna(out["water_length"].iloc[2])
    assert out["main_amenity"].tolist() == ["GULF", "LAKE", ""]


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    wizard_files(tmp_path)
    pd.DataFrame(
        {
            "PROP_ID": [IDS[0], IDS[0], IDS[0], IDS[1], IDS[2], IDS[2]],
            "Amenity": ["GOLF COURSE", "GULF", "Bay", "LAKE", "NULL", "LAKE "],
            "Water_Length": [800, 2534.5, None, 1259, None, 40],
            "DistanceToOpenWater": [None, 10, 30, None, None, None],
        }
    ).to_csv(tmp_path / "amenities.csv", index=False)
    for name in ("shapes", "cama", "sales", "amenities"):
        ext = "parquet" if name == "shapes" else "csv"
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    start_wizard(client, pid)
    assert put_file(client, pid, "amenities", holds="parcels", id_column="PROP_ID").status_code == 200
    return pid


def test_combining_a_files_rows_and_back(client, pid):
    url = f"/api/projects/{pid}/wizard/files/amenities"
    p = client.post(f"{url}/combine/preview", json={}).json()
    assert p["about"] == "Amenity" and (p["rows"], p["parcels"]) == (6, 3)
    # A group per value, to start (most parcels first).
    assert {g["name"]: g["values"] for g in p["groups"]} == {
        "Lake": ["LAKE"],
        "Golf Course": ["GOLF COURSE"],
        "Gulf": ["GULF"],
        "Bay": ["BAY"],
    }
    assert [(m["column"], m["how"]) for m in p["measures"]] == [("Water_Length", "max"), ("DistanceToOpenWater", "min")]
    measures = {"Water_Length": "max", "DistanceToOpenWater": "min"}
    body = {
        "about": "Amenity",
        "groups": p["groups"],
        "measures": measures,
        "main": ["GULF", "BAY", "LAKE", "GOLF COURSE"],
    }
    w = client.put(f"{url}/combine", json=body).json()
    f = next(x for x in w["files"] if x["name"] == "amenities")
    assert f["filename"] == "amenities.combined.parquet" and f["rows"] == 3
    assert f["repeats"]["combined"] and "rows combined" in f["id_check"]["issues"][0]["text"]
    combined = pd.read_parquet(projects.inputs_dir(pid) / "amenities.combined.parquet").set_index("PROP_ID")
    assert combined.loc[IDS[0], "has_gulf"] == 1 and combined.loc[IDS[0], "distancetoopenwater"] == 10
    assert combined.loc[IDS[0], "main_amenity"] == "GULF" and combined.loc[IDS[2], "has_lake"] == 1
    load = read_settings(pid)["data"]["load"]["amenities"]
    assert load["filename"] == "amenities.combined.parquet" and "has_golf_course" in load["load"]
    custom = {c.name for c in projects.load(pid).wizard.custom}
    assert {"has_golf_course", "has_gulf", "has_lake", "water_length", "distancetoopenwater", "main_amenity"} <= custom
    # The dialog still shows the original's repeats.
    assert client.get(f"{url}/repeats").json()["columns"][:2] == ["PROP_ID", "Amenity"]
    # Back to keeping the first row: the original again, its fields gone.
    w = put_file(client, pid, "amenities", dupes="first").json()
    f = next(x for x in w["files"] if x["name"] == "amenities")
    assert f["filename"] == "amenities.csv" and not f["repeats"]["combined"]
    assert not (projects.inputs_dir(pid) / "amenities.combined.parquet").exists()
    assert "has_golf_course" not in {c.name for c in projects.load(pid).wizard.custom}


def test_the_combined_file_is_made_again_when_the_original_changes(client, pid):
    url = f"/api/projects/{pid}/wizard/files/amenities"
    p = client.post(f"{url}/combine/preview", json={}).json()
    client.put(f"{url}/combine", json={"about": "Amenity", "groups": p["groups"], "measures": {}, "main": None})
    src = projects.inputs_dir(pid) / "amenities.csv"
    df = pd.read_csv(src, dtype=str)
    df.loc[len(df)] = [IDS[3], "GOLF COURSE", None, None]
    df.to_csv(src, index=False)
    client.get(f"/api/projects/{pid}/wizard")
    combined = pd.read_parquet(projects.inputs_dir(pid) / "amenities.combined.parquet").set_index("PROP_ID")
    assert combined.loc[IDS[3], "has_golf_course"] == 1

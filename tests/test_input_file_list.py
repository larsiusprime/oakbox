"""F3b The input file list (SPEC §3.0): what each entry shows, rename, remove."""

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box
from test_data_files import NEW, _settings

from oakbox import projects
from oakbox.app import create_app


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    src = tmp_path / "src"
    src.mkdir()
    pd.DataFrame({"PIN": ["1"], "PRICE": [100]}).to_csv(src / "cama.csv", index=False)
    gdf = gpd.GeoDataFrame({"PIN": ["1"]}, geometry=[box(0, 0, 1, 1)], crs=4326)
    gdf.to_parquet(src / "parcels.parquet")  # GeoParquet under a plain .parquet name
    pd.DataFrame({"PIN": ["1"]}).to_parquet(src / "plain.geoparquet")  # and the other way round
    gdf.to_file(src / "roads.shp")
    for name in ("cama.csv", "parcels.parquet", "plain.geoparquet", "roads.shp"):
        r = client.post(
            f"/api/projects/{pid}/files",
            json={"path": str(src / name), "mode": "copy", "name": name.split(".")[0]},
        )
        assert r.status_code == 200, r.text
    return pid


def _files(client, pid):
    return {f["name"]: f for f in client.get(f"/api/projects/{pid}").json()["files"]}


def test_type_and_geometry_come_from_the_file(client, pid):
    files = _files(client, pid)
    assert {n: (f["format"], f["geometry"]) for n, f in files.items()} == {
        "cama": ("CSV", False),
        "parcels": ("Parquet", True),  # checked in the file, not guessed from the name
        "plain": ("Parquet", False),
        "roads": ("Shapefile", True),
    }
    assert files["roads"]["size_bytes"] > (projects.project_dir(pid) / "in" / "roads.shp").stat().st_size


def test_a_missing_file_is_shown_as_missing(client, pid):
    (projects.project_dir(pid) / "in" / "cama.csv").unlink()
    cama = _files(client, pid)["cama"]
    assert cama["missing"] and cama["size_bytes"] == 0 and cama["geometry"] is None


def test_rename_changes_the_entry_not_the_file(client, pid):
    r = client.put(f"/api/projects/{pid}/files/cama/name", json={"name": "cama_2026"})
    assert r.status_code == 200, r.text
    load = _settings(pid)["data"]["load"]
    assert "cama" not in load and load["cama_2026"] == {"filename": "cama.csv"}
    assert (projects.project_dir(pid) / "in" / "cama.csv").is_file()
    assert list(_files(client, pid)) == ["cama_2026", "parcels", "plain", "roads"]  # keeps its place


def test_rename_checks_the_new_name(client, pid):
    bad = client.put(f"/api/projects/{pid}/files/cama/name", json={"name": "Cama 2026"})
    taken = client.put(f"/api/projects/{pid}/files/cama/name", json={"name": "parcels"})
    assert bad.status_code == taken.status_code == 422
    assert client.put(f"/api/projects/{pid}/files/nope/name", json={"name": "x"}).status_code == 404
    assert "cama" in _settings(pid)["data"]["load"]


def test_remove_leaves_the_file_unless_asked(client, pid):
    in_dir = projects.project_dir(pid) / "in"
    assert client.delete(f"/api/projects/{pid}/files/cama").status_code == 200
    assert "cama" not in _settings(pid)["data"]["load"] and (in_dir / "cama.csv").is_file()
    # It can be added back from in/, with no copy or move.
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(in_dir / "cama.csv")}).json()
    assert check["already_in_project"]


def test_remove_with_trash_sends_the_file_and_sidecars_to_the_trash(client, pid, tmp_path):
    in_dir = projects.project_dir(pid) / "in"
    assert client.delete(f"/api/projects/{pid}/files/roads", params={"trash": True}).status_code == 200
    assert not list(in_dir.glob("roads.*"))
    trashed = sorted(p.name for p in (tmp_path / "xdg" / "Trash" / "files").iterdir())
    assert "roads.shp" in trashed and "roads.dbf" in trashed and "roads.shx" in trashed
    assert "roads" not in _settings(pid)["data"]["load"]


def test_a_file_two_entries_use_is_not_trashed(client, pid):
    in_dir = projects.project_dir(pid) / "in"
    body = {"path": str(in_dir / "cama.csv"), "mode": "copy", "name": "cama_again"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    assert client.delete(f"/api/projects/{pid}/files/cama", params={"trash": True}).status_code == 422
    assert (in_dir / "cama.csv").is_file() and "cama" in _settings(pid)["data"]["load"]


def test_show_file_selects_it_in_the_file_manager(client, pid, monkeypatch):
    opened = []
    monkeypatch.setattr(projects.subprocess, "Popen", lambda args: opened.append(args))
    monkeypatch.setattr(projects.shutil, "which", lambda _: "/usr/bin/xdg-open")
    assert client.post(f"/api/projects/{pid}/files/cama/show").status_code == 200
    assert opened == [["xdg-open", str(projects.project_dir(pid) / "in")]]  # Linux: its folder

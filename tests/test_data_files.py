"""F2 Add a data file (SPEC §3.0): files go into in/ and become data.load entries."""

import geopandas as gpd
import pandas as pd
import pytest
from helpers import NEW, read_settings
from shapely.geometry import box

from oakbox import projects


@pytest.fixture
def pid(client):
    return client.post("/api/projects", json=NEW).json()["id"]


def _map(n=3):
    return gpd.GeoDataFrame(
        {"PIN": [str(i) for i in range(n)]}, geometry=[box(i, 0, i + 1, 1) for i in range(n)], crs=4326
    )


def test_copy_a_csv_keeps_the_original(client, pid, tmp_path):
    src = tmp_path / "Sales 2025.csv"
    src.write_text("PIN,PRICE\n1,100\n", encoding="utf-8")
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(src)}).json()
    assert check["problem"] is None and check["format"] == "CSV" and check["suggested_name"] == "sales_2025"
    r = client.post(f"/api/projects/{pid}/files", json={"path": str(src), "mode": "copy", "name": "sales_2025"})
    assert r.status_code == 200, r.text
    assert src.exists()
    assert (projects.project_dir(pid) / "in" / "Sales 2025.csv").read_text(encoding="utf-8") == src.read_text(
        encoding="utf-8"
    )
    assert read_settings(pid)["data"]["load"] == {"sales_2025": {"filename": "Sales 2025.csv"}}


def test_move_a_shapefile_with_its_sidecars(client, pid, tmp_path):
    src_dir = tmp_path / "gis"
    src_dir.mkdir()
    _map().to_file(src_dir / "parcels.2026.shp")
    sidecars = sorted(p.name for p in src_dir.iterdir())
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(src_dir / "parcels.2026.shp")}).json()
    assert check["format"] == "Shapefile" and sorted(check["files"]) == sidecars
    r = client.post(
        f"/api/projects/{pid}/files",
        json={"path": str(src_dir / "parcels.2026.shp"), "mode": "move", "name": "parcels"},
    )
    assert r.status_code == 200, r.text
    assert list(src_dir.iterdir()) == []  # moved, sidecars and all
    in_dir = projects.project_dir(pid) / "in"
    assert sorted(p.name for p in in_dir.iterdir() if p.name != "settings.json") == sidecars
    assert read_settings(pid)["data"]["load"]["parcels"] == {"filename": "parcels.2026.shp", "dupes": "allow"}


def test_a_shapefile_without_its_dbf_is_refused(client, pid, tmp_path):
    _map().to_file(tmp_path / "parcels.shp")
    (tmp_path / "parcels.dbf").unlink()
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(tmp_path / "parcels.shp")}).json()
    assert ".dbf" in check["problem"]


def test_geopackage_layer_is_chosen_and_written(client, pid, tmp_path):
    gpkg = tmp_path / "county.gpkg"
    _map().to_file(gpkg, layer="parcels")
    _map(1).to_file(gpkg, layer="zoning")
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(gpkg)}).json()
    assert check["layers"] == ["parcels", "zoning"]
    body = {"path": str(gpkg), "mode": "copy", "name": "county"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 422  # which layer?
    assert client.post(f"/api/projects/{pid}/files", json=body | {"layer": "zoning"}).status_code == 200
    assert read_settings(pid)["data"]["load"]["county"] == {
        "filename": "county.gpkg",
        "layer": "zoning",
        "dupes": "allow",
    }


def test_a_taken_file_name_needs_a_new_name(client, pid, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "data.csv").write_text("x\n1\n", encoding="utf-8")
    (b / "data.csv").write_text("x\n2\n", encoding="utf-8")
    client.post(f"/api/projects/{pid}/files", json={"path": str(a / "data.csv"), "mode": "copy", "name": "data"})
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(b / "data.csv")}).json()
    assert check["filename_taken"] and check["suggested_name"] == "data_2"
    body = {"path": str(b / "data.csv"), "mode": "copy", "name": "data_2"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 422
    assert client.post(f"/api/projects/{pid}/files", json=body | {"filename": "data_b"}).status_code == 200
    assert read_settings(pid)["data"]["load"]["data_2"] == {"filename": "data_b.csv"}
    # And the entry names stay unique.
    dup = {"path": str(b / "data.csv"), "mode": "copy", "name": "data", "filename": "data_c"}
    assert client.post(f"/api/projects/{pid}/files", json=dup).status_code == 422


def test_a_file_already_in_the_project_is_only_declared(client, pid):
    in_dir = projects.project_dir(pid) / "in"
    (in_dir / "parcels.parquet").write_bytes(b"")
    pd.DataFrame({"PIN": ["1"]}).to_parquet(in_dir / "parcels.parquet")
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(in_dir / "parcels.parquet")}).json()
    assert check["already_in_project"] and not check["filename_taken"]
    body = {"path": str(in_dir / "parcels.parquet"), "mode": "move", "name": "parcels"}
    assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    assert (in_dir / "parcels.parquet").exists()


def test_formats_openavmkit_cant_read_are_refused(client, pid, tmp_path):
    xlsx = tmp_path / "values.xlsx"
    xlsx.write_bytes(b"PK")
    check = client.post(f"/api/projects/{pid}/files/check", json={"path": str(xlsx)}).json()
    assert "can't read .xlsx" in check["problem"]
    missing = client.post(f"/api/projects/{pid}/files/check", json={"path": str(tmp_path / "nope.csv")}).json()
    assert missing["problem"] == "There's no file at that path."


def test_openavmkit_loads_what_was_written(client, pid, tmp_path, monkeypatch):
    # The entry OAK box writes is one OpenAVMKit's own loader accepts.
    from openavmkit.data import load_dataframe

    _map().to_file(tmp_path / "parcels.gpkg", layer="parcels")
    client.post(
        f"/api/projects/{pid}/files", json={"path": str(tmp_path / "parcels.gpkg"), "mode": "copy", "name": "parcels"}
    )
    entry = read_settings(pid)["data"]["load"]["parcels"] | {"load": {"key": ["PIN", "string"]}}
    monkeypatch.chdir(projects.project_dir(pid))
    df = load_dataframe(entry, {})
    assert df is not None
    assert df["key"].tolist() == ["0", "1", "2"] and df.crs.to_epsg() == 4326


def test_a_csv_in_windows_text_is_read_as_it_is(client, pid, tmp_path, monkeypatch):
    """Excel's plain "CSV (Comma delimited)" is the Windows code page (cp1252), not UTF-8. OAK box works that out
    (as OpenAVMKit's "encoding": "auto" does), reads it so in its previews, and writes it into data.load, so the run
    reads the same: no "Couldn't read" and no UnicodeDecodeError on an accented name."""
    from openavmkit.data import load_dataframe

    text = "PIN,OWNER\n1,José Peña\n2,Zoë Müller\n"
    (tmp_path / "owners.csv").write_bytes(text.encode("cp1252"))
    (tmp_path / "plain.csv").write_bytes(text.encode("utf-8"))
    for name in ("owners", "plain"):
        body = {"path": str(tmp_path / f"{name}.csv"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    files = {f["name"]: f for f in client.get(f"/api/projects/{pid}/wizard").json()["files"]}
    assert files["owners"]["problem"] is None and files["owners"]["encoding"] == "cp1252"
    assert files["plain"]["encoding"] == "utf-8"
    owner = next(c for c in files["owners"]["columns"] if c["name"] == "OWNER")
    assert "José Peña" in owner["samples"]
    load = read_settings(pid)["data"]["load"]
    assert load["owners"]["encoding"] == "cp1252"
    assert "encoding" not in load["plain"]  # UTF-8: as before, nothing said
    monkeypatch.chdir(projects.project_dir(pid))
    df = load_dataframe(load["owners"] | {"load": {"key": ["PIN", "string"], "owner": ["OWNER", "string"]}}, {})
    assert df is not None and df["owner"].tolist() == ["José Peña", "Zoë Müller"]

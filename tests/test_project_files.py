"""A project's files as the project view gives them: each one's format, shapes and size, read from the file."""

import geopandas as gpd
import pandas as pd
import pytest
from helpers import NEW
from shapely.geometry import box

from oakbox import projects


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

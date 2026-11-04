"""Plain helpers and constants the test files share (the shared fixtures are in conftest.py)."""

import json
import time

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from oakbox import projects

NEW = {
    "name": "Test County 2026",
    "country": "US",
    "region": "TX",
    "jurisdiction": "Test County",
    "tax_year": 2026,
    "valuation_date": "2026-01-01",
    "units": "imperial",
}


def read_settings(pid):
    """The project's in/settings.json, as OpenAVMKit reads it."""
    return json.loads((projects.project_dir(pid) / "in" / "settings.json").read_text(encoding="utf-8"))


def wait(client, url):
    """The step's view once its run has finished (up to three minutes)."""
    view: dict = {}
    for _ in range(360):
        view = client.get(url).json()
        if view["status"] != "running":
            return view
        time.sleep(0.5)
    raise AssertionError("still running")


# ---------- The Fields wizard's project (test_wizard, test_enrich) ----------

IDS = [f"0012-{n:03d}" for n in range(1, 7)]


def wizard_files(folder):
    """A parcel file with shapes, CAMA, sales, permits, and sales by a second ID."""
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


def wizard_step(w, key):
    return next(s for s in w["steps"] if s["key"] == key)


def put_file(client, pid, name, **body):
    return client.put(f"/api/projects/{pid}/wizard/files/{name}", json=body)


def start_wizard(client, pid):
    """The parcel universe and the sales, as the wizard's first two steps set them."""
    assert put_file(client, pid, "shapes", universe=True).status_code == 200
    client.post(f"/api/projects/{pid}/wizard/steps/universe/visit")
    assert put_file(client, pid, "sales", holds="sales").status_code == 200
    return client.post(f"/api/projects/{pid}/wizard/steps/sales/visit").json()


def visit_big_five(client, pid):
    """Show each of Big five's parts, as Start and Next do; the wizard after the last."""
    w: dict = {}
    for part in projects.BIG_FIVE_PARTS:
        w = client.post(f"/api/projects/{pid}/wizard/steps/{part}/visit").json()
    return w

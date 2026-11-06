"""Check sales as a diagnosis (SPEC F6): how deed names are read (Data › Deeds), the sales related to one set aside,
and the five-pattern table."""

import json

import geopandas as gpd
import pandas as pd
import pytest
from helpers import NEW
from shapely.geometry import box

from oakbox import clean, names, projects, salereview

SELLERS = ["SMITH JOHN A", "LEE ANN & BOB", "ACME HOLDINGS LLC", "PARK JO", "", "GARCIA MARIA"]
BUYERS = ["SMITH MARY", "KIM DAE & LEE SU", "JONES TOM", "PARK JO", "WHITE AL", "TRIAD HOMES LLC"]


@pytest.fixture
def pid(client, tmp_path):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    gpd.GeoDataFrame(
        {"ID": [str(i) for i in range(6)]},
        geometry=[box(-79.8 + i * 0.001, 36.0, -79.8 + i * 0.001 + 0.0005, 36.0005) for i in range(6)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "parcels.parquet")
    pd.DataFrame(
        {
            "PID": [str(i) for i in range(6)],
            "PRICE": [200_000] * 6,
            "DATE": ["2024-01-15"] * 6,
            "GRANTOR": SELLERS,
            "GRANTEE": BUYERS,
        }
    ).to_csv(tmp_path / "sale.csv", index=False)
    for name, ext in (("parcels", "parquet"), ("sale", "csv")):
        body = {"path": str(tmp_path / f"{name}.{ext}"), "mode": "copy", "name": name}
        assert client.post(f"/api/projects/{pid}/files", json=body).status_code == 200
    client.put(f"/api/projects/{pid}/wizard/files/parcels", json={"universe": True, "id_column": "ID"})
    client.put(f"/api/projects/{pid}/wizard/files/sale", json={"holds": "sales", "id_column": "PID"})
    return pid


def test_names_are_read_with_a_format_the_user_confirms(client, pid):
    url = f"/api/projects/{pid}/names"
    assert not client.get(url).json()["available"]  # nothing loaded yet
    field = f"/api/projects/{pid}/wizard/fields"
    client.put(f"{field}/deed_grantor", json={"file": "sale", "column": "GRANTOR"})
    client.put(f"{field}/deed_grantee", json={"file": "sale", "column": "GRANTEE"})

    v = client.get(url).json()
    # Capitals, no commas: surname first, guessed and said why, not yet confirmed.
    assert v["available"] and (v["guess"], v["format"]) == ("first_word", None)
    assert "capitals" in v["why"]
    assert v["sales"] == 5  # one sale has no seller
    # Smith to Smith, Lee to (Kim and) Lee, Park to Park; the company is skipped, not misread.
    assert v["shared"] == 3 and v["companies"] == 2
    assert [r["shared"] for r in v["rows"][:3]] == [["SMITH"], ["LEE"], ["PARK"]]

    # Trying another format is a preview: nothing saved.
    tried = client.get(url, params={"format": "last_word"}).json()
    assert tried["shared"] == 1 and tried["format"] is None  # only PARK JO reads the same both ways
    bad = client.get(url, params={"format": "custom", "pattern": "^(\\w+)"}).json()
    assert "surname" in bad["error"] and bad["shared"] == 0
    assert client.put(url, json={"format": "custom", "pattern": "("}).status_code == 422

    v = client.put(url, json={"format": "custom", "pattern": "^\\s*(?P<surname>\\w+)"}).json()
    assert v["format"] == "custom" and v["shared"] == 3
    project = projects.load(pid)
    project.clean.location = ""  # Check sales in use: its settings are written
    s = clean.settings(project)["analysis"]["sales_scrutiny"]
    assert s["same_surname"] == {"pattern": "^\\s*(?P<surname>\\w+)"} and s["patterns"] == "strict"
    assert all(s["heuristics"][h] for h in ("built_after_sale", "vacant_priced_improved", "same_surname"))


def test_the_guess():
    assert names.guess(["Smith, John", "Lee, Ann", "Park Jo"])[0] == "before_comma"
    assert names.guess(["John Smith", "Ann Lee", "BOB KIM"])[0] == "last_word"
    assert names.guess(["ACME LLC", ""]) == (None, "No names of people to go by.")


def test_related_sales(tmp_path):
    out = clean.out_dir(tmp_path)
    out.mkdir(parents=True)
    pd.DataFrame(
        {
            "key_sale": ["a", "b", "c", "d", "e", "f"],
            "address": ["1 Oak", "3 Oak", "9 Elm", "5 Pine", "7 Ash", "1 Oak"],
            "sale_date": pd.to_datetime(
                ["2024-03-01", "2024-03-01", "2024-03-01", "2024-09-01", "2026-01-01", "2020-05-05"]
            ),
            "sale_price": [400_000, 400_000, 250_000, 300_000, 310_000, 150_000],
            "latitude": [36.0, 36.0003, 36.1, 36.2, 36.3, 36.0],
            "longitude": [-79.8, -79.8, -79.8, -79.8, -79.8, -79.8],
            "deed_grantor": ["X", "Y", "Z", "W", "V", "U"],
            "deed_grantee": [
                "Triad Homes, LLC",
                "TRIAD HOMES LLC",
                "TRIAD HOMES LLC",
                "triad homes llc",
                "TRIAD HOMES LLC",
                "A",
            ],
            "deed": ["B1-P2", "B1-P2", "B9-P9", None, None, "B1-P2"],
        }
    ).to_parquet(out / "related.parquet", index=False)
    got = {r.key_sale: r for r in salereview._related(tmp_path, "a", aside={"b"})}
    # b: the same deed, the same day, 33 m away, the same buyer (written another way); set aside too.
    assert set(got["b"].why) == {"deed", "day_near", "day_buyer"} and got["b"].set_aside
    assert 30 < (got["b"].distance or 0) < 40
    assert got["c"].why == ["day_buyer"]  # far away, same day, same buyer
    assert got["d"].why == ["buyer_year"]  # same buyer six months on
    assert "e" not in got  # same buyer, but almost two years later
    assert got["f"].why == ["deed"]  # the same deed ID on another day
    assert list(got)[0] == "f" or got[list(got)[0]].why[0] == "deed"  # same deed first


def test_flag_only_sales_count_and_stay_in():
    flags = pd.DataFrame(
        {
            "key_sale": ["a", "b", "c"],
            "check": ["cluster", "cluster", "same_surname"],
            "model_group": ["g", "g", "g"],
            "pattern": ["2", "other", None],
            "flag_only": [False, True, False],
            "kept": [False, False, False],
            "dropped": [True, False, True],
        }
    )
    assert clean._flag_only(flags).tolist() == [False, True, False]
    project = projects.Project.model_validate(
        {
            "id": "x",
            "name": "x",
            "created_at": "2026-01-01T00:00:00",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "groups": [{"id": "g", "name": "Houses", "color": "#000"}],
        }
    )
    h = pd.DataFrame({"key_sale": list("abcdefgh"), "model_group": ["g"] * 8})
    tables = clean._pattern_tables(project, flags, h, excluded=set())
    assert [t.group for t in tables] == ["", "g"]
    assert tables[1].sales == 8 and tables[1].counts == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 0, "other": 1}
    assert json.loads(tables[0].model_dump_json())["name"] == "All model groups"

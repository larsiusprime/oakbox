"""A synthetic county for performance runs: a parcel file with shapes and a sales file, at any size.

Usage: python perf/make_county.py <out_dir> <parcels> [--seed N]

Writes <out_dir>/parcels.parquet (shapes in EPSG:4326, near Manassas, VA) and <out_dir>/sales.csv. The data is made
to behave like a real roll where it matters for the run's cost: neighbourhoods that are places on the map, prices that
follow size, age, quality, condition and location, about one parcel in eight sold over five years, some sales not
arm's-length, some vacant land, a few condos and commercial parcels, and the blanks real files have.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


def make(out: Path, n: int, seed: int = 7) -> None:
    import geopandas as gpd
    from shapely.geometry import box

    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)

    # Parcels on a jittered grid: a square county about 75 m a lot, near Manassas, VA.
    side = math.ceil(math.sqrt(n))
    step = 0.0008  # degrees, about 70-90 m
    col = np.arange(n) % side
    row = np.arange(n) // side
    x0 = -77.55 + col * step + rng.uniform(0, step * 0.15, n)
    y0 = 38.70 + row * step + rng.uniform(0, step * 0.15, n)
    w = step * rng.uniform(0.55, 0.85, n)
    h = step * rng.uniform(0.55, 0.85, n)
    geometry = [box(a, b, a + c, b + d) for a, b, c, d in zip(x0, y0, w, h, strict=True)]

    # Neighbourhoods: blocks of the grid, about 500 parcels each, each with its own price level.
    per = max(4, int(math.sqrt(500)))
    nbhd_x, nbhd_y = col // per, row // per
    nbhd = np.char.add(np.char.add("N", nbhd_x.astype(str)), np.char.add("_", nbhd_y.astype(str)))
    levels = {k: rng.normal(0, 0.18) for k in np.unique(nbhd)}
    loc = np.array([levels[k] for k in nbhd])

    use = rng.choice(
        ["RESIDENTIAL", "CONDO", "COMMERCIAL", "AGRICULTURAL", "EXEMPT", "VACANT"],
        size=n,
        p=[0.74, 0.08, 0.06, 0.03, 0.03, 0.06],
    )
    btype = np.where(
        use == "RESIDENTIAL",
        rng.choice(["01-SFR", "02-TOWNHOUSE", "08-DUPLEX"], size=n, p=[0.82, 0.12, 0.06]),
        np.where(use == "CONDO", "04-CONDO", np.where(use == "COMMERCIAL", "20-RETAIL", "")),
    )
    vacant = use == "VACANT"
    area = np.where(vacant, np.nan, np.clip(rng.lognormal(math.log(1800), 0.35, n), 450, 9000)).round()
    land = np.clip(rng.lognormal(math.log(9000), 0.6, n), 1200, 400000).round()
    year = np.where(vacant, np.nan, rng.integers(1925, 2025, n)).astype(float)
    quality = np.where(vacant, np.nan, np.clip(rng.normal(3.5, 0.9, n).round(), 1, 6))
    condition = np.where(vacant, np.nan, np.clip(rng.normal(3, 0.8, n).round(), 1, 5))
    stories = np.where(vacant, np.nan, rng.choice([1, 1.5, 2, 3], size=n, p=[0.45, 0.1, 0.4, 0.05]))
    # Blanks, as real files have them.
    for a, share in ((year, 0.03), (quality, 0.05), (condition, 0.08), (stories, 0.1)):
        a[rng.random(n) < share] = np.nan

    def worth(i_area, i_land, i_year, i_q, i_c, i_loc, i_vac):
        age = np.nan_to_num(2026 - i_year, nan=40)
        bldg = np.nan_to_num(i_area, nan=0) * 155 * (1 + 0.08 * (np.nan_to_num(i_q, nan=3.5) - 3.5))
        bldg *= (1 - np.clip(age, 0, 80) / 160) * (1 + 0.05 * (np.nan_to_num(i_c, nan=3) - 3))
        return (bldg * (~i_vac) + i_land * 6.5) * np.exp(i_loc)

    value = worth(area, land, year, quality, condition, loc, vacant)
    ids = np.array([f"{100000 + i}" for i in range(n)])
    parcels = gpd.GeoDataFrame(
        {
            "PARCEL_ID": ids,
            "LANDUSE": use,
            "BLDGTYPE": btype,
            "LIVING_AREA": area,
            "YR_BUILT": year,
            "QUALITY": quality,
            "CONDITION": condition,
            "STORIES": stories,
            "NBHD": nbhd,
            "ASSESSED": (value * rng.normal(0.92, 0.08, n)).round(-2),
        },
        geometry=geometry,
        crs="EPSG:4326",
    )
    parcels.to_parquet(out / "parcels.parquet")

    # Sales: about one parcel in eight over five years, a few twice; prices from the same worth, with time trend.
    sold = rng.choice(n, size=int(n * 0.14), replace=True)
    days = rng.integers(0, 5 * 365, len(sold))
    date = pd.Timestamp("2021-01-01") + pd.to_timedelta(days, unit="D")
    trend = 1 + 0.06 * days / 365
    price = worth(area[sold], land[sold], year[sold], quality[sold], condition[sold], loc[sold], vacant[sold])
    price = (price * trend * rng.lognormal(0, 0.12, len(sold))).round(-2)
    qualified = rng.choice(["Q", "U"], size=len(sold), p=[0.82, 0.18])
    price[qualified == "U"] *= rng.uniform(0.2, 1.0, (qualified == "U").sum())
    price[rng.random(len(sold)) < 0.01] = 0  # nominal transfers
    pd.DataFrame(
        {
            "PARCEL_ID": ids[sold],
            "SALE_PRICE": price.round(-2),
            "SALE_DATE": date.strftime("%m/%d/%Y"),
            "QUALIFIED": qualified,
            "VACANT_AT_SALE": np.where(vacant[sold], "Y", "N"),
        }
    ).sort_values("SALE_DATE").to_csv(out / "sales.csv", index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("parcels", type=int)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    make(a.out, a.parcels, a.seed)
    print(f"{a.parcels:,} parcels in {a.out}")


if __name__ == "__main__":
    main()

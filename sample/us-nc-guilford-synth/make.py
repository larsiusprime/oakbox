"""Builds the synthetic Guilford-style sample county (see README.md). Deterministic: same seed, same files.

uv run python sample/us-nc-guilford-synth/make.py
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point, box

HERE = Path(__file__).parent
IN = HERE / "in"
rng = np.random.default_rng(336)

# ---------- Parcels: blocks of lots on a street grid, near Greensboro (NC State Plane, US feet) ----------

E0, N0 = 1_760_000, 850_000
NBHDS = {  # code: (city, zip, land $/sqft, lot width ft, lot depth ft, typical year built, quality)
    "1001": ("GREENSBORO", "27401", 4.0, 50, 120, 1925, 0.85),
    "1002": ("GREENSBORO", "27403", 6.5, 60, 140, 1950, 1.00),
    "1003": ("GREENSBORO", "27408", 11.0, 90, 160, 1965, 1.25),
    "2001": ("HIGH POINT", "27260", 3.5, 55, 120, 1940, 0.85),
    "2002": ("HIGH POINT", "27265", 5.5, 75, 150, 1995, 1.05),
    "3001": ("JAMESTOWN", "27282", 7.0, 100, 180, 2005, 1.15),
    "3002": ("SUMMERFIELD", "27358", 4.5, 160, 260, 2012, 1.20),
    "1004": ("GREENSBORO", "27406", 3.0, 55, 115, 1975, 0.80),
}
STREETS = [
    "ELM",
    "SPRING GARDEN",
    "LEE",
    "FRIENDLY",
    "WENDOVER",
    "BATTLEGROUND",
    "LAWNDALE",
    "MARTIN LUTHER KING JR",
    "ASPEN",
    "HOLDEN",
    "COLLEGE",
    "MAIN",
    "LEXINGTON",
    "BRIDFORD",
    "GUILFORD COLLEGE",
    "PLEASANT GARDEN",
]
SUFFIX = ["ST", "RD", "AVE", "DR", "LN", "CT", "PKWY"]

rows = []
reid = 118_000
for b, (nbhd, (city, zipc, land_rate, w, d, yb, q)) in enumerate(NBHDS.items()):
    # each neighborhood is a patch of blocks; each block is 2 rows of lots back to back
    bx, by = E0 + (b % 4) * 9_000, N0 + (b // 4) * 9_000
    lots_per_row, blocks_x, blocks_y = 10, 4, 8
    for i in range(blocks_x):
        for j in range(blocks_y):
            x0, y0 = bx + i * (lots_per_row * w + 60), by + j * (2 * d + 60)
            street = f"{STREETS[(b * 3 + j) % len(STREETS)]} {SUFFIX[(i + j) % len(SUFFIX)]}"
            for side in range(2):
                for k in range(lots_per_row):
                    ww = w * rng.uniform(0.85, 1.2)
                    geom = box(x0 + k * w, y0 + side * d, x0 + k * w + ww * 0.98, y0 + (side + 1) * d - 1)
                    reid += int(rng.integers(1, 4))
                    rows.append(
                        dict(
                            reid=reid,
                            nbhd=nbhd,
                            city=city,
                            zip=zipc,
                            land_rate=land_rate,
                            yb=yb,
                            q=q,
                            street=street,
                            house=100 + 2 * k + side + 40 * i,
                            geometry=geom,
                        )
                    )
p = pd.DataFrame(rows)
n = len(p)
p["sqft_land"] = [g.area for g in p.geometry]
p["vacant"] = rng.random(n) < 0.06
p["area"] = np.where(p.vacant, 0, np.clip(rng.lognormal(np.log(1700 * p.q), 0.28), 640, 6500)).round(-1)
p["year"] = np.where(p.vacant, 0, np.clip(p.yb + rng.normal(0, 12, n), 1900, 2024)).astype(int)
p["eff_year"] = np.where(p.vacant, 0, np.maximum(p.year, p.year + (rng.random(n) < 0.3) * rng.integers(5, 40, n)))
p["eff_year"] = np.minimum(p.eff_year, 2024)
grade_idx = np.clip(np.round(2 - (p.q - 1) * 4 + rng.normal(0, 0.6, n)), 0, 4).astype(int)
p["grade"] = np.array(["A", "B", "C", "D", "E"])[grade_idx]
cond_idx = np.clip(np.round(2 + (2024 - p.eff_year) / 40 + rng.normal(0, 0.7, n)), 0, 5).astype(int)
p["cond"] = np.array(["EX", "VG", "GD", "AV", "FR", "PR"])[cond_idx]
p["beds"] = np.where(p.vacant, 0, np.clip(np.round(p.area / 600 + rng.normal(0, 0.6, n)), 1, 7)).astype(int)
p["full"] = np.where(p.vacant, 0, np.clip(np.round(p.area / 1000 + rng.normal(0, 0.4, n)), 1, 5)).astype(int)
p["half"] = np.where(p.vacant, 0, (rng.random(n) < 0.45).astype(int))
p["stories"] = np.where(p.vacant, 0, np.where(p.area > 2400, 2.0, np.where(rng.random(n) < 0.15, 1.5, 1.0)))

# The "true" market value in Jan 2025, from which sales and assessments are drawn.
grade_f = np.array([1.35, 1.15, 1.0, 0.85, 0.7])[grade_idx]
cond_f = np.array([1.1, 1.05, 1.0, 0.92, 0.8, 0.65])[cond_idx]
age = np.where(p.vacant, 0, 2025 - p.eff_year)
land = p.land_rate * p.sqft_land**0.85 * 5.5
bldg = np.where(p.vacant, 0, p.area * 215 * grade_f * cond_f * np.maximum(0.35, 1 - age * 0.009))
p["market"] = (land + bldg) * rng.lognormal(0, 0.06, n)

# Assessed values from the 2022 revaluation: below today's market, and noisy.
p["land_val"] = (land * 0.78 * rng.lognormal(0, 0.1, n)).round(-2)
p["bldg_val"] = (bldg * 0.78 * rng.lognormal(0, 0.12, n)).round(-2)
p["total_val"] = p.land_val + p.bldg_val

# PIN: 10 digits from the map grid, like Guilford's PIN_PLUS_EXT without the extension.
p["pin"] = [
    f"{7800 + int((g.centroid.x - E0) // 4000):04d}{int((g.centroid.y - N0) // 100) % 100:02d}{i % 10000:04d}"
    for i, g in enumerate(p.geometry)
]

# ---------- Planted problems ----------
# 1. Parcel IDs from the old system are zero-padded to 10 characters; IDs given since aren't. Sales and CAMA
#    files use the plain number, so only the unpadded parcels match until leading zeros are removed.
padded = rng.random(n) < 0.86
p["GDV_REID"] = [f"{r:010d}" if pad else str(r) for r, pad in zip(p.reid, padded, strict=True)]
# 2. A parcel split on the map but not in the records: two shapes with the same ID.
split = p.index[50]
twin = p.loc[[split]].copy()
g = p.at[split, "geometry"]
minx, miny, maxx, maxy = g.bounds
p.at[split, "geometry"] = box(minx, miny, (minx + maxx) / 2, maxy)
twin["geometry"] = [box((minx + maxx) / 2, miny, maxx, maxy)]
# 3. Right-of-way and common-area slivers with no ID at all.
slivers = []
for k in range(14):
    x, y = E0 - 500 + k * 300, N0 - 400
    slivers.append(
        dict(
            GDV_REID=None,
            pin="",
            nbhd="",
            city="",
            zip="",
            street="",
            house=0,
            sqft_land=0,
            land_val=0,
            bldg_val=0,
            total_val=0,
            geometry=box(x, y, x + 40, y + 900),
        )
    )

parcels = gpd.GeoDataFrame(
    pd.concat([p, twin], ignore_index=True).assign(
        PIN_PLUS_EXT=lambda d: d.pin + " 000",
        ACRES=lambda d: (d.sqft_land / 43_560).round(3),
        PHYADDR=lambda d: d.house.astype(str) + " " + d.street,
        PHYCITY=lambda d: d.city,
        PHYZIP=lambda d: d.zip,
        NBHD=lambda d: d.nbhd,
        LAND_VALUE=lambda d: d.land_val,
        BLDG_VALUE=lambda d: d.bldg_val,
        TOTAL_VALUE=lambda d: d.total_val,
    )[
        [
            "GDV_REID",
            "PIN_PLUS_EXT",
            "ACRES",
            "PHYADDR",
            "PHYCITY",
            "PHYZIP",
            "NBHD",
            "LAND_VALUE",
            "BLDG_VALUE",
            "TOTAL_VALUE",
            "geometry",
        ]
    ],
    crs="EPSG:2264",
)
sl = gpd.GeoDataFrame(pd.DataFrame(slivers), crs="EPSG:2264").assign(
    PIN_PLUS_EXT="",
    ACRES=lambda d: (d.geometry.area / 43_560).round(3),
    PHYADDR="",
    PHYCITY="",
    PHYZIP="",
    NBHD="",
    LAND_VALUE=0,
    BLDG_VALUE=0,
    TOTAL_VALUE=0,
)[parcels.columns]
parcels = gpd.GeoDataFrame(pd.concat([parcels, sl], ignore_index=True), crs="EPSG:2264")
parcels = parcels.sample(frac=1, random_state=7).reset_index(drop=True)  # files are rarely sorted helpfully

# ---------- CAMA: one row per building card. ~3% of parcels have a second card (a garage apartment, a barn). ----------
built = p[~p.vacant]
cards = built.assign(CARD=1)
second = built.sample(frac=0.03, random_state=11).assign(
    CARD=2,
    area=lambda d: (d.area * rng.uniform(0.2, 0.45, len(d))).round(-1),
    beds=lambda d: d.beds.clip(upper=1),
    full=1,
    half=0,
    stories=1.0,
)
cards = pd.concat([cards, second]).sort_values(["reid", "CARD"])
cama = pd.DataFrame(
    {
        "REID": cards.reid,
        "CARD_NUM": cards.CARD,
        "HEATED_AREA": cards.area.astype(int),
        "YEAR_BUILT": cards.year,
        "EFF_YEAR": cards.eff_year,
        "GRADE": cards.grade,
        "COND": cards.cond,
        "STORIES": cards.stories,
        "BEDROOMS": cards.beds,
        "FULL_BATHS": cards.full,
        "HALF_BATHS": cards.half,
    }
)

# Quality and condition the other ways exports write them, from the same grade and condition: with
# +/- (B+, C-), a 1-10 number, words. A separate random stream, so the columns above don't change.
q_rng = np.random.default_rng(2048)
grade_letter = cama["GRADE"].to_numpy()
cama["GRADE_PLUS"] = [g + q_rng.choice(["+", "", "-"], p=[0.3, 0.4, 0.3]) for g in grade_letter]
cama["QUALITY_NUM"] = [
    int(np.clip({"A": 9, "B": 7, "C": 5, "D": 3, "E": 2}[g] + q_rng.integers(-1, 2), 1, 10)) for g in grade_letter
]
words = {"EX": "Excellent", "VG": "Very Good", "GD": "Good", "AV": "Average", "FR": "Fair", "PR": "Poor"}
cama["COND_DESC"] = [words[c] for c in cama["COND"]]
cama["COND_NUM"] = [{"EX": 6, "VG": 5, "GD": 4, "AV": 3, "FR": 2, "PR": 1}[c] for c in cama["COND"]]

# ---------- Sales, 2019-2025: about a third of parcels, some twice. No sale ID column. ----------
sold = p.sample(frac=0.34, random_state=3)
again = sold.sample(frac=0.15, random_state=4)
s = pd.concat([sold, again], ignore_index=True)
days = rng.integers(0, (pd.Timestamp("2025-12-31") - pd.Timestamp("2019-01-01")).days, len(s))
dates = pd.Timestamp("2019-01-01") + pd.to_timedelta(days, unit="D")
years = (dates - pd.Timestamp("2025-01-01")).days / 365.25
price = s.market.to_numpy() * np.exp(0.065 * years) * rng.lognormal(0, 0.09, len(s))
qualified = rng.random(len(s)) > 0.12
# unqualified: family transfers, foreclosures, nominal deeds
price = np.where(qualified, price, price * rng.choice([0.0, 0.4, 0.7], len(s), p=[0.25, 0.35, 0.4]))
price = np.where(price == 0, 10, price).round(-2)
price = np.where(price < 100, 10, price)
reid_txt = s.reid.astype(str).to_numpy().astype(object)
# 4. Hand-keyed IDs: a few with a trailing space.
for i in rng.choice(len(s), 18, replace=False):
    reid_txt[i] = reid_txt[i] + " "
# 5. Sales of parcels since combined away: their IDs aren't in the universe any more.
for i in rng.choice(len(s), 6, replace=False):
    reid_txt[i] = str(900_000 + i)
pin = s.pin.to_numpy()
sales = pd.DataFrame(
    {
        "REID": reid_txt,
        # 6. The PIN as printed on the deed: hyphenated, unlike the parcel file.
        "PIN": [f"{x[:4]}-{x[4:6]}-{x[6:]}" for x in pin],
        "DEED_DATE": [f"{d.month}/{d.day}/{d.year} 0:00" for d in dates],
        "DEED_BOOK": rng.integers(7000, 8900, len(s)),
        "DEED_PAGE": rng.integers(1, 3200, len(s)),
        "SALE_PRICE": price.astype(int),
        "QUALIFIED": np.where(qualified, "Q", "U"),
        "VACANT_LOT": np.where(s.vacant, "Y", ""),
    }
).sort_values("DEED_BOOK", kind="stable")

# 10. The same prices written the ways exports write them, one column each, to try the price checks on.
#     A separate random stream, so the columns above don't change.
fmt_rng = np.random.default_rng(1024)
p = sales["SALE_PRICE"].to_numpy()
price_blank = fmt_rng.random(len(p)) < 0.02  # some exports leave the price out
sales["PRICE_DOLLARS"] = [f"${v:,.2f}" for v in p]  # $250,000.00
sales["PRICE_COMMAS"] = [f"{v:,}" for v in p]  # 250,000
sales["PRICE_DECIMAL"] = [f"{v:.2f}" for v in p]  # 250000.00
sales["PRICE_PADDED"] = [f"$ {v:>12,.2f} " for v in p]  # fixed-width report: "$   250,000.00 "
sales["PRICE_EURO"] = [f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".") for v in p]  # 250.000,00
sales["PRICE_THOUSANDS"] = [f"{v / 1000:g}" for v in p]  # 250 (in $1,000s, as some summaries give it)
sales["PRICE_CENTS"] = [str(v * 100) for v in p]  # 25000000 (whole cents)
sales["PRICE_EXCEL"] = [f"{v:.2E}" if v >= 1_000_000 else str(v) for v in p]  # 1.25E+06: Excel's big numbers
sales["PRICE_SHORT"] = [f"${v / 1e6:.2f}M" if v >= 1e6 else f"${v / 1000:.0f}K" for v in p]  # $250K, $1.25M
sales["PRICE_MIXED"] = [  # hand-kept: a bit of everything, with blanks and placeholders
    "" if b else fmt_rng.choice([f"${v:,}", f"{v:,}", str(v), f"${v:,.2f}", f"{v}.00"])
    for v, b in zip(p, price_blank, strict=True)
]
for i in np.flatnonzero(fmt_rng.random(len(p)) < 0.01):
    sales.iloc[i, sales.columns.get_loc("PRICE_MIXED")] = fmt_rng.choice(["N/A", "-", "0", "$0.00", "TBD"])
sales["PRICE_NEGATIVE"] = [f"({v:,})" if v < 100 else f"{v:,}" for v in p]  # accounting: (10) for a $10 deed refund

(IN / "geo").mkdir(parents=True, exist_ok=True)

# ---------- Map layers (the Shapefiles section): zoning polygons and school points ----------
# A separate random stream, so the files above don't change.
geo_rng = np.random.default_rng(4096)
zones = []
for b, (_nbhd, (_, _, _, w, d, _, q)) in enumerate(NBHDS.items()):
    bx, by = E0 + (b % 4) * 9_000, N0 + (b // 4) * 9_000
    width, height = 4 * (10 * w + 60), 8 * (2 * d + 60)
    # Two zoning districts per neighborhood, split east-west; commercial along the eastern edge.
    code = "R-3" if q < 0.95 else "R-5" if q < 1.1 else "RS-12"
    zones.append(
        dict(
            ZONE_CODE=code,
            ZONE_DESC={"R-3": "Residential 3", "R-5": "Residential 5", "RS-12": "Residential single-family 12"}[code],
            geometry=box(bx - 50, by - 50, bx + width * 0.7, by + height + 50),
        )
    )
    zones.append(
        dict(
            ZONE_CODE="C-M",
            ZONE_DESC="Commercial medium",
            geometry=box(bx + width * 0.7, by - 50, bx + width + 50, by + height + 50),
        )
    )
zoning = gpd.GeoDataFrame(pd.DataFrame(zones), crs="EPSG:2264").to_crs(4326)
schools = []
for b in range(len(NBHDS)):
    bx, by = E0 + (b % 4) * 9_000, N0 + (b // 4) * 9_000
    for k in range(2):
        x, y = bx + geo_rng.uniform(-1500, 5500), by + geo_rng.uniform(-1500, 8000)
        schools.append(dict(SCHOOL=f"School {b * 2 + k + 1}", LEVEL=["Elementary", "Middle"][k], geometry=Point(x, y)))
schools_gdf = gpd.GeoDataFrame(pd.DataFrame(schools), crs="EPSG:2264")

# School attendance zones (polygons covering every parcel): one per pair of neighborhoods, split north-south.
zone_rows = []
for i in range(4):
    x0 = E0 + i * 9_000 - 3_000
    for j, (name, lo, hi) in enumerate([("South", N0 - 3_000, N0 + 6_000), ("North", N0 + 6_000, N0 + 15_000)]):
        zone_rows.append(
            dict(
                ZONE_ID=f"ES-{i * 2 + j + 1:02d}",
                ZONE_NAME=f"{name} Elementary {i + 1}",
                GRADES="K-5",
                geometry=box(x0, lo, x0 + 9_000, hi),
            )
        )
school_zones = gpd.GeoDataFrame(pd.DataFrame(zone_rows), crs="EPSG:2264")

# Flood zones (polygons covering some parcels): bands along creeks through a few neighborhoods. AE is the
# 1% annual chance floodplain; X (shaded) the 0.2%.
flood_rows = []
for b in (0, 2, 5, 7):
    bx, by = E0 + (b % 4) * 9_000, N0 + (b // 4) * 9_000
    y = by + float(geo_rng.uniform(800, 3_000))
    flood_rows.append(
        dict(FLD_ZONE="AE", ZONE_SUBTY="1% ANNUAL CHANCE", geometry=box(bx - 500, y, bx + 6_000, y + 350))
    )
    flood_rows.append(
        dict(FLD_ZONE="X", ZONE_SUBTY="0.2% ANNUAL CHANCE", geometry=box(bx - 500, y + 350, bx + 6_000, y + 650))
    )
flood_zones = gpd.GeoDataFrame(pd.DataFrame(flood_rows), crs="EPSG:2264")

# For distances: lakes (polygons), rivers (lines) and the central business district (one polygon). The
# neighborhood blocks sit on a 4 x 2 grid, 9,000 ft apart, from (E0, N0); these lie between and beside them.
lakes = gpd.GeoDataFrame(
    {
        "NAME": ["Lake Brandt", "Lake Higgins", "Oak Hollow Lake"],
        "TYPE": ["Reservoir", "Reservoir", "Reservoir"],
    },
    geometry=[
        Point(E0 + 7_400, N0 + 13_800).buffer(1_400),
        Point(E0 + 16_200, N0 + 15_600).buffer(900),
        Point(E0 + 26_300, N0 + 4_200).buffer(1_200),
    ],
    crs="EPSG:2264",
)
rivers = gpd.GeoDataFrame(
    {"NAME": ["Reedy Fork", "Deep River"], "TYPE": ["Creek", "River"]},
    geometry=[
        LineString(
            [(E0 - 2_000, N0 + 7_600), (E0 + 8_000, N0 + 8_200), (E0 + 18_000, N0 + 7_400), (E0 + 34_000, N0 + 8_300)]
        ),
        LineString(
            [
                (E0 + 20_500, N0 - 2_000),
                (E0 + 21_500, N0 + 5_000),
                (E0 + 19_800, N0 + 12_000),
                (E0 + 20_600, N0 + 18_000),
            ]
        ),
    ],
    crs="EPSG:2264",
)
# Downtown: the northeast corner of the oldest Greensboro neighborhood (1001) and the gap beside it.
cbd = gpd.GeoDataFrame(
    {"NAME": ["Downtown Greensboro"]}, geometry=[box(E0 + 1_200, N0 + 2_400, E0 + 3_800, N0 + 5_200)], crs="EPSG:2264"
)
parcels.to_parquet(IN / "geo" / "parcels.parquet")
zoning.to_file(IN / "geo" / "zoning.geojson", driver="GeoJSON")  # in degrees, unlike the parcels
schools_gdf.to_file(IN / "geo" / "schools.shp")
school_zones.to_file(IN / "geo" / "school_zones.shp")
flood_zones.to_file(IN / "geo" / "flood_zones.shp")
lakes.to_file(IN / "geo" / "lakes.shp")
rivers.to_file(IN / "geo" / "rivers.shp")
cbd.to_file(IN / "geo" / "cbd.gpkg", layer="cbd", driver="GPKG")
cama.to_csv(IN / "cama.csv", index=False)
sales.to_csv(IN / "sales.csv", index=False)
print(f"{len(parcels):,} parcel shapes, {len(cama):,} building cards, {len(sales):,} sales")

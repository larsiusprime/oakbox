"""Builds the Guilford sample county (see README.md) from a slice of Guilford County, NC's real data, altered and
with problems planted. Deterministic: same seed, same files.

uv run python sample/us-nc-guilford-synth/make.py

The first run downloads Guilford's files (about 300 MB) from OpenAVMKit's public sample-locality container into
.cache/ beside this file; later runs reuse them.
"""

import shutil
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

HERE = Path(__file__).parent
IN = HERE / "in"
CACHE = HERE / ".cache"
SOURCE = "https://landeconomics.blob.core.windows.net/localities-public/us/nc/guilford"
rng = np.random.default_rng(336)

# Downtown Greensboro north to Buffalo Lake, in NC State Plane (EPSG:2264, US feet): about 9,400 parcels, mostly
# single-family houses and condos, with 1,400 qualified house sales since 2018. Parcels are kept when their
# centre falls inside; map layers are cut to the window plus a margin.
X0, Y0, X1, Y1 = 1_760_000, 843_000, 1_772_000, 862_000
MARGIN = 3_000
SINCE = 2015


def fetch(name: str) -> Path:
    path = CACHE / name
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name}")
        with urllib.request.urlopen(f"{SOURCE}/{name}") as r, open(path.with_suffix(".part"), "wb") as f:
            shutil.copyfileobj(r, f)
        path.with_suffix(".part").rename(path)
    return path


def layer(name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_parquet(fetch(f"geo/{name}.parquet"))
    area = gpd.GeoSeries([box(X0 - MARGIN, Y0 - MARGIN, X1 + MARGIN, Y1 + MARGIN)], crs=2264).to_crs(gdf.crs)
    return gdf[gdf.intersects(area.iloc[0])].reset_index(drop=True)


# ---------- Parcels: the real shapes, with new IDs, shuffled house numbers and nudged values ----------

real = gpd.read_parquet(
    fetch("geo/parcels.parquet"),
    columns=[
        "REID",
        "GDV_REID",
        "PIN_PLUS_EXT",
        "TOTAL_ACRES",
        "PHYADDR_STR_NUM",
        "PHYADDR_DIR_PFX",
        "PHYADDR_STR",
        "PHYADDR_STR_TYPE",
        "PHYADDR_CITY",
        "PHYADDR_ZIP",
        "NEIGHBORHOOD",
        "LAND_CLASS",
        "ZONING",
        "TOTAL_LAND_VALUE_ASSESSED",
        "TOTAL_BLDG_VALUE_ASSESSED",
        "geometry",
    ],
)
real = real.set_crs(2264, allow_override=True)  # the file's CRS is State Plane, but unnamed
centre = real.geometry.centroid
p = real[(centre.x.between(X0, X1) & centre.y.between(Y0, Y1)).to_numpy()].reset_index(drop=True)
n = len(p)

# New parcel IDs: plain numbers, as Guilford's are, but not theirs.
new_id = dict(zip(p.REID, rng.permutation(np.arange(118_000, 118_000 + 3 * n, 3))[:n].astype(str), strict=True))
p["reid"] = p.REID.map(new_id)
p.loc[p.GDV_REID.isna(), "reid"] = None  # the few shapes Guilford has no ID for (right-of-way) keep none


def text(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


# Real streets, house numbers shuffled among the parcels on each street.
street = (
    (text(p.PHYADDR_DIR_PFX) + " " + text(p.PHYADDR_STR) + " " + text(p.PHYADDR_STR_TYPE)).str.split().str.join(" ")
)
house = text(p.PHYADDR_STR_NUM).to_numpy().copy()
for _, idx in street.groupby(street).groups.items():
    idx = np.asarray(idx)
    house[idx] = rng.permutation(house[idx])
p["addr"] = np.where((street != "") & (house != ""), house + " " + street, "")

# Assessed values (2022 revaluation): the real ones, each nudged a little.
land = pd.to_numeric(p.TOTAL_LAND_VALUE_ASSESSED, errors="coerce").fillna(0)
bldg = pd.to_numeric(p.TOTAL_BLDG_VALUE_ASSESSED, errors="coerce").fillna(0)
p["land_val"] = (land * rng.lognormal(0, 0.04, n)).round(-2)
p["bldg_val"] = (bldg * rng.lognormal(0, 0.04, n)).round(-2)

# ---------- Planted problems in the parcel file ----------
# 1. Parcel IDs from the old system are zero-padded to 10 characters; IDs given since aren't. The sales and
#    building files use the plain number, so only the unpadded parcels match until leading zeros are removed.
padded = rng.random(n) < 0.86
p["GDV_REID"] = [r if r is None or not pad else f"{int(r):010d}" for r, pad in zip(p.reid, padded, strict=True)]
# 2. A parcel split on the map but not in the records: two shapes with the same ID.
split = int(np.flatnonzero((p.LAND_CLASS == "RESIDENTIAL").to_numpy())[50])
g = p.geometry.iloc[split]
minx, miny, maxx, maxy = g.bounds
twin = p.iloc[[split]].copy()
p.loc[split, "geometry"] = g.intersection(box(minx, miny, (minx + maxx) / 2, maxy))
twin["geometry"] = [g.intersection(box((minx + maxx) / 2, miny, maxx, maxy))]
p = pd.concat([p, twin], ignore_index=True)

parcels = gpd.GeoDataFrame(
    {
        "GDV_REID": p.GDV_REID,
        "PIN_PLUS_EXT": p.PIN_PLUS_EXT,
        "TOTAL_ACRES": pd.to_numeric(p.TOTAL_ACRES, errors="coerce"),  # land size, in acres
        "LOCATION_ADDR": p.addr,
        "PHYADDR_CITY": text(p.PHYADDR_CITY),
        "PHYADDR_ZIP": text(p.PHYADDR_ZIP),
        "NEIGHBORHOOD": text(p.NEIGHBORHOOD),
        "LAND_CLASS": text(p.LAND_CLASS),
        "ZONING": text(p.ZONING),
        "TOTAL_LAND_VALUE_ASSESSED": p.land_val.astype(int),
        "TOTAL_BLDG_VALUE_ASSESSED": p.bldg_val.astype(int),
        "TOTAL_PROP_VALUE": (p.land_val + p.bldg_val).astype(int),
    },
    geometry=p.geometry.to_numpy(),
    crs=2264,
)
# 9. Condo units on the roll, not on the map: as many counties keep them, a unit has no shape of its own. Its
#    building's parcel (the PIN's -000 extension) is on the map; the units (-001, -002, ...) are rows of their own
#    file, with the parcel file's columns and the plain ID. A building without a -000 parcel keeps its units' shapes.
pin10 = parcels.PIN_PLUS_EXT.fillna("").str[:10]
ext = parcels.PIN_PLUS_EXT.fillna("").str[11:]
has_building = set(pin10[ext == "000"])
unit = (ext != "000") & (ext != "") & pin10.isin(has_building)
units = pd.DataFrame(parcels[unit].drop(columns="geometry"))
units.insert(0, "REID", units.pop("GDV_REID").str.lstrip("0"))
units = units.sample(frac=1, random_state=11).reset_index(drop=True)
parcels = parcels[~unit]
parcels = parcels.sample(frac=1, random_state=7).reset_index(drop=True)  # files are rarely sorted helpfully

# ---------- Buildings: each parcel's own real building cards, nudged together so they still agree ----------
# Moving a building a few years or a few percent keeps it whole: the effective year moves with the year built,
# the footprint with the heated area, and a parcel without a building (vacant land) still has none.
BUILDING = [
    "REID",
    "BLDG_CARD",
    "BLDG_DESC",
    "BLDG_TYPE",
    "UNITS",
    "HEATED_AREA",
    "MB_FOOTPRINT_AREA",
    "STYLE",
    "EXTERIOR",
    "HEATING",
    "AIR_COND",
    "YEAR_BUILT",
    "EFF_YEAR",
    "GRADE",
    "GRADE_LETTER",
    "GRADE_SCORE",
    "CONDITION",
    "CONDITION_CODE",
    "CONDITION_SCORE",
    "BEDROOMS",
    "BATH_FULL",
    "BATH_HALF",
]
b = pd.read_csv(fetch("building.csv"), dtype=str, usecols=BUILDING)
b = b[b.REID.isin(new_id)].copy()
b["REID"] = b.REID.map(new_id)
m = len(b)
scale = rng.uniform(0.95, 1.05, m)
for col in ("HEATED_AREA", "MB_FOOTPRINT_AREA"):
    v = pd.to_numeric(b[col], errors="coerce")
    b[col] = (v * scale).round().astype("Int64")
shift = rng.integers(-3, 4, m)
yb = pd.to_numeric(b.YEAR_BUILT, errors="coerce")
eff = pd.to_numeric(b.EFF_YEAR, errors="coerce")
b["YEAR_BUILT"] = np.minimum(yb + shift, 2024).astype("Int64")
b["EFF_YEAR"] = np.maximum(np.minimum(eff + shift, 2024), b.YEAR_BUILT).astype("Int64")
b = b.sort_values(["REID", "BLDG_CARD"], key=lambda s: pd.to_numeric(s, errors="coerce"))
buildings = b[BUILDING].copy()

# 9. Quality and condition written the ways other systems combine them, from the same grade and condition:
#    QC_RATING is a UAD-style pair (Q1 best … Q6; C1 best … C6) in one value, and CDU a condition, desirability
#    and utility rating (EX … VP). A separate random stream, so the columns above don't change.
qc_rng = np.random.default_rng(2048)
grade_q = buildings.GRADE_LETTER.map({"AA": 1, "A": 2, "B": 3, "C": 4, "D": 5, "E": 6}).fillna(4).astype(int)
good = 1 - pd.to_numeric(buildings.CONDITION_SCORE, errors="coerce").fillna(0.2)
cond_c = pd.cut(good, [-1, 0.35, 0.55, 0.7, 0.82, 0.93, 2], labels=[6, 5, 4, 3, 2, 1]).astype(int)
sep = qc_rng.choice(["", "", " ", "/", "-"], len(buildings))
buildings["QC_RATING"] = ["Q" + str(q) + s + "C" + str(c) for q, s, c in zip(grade_q, sep, cond_c, strict=True)]
cdu_words = {1: "EX", 2: "VG", 3: "GD", 4: "AV", 5: "FR", 6: "PR"}
buildings["CDU"] = [cdu_words[int(min(6, max(1, c + qc_rng.integers(-1, 2))))] for c in cond_c]

# ---------- Sales since 2015: the real deeds, dates moved up to a month and prices nudged. No sale ID. ----------
s = pd.read_csv(
    fetch("sale.csv"),
    dtype=str,
    usecols=["REID", "SALE_DATE", "SALE_PRICE", "SALE_STATUS", "SALE_TYPE", "DEED_BOOK", "DEED_PAGE"],
)
s = s[s.REID.isin(new_id)].copy()
when = pd.to_datetime(s.SALE_DATE, format="%m/%d/%Y %H:%M")
s = s[when.dt.year >= SINCE]
when = when[s.index] + pd.to_timedelta(rng.integers(-30, 31, len(s)), unit="D")
when = when.clip(lower=pd.Timestamp(f"{SINCE}-01-01"))
price = pd.to_numeric(s.SALE_PRICE, errors="coerce").to_numpy()
price = np.where(price < 1_000, price, (price * rng.lognormal(0, 0.03, len(s))).round(-2)).astype(int)
qualified = (s.SALE_STATUS == "QUALIFIED").to_numpy()
# Some unqualified deeds are recorded at a nominal $10 (gifts, family transfers).
nominal = ~qualified & (rng.random(len(s)) < 0.12)
price = np.where(nominal, 10, price)

reid_txt = s.REID.map(new_id).to_numpy().astype(object)
# 3. Hand-keyed IDs: a few with a trailing space.
for i in rng.choice(len(s), 18, replace=False):
    reid_txt[i] = reid_txt[i] + " "
# 4. Sales of parcels since combined away: their IDs aren't in the parcel file any more.
for i in rng.choice(len(s), 6, replace=False):
    reid_txt[i] = str(900_000 + i)
pins = s.REID.map(dict(zip(p.REID, p.PIN_PLUS_EXT, strict=False))).fillna("").str[:10].to_numpy()
sales = pd.DataFrame(
    {
        "REID": reid_txt,
        # 5. The PIN as printed on the deed: hyphenated, unlike the parcel file's 7865743125-000.
        "PIN": [f"{x[:4]}-{x[4:6]}-{x[6:]}" if len(x) == 10 else "" for x in pins],
        "SALE_DATE": [f"{d.month}/{d.day}/{d.year} {d.hour}:{d.minute:02d}" for d in when],  # with a time
        "DEED_BOOK": s.DEED_BOOK.to_numpy(),
        "DEED_PAGE": s.DEED_PAGE.to_numpy(),
        "SALE_PRICE": price,
        "SALE_STATUS": s.SALE_STATUS.to_numpy(),  # QUALIFIED / UNQUALIFIED
        "SALE_TYPE": s.SALE_TYPE.fillna("").to_numpy(),  # IMPROVED / VACANT
    }
).sort_values(["DEED_BOOK", "DEED_PAGE"], key=lambda c: pd.to_numeric(c, errors="coerce"), kind="stable")

# 6. The same prices written the ways exports write them, one column each, to try the price checks on.
#    A separate random stream, so the columns above don't change.
fmt_rng = np.random.default_rng(1024)
v = sales["SALE_PRICE"].to_numpy()
price_blank = fmt_rng.random(len(v)) < 0.02  # some exports leave the price out
sales["PRICE_DOLLARS"] = [f"${x:,.2f}" for x in v]  # $250,000.00
sales["PRICE_COMMAS"] = [f"{x:,}" for x in v]  # 250,000
sales["PRICE_DECIMAL"] = [f"{x:.2f}" for x in v]  # 250000.00
sales["PRICE_PADDED"] = [f"$ {x:>12,.2f} " for x in v]  # fixed-width report: "$   250,000.00 "
sales["PRICE_EURO"] = [f"{x:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".") for x in v]  # 250.000,00
sales["PRICE_THOUSANDS"] = [f"{x / 1000:g}" for x in v]  # 250 (in $1,000s, as some summaries give it)
sales["PRICE_CENTS"] = [str(x * 100) for x in v]  # 25000000 (whole cents)
sales["PRICE_EXCEL"] = [f"{x:.2E}" if x >= 1_000_000 else str(x) for x in v]  # 1.25E+06: Excel's big numbers
sales["PRICE_SHORT"] = [f"${x / 1e6:.2f}M" if x >= 1e6 else f"${x / 1000:.0f}K" for x in v]  # $250K, $1.25M
sales["PRICE_MIXED"] = [  # hand-kept: a bit of everything, with blanks and placeholders
    "" if blank else fmt_rng.choice([f"${x:,}", f"{x:,}", str(x), f"${x:,.2f}", f"{x}.00"])
    for x, blank in zip(v, price_blank, strict=True)
]
for i in np.flatnonzero(fmt_rng.random(len(v)) < 0.01):
    sales.iloc[i, sales.columns.get_loc("PRICE_MIXED")] = fmt_rng.choice(["N/A", "-", "0", "$0.00", "TBD"])
sales["PRICE_NEGATIVE"] = [f"({x:,})" if x < 100 else f"{x:,}" for x in v]  # accounting: (10) for a $10 deed

# ---------- Map layers: Guilford's own, cut to the window ----------
zoning = layer("zoning")[["ZONING", "CLASSIFICATION", "geometry"]]
zoning["geometry"] = zoning.geometry.simplify(1.0)
zoning = zoning.to_crs(4326)  # 7. in degrees, unlike the parcels
lakes = layer("lakes")[["MAJORLAKES", "geometry"]]
streams = layer("streams")[["NAME", "geometry"]]
districts = layer("school_district")[["DISTRICT", "geometry"]]
cbd = layer("central_business_district")[["geometry"]].assign(NAME="Downtown Greensboro")
parks = layer("parks")[["name", "geometry"]]
universities = layer("universities")[["name", "geometry"]]
universities["geometry"] = universities.to_crs(2264).geometry.representative_point().to_crs(universities.crs)

# Flood zones: Guilford's FEMA maps aren't in the container, so bands along the real streams stand in. AE (1%
# annual chance) within 150 ft of a stream, X (0.2%) out to 400 ft: most parcels are in neither.
s2264 = streams.to_crs(2264).geometry.union_all()
ae = s2264.buffer(150)
flood = gpd.GeoDataFrame(
    {"FLD_ZONE": ["AE", "X"], "ZONE_SUBTY": ["1% ANNUAL CHANCE", "0.2% ANNUAL CHANCE"]},
    geometry=[ae, s2264.buffer(400).difference(ae)],
    crs=2264,
)

if IN.exists():
    shutil.rmtree(IN)
(IN / "geo").mkdir(parents=True)
parcels.to_parquet(IN / "geo" / "parcels.parquet")
zoning.to_file(IN / "geo" / "zoning.geojson", driver="GeoJSON")
lakes.to_file(IN / "geo" / "lakes.shp")
streams.to_file(IN / "geo" / "streams.shp")
districts.to_file(IN / "geo" / "school_districts.shp")
flood.to_file(IN / "geo" / "flood_zones.shp")
cbd.to_file(IN / "geo" / "cbd.gpkg", layer="cbd", driver="GPKG")
universities.to_file(IN / "geo" / "universities.shp")
parks.to_file(IN / "geo" / "parks.shp")
(IN / "geo" / "parks.prj").unlink()  # 8. a shapefile that lost its .prj: no coordinate system
buildings.to_csv(IN / "building.csv", index=False)
units.to_csv(IN / "condo_units.csv", index=False)
sales.to_csv(IN / "sales.csv", index=False)
print(
    f"{len(parcels):,} parcel shapes, {len(units):,} condo units without one, {len(buildings):,} building cards, "
    f"{len(sales):,} sales"
)

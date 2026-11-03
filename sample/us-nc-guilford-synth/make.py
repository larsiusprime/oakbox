"""Builds the Guilford sample county (see README.md) from a slice of Guilford County, NC's real data, altered and
with problems planted. Every price and assessed value comes from one known model of market value, fitted to
Guilford's own sales, so a model's values can be scored against the truth (answers/). Deterministic: same seed, same
files.

uv run python sample/us-nc-guilford-synth/make.py

The first run downloads Guilford's files (about 300 MB) from OpenAVMKit's public sample-locality container into
.cache/ beside this file; later runs reuse them.
"""

import json
import shutil
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

import deed_names

HERE = Path(__file__).parent
IN = HERE / "in"
ANSWERS = HERE / "answers"
CACHE = HERE / ".cache"
SOURCE = "https://landeconomics.blob.core.windows.net/localities-public/us/nc/guilford"
rng = np.random.default_rng(336)

# Downtown Greensboro north to Buffalo Lake, in NC State Plane (EPSG:2264, US feet): about 9,400 parcels, mostly
# single-family houses and condos, with 1,400 qualified house sales since 2018. Parcels are kept when their
# centre falls inside; map layers are cut to the window plus a margin.
X0, Y0, X1, Y1 = 1_760_000, 843_000, 1_772_000, 862_000
MARGIN = 3_000
# Every date in Guilford's data moves this many years later: the sales then run up to the end of 2025, so a 2026 tax
# year (valued 1 January 2026) has a year of sales before its valuation date, as a ratio study's study set needs.
LATER = 1
SINCE = 2015 + LATER
# The date the true values are for: the day after the last sale.
VALUATION = pd.Timestamp(f"{2025 + LATER}-01-01")
# The revaluation Guilford's own assessed values are from, moved with the rest.
REVAL = pd.Timestamp(f"{2022 + LATER}-01-01")
# How far a qualified sale's price strays from its true value (log scale): with a perfect model, a COD of about 8.
NOISE = 0.10


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

# Guilford's 2022 assessed values (dated REVAL here, with the rest): each parcel's share of land, and for parcels
# without a building card (shops, offices, vacant land), where the truth starts from (below). The published
# assessed values come from the truth.
land = pd.to_numeric(p.TOTAL_LAND_VALUE_ASSESSED, errors="coerce").fillna(0)
bldg = pd.to_numeric(p.TOTAL_BLDG_VALUE_ASSESSED, errors="coerce").fillna(0)
p["real_total"] = land + bldg
p["land_share"] = (land / (land + bldg)).where(land + bldg > 0, 1.0).clip(0.1, 1.0)
rng.lognormal(0, 0.04, n), rng.lognormal(0, 0.04, n)  # draws kept, so the ones after them don't change
lakes_2264 = layer("lakes").to_crs(2264).geometry.union_all()
p["d_lake"] = p.geometry.centroid.distance(lakes_2264).to_numpy()

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

# ---------- Building permits: made up, one row per permit, on the plain parcel ID ----------
# Renovations (alterations and additions) raise a house's true value for five years (below). Teardowns follow the
# sales. Its own random stream, so nothing else changes.
permit_rng = np.random.default_rng(4242)
KINDS = ["ALTERATION", "REROOF", "ADDITION", "ELECTRICAL", "NEW CONSTRUCTION", "DEMOLITION", "POOL"]
WEIGHTS = [0.32, 0.22, 0.14, 0.14, 0.09, 0.04, 0.05]
n_permits = 2_100
permit_ids = permit_rng.choice(p["reid"].dropna().to_numpy(), n_permits)
issued = pd.Timestamp(f"{2011 + LATER}-01-01") + pd.to_timedelta(permit_rng.integers(0, 15 * 365, n_permits), unit="D")
kinds = permit_rng.choice(KINDS, n_permits, p=WEIGHTS)


def time_index() -> pd.DataFrame:
    """The market's quarterly price index, as a county might publish one: slow growth for five years, a run-up for
    three, then flat. Every price follows it (below), so it's the true time adjustment."""
    rows, level = [], 100.0
    for year in range(SINCE, VALUATION.year):
        for q in range(1, 5):
            rows.append({"period": f"{year}-Q{q}", "index": round(level, 1)})
            level *= 1.008 if year < SINCE + 5 else 1.025 if year < SINCE + 8 else 1.0
    return pd.DataFrame(rows)


INDEX = time_index()
_mid = [pd.Period(x.replace("-", ""), freq="Q") for x in INDEX.period]
_mid_ns = np.array([(q.start_time + (q.end_time - q.start_time) / 2).value for q in _mid], dtype=float)


def market(dates) -> np.ndarray:
    """The index on each date, as a multiple of its level on the valuation date (between quarters, a straight line;
    before the first or after the last, flat)."""
    at = pd.DatetimeIndex(dates).asi8.astype(float)
    return np.interp(at, _mid_ns, INDEX["index"]) / np.interp(VALUATION.value, _mid_ns, INDEX["index"])


# ---------- The truth: every parcel's market value, from one known model ----------
# A house or condo's value is a log-linear hedonic model of what's in the files: heated area, land, quality (grade),
# % good (condition), baths, central air, house or condo, its neighbourhood; plus two effects planted, because a
# sample should have something to find: being near Buffalo Lake, and a renovation in the last five years. The
# coefficients are fitted to Guilford's own qualified sales in the window (quarter by quarter, neighbourhoods shrunk
# toward the average), then rounded: they're the model, written to answers/model.json.
LAKE = 0.12  # +12% on the shore, fading by 1/e every 1,000 ft
LAKE_FT = 1_000
RENO = 0.07  # +7% for five years after an alteration or addition permit
RENO_YEARS = 5


def _num(c: pd.Series) -> pd.Series:
    return pd.to_numeric(c, errors="coerce")


cards = buildings.assign(area=_num(buildings.HEATED_AREA))
card1 = cards.groupby("REID").first()
X = pd.DataFrame(index=card1.index)
X["log_area"] = np.log(cards.groupby("REID").area.sum().clip(lower=200))
X["grade"] = _num(card1.GRADE_SCORE).fillna(_num(card1.GRADE_SCORE).median())
X["log_good"] = np.log(1 - _num(card1.CONDITION_SCORE).fillna(0.1).clip(0, 0.9))
X["baths"] = _num(card1.BATH_FULL).fillna(0) + 0.5 * _num(card1.BATH_HALF).fillna(0)
X["air"] = card1.AIR_COND.fillna("NONE").ne("NONE").astype(float)
X["condo"] = card1.BLDG_TYPE.fillna("").str.startswith("03").astype(float)
site = p.drop_duplicates("reid").set_index("reid")
X["log_acres"] = np.log(_num(site.TOTAL_ACRES).reindex(X.index).fillna(0).clip(lower=0.01))
X["nbhd"] = text(site.NEIGHBORHOOD).reindex(X.index).fillna("")
X["lake"] = np.exp(-site.d_lake.reindex(X.index).fillna(1e9) / LAKE_FT)
HEDONIC = ["log_area", "log_acres", "grade", "log_good", "baths", "air", "condo"]

# The fit: Guilford's own prices (before any change), single-parcel qualified sales of a house or condo since SINCE.
real_sales = pd.read_csv(
    fetch("sale.csv"),
    dtype=str,
    usecols=["REID", "SALE_DATE", "SALE_PRICE", "SALE_STATUS", "SALE_TYPE", "DEED_BOOK", "DEED_PAGE"],
)
real_sales = real_sales[real_sales.REID.isin(new_id)].copy()
real_sales["when"] = pd.to_datetime(real_sales.SALE_DATE, format="%m/%d/%Y %H:%M") + pd.DateOffset(years=LATER)
real_sales = real_sales[real_sales.when.dt.year >= SINCE].copy()
real_sales["SALE_DATE"] = [f"{d.month}/{d.day}/{d.year} {d.hour}:{d.minute:02d}" for d in real_sales.when]
deed_of = real_sales.DEED_BOOK.fillna("") + "/" + real_sales.DEED_PAGE.fillna("") + "/" + real_sales.SALE_DATE
fit = real_sales[
    (real_sales.SALE_STATUS == "QUALIFIED")
    & (real_sales.SALE_TYPE == "IMPROVED")
    & deed_of.map(deed_of.value_counts()).eq(1)
].assign(reid=lambda d: d.REID.map(new_id), price=lambda d: _num(d.SALE_PRICE))
fit = fit[fit.reid.isin(X.index) & (fit.price > 20_000)]
fit = fit.join(X, on="reid")
quarters = fit.when.dt.to_period("Q").astype(str)
nbhds = sorted(fit.nbhd.unique())
design = np.column_stack(
    [
        fit[HEDONIC].to_numpy(float),
        pd.get_dummies(quarters).iloc[:, 1:].to_numpy(float),  # the first quarter is the base
        pd.get_dummies(pd.Categorical(fit.nbhd, categories=nbhds)).to_numpy(float),  # one each, no intercept
    ]
)
beta = np.linalg.lstsq(design, np.log(fit.price.to_numpy()), rcond=None)[0]
coef = {k: round(float(b), 3) for k, b in zip(HEDONIC, beta, strict=False)}
q_last = pd.get_dummies(quarters).columns[-1]
q_effect = float(beta[len(HEDONIC) + pd.get_dummies(quarters).columns.get_loc(q_last) - 1])
raw_nb = pd.Series(beta[-len(nbhds) :], index=nbhds) + q_effect  # in the last quarter's prices
counts = fit.nbhd.value_counts()
centre = float(np.average(raw_nb, weights=counts.reindex(nbhds)))
SHRINK = 8  # a neighbourhood with 8 sales moves halfway from the average to its own figure
nb_effect = centre + (raw_nb - centre) * counts.reindex(nbhds) / (counts.reindex(nbhds) + SHRINK)
# The market moved between the last quarter's prices and the valuation date as the index did; the intercept is the
# value at the valuation date.
intercept = round(centre - float(np.log(market([fit.when.max()])[0])), 3)
nb_effect = (nb_effect - centre).round(3)
# Neighbourhoods with no such sale: the average of the three nearest that have one.
all_nb = text(site.NEIGHBORHOOD)
nb_xy = site.geometry.centroid.groupby(all_nb.to_numpy()).agg(lambda g: (g.x.mean(), g.y.mean()))
known = [n for n in nb_effect.index if n in nb_xy.index]
for name in nb_xy.index.difference(nb_effect.index):
    x, y = nb_xy[name]
    near = sorted(known, key=lambda k: (nb_xy[k][0] - x) ** 2 + (nb_xy[k][1] - y) ** 2)[:3]
    nb_effect[name] = round(float(nb_effect[near].mean()), 3)

base = intercept + sum(coef[k] * X[k] for k in HEDONIC) + X.nbhd.map(nb_effect).fillna(0) + LAKE * X.lake
reno_permits = pd.DataFrame(
    {"reid": permit_ids, "issued": issued, "reno": np.isin(kinds, ["ALTERATION", "ADDITION"])}
).query("reno")


def renovated(reids, dates) -> np.ndarray:
    """Whether each parcel had an alteration or addition permit in the five years up to each date."""
    d = pd.DataFrame({"reid": list(reids), "at": pd.DatetimeIndex(dates)}).reset_index()
    m = d.merge(reno_permits, on="reid")
    m = m[(m.issued <= m["at"]) & (m.issued > m["at"] - pd.DateOffset(years=RENO_YEARS))]
    return d["index"].isin(m["index"]).to_numpy()


# Parcels without a building card (shops, offices, land): Guilford's own assessed value (as of REVAL), brought to the
# valuation date by the index. Not a model: there's too little to fit one on, and they're not what the sample is for.
anchor = (site.real_total * market([REVAL])[0] ** -1).where(site.real_total > 0)
anchor = anchor.drop(index=X.index, errors="ignore")


def true_value(reids, dates, land_only=None) -> np.ndarray:
    """Each parcel's true market value on each date (blank: no way to tell), or its land's when land_only."""
    reids = pd.Series(list(reids))
    at = pd.DatetimeIndex(dates)
    log_v = reids.map(base).to_numpy() + RENO * renovated(reids, at)
    v = np.where(np.isnan(log_v), reids.map(anchor).to_numpy(), np.exp(log_v)) * market(at)
    if land_only is not None:
        v = np.where(land_only, v * reids.map(site.land_share).fillna(1.0).to_numpy(), v)
    return v


truth_rng = np.random.default_rng(5150)  # its own stream: the prices and assessed values, from the truth
ids = site.index.dropna()
truth = pd.DataFrame({"reid": ids})
truth["value"] = true_value(ids, [VALUATION] * len(ids))
truth["land"] = truth.value * truth.reid.map(site.land_share).fillna(1.0).to_numpy()
truth = truth.set_index("reid")

# The roll's assessed values: the revaluation's (REVAL), from the truth, with the faults a real roll has. Valued at
# 97% of that market, regressive (a parcel worth twice the median assessed 8% lower than it should be), and
# about 10% off either way.
v2022 = truth.value * market([REVAL])[0]
median = float(v2022.median())
assessed = (v2022 * 0.97 * (v2022 / median) ** -0.12 * truth_rng.lognormal(0, 0.10, len(v2022))).round(-2)
assessed_land = (assessed * site.land_share.reindex(truth.index)).round(-2)
assessed_bldg = (assessed - assessed_land).clip(lower=0)


def roll(frame: pd.DataFrame, plain_ids: pd.Series) -> None:
    """Puts the assessed values on the parcel or condo-unit file, by plain parcel ID."""
    frame["TOTAL_LAND_VALUE_ASSESSED"] = plain_ids.map(assessed_land).fillna(0).astype(int).to_numpy()
    frame["TOTAL_BLDG_VALUE_ASSESSED"] = plain_ids.map(assessed_bldg).fillna(0).astype(int).to_numpy()
    frame["TOTAL_PROP_VALUE"] = frame.TOTAL_LAND_VALUE_ASSESSED + frame.TOTAL_BLDG_VALUE_ASSESSED


roll(parcels, parcels.GDV_REID.fillna("").str.lstrip("0"))
roll(units, units.REID)
parcels = parcels[[*[c for c in parcels.columns if c != "geometry"], "geometry"]]

# ---------- Sales since SINCE: the real deeds, priced from the truth. No sale ID. ----------
s = real_sales.drop(columns="when")
when = pd.to_datetime(s.SALE_DATE, format="%m/%d/%Y %H:%M")
# Several sales on one deed (one sale of several parcels) move together, keeping its date and price the same: that
# is how sales scrutiny finds them.
deed = (s.DEED_BOOK.fillna("") + "/" + s.DEED_PAGE.fillna("") + "/" + s.SALE_DATE).to_numpy()
first = pd.Series(np.arange(len(s))).groupby(deed).transform("first").to_numpy()
shift = rng.integers(-30, 31, len(s))[first]
when = when + pd.to_timedelta(shift, unit="D")
when = when.clip(lower=pd.Timestamp(f"{SINCE}-01-01"))
real_price = _num(s.SALE_PRICE).to_numpy()
rng.lognormal(0, 0.03, len(s))  # a draw kept, so the ones after it don't change
qualified = (s.SALE_STATUS == "QUALIFIED").to_numpy()
vacant = (s.SALE_TYPE == "VACANT").to_numpy()
# Each sale's true value on its date (a vacant sale, the land's); a deed of several parcels sold them all at once.
reids = s.REID.map(new_id)
value = true_value(reids, when, land_only=vacant)
deed_value = pd.Series(value).groupby(first).transform("sum").to_numpy()
# A qualified sale strays from it by NOISE; one of a parcel with no building card (no model, above) by twice that.
# An unqualified sale is usually under (a family sale, a quick sale), and further off.
modeled = reids.isin(X.index).to_numpy()
spread = np.where(qualified, np.where(modeled, NOISE, 2 * NOISE), 0.25)
centre_off = np.where(qualified, 0.0, -0.15)
draw = truth_rng.normal(0, 1, len(s))[first]
deed_price = deed_value * np.exp(centre_off + spread * draw)
# On a deed of several parcels, each sale has the whole price where Guilford's did, otherwise its share.
same = pd.Series(real_price).groupby(first).transform(lambda x: x.nunique() == 1).to_numpy()
price = np.where(same | (deed_value == value), deed_price, deed_price * value / deed_value)
# No true value (a parcel no model covers, with no assessed value): Guilford's own price.
price = np.where(np.isnan(price), real_price, price)
price = np.where(real_price < 1_000, real_price, np.round(price, -2)).astype(int)
# Some unqualified deeds are recorded at a nominal $10 (gifts, family transfers).
nominal = ~qualified & (rng.random(len(s)) < 0.12)[first]
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

# ---------- Teardowns, and the permits file ----------
# 15. Teardowns: 40 improved, qualified sales are followed by a demolition permit within a year, so the sale was
#     really of the land.
torn = sales[(sales.SALE_STATUS == "QUALIFIED") & (sales.SALE_TYPE == "IMPROVED") & sales.REID.isin(X.index)]
torn = torn.iloc[permit_rng.choice(len(torn), 40, replace=False)]
torn_when = pd.to_datetime(torn.SALE_DATE, format="%m/%d/%Y %H:%M") + pd.to_timedelta(
    permit_rng.integers(20, 330, len(torn)), unit="D"
)
# The buyer paid for the land: its true value on the day, give or take NOISE.
torn_sold = pd.to_datetime(torn.SALE_DATE, format="%m/%d/%Y %H:%M")
torn_land = true_value(torn.REID, torn_sold, land_only=np.ones(len(torn), bool))
sales.loc[torn.index, "SALE_PRICE"] = np.round(torn_land * truth_rng.lognormal(0, NOISE, len(torn)), -2).astype(int)
permits = pd.DataFrame(
    {
        "REID": [*permit_ids, *torn.REID],
        "ISSUE_DATE": [d.strftime("%Y-%m-%d") for d in [*issued, *torn_when]],
        "WORK_CLASS": [*kinds, *["DEMOLITION"] * len(torn)],
    }
).sort_values("ISSUE_DATE", kind="stable")
permits.insert(0, "PERMIT_NO", [f"BP-{d[:4]}-{i:05d}" for i, d in enumerate(permits.ISSUE_DATE)])
permits["VALUATION"] = (permit_rng.lognormal(9.5, 1.0, len(permits)) // 100 * 100).astype(int)

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
deed_names.add(sales).to_csv(IN / "sales.csv", index=False)  # 16. buyers and sellers (GRANTOR, GRANTEE)
permits.to_csv(IN / "permits.csv", index=False)

# The answers: kept out of in/, so they're never loaded by mistake. Each parcel's true value on the valuation date
# (by plain parcel ID, condo units too), and the model that made every price.
if ANSWERS.exists():
    shutil.rmtree(ANSWERS)
ANSWERS.mkdir()
pd.DataFrame(
    {
        "REID": truth.index,
        "true_market_value": truth.value.round(-2).astype("Int64").to_numpy(),
        "true_land_value": truth.land.round(-2).astype("Int64").to_numpy(),
        "how": np.where(truth.index.isin(X.index), "model", np.where(truth.value.notna(), "assessed", "")),
    }
).sort_values("REID", key=lambda c: pd.to_numeric(c)).to_csv(ANSWERS / "true_values.csv", index=False)
(ANSWERS / "model.json").write_text(
    json.dumps(
        {
            "valuation_date": VALUATION.date().isoformat(),
            "log_value": "intercept + sum(coefficient * variable) + neighbourhood + lake * exp(-feet / lake_feet) "
            "+ renovation * (alteration or addition permit in the last renovation_years)",
            "intercept": intercept,
            "coefficients": coef,
            "variables": {
                "log_area": "log of HEATED_AREA, every card summed",
                "log_acres": "log of TOTAL_ACRES (0.01 at least)",
                "grade": "GRADE_SCORE (card 1)",
                "log_good": "log(1 - CONDITION_SCORE) (card 1)",
                "baths": "BATH_FULL + BATH_HALF / 2 (card 1)",
                "air": "1 with central air (AIR_COND not NONE)",
                "condo": "1 for a condo (BLDG_TYPE 03-...)",
            },
            "lake": LAKE,
            "lake_feet": LAKE_FT,
            "renovation": RENO,
            "renovation_years": RENO_YEARS,
            "neighbourhood": nb_effect.sort_index().to_dict(),
            "time": "in/time_adjustment_index.csv, linear between quarter midpoints",
            "noise": {
                "qualified": NOISE,
                "qualified_no_card": 2 * NOISE,
                "unqualified": 0.25,
                "unqualified_mean": -0.15,
            },
            "assessed": {"revaluation": REVAL.date().isoformat(), "level": 0.97, "regressivity": -0.12, "noise": 0.10},
            "no_card": "parcels with no building card: Guilford's assessed value at the revaluation, "
            "brought to the valuation date",
        },
        indent=1,
    ),
    encoding="utf-8",
)


INDEX.to_csv(IN / "time_adjustment_index.csv", index=False)
# The same with problems planted: a period that isn't one, a quarter twice, a negative and a missing level.
(IN / "time_adjustment_index_broken.csv").write_text(
    "period,index\n2015-Q1,100\n2015-Q2,100.8\nspring 2015,101.2\n2015-Q3,-4\n2015-Q3,102\n2015-Q4,n/a\n",
    encoding="utf-8",
)
print(
    f"{len(parcels):,} parcel shapes, {len(units):,} condo units without one, {len(buildings):,} building cards, "
    f"{len(sales):,} sales, {len(permits):,} permits"
)

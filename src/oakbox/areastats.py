"""Per area statistics: OpenAVMKit's area statistics, as OAK box offers it (SPEC §3.12.3).

Each parcel gets its area's figures (the median sale price of its census tract, the median finished area of its
neighbourhood) as variables to model with: the cousin of Spatial average statistics (spatiallag.py), by named areas
instead of the nearest. Worked out as each run starts, after the sales are split: OpenAVMKit takes the price figures
from training sales only. Off to start.

Variables are offered under stable names (`area_stat_<location>_sale_price…`) and written as OpenAVMKit names them
(after the price it models: `sale_price_time_adj` when Check sales adjusts), as the nearby averages are.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import fields
from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    from oakbox.projects import Project

PREFIX = "area_stat_"
Stat = Literal["median", "mean", "std", "p25", "p75", "min", "max"]
STATS: tuple[Stat, ...] = ("median", "mean", "std", "p25", "p75", "min", "max")
RowId = Literal["price", "price_impr", "price_vacant_land", "sales", "finished", "land", "age", "quality", "condition"]
SALES_ROWS: tuple[RowId, ...] = ("price", "price_impr", "price_vacant_land", "sales")
PARCEL_ROWS: tuple[RowId, ...] = ("finished", "land", "age", "quality", "condition")


class AreaState(BaseModel):
    """Per area statistics: off to start; which figures, by which location, of which statistics."""

    on: bool = False
    stats: list[Stat] = Field(default_factory=lambda: ["median"], description="The statistics of each figure.")
    min_count: int = Field(
        default=5, ge=1, le=1000, description="An area with fewer sales (prices) or parcels has that figure blank."
    )
    ticks: dict[str, list[RowId]] | None = Field(
        default=None, description="Location field -> the figures worked out by it; None: as proposed (proposed)."
    )


def row_field(row: RowId, unit: str) -> str | None:
    """The field OpenAVMKit summarizes for a row, by its stable name (the number of sales is a count, no field)."""
    return {
        "price": "sale_price",
        "price_impr": f"sale_price_impr_{unit}",
        "price_vacant_land": f"sale_price_vacant_land_{unit}",
        "finished": f"bldg_area_finished_{unit}",
        "land": f"land_area_{unit}",
        "age": "bldg_age_years",
        "quality": "bldg_quality_num",
        "condition": "bldg_condition_num",
    }.get(row)


def _unit(project: Project) -> str:
    return "sqft" if project.units == "imperial" else "sqm"


def rows(project: Project, columns: set[str]) -> list[RowId]:
    """The figures there can be: the sales' always (prices), the parcels' whose field the data has."""
    u = _unit(project)
    out: list[RowId] = [*SALES_ROWS, *[r for r in PARCEL_ROWS if row_field(r, u) in columns]]
    return out


def variable(location: str, row: RowId, stat: Stat | None, unit: str) -> str:
    """A figure's variable, by its stable name (`area_stat_<location>_<field>_<stat>`, OpenAVMKit's)."""
    if row == "sales":
        return f"{PREFIX}{location}_sales_count"
    return f"{PREFIX}{location}_{row_field(row, unit)}_{stat}"


def actual(name: str, sale: str) -> str:
    """A figure's variable as OpenAVMKit writes it: the price figures carry the price field's name."""
    if sale == "sale_price" or not name.startswith(PREFIX) or "_sale_price" not in name:
        return name
    return name.replace("_sale_price", f"_{sale}", 1)


def stable(sup, sale: str):
    """The price figures under their stable names too (a copy of OpenAVMKit's columns), as variables are offered."""
    if sale == "sale_price":
        return sup
    for df in (sup.sales, sup.universe):
        for c in [c for c in df.columns if c.startswith(PREFIX) and f"_{sale}" in c]:
            df[c.replace(f"_{sale}", "_sale_price", 1)] = df[c]
    return sup


# ---------- The areas: how many, and how many sales each ----------


class AreaCount(BaseModel):
    location: str
    name: str
    areas: int = Field(description="Distinct areas the parcels are in.")
    typical_sales: int = Field(description="Sales in the median area.")
    under: int = Field(description="Areas with fewer sales than the minimum: their price figures are blank.")
    under_names: list[str] = Field(description="Those areas, fewest sales first (up to 50).")
    parcels_under: int = Field(description="Parcels in those areas, or in none.")


_cache: dict[str, tuple[tuple, list[AreaCount]]] = {}


def counts(project_dir: Path, universe_path: Path, sales_path: Path, locations: list[str], min_count: int):
    """Each location's areas, from the prepared parcels and sales (every valid sale; a run takes training ones)."""
    import pandas as pd
    import pyarrow.parquet as pq

    stamp = (
        tuple(locations),
        min_count,
        universe_path.stat().st_mtime_ns,
        sales_path.stat().st_mtime_ns if sales_path.is_file() else 0,
    )
    hit = _cache.get(str(project_dir))
    if hit and hit[0] == stamp:
        return hit[1]
    have = set(pq.ParquetFile(universe_path).schema_arrow.names)
    locs = [x for x in locations if x in have]
    u = pd.read_parquet(universe_path, columns=["key", *locs])
    keys = pd.Series(dtype=str)
    if sales_path.is_file():
        s_cols = set(pq.ParquetFile(sales_path).schema_arrow.names)
        s = pd.read_parquet(sales_path, columns=["key", *[c for c in ("valid_sale",) if c in s_cols]])
        if "valid_sale" in s:
            s = s[s["valid_sale"].astype("boolean").fillna(False)]
        keys = cast("pd.Series", s["key"].astype(str))
    names = fields.names()
    out = []
    for loc in locs:
        area = cast("pd.Series", u.set_index(u["key"].astype(str))[loc])
        per_area = keys.map(area).dropna().astype(str).value_counts()
        every = area.dropna().astype(str)
        sold = cast("pd.Series", per_area.reindex(every.unique(), fill_value=0))
        under = cast("pd.Series", sold[sold < min_count]).sort_values(kind="stable")
        parcels_under = int(every.isin(list(under.index)).sum()) + int(area.isna().sum())
        out.append(
            AreaCount(
                location=loc,
                name=names.get(loc) or loc.replace("_", " ").capitalize(),
                areas=len(sold),
                typical_sales=int(sold.median()) if len(sold) else 0,
                under=len(under),
                under_names=[f"{a} ({n})" for a, n in under.head(50).items()],
                parcels_under=parcels_under,
            )
        )
    _cache[str(project_dir)] = (stamp, out)
    return out


def proposed(found: list[AreaCount], near: str | None, columns: set[str], project: Project) -> dict[str, list[RowId]]:
    """What's ticked to start: the sales' figures for the location Check sales uses and the next coarser one (fewer,
    bigger areas; vacant land prices there only, vacant sales being few); the parcels' for the first."""
    if not found:
        return {}
    by = {c.location: c for c in found}
    first = by.get(near or "") or found[0]
    coarser = max((c for c in found if c.areas < first.areas), key=lambda c: c.areas, default=None)
    parcel_rows: list[RowId] = [r for r in rows(project, columns) if r in PARCEL_ROWS]
    sales_rows: list[RowId] = ["price", "price_impr", "sales"]
    out: dict[str, list[RowId]] = {first.location: [*sales_rows, *parcel_rows]}
    if coarser is not None:
        out[coarser.location] = ["price", "price_impr", "price_vacant_land", "sales"]
    else:
        out[first.location].insert(2, "price_vacant_land")
    return out


def ticks(project: Project, found: list[AreaCount], columns: set[str]) -> dict[str, list[RowId]]:
    """The figures by location, as set or proposed, only for locations there and figures there can be."""
    have = {c.location for c in found}
    can = set(rows(project, columns))
    raw = project.model.area.ticks
    if raw is None:
        raw = proposed(found, project.clean.location, columns, project)
    return {loc: [r for r in rs if r in can] for loc, rs in raw.items() if loc in have}


def offered(project: Project, found: list[AreaCount], columns: set[str]) -> list[tuple[str, str, int, bool]]:
    """(variable, name, parcels it's blank for, whether it can be blank) of each figure ticked, by its stable name.
    The vacant land price can be blank in many more areas than the sales' count shows (vacant sales are few)."""
    u = _unit(project)
    a = project.model.area
    by = {c.location: c for c in found}
    out = []
    for loc, rs in ticks(project, found, columns).items():
        c = by[loc]
        wanted: list[RowId] = [x for x in rows(project, columns) if x in rs]
        for r in wanted:
            row: RowId = r
            if row == "sales":
                out.append((variable(loc, row, None, u), f"{c.name} number of sales", 0, False))
                continue
            for st in a.stats:
                blank = c.parcels_under if row in SALES_ROWS else 0
                can_blank = blank > 0 or row == "price_vacant_land"
                out.append((variable(loc, row, st, u), name(c.name, row, st, u), blank, can_blank))
    return out


def name(location: str, row: RowId, stat: Stat, unit: str) -> str:
    """A figure's name: "Census tract median sale price", "Census tract sale price, spread"."""
    what = ROW_NAMES[row](unit)
    return f"{location} {stat} {what}" if stat in ("median", "mean") else f"{location} {what}, {STAT_NAMES[stat]}"


STAT_NAMES: dict[str, str] = {
    "median": "median",
    "mean": "mean",
    "std": "spread",
    "p25": "25th percentile",
    "p75": "75th percentile",
    "min": "smallest",
    "max": "largest",
}


def _area_word(u: str) -> str:
    return "sq ft" if u == "sqft" else "m²"


ROW_NAMES = {
    "price": lambda u: "sale price",
    "price_impr": lambda u: f"price per finished {_area_word(u)}",
    "price_vacant_land": lambda u: f"price per land {_area_word(u)}, vacant",
    "sales": lambda u: "number of sales",
    "finished": lambda u: "finished area",
    "land": lambda u: "land area",
    "age": lambda u: "building age",
    "quality": lambda u: "quality",
    "condition": lambda u: "condition",
}


def settings(project: Project, found: list[AreaCount], columns: set[str]) -> dict:
    """data.process.enrich.area_stats: the locations ticked, the fields summarized (a bare sale_price is OpenAVMKit's
    price and its per-area rates), the statistics, the minimum. Nothing when off or nothing ticked."""
    a = project.model.area
    if not a.on:
        return {}
    t = {loc: rs for loc, rs in ticks(project, found, columns).items() if rs}
    if not t:
        return {}
    u = _unit(project)
    every = {r for rs in t.values() for r in rs}
    flds = (["sale_price"] if every & {"price", "price_impr", "price_vacant_land"} else []) + [
        f for r in PARCEL_ROWS if r in every and (f := row_field(r, u))
    ]
    return {
        "locations": [c.location for c in found if c.location in t],
        "fields": flds,
        "stats": [s for s in STATS if s in a.stats] or ["median"],
        "min_count": a.min_count,
    }


def locations(project_dir: Path, columns: list[str] | set[str]) -> list[str]:
    """The location fields offered: Check sales' "near" ones that the prepared parcels have."""
    import pandas as pd

    from oakbox import clean

    return clean.location_fields(project_dir, pd.DataFrame(columns=pd.Index(list(columns))))


def found(project: Project, project_dir: Path, universe_path: Path, sales_path: Path, columns: list[str] | set[str]):
    """Each offered location's areas, under the project's minimum."""
    return counts(project_dir, universe_path, sales_path, locations(project_dir, columns), project.model.area.min_count)

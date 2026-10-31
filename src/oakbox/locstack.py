"""Location stacks (SPEC F9): the location fields a model reads, broadest first as shown, finest first as OpenAVMKit
takes them (`locations` on a Multi-MRA or Local area model). Multi-MRA fits a regression in each area of the
finest level with 15 or more sales, an area with fewer falling back to the level above it, and the whole model
group last; Local area takes each area's median price per area the same way.

A preview of a stack in a model group: per level, its areas, their median sales, the areas with enough sales, and
whether it nests in the level above it (each of its areas inside one of the level above's).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import Field

from oakbox import clean, fields
from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    import pandas as pd

# Sales an area needs for a regression of its own (OpenAVMKit's Multi-MRA min_sample_size).
ENOUGH = 15


class LocationField(BaseModel):
    field: str
    name: str


class Level(BaseModel):
    field: str
    name: str
    areas: int = Field(description="Its areas among the group's parcels.")
    median_sales: float = Field(description="Sales per area, the median.")
    enough: int = Field(description=f"Areas with {ENOUGH} or more sales.")
    split: int = Field(description="Its areas that span more than one area of the level above (0: it nests).")


class StackPreview(BaseModel):
    group: str
    sales: int
    levels: list[Level] = Field(description="Broadest first, as shown.")


def _paths(project_dir: Path) -> tuple[Path, Path]:
    look = project_dir / "out" / "look"
    return look / "2-clean-universe.parquet", look / "2-clean-sales.parquet"


@lru_cache(maxsize=4)
def _frame(universe: str, u_mtime: float, sales: str, s_mtime: float, wanted: tuple[str, ...]):
    """The universe's model group and location fields, with whether each parcel sold."""
    import pandas as pd
    import pyarrow.parquet as pq

    have = set(pq.ParquetFile(universe).schema_arrow.names)
    columns = ["key", "model_group", *[f for f in wanted if f in have]]
    df = pd.read_parquet(universe, columns=columns)
    keys = set(pd.read_parquet(sales, columns=["key"])["key"].astype(str)) if Path(sales).is_file() else set()
    df["sold"] = df["key"].astype(str).isin(list(keys))
    return df


def _labels(column) -> pd.Series:
    """A location field's areas as text, a blank one an area of its own."""
    return cast("pd.Series", column.astype("string")).fillna("(blank)")


def _sold(df, labels: pd.Series) -> pd.Series:
    """Sales per area."""
    return cast("pd.Series", df.groupby(labels, observed=True)["sold"].sum())


def offered(project_dir: Path) -> list[LocationField]:
    """The location fields the prepared universe has: the user's own, map layers', census areas."""
    import pandas as pd
    import pyarrow.parquet as pq

    universe, _ = _paths(project_dir)
    if not universe.is_file():
        return []
    columns = pq.ParquetFile(universe).schema_arrow.names
    names = fields.names()
    return [
        LocationField(field=f, name=names.get(f) or f)
        for f in clean.location_fields(project_dir, pd.DataFrame(columns=pd.Index(columns)))
    ]


def _group(project_dir: Path, group: str, wanted: list[str]):
    universe, sales = _paths(project_dir)
    if not universe.is_file():
        return None
    df = _frame(
        str(universe),
        universe.stat().st_mtime,
        str(sales),
        sales.stat().st_mtime if sales.is_file() else 0.0,
        tuple(sorted(wanted)),
    )
    return df[df["model_group"].astype(str).eq(group)]


def preview(project_dir: Path, group: str, broadest_first: list[str]) -> StackPreview:
    names = {x.field: x.name for x in offered(project_dir)}
    df = _group(project_dir, group, list(names))
    if df is None:
        raise LookupError("Prepare the fields first: the stack is read from what it writes.")
    levels: list[Level] = []
    above: str | None = None
    for f in broadest_first:
        if f not in df.columns:
            continue
        areas = _labels(df[f])
        sold = _sold(df, areas)
        split = 0
        if above is not None:
            parents = cast("pd.Series", _labels(df[above]).groupby(areas, observed=True).nunique())
            split = int((parents > 1).sum())
        levels.append(
            Level(
                field=f,
                name=names.get(f, f),
                areas=len(sold),
                median_sales=float(sold.median()) if len(sold) else 0.0,
                enough=int((sold >= ENOUGH).sum()),
                split=split,
            )
        )
        above = f
    return StackPreview(group=group, sales=int(df["sold"].sum()), levels=levels)


def proposed(project_dir: Path, group: str) -> list[str]:
    """A group's stack unless told otherwise, finest first (as written): every location field with more than one
    area in the group and at least two areas with enough sales for a regression of their own (one would be the whole
    group again), broader (fewer areas) above finer."""
    names = [x.field for x in offered(project_dir)]
    df = _group(project_dir, group, names)
    if df is None:
        return []
    kept: list[tuple[int, str]] = []
    for f in names:
        if f not in df.columns:
            continue
        sold = _sold(df, _labels(df[f]))
        if int((sold >= ENOUGH).sum()) >= 2:
            kept.append((len(sold), f))
    return [f for _, f in sorted(kept, reverse=True)]

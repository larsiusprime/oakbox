"""The main sales file's columns that only it has (SPEC F3d Sales as sold; Outliers, 2026-11-08).

A column describing the sale or the property as sold that no parcel file has (Guilford's REMODELED, SALE_TYPE,
DEED_TYPE) can't be a model variable: a model values every parcel, and parcels don't have it. It can still decide
which sales are valid (a rule on Valid sale), and it's context when a sale looks wrong (Outliers). Left out: columns
already loaded for a field, the ones that mirror a characteristic (the same name as a parcel column, or a name the
field dictionary knows: Sales as sold's), blank or one-valued ones, and ones nearly unique per row (IDs, deed pages,
links).
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from oakbox.datafiles import BaseModel, DataFile
from oakbox.projects import Project
from oakbox.wizard.base import normalized
from oakbox.wizard.checks import _names
from oakbox.wizard.files import Files, dictionary_by_key, file_stamp, sales_file, values_of

TOP = 4  # most common values shown
NEARLY_UNIQUE = 0.9  # distinct values at least this share of the rows with one: an ID or a link, not a description


class SalesOnlyColumn(BaseModel):
    column: str
    have: int = Field(description="Sales with a value in it.")
    rows: int
    distinct: int
    top: list[list[str]] = Field(description="[value, count], the most common first.")
    in_rule: bool = Field(description="A valid or vacant sale rule tests it already.")


class SalesOnlyView(BaseModel):
    sales_file: str | None
    filename: str | None
    columns: list[SalesOnlyColumn]


def _excluded(project: Project, files: Files, sales: DataFile) -> set[str]:
    """The sales file's columns that aren't only its own: loaded for a field, or mirroring a parcel column."""
    out = {spec[0] for spec in sales.load.values() if spec}
    parcel_cols = {normalized(c.name) for f in project.files if f.holds == "parcels" for c in files.columns(f.name)}
    known = {n for d in dictionary_by_key().values() for n in _names(d)}
    for c in files.columns(sales.name):
        if normalized(c.name) in parcel_cols or normalized(c.name) in known:
            out.add(c.name)
    out.update(project.wizard.as_sold.values())
    return out


@lru_cache(maxsize=64)
def _summary(stamp: tuple[str, float, int], layer: str | None, column: str) -> tuple[int, int, int, tuple]:
    values = values_of(stamp, layer, column)
    counts = Counter(v for v in values if v)
    have = sum(counts.values())
    top = tuple((v, n) for v, n in counts.most_common(TOP))
    return have, len(values), len(counts), top


def columns(project: Project, in_dir: Path) -> list[SalesOnlyColumn]:
    files = Files(project, in_dir)
    sales = sales_file(project)
    if sales is None or sales.name not in files.preview:
        return []
    skip = _excluded(project, files, sales)
    ruled = {c.column for r in sales.rules.values() for c in r.conditions}
    stamp = file_stamp(files.in_dir / sales.filename)
    out = []
    for c in files.columns(sales.name):
        if c.name in skip:
            continue
        have, rows, distinct, top = _summary(stamp, sales.layer, c.name)
        if distinct < 2 or (have > 50 and distinct >= NEARLY_UNIQUE * have):  # one value, or an ID/link
            continue
        out.append(
            SalesOnlyColumn(
                column=c.name,
                have=have,
                rows=rows,
                distinct=distinct,
                top=[[v, str(n)] for v, n in top],
                in_rule=c.name in ruled,
            )
        )
    return out


def view(project: Project, in_dir: Path) -> SalesOnlyView:
    sales = sales_file(project)
    return SalesOnlyView(
        sales_file=sales.name if sales else None,
        filename=sales.filename if sales else None,
        columns=columns(project, in_dir),
    )


@lru_cache(maxsize=8)
def _rows_by_sale(
    stamp: tuple[str, float, int], layer: str | None, date_column: str, fmt: str | None, parcels: tuple[str, ...]
) -> dict[tuple[str, str], int]:
    """(parcel, sale date as YYYY-MM-DD) -> the sales file's first row for it."""
    import pandas as pd

    raw = values_of(stamp, layer, date_column)
    dates = pd.to_datetime(pd.Series(raw), format=fmt or None, errors="coerce")
    out: dict[tuple[str, str], int] = {}
    for i, (p, d) in enumerate(zip(parcels, dates, strict=False)):
        if p and not pd.isna(d):
            out.setdefault((p, d.strftime("%Y-%m-%d")), i)
    return out


def context(project: Project, in_dir: Path, parcel: str, date: str) -> list[list[str]]:
    """A sale's own values in the columns only the sales file has: [column, value], blanks left out. The sale is
    found by its parcel and date (as the run makes its key_sale)."""
    files = Files(project, in_dir)
    sales = sales_file(project)
    if sales is None or sales.name not in files.preview or "sale_date" not in sales.load:
        return []
    spec = sales.load["sale_date"]
    stamp = file_stamp(files.in_dir / sales.filename)
    fmt = spec[2] if len(spec) > 2 else None
    index = _rows_by_sale(stamp, sales.layer, spec[0], fmt, tuple(files.parcel_ids(sales.name)))
    row = index.get((parcel, date[:10]))
    if row is None:
        return []
    out = []
    for c in columns(project, in_dir):
        v = values_of(stamp, sales.layer, c.column)[row]
        if v:
            out.append([c.column, v])
    return out

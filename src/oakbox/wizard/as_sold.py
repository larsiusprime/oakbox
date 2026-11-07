"""Data › Sales as sold (SPEC §3.0 F3d, 2026-11-07): the main sales file's columns that describe the property, beside
the parcel fields they mirror.

A sale should be described as the property was when it sold (it may have changed since): those are what the models
learn from. Parcels are valued on what they are now: the parcel files. Where a sale has no characteristics of its own,
OpenAVMKit fills them in from its parcel today (it hydrates the sales): an assumption that the parcel hasn't changed.

For each characteristic loaded from a parcel file, the sales file's column that mirrors it: the same column name, a
name the field dictionary knows, else a column whose values agree with today's on the same parcels for most sales (an
area tried in each unit: TOTAL_ACREAGE in acres where today's is sq ft). Checked against today's value on the same
parcels, in today's unit: how many sales have one, how many differ, and which.

The user's choice per field (`project.wizard.as_sold`): the sale's (its column loaded into the sales file, read as the
parcel's is: number format, scale; an area in its own unit) or today's (nothing loaded). Until chosen, today's:
nothing changes silently; the step, and each field's At the sale box, suggests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import AREA_FIELDS, SQFT_PER, AreaUnit, BaseModel, DataFile, guess_area_unit
from oakbox.projects import Project
from oakbox.wizard.base import CHARACTERISTIC_STEPS, RENAMED, STEPS, normalized
from oakbox.wizard.checks import _names
from oakbox.wizard.files import Files, dictionary_by_key, file_stamp, sales_file, values_of

SAME_ENOUGH = 0.99  # this share the same as today's: a snapshot exported with the sales, not history
WRITTEN_DIFFERENTLY = 0.2  # under this share of the sale's values among today's: written another way
EXAMPLES = 3
DIFFS = 50  # the sales that differ, listed (See them)
BY_VALUES = 0.5  # a column found by its values: the same as today's for at least this share
SAMPLE = 4000  # sales compared when looking for a column by its values


def characteristic_keys() -> list[str]:
    return [k for s in STEPS if s.key in CHARACTERISTIC_STEPS for k in (*s.fields, *s.more)]


class AsSoldDiff(BaseModel):
    parcel: str
    date: str = Field(description="The sale's date as written ('' if no date is loaded).")
    sold: str
    today: str


class AsSoldRow(BaseModel):
    key: str
    name: str
    parcel_file: str = Field(description="The parcel file it's loaded from (today's).")
    parcel_column: str
    column: str | None = Field(
        description="The sales file's column: chosen, else the one that mirrors it; None: none found."
    )
    found: bool = Field(description="The column was found (not chosen by hand).")
    how: Literal["name", "known", "values"] | None = Field(
        default=None, description="How it was found: the parcel's column name, a name it's known by, its values."
    )
    unit: AreaUnit | None = Field(default=None, description="An area: the unit the sales file's column is in.")
    today_unit: AreaUnit | None = Field(default=None, description="An area: the unit today's column is in.")
    choice: Literal["sale", "today"] | None = Field(description="The user's; None: not chosen (today's is used).")
    suggest: Literal["sale", "today"] | None = Field(
        description="What the figures suggest: today's when they're the same; None: written another way."
    )
    sales: int = Field(description="Sales on a parcel.")
    have: int = Field(description="Of them, with a value in the column.")
    compared: int = Field(description="Of those, on a parcel with today's value too.")
    same: int = Field(description="Of those, the same as today's.")
    examples: list[list[str]] = Field(description="[as sold, today] where they differ.")
    diffs: list[AsSoldDiff] = Field(default_factory=list, description="The sales that differ (the first 50).")
    written_differently: bool = Field(description="Its values aren't written as today's are (another code).")


class AsSoldView(BaseModel):
    sales_file: str | None
    filename: str | None = Field(default=None, description="The sales file's own name (sale.csv).")
    columns: list[str] = Field(description="The sales file's columns, to choose from.")
    rows: list[AsSoldRow]


def _parcel_source(project: Project, key: str) -> DataFile | None:
    return next(
        (f for f in project.files if key in f.load and f.holds == "parcels" and key not in f.rules),
        None,
    )


def _found(files: Files, sales: DataFile, key: str, parcel_column: str, taken: set[str]) -> tuple[str, str] | None:
    """The sales file's column that mirrors the field by name: the parcel's own column name, else a name it's known
    by. (column, "name" | "known")."""
    d = dictionary_by_key()[key]
    names = _names(d)
    cols = [c.name for c in files.columns(sales.name) if c.name not in taken]
    same = next((c for c in cols if normalized(c) == normalized(parcel_column)), None)
    if same:
        return same, "name"
    known = next((c for c in cols if normalized(c) in names), None)
    return (known, "known") if known else None


def _by_values(
    files: Files, sales: DataFile, key: str, src: DataFile, taken: set[str], only: str | None = None
) -> tuple[str, AreaUnit | None] | None:
    """Nothing by name: the sales file's column that agrees with today's for most sales on the same parcels (an area
    in whichever unit agrees). (column, its unit)."""
    from oakbox.wizard.quality import _by_parcel

    numeric = _numeric(key)
    today = _by_parcel(files, src, src.load[key][0])
    if not today:
        return None
    parcels = files.parcel_ids(sales.name)
    stamp = file_stamp(files.in_dir / sales.filename)
    units: list[AreaUnit | None] = list(SQFT_PER) if key in AREA_FIELDS else [None]  # type: ignore[list-item]
    today_unit = src.area_units.get(key, "sqft") if key in AREA_FIELDS else None
    best: tuple[float, str, AreaUnit | None] | None = None
    for c in files.columns(sales.name):
        if c.name in taken or (only is not None and c.name != only):
            continue
        sold = values_of(stamp, sales.layer, c.name)
        pairs = [(v, today[p]) for p, v in zip(parcels, sold, strict=False) if p and v and p in today][:SAMPLE]
        if len(pairs) < 20 or (numeric and _num(pairs[0][0]) is None):
            continue
        for u in units:
            f = SQFT_PER[u] / SQFT_PER[today_unit] if u and today_unit else 1.0
            share = sum(_same(v, t, numeric, f) for v, t in pairs) / len(pairs)
            if share >= BY_VALUES and (best is None or share > best[0]):
                best = (share, c.name, u)
    return (best[1], best[2]) if best else None


def _numeric(key: str) -> bool:
    return dictionary_by_key()[key].type in ("number", "float", "integer", "int") or key in AREA_FIELDS


def _num(v: str) -> float | None:
    try:
        x = float(v.replace(",", ""))
    except ValueError:
        return None
    return x if x == x else None


def _same(a: str, b: str, numeric: bool, factor: float = 1.0) -> bool:
    """As sold against today's; `factor` turns the sale's unit into today's (acres to sq ft: 43,560)."""
    if numeric:
        x, y = _num(a), _num(b)
        if x is not None and y is not None:
            x *= factor
            return abs(x - y) <= max(0.5, 0.005 * abs(y), 0.01 * factor)
    return a.strip().upper() == b.strip().upper()


def _compare(
    project: Project, files: Files, sales: DataFile, key: str, column: str, src: DataFile, unit: AreaUnit | None
) -> dict:
    """The sale's column against today's value of each sale's parcel, in today's unit."""
    from oakbox.wizard.quality import _by_parcel

    numeric = _numeric(key)
    today_unit = src.area_units.get(key, "sqft") if key in AREA_FIELDS else None
    factor = SQFT_PER[unit] / SQFT_PER[today_unit] if unit and today_unit else 1.0
    today = _by_parcel(files, src, src.load[key][0])
    stamp = file_stamp(files.in_dir / sales.filename)
    sold = values_of(stamp, sales.layer, column)
    date_col = sales.load.get("sale_date", [None])[0]
    dates = values_of(stamp, sales.layer, date_col) if date_col else ()
    parcels = files.parcel_ids(sales.name)
    n = have = compared = same = 0
    examples: list[list[str]] = []
    diffs: list[AsSoldDiff] = []
    mine_values: set[str] = set()
    for i, (p, v) in enumerate(zip(parcels, sold, strict=False)):
        if not p:
            continue
        n += 1
        if not v or not v.strip():
            continue
        have += 1
        mine_values.add(v.strip().upper())
        t = today.get(p)
        if t is None:
            continue
        compared += 1
        if _same(v, t, numeric, factor):
            same += 1
            continue
        if len(examples) < EXAMPLES:
            examples.append([v.strip(), t.strip()])
        if len(diffs) < DIFFS:
            diffs.append(AsSoldDiff(parcel=p, date=dates[i] if i < len(dates) else "", sold=v.strip(), today=t.strip()))
    today_values = {t.strip().upper() for t in today.values()}
    overlap = len(mine_values & today_values) / len(mine_values) if mine_values else 1.0
    if numeric or all(_num(t) is not None for t in list(today_values)[:200]):
        # Numbers today, and mostly not numbers as sold ("B-5  120%" where today's is 1.2): another way of writing.
        as_numbers = sum(_num(v) is not None for v in mine_values) / len(mine_values) if mine_values else 1.0
        differently = compared >= 20 and same / compared < WRITTEN_DIFFERENTLY and as_numbers < 0.5
    else:
        differently = compared >= 20 and same / compared < WRITTEN_DIFFERENTLY and overlap < WRITTEN_DIFFERENTLY
    return {
        "sales": n,
        "have": have,
        "compared": compared,
        "same": same,
        "examples": examples,
        "diffs": diffs,
        "written_differently": differently,
    }


def view(project: Project, in_dir: Path) -> AsSoldView:
    files = Files(project, in_dir)
    sales = sales_file(project)
    if sales is None or sales.name not in files.preview:
        return AsSoldView(sales_file=None, columns=[], rows=[])
    by_key = dictionary_by_key()
    chosen = project.wizard.as_sold
    # Columns the sales file already gives a field of its own (price, date…): not a characteristic's.
    taken = {s[0] for k, s in sales.load.items() if k not in characteristic_keys()}
    rows = []
    for key in characteristic_keys():
        src = _parcel_source(project, key)
        if src is None or key not in by_key:
            continue
        pcol = src.load[key][0]
        mine = chosen.get(key, "")
        today_unit = src.area_units.get(key, "sqft") if key in AREA_FIELDS else None
        how: Literal["name", "known", "values"] | None = None
        column: str | None = mine or None
        unit: AreaUnit | None = sales.area_units.get(key) if mine else None
        if not mine:
            hit = _found(files, sales, key, pcol, taken)
            if hit:
                column, how = hit[0], hit[1]  # type: ignore[assignment]
                # An area found by name: the unit its name gives away (ACREAGE), else the one that agrees.
                unit = guess_area_unit(column) if key in AREA_FIELDS else None
                if key in AREA_FIELDS and unit is None:
                    by_unit = _by_values(files, sales, key, src, set(), only=column)
                    unit = by_unit[1] if by_unit else today_unit
            elif (by := _by_values(files, sales, key, src, taken)) is not None:
                column, unit, how = by[0], by[1] or today_unit, "values"
        unit = unit or today_unit
        name = RENAMED.get(key, (by_key[key].name, ""))[0]
        empty = {
            "sales": 0,
            "have": 0,
            "compared": 0,
            "same": 0,
            "examples": [],
            "diffs": [],
            "written_differently": False,
        }
        c = _compare(project, files, sales, key, column, src, unit) if column else empty
        suggest: Literal["sale", "today"] | None = None
        if column and not c["written_differently"] and c["compared"]:
            suggest = "today" if c["same"] / c["compared"] >= SAME_ENOUGH else "sale"
        rows.append(
            AsSoldRow(
                key=key,
                name=name,
                parcel_file=src.name,
                parcel_column=pcol,
                column=column,
                found=not mine,
                how=how,
                unit=unit if key in AREA_FIELDS else None,
                today_unit=today_unit,
                choice=("sale" if mine else "today") if key in chosen else None,
                suggest=suggest,
                **c,
            )
        )
    return AsSoldView(
        sales_file=sales.name,
        filename=sales.filename,
        columns=[c.name for c in files.columns(sales.name)],
        rows=rows,
    )


def choose(project: Project, in_dir: Path, key: str, column: str | None, area_unit: AreaUnit | None = None) -> None:
    """The sale's (its column, read as the parcel's, an area in its own unit if given) or today's (None)."""
    from oakbox.wizard.setfield import set_field

    if key not in characteristic_keys():
        raise ValueError(f"{key} isn't a characteristic a sale can carry.")
    sales = sales_file(project)
    src = _parcel_source(project, key)
    if sales is None:
        raise ValueError("Add the sales file first.")
    if src is None:
        raise ValueError("Load it for the parcels first: a sale's value is used beside the parcel's, never alone.")
    if column is None:
        set_field(project, in_dir, key, None, None, False, only=sales.name)
        project.wizard.as_sold[key] = ""
        return
    set_field(
        project,
        in_dir,
        key,
        sales.name,
        column,
        False,
        area_unit=area_unit or _unit_of(project, in_dir, key, column, sales, src),
        number_format=src.numbers.get(key),
        scale=src.scales.get(key),
        only=sales.name,
    )
    project.wizard.as_sold[key] = column


def _unit_of(project: Project, in_dir: Path, key: str, column: str, sales: DataFile, src: DataFile) -> AreaUnit | None:
    """An area column's unit when none is given: as already read, else as its name says (ACREAGE), else the one that
    agrees with today's, else today's."""
    if key not in AREA_FIELDS:
        return None
    if project.wizard.as_sold.get(key) == column and key in sales.area_units:
        return sales.area_units[key]
    by = (
        guess_area_unit(column)
        or ((_by_values(Files(project, in_dir), sales, key, src, set(), only=column) or (None, None))[1])
    )
    return by or src.area_units.get(key)


def resync(project: Project, in_dir: Path, key: str) -> None:
    """The parcel field changed: the sale's column read as it now is, or today's if it's no longer loaded."""
    column = project.wizard.as_sold.get(key)
    if not column:
        return
    if _parcel_source(project, key) is None:
        # No parcel field any more: nothing for the sales' value to stand beside. Dropped, and the choice with it.
        from oakbox.wizard.setfield import set_field

        sales = sales_file(project)
        if sales is not None:
            set_field(project, in_dir, key, None, None, False, only=sales.name)
        project.wizard.as_sold.pop(key, None)
        return
    choose(project, in_dir, key, column)

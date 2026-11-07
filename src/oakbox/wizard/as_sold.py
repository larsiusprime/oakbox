"""Data › Sales as sold (SPEC §3.0 F3d, 2026-11-07): the main sales file's columns that describe the property, beside
the parcel fields they mirror.

A sale should be described as the property was when it sold (it may have changed since): those are what the models
learn from. Parcels are valued on what they are now: the parcel files. Where a sale has no characteristics of its own,
OpenAVMKit fills them in from its parcel today (it hydrates the sales): an assumption that the parcel hasn't changed.

For each characteristic loaded from a parcel file, the sales file's column that mirrors it (the same column name, or
a name the field dictionary knows), checked against today's value on the same parcels: how many sales have one, how
many differ. The user's choice per field (`project.wizard.as_sold`): the sale's (its column loaded into the sales file,
read as the parcel's is: unit, number format, scale) or today's (nothing loaded). Until chosen, today's: nothing
changes silently; the step suggests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import AREA_FIELDS, BaseModel, DataFile
from oakbox.projects import Project
from oakbox.wizard.base import CHARACTERISTIC_STEPS, RENAMED, STEPS, normalized
from oakbox.wizard.checks import _names
from oakbox.wizard.files import Files, dictionary_by_key, file_stamp, sales_file, values_of

SAME_ENOUGH = 0.99  # this share the same as today's: a snapshot exported with the sales, not history
WRITTEN_DIFFERENTLY = 0.2  # under this share of the sale's values among today's: written another way
EXAMPLES = 3


def characteristic_keys() -> list[str]:
    return [k for s in STEPS if s.key in CHARACTERISTIC_STEPS for k in (*s.fields, *s.more)]


class AsSoldRow(BaseModel):
    key: str
    name: str
    parcel_file: str = Field(description="The parcel file it's loaded from (today's).")
    parcel_column: str
    column: str | None = Field(description="The sales file's column: chosen, else the one that mirrors it.")
    found: bool = Field(description="The column was found by its name (not chosen by hand).")
    choice: Literal["sale", "today"] | None = Field(description="The user's; None: not chosen (today's is used).")
    suggest: Literal["sale", "today"] | None = Field(
        description="What the figures suggest: today's when they're the same; None: written another way."
    )
    sales: int = Field(description="Sales on a parcel.")
    have: int = Field(description="Of them, with a value in the column.")
    compared: int = Field(description="Of those, on a parcel with today's value too.")
    same: int = Field(description="Of those, the same as today's.")
    examples: list[list[str]] = Field(description="[as sold, today] where they differ.")
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


def _found(files: Files, sales: DataFile, key: str, parcel_column: str, taken: set[str]) -> str | None:
    """The sales file's column that mirrors the field: the parcel's own column name, else a name it's known by."""
    d = dictionary_by_key()[key]
    names = _names(d)
    cols = [c.name for c in files.columns(sales.name) if c.name not in taken]
    same = next((c for c in cols if normalized(c) == normalized(parcel_column)), None)
    return same or next((c for c in cols if normalized(c) in names), None)


def _num(v: str) -> float | None:
    try:
        x = float(v.replace(",", ""))
    except ValueError:
        return None
    return x if x == x else None


def _same(a: str, b: str, numeric: bool) -> bool:
    if numeric:
        x, y = _num(a), _num(b)
        if x is not None and y is not None:
            return abs(x - y) <= max(0.5, 0.005 * abs(y))
    return a.strip().upper() == b.strip().upper()


def _compare(project: Project, files: Files, sales: DataFile, key: str, column: str, src: DataFile) -> dict:
    """The sale's column against today's value of each sale's parcel."""
    from oakbox.wizard.quality import _by_parcel

    d = dictionary_by_key()[key]
    numeric = d.type in ("number", "float", "integer", "int") or key in AREA_FIELDS
    today = _by_parcel(files, src, src.load[key][0])
    sold = values_of(file_stamp(files.in_dir / sales.filename), sales.layer, column)
    parcels = files.parcel_ids(sales.name)
    n = have = compared = same = 0
    examples: list[list[str]] = []
    mine_values: set[str] = set()
    for p, v in zip(parcels, sold, strict=False):
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
        if _same(v, t, numeric):
            same += 1
        elif len(examples) < EXAMPLES:
            examples.append([v.strip(), t.strip()])
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
        "written_differently": differently,
    }


def view(project: Project, in_dir: Path) -> AsSoldView:
    files = Files(project, in_dir)
    sales = sales_file(project)
    if sales is None or sales.name not in files.preview:
        return AsSoldView(sales_file=None, columns=[], rows=[])
    by_key = dictionary_by_key()
    chosen = project.wizard.as_sold
    taken = {s[0] for k, s in sales.load.items() if k not in chosen}
    rows = []
    for key in characteristic_keys():
        src = _parcel_source(project, key)
        if src is None or key not in by_key:
            continue
        pcol = src.load[key][0]
        mine = chosen.get(key, "")
        column = mine or _found(files, sales, key, pcol, taken)
        if column is None:
            continue
        c = _compare(project, files, sales, key, column, src)
        suggest: Literal["sale", "today"] | None = None
        if not c["written_differently"] and c["compared"]:
            suggest = "today" if c["same"] / c["compared"] >= SAME_ENOUGH else "sale"
        name = RENAMED.get(key, (by_key[key].name, ""))[0]
        rows.append(
            AsSoldRow(
                key=key,
                name=name,
                parcel_file=src.name,
                parcel_column=pcol,
                column=column,
                found=not mine,
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


def choose(project: Project, in_dir: Path, key: str, column: str | None) -> None:
    """The sale's (its column, read as the parcel's) or today's (None) for a characteristic."""
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
        area_unit=src.area_units.get(key),
        number_format=src.numbers.get(key),
        scale=src.scales.get(key),
        only=sales.name,
    )
    project.wizard.as_sold[key] = column


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

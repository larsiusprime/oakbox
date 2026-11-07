"""Setting a field in the Data wizard: which file and column it's loaded from (and how it's read), or that it's
assumed, or that the data doesn't have it. The wizard's steps (core.py) and a file appended as rows (rows.py, which
copies the main file's fields) both set fields through it.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from oakbox.datafiles import (
    AREA_FIELDS,
    QC_FIELDS,
    AreaUnit,
    Condition,
    DataFile,
    Match,
    NumberFormat,
    Rule,
    Scale,
    guess_area_unit,
    small_unit,
)
from oakbox.errors import NotFound
from oakbox.projects import Project
from oakbox.wizard.base import ABSENT_OK, ASSUMABLE, CHARACTERISTIC_STEPS, PAIRS, ROWS, SCALED, STEPS
from oakbox.wizard.checks import field_check
from oakbox.wizard.files import Files, dictionary_by_key, field_files, file_stamp, is_more_sales, sales_file, values_of
from oakbox.wizard.money import detect_number_format, is_money, plain_numbers
from oakbox.wizard.quality import new_scale


def made_sale_id(match: Match) -> list:
    """The sale ID made from the parcel ID + sale date, e.g. "0012-001-2023-01-09" (an OpenAVMKit calc)."""
    return ["join", ["values", match, "sale_date"], "str:-"]


def set_field(
    project: Project,
    in_dir: Path,
    key: str,
    file: str | None,
    column: str | None,
    assume: bool,
    date_format: str | None = None,
    area_unit: AreaUnit | None = None,
    number_format: NumberFormat | None = None,
    scale: Scale | None = None,
    absent: bool = False,
    only: str | None = None,
) -> None:
    """Load a field from one file's column, from nowhere, or (valid/vacant sale) as an assumption.

    A yes/no field from a column that isn't yes/no gets a rule to fill in: which values mean yes. ``only``: in
    that one file, which carries its own (a file appended as rows, or the date of more sales details joined on a
    made sale ID), the other files untouched."""
    by_key = dictionary_by_key()
    step = next((s for s in STEPS if key in s.fields or key in s.more), None)
    if step is None or key not in by_key:
        raise NotFound(key)
    allowed = field_files(project, step.sales)
    if only is not None:
        # A file of its own rows, more sales details, or the main sales file carrying a characteristic as sold
        # (Sales as sold: as_sold.choose).
        allowed = [
            f
            for f in project.files
            if f.name == only
            and (f.holds in ROWS or is_more_sales(f) or (f.holds == "sales" and step.key in CHARACTERISTIC_STEPS))
        ]
        if not allowed:
            raise NotFound(only)
        if allowed[0].holds in ROWS or is_more_sales(allowed[0]):
            step = step.model_copy(update={"sales": allowed[0].holds in ("sales", "sale_rows")})
    sales = sales_file(project)
    target: DataFile | None = None
    spec: list[str] | None = None
    reading: NumberFormat | None = None
    if file is not None and column is not None:
        target = next((f for f in allowed if f.name == file), None)
        if target is None:
            where = "the sales record" if step.sales else "the parcel universe or a file joined to it"
            raise ValueError(f"{key} comes from {where}.")
        col = Files(project, in_dir).column(file, column)
        if col is None:
            raise ValueError(f"{file} has no column {column}.")
        d = by_key[key]
        check, spec = field_check(d, col)
        if d.type == "boolean" and step.sales:
            # Which values mean a valid (or vacant) sale is the user's to say, even in a yes/no column: never read
            # as "true = yes" on its own. It becomes a rule with no values yet, which the row asks for.
            spec = None
        if key in SCALED:
            # Numbers, or a category to rank into tiers: either way it becomes a number (F3d).
            entry = next(f for f in allowed if f.name == file)
            plain = plain_numbers(values_of(file_stamp(in_dir / entry.filename), entry.layer, column))
            # Numbers or a category is the user's to say: numbers (1–6) can be codes to rank, too.
            tiers = not plain or (scale is not None and scale.kind == "tiers")
            spec = [column, "string"] if tiers else [column, "float"]
            if not plain and scale is not None and scale.kind not in (None, "tiers"):
                raise ValueError(f"{column} isn't numbers: rank its tiers instead.")
        if is_money(key):
            # Money written as text ($250,000.00, N/A): read with a format, worked out from the whole column.
            entry = next(f for f in allowed if f.name == file)
            values = values_of(file_stamp(in_dir / entry.filename), entry.layer, column)
            reading = number_format or (
                None if plain_numbers(values) else detect_number_format(values, project.numbers)[0]
            )
            if reading is not None:
                spec = [column, "float"]
        if d.type == "date" and date_format:
            spec = [column, "datetime", date_format]
        elif spec is None and d.type == "boolean" and step.sales:
            spec = None  # becomes a rule, below
        elif spec is None:
            raise ValueError(f"{column}: {check.text}.")
        for other, s in target.load.items():
            # A category can be both the text and, ranked, the number (F3d).
            if s[0] == column and other != key and not (key in QC_FIELDS and other in QC_FIELDS):
                raise ValueError(f"{column} is already loaded as {other}.")
    elif assume and (key not in ASSUMABLE or sales is None):
        raise ValueError(f"{key} can't be assumed.")
    elif absent and key not in ABSENT_OK:
        raise ValueError(f"{key} can't be said not to exist.")
    # The category's text follows a category number (one column, both ways); a number drops it again.
    pair = PAIRS.get(key) if key in SCALED and only is None else None
    was = next((f.load[key][0] for f in allowed if key in f.load), None)
    if pair is not None:
        for f in allowed:
            if was is not None and f.load.get(pair, [None])[0] == was:
                f.load.pop(pair, None)
    for f in allowed:
        f.load.pop(key, None)
        f.rules.pop(key, None)
        f.area_units.pop(key, None)
        f.numbers.pop(key, None)
        f.scales.pop(key, None)
    if only is None and key in project.wizard.absent:
        project.wizard.absent.remove(key)
    if absent and only is None:
        project.wizard.absent.append(key)
    if only is None and sales is not None and key in ASSUMABLE:  # (one file's own: the sales record untouched)
        sales.calc.pop(key, None)
    if target is not None and spec is None:
        target.rules[key] = Rule(conditions=[Condition(column=cast(str, column))])
    if target is not None and spec is not None:
        target.load[key] = spec
        if key in AREA_FIELDS:
            target.area_units[key] = area_unit or guess_area_unit(cast(str, column)) or small_unit(project.units)
        if reading is not None:
            target.numbers[key] = reading
        if key in SCALED:
            target.scales[key] = new_scale(Files(project, in_dir), target, key, spec[0], scale)
            if pair is not None and target.scales[key].kind == "tiers" and not any(pair in f.load for f in allowed):
                target.load[pair] = [cast(str, column), "string"]
    elif assume and sales is not None:
        sales.calc[key] = ["set", ASSUMABLE[key]]
    if only is not None:
        return
    if key in project.wizard.as_sold:
        # The sales' copy of it (Sales as sold) follows: read as the parcel's now is, or today's if it's gone.
        from oakbox.wizard.as_sold import resync

        resync(project, in_dir, key)
    if key not in project.wizard.decided:
        project.wizard.decided.append(key)
    if step.key in project.wizard.skipped and (file or assume):
        project.wizard.skipped.remove(step.key)

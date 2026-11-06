"""Data › More files: files appended as extra rows (F3d). More sales (older sales, sales found some other way) added
to the sales record, or more parcels added to the parcel universe, each row one sale or one parcel of its own.

The file's columns are matched to the main file's fields (the sales record's, or the universe's): by the same
column name, else a column named as the field, else the usual guess; each can be changed. Valid and vacant sale
take the sales record's rule, on this file's column. Two checks before them: how many of the main file's fields it
has (warned at half or fewer: likely the wrong file, or a different layout), and whether its IDs look like the
main file's (length, digits, leading zeros). Written as OpenAVMKit's ``data.process.merge`` with ``"how":
"append"``; a row in both files is kept once, the main file's (projects._data).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from oakbox.datafiles import Condition, DataFile, Rule
from oakbox.wizard.base import ROWS
from oakbox.wizard.files import Files, dictionary_by_key, sales_file
from oakbox.wizard.models import RowField, RowsView
from oakbox.wizard.setfield import made_sale_id, set_field

if TYPE_CHECKING:
    from oakbox.projects import Project

# Fields that aren't the main file's own to copy: the ID is the file's join, and made fields are worked out.
NOT_MIRRORED = {"key", "key2", "key3"}


def main_of(project: Project, holds: str) -> DataFile | None:
    """The file appended rows join: the sales record, or the parcel universe."""
    return sales_file(project) if ROWS.get(holds) == "sales" else project.base_file()


# Fields the sales record may assume rather than read (valid and vacant sale): an appended file assumes the same
# unless given a column of its own.
ASSUMABLE = ("valid_sale", "vacant_sale")


def mirrored(main: DataFile) -> list[str]:
    """The main file's fields an appended file should have: what it loads, its yes/no rules, what it assumes."""
    keys = [*main.load, *main.rules, *(k for k in ASSUMABLE if k in main.calc)]
    return [k for k in dict.fromkeys(keys) if k not in NOT_MIRRORED and not k.startswith("_")]


def _find(files: Files, main: DataFile, entry: DataFile, key: str) -> str | None:
    """The column an appended file has for a field: the main file's column by name, else one named as the field."""
    names = {c.name for c in files.columns(entry.name)}
    lower = {c.lower(): c for c in names}
    source = None
    if key in main.load:
        source = main.load[key][0]
    elif key in main.rules and main.rules[key].conditions:
        source = main.rules[key].conditions[0].column
    for want in (source, key):
        if want and want in names:
            return want
        if want and want.lower() in lower:
            return lower[want.lower()]
    from oakbox.wizard.checks import guess_field

    d = dictionary_by_key().get(key)
    found = guess_field(files, d, [entry.name], {}) if d else None
    return found[1][0] if found else None


def propose(project: Project, in_dir: Path, entry: DataFile) -> None:
    """Match an appended file's columns to the main file's fields, never over one already chosen."""
    from oakbox.errors import NotFound

    main = main_of(project, entry.holds or "")
    if main is None:
        return
    files = Files(project, in_dir)
    for key in mirrored(main):
        if key in entry.load or key in entry.rules:
            continue
        column = _find(files, main, entry, key)
        if column is None:
            continue
        try:
            set_field(project, in_dir, key, entry.name, column, False, only=entry.name)
        except (ValueError, NotFound):
            continue
        copy_rule(main, entry, key)
    if entry.holds == "sale_rows":
        # Its sale ID: made as the sales record's is, or its own column.
        if "key_sale" in main.calc:
            entry.calc["key_sale"] = made_sale_id("key")
        assume(main, entry)


def assume(main: DataFile, entry: DataFile) -> None:
    """An assumed valid or vacant sale: assumed here too, unless this file has a column for it."""
    for k in ASSUMABLE:
        if k in main.calc and k not in entry.load and k not in entry.rules:
            entry.calc[k] = main.calc[k]


def copy_rule(main: DataFile, entry: DataFile, key: str) -> None:
    """A yes/no field's rule: the main file's, on this file's column (one column tested), when it has one."""
    rule = main.rules.get(key)
    mine = entry.rules.get(key)
    if rule is None or mine is None or len({c.column for c in rule.conditions}) != 1 or not mine.conditions:
        return
    column = mine.conditions[0].column
    entry.rules[key] = Rule(
        join=rule.join,
        conditions=[Condition(column=column, op=c.op, values=list(c.values)) for c in rule.conditions],
    )


# ---------- The view ----------


def _shape(values: list[str]) -> tuple[int | None, bool, bool]:
    """The usual length of an ID, whether IDs are digits, and whether some start with a zero."""
    present = [v for v in values if v]
    if not present:
        return None, False, False
    length = Counter(len(v) for v in present).most_common(1)[0][0]
    digits = sum(v.isdigit() for v in present) >= 0.9 * len(present)
    zeros = any(v.startswith("0") for v in present if v.isdigit())
    return length, digits, zeros


def describe_steps(length: int | None, digits: bool, zeros: bool) -> str:
    kind = "digits" if digits else "characters"
    return f"{length} {kind}" + (", leading zeros kept" if zeros else "")


def _made_keys(files: Files, entry: DataFile) -> set[str]:
    """Sale IDs made as OpenAVMKit makes them: parcel ID, a dash, the sale date as read."""
    import pandas as pd

    spec = entry.load.get("sale_date")
    if spec is None or "key" not in entry.load:
        return set()
    ids = files.ids(entry.name, "key")
    raw = files.values(entry.name, spec[0])
    fmt = spec[2] if len(spec) > 2 else None
    dates = pd.to_datetime(pd.Series(raw), format=fmt, errors="coerce")
    return {f"{i}-{d}" for i, d in zip(ids, dates, strict=False) if i and not pd.isna(d)}


def sale_keys(files: Files, entry: DataFile) -> set[str]:
    """A sales file's sale IDs: its column's, or made from parcel ID and date."""
    if "key_sale" in entry.load:
        return {v for v in files.ids(entry.name, "key_sale") if v}
    if "key_sale" in entry.calc:
        return _made_keys(files, entry)
    return set()


def view(project: Project, files: Files, entry: DataFile) -> RowsView | None:
    main = main_of(project, entry.holds or "")
    if main is None or entry.name not in files.preview:
        return None
    names = dictionary_by_key()
    wanted = mirrored(main)
    fields = []
    for k in wanted:
        col = entry.load.get(k, [None])[0] or (
            entry.rules[k].conditions[0].column if k in entry.rules and entry.rules[k].conditions else None
        )
        d = names.get(k)
        assumed = col is None and k in entry.calc
        fields.append(RowField(key=k, name=d.name if d else k, column=col, assumed=assumed))
    have = sum(1 for f in fields if f.column or f.assumed)
    mine = list(files.ids(entry.name, "key")) if "key" in entry.load else []
    theirs = list(files.ids(main.name, "key")) if "key" in main.load else []
    a, b = _shape(mine), _shape(theirs)
    what = "sales record's" if entry.holds == "sale_rows" else "parcel universe's"
    if not mine:
        key_text, key_ok = "pick its parcel ID", False
    elif a == b:
        key_text, key_ok = f"its parcel IDs look like the {what}: {describe_steps(*a)}", True
    else:
        key_text = f"its parcel IDs don't look like the {what}: {describe_steps(*a)} here, {describe_steps(*b)} there"
        key_ok = False
    universe = project.base_file()
    parcels = set(files.ids(universe.name, "key")) if universe is not None and "key" in universe.load else set()
    present = [v for v in mine if v]
    found = sum(1 for v in present if v in parcels)
    if entry.holds == "sale_rows":
        overlap = len(sale_keys(files, entry) & sale_keys(files, main))
    else:
        overlap = found  # a parcel already in the universe: kept once, the universe's
    return RowsView(
        adds_to=entry.holds and ROWS[entry.holds] or "",
        fields=fields,
        have=have,
        of=len(fields),
        few=bool(fields) and have * 2 <= len(fields),
        key_text=key_text,
        key_ok=key_ok,
        found=found,
        rows=len(present),
        overlap=overlap,
    )

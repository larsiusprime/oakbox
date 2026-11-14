"""A parcel file whose rows each say something different about the parcel (one row per amenity: lake, golf
course, canal), combined into one row per parcel instead of keeping one of them (F3d, the duplicates dialog).

What each row is about (a column: Amenity) becomes a yes/no field per value (has_lake, has_golf_course), or per
group of values the user puts together; each number column one number per parcel (the largest, the smallest, the
total...); and, if asked, the main value as a category (the first of an order the user sets that the parcel has).
OpenAVMKit can't reshape a file, so OAK box writes the combined file beside the original in in/
(`<name>.combined.parquet`), and the project loads that; it's made again whenever the original or the set-up
changes (ensure, from Files).
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field

from oakbox.datafiles import BaseModel, Combine, CombineGroup, CombineHow, DataFile
from oakbox.projects import CustomField, Project

NONE = {"", "NULL", "NONE", "NAN", "N/A", "NA", "-"}
FEW_NUMBERS = 4  # a file with this many number columns or fewer: each suggested as a number per parcel
AREA = re.compile(r"area|sq_?ft|sqft|size|_sf$", re.IGNORECASE)  # a number column a group's total is likely of
MAX_VALUES = 500  # a column with more different values isn't what rows are about
META = b"oakbox_combine"


def norm(v: str) -> str:
    """A value as compared: capitals, extra spaces ignored; "" for none."""
    n = " ".join(v.upper().split())
    return "" if n in NONE else n


def slug(text: str) -> str:
    s = re.sub(r"[^0-9a-z]+", "_", text.lower()).strip("_")
    return s if s and s[0].isalpha() else f"f_{s}"


def group_field(name: str) -> str:
    return f"has_{slug(name)}"


def main_field(about: str) -> str:
    return f"main_{slug(about)}"


def count_field(name: str) -> str:
    return f"{slug(name)}_count"


def total_field(name: str, measure: str) -> str:
    return f"{slug(name)}_{slug(measure)}"


ROWS_FIELD = "row_count"


def group_fields(g: CombineGroup, measure: str | None) -> list[str]:
    """The fields a group makes, in order: yes/no, how many, total (only with a measure)."""
    out = []
    if "has" in g.makes:
        out.append(group_field(g.name))
    if "count" in g.makes:
        out.append(count_field(g.name))
    if "total" in g.makes and measure:
        out.append(total_field(g.name, measure))
    return out


def fields_of(c: Combine) -> list[tuple[str, str]]:
    """The fields a combined file has, beside its ID: (name, category or number)."""
    out = [(f, "number") for g in c.groups if g.values for f in group_fields(g, c.measure)]
    out += [(slug(col), "number") for col in c.measures]
    if c.rows:
        out.append((ROWS_FIELD, "number"))
    if c.main:
        out.append((main_field(c.about), "category"))
    return out


FEW_VALUES = 40  # up to this many values, a group per value to start; more, none (the user picks)


def suggest_groups(values: Iterable[str]) -> list[CombineGroup]:
    """To start: a group per value, its field named after it (a few values: amenities); with many (95 kinds of
    sub-area) none, the user makes the groups that matter. Values that mean the same are put together by hand
    (Edit groups…): no guessing from the values' words, which only ever fit one county's codes."""
    values = list(values)
    if len(values) > FEW_VALUES:
        return []
    out: list[CombineGroup] = []
    fields: set[str] = set()
    for v in values:
        name, n = v.title(), 2
        while group_field(name) in fields:  # "RAIL-ROAD" and "RAIL ROAD" would make the same field
            name, n = f"{v.title()} {n}", n + 1
        fields.add(group_field(name))
        out.append(CombineGroup(name=name, values=[v]))
    return out


def default_how(column: str) -> CombineHow:
    """A distance is the nearest; anything else the largest (frontage, width)."""
    return "min" if re.search(r"dist", column, re.IGNORECASE) else "max"


def combined_name(source: str) -> str:
    return f"{Path(source).stem}.combined.parquet"


# ---------- the data ----------


def _read(in_dir: Path, f: DataFile, source: str, columns: list[str]) -> Any:
    """The source file's columns as text (the ID raw), a DataFrame."""
    import pandas

    pd: Any = pandas  # typed loosely: this is all frames and series

    from oakbox.wizard.files import file_stamp, values_of

    stamp = file_stamp(in_dir / source)
    return pd.DataFrame({c: pd.Series(values_of(stamp, f.layer, c, raw=True), dtype=object) for c in columns})


def build(ids: Any, about: Any, numbers: dict[str, Any], c: Combine) -> Any:
    """One row per ID (in the order they first appear): ids and about as text, numbers (the measures' columns and
    the groups' measure) as written, row by row."""
    import pandas

    pd: Any = pandas  # typed loosely: this is all frames and series

    def number(col: str) -> Any:
        return pd.to_numeric(pd.Series(numbers[col], dtype=object), errors="coerce").to_numpy()

    df = pd.DataFrame({"id": ids, "about": about.map(lambda v: norm(str(v)))})
    if c.measure:
        df["m"] = number(c.measure)
    for col in c.measures:
        df[f"x:{col}"] = number(col)
    df = df[df["id"] != ""]
    parcels = pd.Index(df["id"].drop_duplicates())
    out = pd.DataFrame(index=parcels)
    for g in c.groups:
        if not g.values:
            continue
        rows = df[df["about"].isin(set(g.values))]
        per = rows.groupby("id")
        if "has" in g.makes:
            out[group_field(g.name)] = parcels.isin(set(rows["id"])).astype("int8")
        if "count" in g.makes:
            out[count_field(g.name)] = per.size().reindex(parcels).fillna(0).astype("int64")
        if "total" in g.makes and c.measure:
            out[total_field(g.name, c.measure)] = per["m"].sum().reindex(parcels).fillna(0.0).astype("float64")
    for col, how in c.measures.items():
        per = df.groupby("id")[f"x:{col}"].agg("count" if how == "count" else how)
        out[slug(col)] = per.reindex(parcels).astype("float64")
    if c.rows:
        out[ROWS_FIELD] = df.groupby("id").size().reindex(parcels).astype("int64")
    if c.main:
        rank = {v: i for i, v in enumerate(c.main)}
        r = df.assign(rank=df["about"].map(rank)).dropna(subset=["rank"]).sort_values("rank", kind="stable")
        first = r.drop_duplicates("id").set_index("id")["about"]
        out[main_field(c.about)] = first.reindex(parcels).fillna("").astype(object)
    return out


def _spec_key(c: Combine, id_column: str) -> str:
    return json.dumps({"spec": c.model_dump(), "id": id_column}, sort_keys=True)


_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _lock(path: Path) -> threading.Lock:
    with _locks_lock:
        return _locks.setdefault(str(path), threading.Lock())


def ensure(in_dir: Path, f: DataFile) -> None:
    """The combined file, as the original and the set-up stand: made again if either changed (or it's gone)."""
    c = f.combine
    spec = f.load.get(f.match)
    if c is None or spec is None or not (in_dir / c.source).is_file():
        return
    src = (in_dir / c.source).stat()
    key = json.dumps([src.st_size, src.st_mtime_ns, _spec_key(c, spec[0])])
    target = in_dir / combined_name(c.source)
    with _lock(target):
        if _made(str(target), target.stat().st_mtime_ns if target.is_file() else 0) == key:
            return
        _write(in_dir, f, c, spec[0], target, key)
        _made.cache_clear()


@lru_cache(maxsize=64)
def _made(target: str, _mtime: int) -> str | None:
    """What a combined file was made from (its key), from its own metadata."""
    import pyarrow.parquet as pq

    p = Path(target)
    if not p.is_file():
        return None
    try:
        meta = pq.read_schema(p).metadata or {}
    except Exception:  # noqa: BLE001 - unreadable: made again
        return None
    v = meta.get(META)
    return v.decode() if v else None


def _write(in_dir: Path, f: DataFile, c: Combine, id_column: str, target: Path, key: str) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    from oakbox.atomic import replace_with

    numbers: list[str] = list(dict.fromkeys([*c.measures, *([c.measure] if c.measure else [])]))
    wanted: list[str] = list(dict.fromkeys([id_column, c.about, *numbers]))
    raw = _read(in_dir, f, c.source, wanted)
    out = build(raw[id_column], raw[c.about], {m: raw[m] for m in numbers}, c)
    out.index.name = id_column
    table = pa.Table.from_pandas(out.reset_index(), preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), META: key.encode()})
    replace_with(target, lambda tmp: pq.write_table(table, tmp))


# ---------- the dialog ----------


class ValueCount(BaseModel):
    value: str
    parcels: int


class MeasureView(BaseModel):
    column: str
    parcels: int = Field(description="Parcels with a number in it, on any of their rows.")
    how: CombineHow = Field(description="As set, or the suggestion.")
    used: bool = Field(description="In the combined file (as set; suggested: every number column).")


class CombinePreview(BaseModel):
    """What combining a file's rows would make, for the dialog: as set, or as suggested."""

    abouts: list[str] = Field(description="Columns that could say what rows are about, the likeliest first.")
    about: str | None
    values: list[ValueCount] = Field(description="The about column's values, as compared, most parcels first.")
    groups: list[CombineGroup]
    group_parcels: list[int] = Field(description="Parcels in each group (a parcel can be in several).")
    numbers: list[str] = Field(description="The file's number columns: what groups can total (the measure).")
    measure: str | None = Field(description="The column groups total: as set, or the suggestion (an area).")
    rows_on: bool = Field(description="Also how many rows each parcel has.")
    none: int = Field(description="Parcels in no group (no value, or only values left out).")
    measures: list[MeasureView]
    main: list[str] = Field(description="The order for the main value: as set, or most parcels first.")
    main_on: bool = Field(description="The main value is made.")
    main_parcels: list[int] = Field(description="Parcels each value would be the main one for.")
    rows: int
    parcels: int
    fields: int = Field(description="Fields it makes: groups, numbers kept, and the main value if made.")


def preview(
    project: Project,
    in_dir: Path,
    name: str,
    about: str | None = None,
    groups: list[CombineGroup] | None = None,
    main: list[str] | None = None,
    main_on: bool | None = None,
    measures: dict[str, CombineHow] | None = None,
    measure: str | None = None,
    rows_on: bool | None = None,
) -> CombinePreview:
    """measure: None, as set (or suggested); "": none."""
    from oakbox.wizard.files import Files

    files = Files(project, in_dir)
    f = files.entry(name)
    spec = f.load.get(f.match)
    if spec is None:
        raise ValueError(f"Pick the ID column of {name} first.")
    id_col = spec[0]
    set_ = f.combine
    cols = files.columns(name, source=True)
    text_cols = [c.name for c in cols if c.name != id_col and c.type not in ("number", "date")]
    num_cols = [c.name for c in cols if c.name != id_col and c.type == "number"]
    source = set_.source if set_ else f.filename
    from oakbox.wizard.files import file_stamp, steps_key

    # The heavy part (every row read and its value compared), kept per file and column: a change of groups only
    # counts again.
    key = (file_stamp(in_dir / source), f.layer, id_col, steps_key(f.clean.get(f.match, [])))
    abouts = list(_abouts_of(*key, tuple(text_cols)))
    about = about or (set_.about if set_ else None) or (abouts[0] if abouts else None)
    base = _prepared(*key, about, tuple(num_cols)) if about else _prepared(*key, None, ())
    rows, parcels = base.rows, base.parcels
    if about is None:
        return CombinePreview(
            abouts=abouts, about=None, values=[], groups=[], group_parcels=[], numbers=num_cols, measure=None,
            rows_on=False, none=parcels, measures=[], main=[], main_on=False, main_parcels=[], rows=rows,
            parcels=parcels, fields=0,
        )  # fmt: skip
    df, per_value = base.df, base.per_value
    values = [ValueCount(value=str(v), parcels=int(n)) for v, n in per_value.items()]
    if groups is None:
        groups = set_.groups if set_ and set_.about == about else suggest_groups(per_value.index)
    in_group = {v: g.name for g in groups for v in g.values}
    dg = df.assign(g=df["v"].map(in_group)).dropna(subset=["g"])
    by_group = dg.drop_duplicates(["id", "g"]).groupby("g")["id"].nunique()
    group_parcels = [int(by_group.get(g.name, 0)) for g in groups]
    none = parcels - int(dg["id"].nunique())
    if main is None:
        main = set_.main if set_ and set_.main and set_.about == about else None
    order = [v for v in (main or []) if v in per_value.index] + [v for v in per_value.index if v not in (main or [])]
    rank = {v: i for i, v in enumerate(order)}
    first = df.assign(r=df["v"].map(rank)).sort_values("r", kind="stable").drop_duplicates("id")
    main_counts = first["v"].value_counts()
    main_parcels = [int(main_counts.get(v, 0)) for v in order]
    if main_on is None:
        main_on = bool(set_ and set_.main)
    chosen = measures if measures is not None else (set_.measures if set_ else None)
    mviews = []
    for col in num_cols:
        filled = base.filled.get(col, 0)
        if filled == 0:
            continue
        how = (chosen or {}).get(col) or default_how(col)
        # Suggested: every number column of a file with a few (an amenity's lengths and distances); of one with
        # many (a building's year, number, floor...) none.
        used = col in chosen if chosen is not None else len(num_cols) <= FEW_NUMBERS
        mviews.append(MeasureView(column=col, parcels=filled, how=how, used=used))
    if measure is None:
        measure = set_.measure if set_ else next((c for c in num_cols if AREA.search(c)), None)
    measure = measure or None
    if measure is not None and measure not in num_cols:
        raise ValueError(f"{name} has no number column {measure}.")
    if rows_on is None:
        rows_on = bool(set_ and set_.rows)
    n_fields = (
        sum(len(group_fields(g, measure)) for g in groups if g.values)
        + sum(1 for m in mviews if m.used)
        + (1 if rows_on else 0)
        + (1 if main_on else 0)
    )
    return CombinePreview(
        abouts=abouts, about=about, values=values, groups=list(groups), group_parcels=group_parcels, none=none,
        numbers=num_cols, measure=measure, rows_on=rows_on, measures=mviews, main=order, main_on=main_on,
        main_parcels=main_parcels, rows=rows, parcels=parcels, fields=n_fields,
    )  # fmt: skip


@dataclass(frozen=True)
class _Prepared:
    rows: int
    parcels: int
    df: Any  # id, v (the about column's value, as compared): rows with both
    per_value: Any  # value -> parcels, most first
    filled: dict[str, int]  # number column -> parcels with a number in it


def _ids_of(stamp: tuple[str, float, int], layer: str | None, id_col: str, steps: str) -> Any:
    import pandas

    from oakbox.wizard.files import cleaned_ids

    return pandas.Series(cleaned_ids(stamp, layer, id_col, steps), dtype=object)


@lru_cache(maxsize=8)
def _prepared(
    stamp: tuple[str, float, int], layer: str | None, id_col: str, steps: str, about: str | None, nums: tuple
) -> _Prepared:
    import pandas

    from oakbox.wizard.files import values_of

    pd: Any = pandas  # typed loosely: this is all frames and series

    ids = _ids_of(stamp, layer, id_col, steps)
    present = ids != ""
    rows, parcels = len(ids), int(ids[present].nunique())
    if about is None:
        return _Prepared(rows, parcels, None, None, {})
    raw = pd.Series(values_of(stamp, layer, about, raw=True), dtype=object)
    # Each distinct value compared once (norm), not every row's.
    codes, uniques = pd.factorize(raw)
    normed = pd.Series([norm(str(u)) for u in uniques], dtype=object)
    vals = pd.Series(normed.to_numpy()[codes], dtype=object) if len(uniques) else raw
    keep = present & (vals != "")
    df = pd.DataFrame({"id": ids[keep], "v": vals[keep]})
    per_value = df.drop_duplicates().groupby("v")["id"].nunique().sort_values(ascending=False, kind="stable")
    filled = {}
    for col in nums:
        x = pd.to_numeric(pd.Series(values_of(stamp, layer, col), dtype=object), errors="coerce")
        filled[col] = int(ids[present & x.notna()].nunique())
    return _Prepared(rows, parcels, df, per_value, filled)


@lru_cache(maxsize=8)
def _abouts_of(stamp: tuple[str, float, int], layer: str | None, id_col: str, steps: str, text_cols: tuple) -> tuple:
    """Text columns that say what each of an ID's rows is about: different on each of its rows, few values in all.
    The ones that tell an ID's rows apart best first."""
    import pandas

    from oakbox.wizard.files import values_of

    pd: Any = pandas  # typed loosely: this is all frames and series

    ids = _ids_of(stamp, layer, id_col, steps)
    scored = []
    for col in text_cols:
        v = pd.Series(values_of(stamp, layer, col), dtype=object)
        distinct = v.nunique()
        if distinct < 2 or distinct > MAX_VALUES:
            continue
        pairs = pd.DataFrame({"id": ids, "v": v})[ids != ""]
        repeats = int(pairs.duplicated().sum())  # an ID with the same value twice: not what tells its rows apart
        scored.append((repeats, distinct, col))
    return tuple(c for _r, _d, c in sorted(scored))


# ---------- saving ----------


def set_combine(
    project: Project,
    in_dir: Path,
    name: str,
    about: str,
    groups: list[CombineGroup],
    measures: dict[str, CombineHow],
    main: list[str] | None,
    measure: str | None = None,
    rows: bool = False,
) -> None:
    """Combine a parcel file's rows (or change how): the combined file made, the project loading it, and its fields
    the user's own (Your own fields: land), there to use."""
    from oakbox.wizard.files import Files

    files = Files(project, in_dir)
    f = files.entry(name)
    if f.holds != "parcels" or name == project.wizard.base:
        raise ValueError("Only a file of more parcel details can have its rows combined.")
    columns = {c.name for c in files.columns(name, source=True)}
    for col in [about, *measures, *([measure] if measure else [])]:
        if col not in columns:
            raise ValueError(f"{name} has no column {col}.")
    groups = [g for g in groups if g.values and g.name.strip() and g.makes]
    source = f.combine.source if f.combine else f.filename
    made = Combine(
        source=source, about=about, measure=measure or None, rows=rows, groups=groups, measures=measures,
        main=main or None,
    )  # fmt: skip
    names = [n for n, _k in fields_of(made)]
    if len(set(names)) != len(names):
        dup = next(n for n in names if names.count(n) > 1)
        raise ValueError(f"Two fields would both be {dup}: rename a group.")
    _drop_fields(project, f)
    f.combine = made
    f.filename = combined_name(source)
    f.dupes, f.dupes_sort, f.dupes_desc, f.dupes_by = None, None, False, []
    ensure(in_dir, f)
    taken = {k for other in project.files if other is not f for k in other.load} | set(project.wizard.locations)
    for field, kind in fields_of(f.combine):
        if field in taken:
            raise ValueError(f"{field} is already a field of another file: rename the group.")
        f.load[field] = [field, "float" if kind == "number" else "string"]
        project.wizard.custom = [c for c in project.wizard.custom if c.name != field]
        project.wizard.custom.append(CustomField(name=field, group="land", type=kind))  # type: ignore[arg-type]


def uncombine(project: Project, in_dir: Path, f: DataFile) -> None:
    """Back to the original file, its rows as they are (to keep the first of each, or drop them)."""
    if f.combine is None:
        return
    _drop_fields(project, f)
    target = in_dir / combined_name(f.combine.source)
    f.filename, f.combine = f.combine.source, None
    target.unlink(missing_ok=True)


def _drop_fields(project: Project, f: DataFile) -> None:
    if f.combine is None:
        return
    mine = {field for field, _kind in fields_of(f.combine)}
    for field in mine:
        f.load.pop(field, None)
    project.wizard.custom = [c for c in project.wizard.custom if c.name not in mine]

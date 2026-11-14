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
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field

from oakbox.datafiles import BaseModel, Combine, CombineGroup, CombineHow, DataFile
from oakbox.projects import CustomField, Project

NONE = {"", "NULL", "NONE", "NAN", "N/A", "NA", "-"}
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


def fields_of(c: Combine) -> list[tuple[str, str]]:
    """The fields a combined file has, beside its ID: (name, category or number)."""
    out = [(group_field(g.name), "number") for g in c.groups if g.values]
    out += [(slug(col), "number") for col in c.measures]
    if c.main:
        out.append((main_field(c.about), "category"))
    return out


def suggest_groups(values: Iterable[str]) -> list[CombineGroup]:
    """To start: a group per value, its field named after it. Values that mean the same are put together by hand
    (Edit groups…): no guessing from the values' words, which only ever fit one county's codes."""
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
    """One row per ID (in the order they first appear): ids and about as text, numbers as numbers, row by row."""
    import pandas

    pd: Any = pandas  # typed loosely: this is all frames and series

    df = pd.DataFrame({"id": ids, "about": about.map(lambda v: norm(str(v)))})
    keep = df["id"] != ""
    df = df[keep]
    parcels = pd.Index(df["id"].drop_duplicates())
    out = pd.DataFrame(index=parcels)
    to_group = {v: group_field(g.name) for g in c.groups for v in g.values}
    grouped = df.assign(field=df["about"].map(to_group)).dropna(subset=["field"])
    for g in c.groups:
        if not g.values:
            continue
        name = group_field(g.name)
        has = set(grouped.loc[grouped["field"] == name, "id"])
        out[name] = parcels.isin(has).astype("int8")
    for col, how in c.measures.items():
        x = pd.to_numeric(
            pd.Series(numbers[col], dtype=object)[keep.to_numpy()].reset_index(drop=True), errors="coerce"
        )
        per = x.groupby(df["id"].reset_index(drop=True)).agg("count" if how == "count" else how)
        out[slug(col)] = per.reindex(parcels).astype("float64")
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

    raw = _read(in_dir, f, c.source, [id_column, c.about, *c.measures])
    out = build(raw[id_column], raw[c.about], {m: raw[m] for m in c.measures}, c)
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
) -> CombinePreview:
    import pandas

    pd: Any = pandas  # typed loosely: this is all frames and series

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
    ids = pd.Series(files.ids(name, f.match, source=True), dtype=object)
    abouts = _abouts(files, name, ids, text_cols)
    about = about or (set_.about if set_ else None) or (abouts[0] if abouts else None)
    present = ids != ""
    rows, parcels = len(ids), int(ids[present].nunique())
    if about is None:
        return CombinePreview(
            abouts=abouts, about=None, values=[], groups=[], group_parcels=[], none=parcels, measures=[], main=[],
            main_on=False, main_parcels=[], rows=rows, parcels=parcels, fields=0,
        )  # fmt: skip
    raw = _read(in_dir, f, source, [about, *num_cols])
    vals = raw[about].map(lambda v: norm(str(v)))
    df = pd.DataFrame({"id": ids, "v": vals})[present & (vals != "")]
    per_value = df.drop_duplicates().groupby("v")["id"].nunique().sort_values(ascending=False, kind="stable")
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
        x = pd.to_numeric(raw[col], errors="coerce")
        filled = int(ids[present & x.notna()].nunique())
        if filled == 0:
            continue
        how = (chosen or {}).get(col) or default_how(col)
        used = col in chosen if chosen is not None else True
        mviews.append(MeasureView(column=col, parcels=filled, how=how, used=used))
    n_fields = sum(1 for g in groups if g.values) + sum(1 for m in mviews if m.used) + (1 if main_on else 0)
    return CombinePreview(
        abouts=abouts, about=about, values=values, groups=list(groups), group_parcels=group_parcels, none=none,
        measures=mviews, main=order, main_on=main_on, main_parcels=main_parcels, rows=rows, parcels=parcels,
        fields=n_fields,
    )  # fmt: skip


def _abouts(files: Any, name: str, ids: Any, text_cols: list[str]) -> list[str]:
    """Text columns that say what each of an ID's rows is about: different on each of its rows, few values in all.
    The ones that tell an ID's rows apart best first."""
    import pandas

    pd: Any = pandas  # typed loosely: this is all frames and series

    scored = []
    for col in text_cols:
        v = pd.Series(files.values(name, col, source=True), dtype=object)
        distinct = v.nunique()
        if distinct < 2 or distinct > MAX_VALUES:
            continue
        pairs = pd.DataFrame({"id": ids, "v": v})[ids != ""]
        repeats = int(pairs.duplicated().sum())  # an ID with the same value twice: not what tells its rows apart
        scored.append((repeats, distinct, col))
    return [c for _r, _d, c in sorted(scored)]


# ---------- saving ----------


def set_combine(
    project: Project,
    in_dir: Path,
    name: str,
    about: str,
    groups: list[CombineGroup],
    measures: dict[str, CombineHow],
    main: list[str] | None,
) -> None:
    """Combine a parcel file's rows (or change how): the combined file made, the project loading it, and its fields
    the user's own (Your own fields: land), there to use."""
    from oakbox.wizard.files import Files

    files = Files(project, in_dir)
    f = files.entry(name)
    if f.holds != "parcels" or name == project.wizard.base:
        raise ValueError("Only a file of more parcel details can have its rows combined.")
    columns = {c.name for c in files.columns(name, source=True)}
    for col in [about, *measures]:
        if col not in columns:
            raise ValueError(f"{name} has no column {col}.")
    groups = [g for g in groups if g.values and g.name.strip()]
    names = [group_field(g.name) for g in groups]
    if len(set(names)) != len(names):
        raise ValueError("Two groups have the same name.")
    source = f.combine.source if f.combine else f.filename
    _drop_fields(project, f)
    f.combine = Combine(source=source, about=about, groups=groups, measures=measures, main=main or None)
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

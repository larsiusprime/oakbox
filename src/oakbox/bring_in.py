"""Step 1, Bring in data: OpenAVMKit loads the files as the Data wizard set them up and joins them into the
parcel universe and the sales record, enriched; then a receipt of what came out (SPEC §3.3).

The run is OpenAVMKit's 1-assemble up to model groups (load_dataframes, process_dataframes), in a process of its
own: `python -m oakbox.bring_in <project id>`. It prints one JSON line per step and writes its results to
out/oakbox/bring_in/ (in a temporary folder first, so a stopped or failed run leaves the last good one):

- receipt.json: the receipt, and settings.json: the settings it ran with (to say what changed since);
- universe.parquet and sales.parquet: the parcel universe and the sales record (no shapes), for the row viewer;
- rows/<set>.parquet: the rows behind each count (dropped rows as written in their file);
- sup.pickle: the SalesUniversePair, for model groups.

Parquet is written in small row groups, so a page of rows reads only the groups it needs.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import BaseModel
from oakbox.enrichments import SOURCES, EnrichResult, instrument, recount

ROW_GROUP = 1_000
PAGE = 50
HELPER_SUFFIXES = ("_src", "_raw", "_text", "_num_src")


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "bring_in"


# ---------- The receipt ----------


class Line(BaseModel):
    op: Literal["", "−", "+", "="] = ""
    n: int
    text: str
    rows: str | None = Field(default=None, description="The row set behind it, for See them.")


class Funnel(BaseModel):
    file: str = Field(description="The file it's about (as added).")
    filename: str = Field(default="", description="Its file's name, as the user knows it.")
    lines: list[Line]
    note: str | None = None


class FieldRow(BaseModel):
    field: str
    group: Literal["files", "layers", "public", "engine"]
    filled: int
    share: float
    summary: str
    source: str
    note: str | None = None


class Said(BaseModel):
    what: str
    said: str
    got: str
    ok: bool


class Dataset(BaseModel):
    rows: int
    funnels: list[Funnel]
    fields: list[FieldRow]


class Receipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    universe: Dataset = Field(description="The parcel universe.")
    sales: Dataset = Field(description="The sales record.")
    checks: list[Said] = Field(description="What the Data wizard said, against what OpenAVMKit got.")
    notes: list[str] = Field(description="What OpenAVMKit warned about.")
    notices: int = Field(description="Warnings from the libraries it uses, not shown.")
    timings: list[list] = Field(description="[step, seconds].")
    enrichments: list[EnrichResult] = Field(default_factory=list, description="Public data (F3e), as it went.")


def settings_key(settings: dict) -> dict:
    """The parts of the settings this step depends on."""
    return {k: settings.get(k) for k in ("data", "field_classification", "locality")}


def settings_hash(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings_key(settings), sort_keys=True, default=str).encode()).hexdigest()[:16]


def changes(old: dict, new: dict) -> list[str]:
    """What changed in the settings since a run, in words: the files and the parts of processing."""
    out: list[str] = []
    a, b = old.get("data", {}), new.get("data", {})
    la, lb = a.get("load", {}), b.get("load", {})
    for name in lb:
        if name not in la:
            out.append(f"{name} added")
        elif la[name] != lb[name]:
            out.append(f"how {name} is read")
    out += [f"{name} removed" for name in la if name not in lb]
    pa, pb = a.get("process", {}), b.get("process", {})
    if pa.get("merge") != pb.get("merge"):
        out.append("how the files join")
    ea, eb = pa.get("enrich", {}), pb.get("enrich", {})
    if ea.get("geometry") != eb.get("geometry") or _layers(ea) != _layers(eb):
        out.append("map layers")
    for part, words in (("overture", "building footprints"), ("census", "census"), ("dem", "elevation")):
        if ea.get(part) != eb.get(part):
            out.append(words)
    if _osm(ea) != _osm(eb):
        out.append("distances to OpenStreetMap features")
    if ea.get("ref_tables") != eb.get("ref_tables"):
        out.append("how sales find their parcel")
    if old.get("locality") != new.get("locality"):
        out.append("the centre")
    if pa.get("condos") != pb.get("condos"):
        out.append("condo units")
    fa, fb = old.get("field_classification", {}), new.get("field_classification", {})
    if fa.get("important") != fb.get("important"):
        out.append("location fields")
    if _own(old, fa) != _own(new, fb):
        out.append("your own fields")
    return list(dict.fromkeys(out))


def _osm(enrich: dict) -> dict:
    return {k: v for k, v in enrich.get("distances", {}).items() if isinstance(v, dict) and v.get("osm")}


def _layers(enrich: dict) -> dict:
    return {k: v for k, v in enrich.get("distances", {}).items() if isinstance(v, dict) and not v.get("osm")}


def _own(settings: dict, fc: dict) -> dict:
    """The user's own classified fields: field_classification's land / impr / other, without map layers' fields."""
    stamped = {
        x
        for g in settings.get("data", {}).get("process", {}).get("enrich", {}).get("geometry", [])
        for x in g["fields"]
    }
    return {
        (bucket, kind): sorted(set(names) - stamped)
        for bucket in ("land", "impr", "other")
        for kind, names in fc.get(bucket, {}).items()
    }


# ---------- Reading the results: a page of rows, or all of them as CSV ----------


class Rows(BaseModel):
    set: str
    total: int
    offset: int
    columns: list[str]
    rows: list[list[str]]
    kept: list[bool] | None = Field(default=None, description="Repeated IDs: per row, the one kept.")
    kept_total: int | None = Field(default=None, description="Repeated IDs: how many of the set's rows are kept.")
    bands: list[int] | None = Field(
        default=None,
        description="Repeated IDs (sorted by the ID, its first column): 0 or 1 per row, alternating per ID, so the "
        "rows of one ID share a background.",
    )


def bands(values) -> list[int]:
    """0 or 1 per row, changing where the value does: the rows of one ID share a background, IDs alternate."""
    out, band, last = [], 1, object()
    for v in values:
        if v != last:
            band, last = 1 - band, v
        out.append(band)
    return out


def by_id(df, ids):
    """Rows of repeated IDs, the ID column first and the rows sorted by it (each ID's rows in file order)."""
    values = [str(v) for v in ids]
    # Numbers in an ID as numbers: 99 before 100.
    order = sorted(range(len(values)), key=lambda i: _natural(values[i]))
    out = df.iloc[order]
    column = getattr(ids, "name", None)
    if column in out.columns:
        out = out[[column, *[c for c in out.columns if c != column]]]
    return out


def _rows_path(project_dir: Path, name: str) -> Path:
    base = out_dir(project_dir)
    if name in ("universe", "sales"):
        return base / f"{name}.parquet"
    if not name.replace("_", "").isalnum():
        raise LookupError(name)
    return base / "rows" / f"{name}.parquet"


def _text(df) -> list[list[str]]:
    import pandas as pd

    def cell(v) -> str:
        if v is None or (not isinstance(v, (list, tuple)) and pd.isna(v)):
            return ""
        if isinstance(v, float):
            return f"{v:,.2f}".rstrip("0").rstrip(".") if v != round(v) or abs(v) >= 1e15 else f"{v:.0f}"
        if isinstance(v, (pd.Timestamp, dt.datetime)):
            midnight = (v.hour, v.minute, v.second, v.microsecond) == (0, 0, 0, 0)
            return v.strftime("%Y-%m-%d") if midnight else v.strftime("%Y-%m-%d %H:%M")
        return str(v)

    return [[cell(v) for v in row] for row in df.itertuples(index=False, name=None)]


def _natural(v: str) -> list:
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", v) if p]


# The column marking each repeated row: a name no assessor's file uses.
MARK, KEPT, LEFT_OUT = "kept?", "✓ kept", "left out"


def _repeats(raw, ids, dropped, blank, f, field: str):
    """Every row of each repeated ID, the one kept marked as kept (none when all are dropped), sorted by the ID: the
    kept row is what the others are judged against."""
    group = ids.isin(set(ids[dropped])) & ~blank
    rows = raw[group].copy()
    rows.insert(0, MARK, [LEFT_OUT if d else KEPT for d in dropped[group]])
    return by_id(rows, _named(ids[group], f, field))


def _named(ids, f, field: str):
    """The IDs, named as their column in the file, to sort and lead the rows by."""
    return ids.reset_index(drop=True).rename(f.load.get(field, [None])[0])


def page(project_dir: Path, name: str, offset: int, limit: int = PAGE) -> Rows:
    """Rows offset.. of a set, reading only the row groups they're in."""
    import pyarrow.parquet as pq

    path = _rows_path(project_dir, name)
    if not path.is_file():
        raise LookupError(name)
    pf = pq.ParquetFile(path)
    total = pf.metadata.num_rows
    offset = max(0, min(offset, max(0, total - 1)))
    limit = max(1, min(limit, 500))
    groups, start, first = [], 0, None
    for g in range(pf.num_row_groups):
        n = pf.metadata.row_group(g).num_rows
        if start + n > offset and start < offset + limit:
            groups.append(g)
            first = start if first is None else first
        start += n
    df = pf.read_row_groups(groups).to_pandas() if groups else pf.schema_arrow.empty_table().to_pandas()
    skip = offset - (first or 0)
    df = df.iloc[skip : skip + limit]
    banded, kept, kept_total = None, None, None
    if name.endswith("_repeats") and total:
        # Bands over the whole set, so they carry on from one page to the next.
        first_col = pf.schema_arrow.names[0]
        banded = bands(pf.read(columns=[first_col]).column(0).to_pylist())[offset : offset + len(df)]
        if MARK in df.columns:
            kept = [v == KEPT for v in df[MARK]]
            kept_total = sum(v == KEPT for v in pf.read(columns=[MARK]).column(0).to_pylist())
    return Rows(
        set=name,
        total=total,
        offset=offset,
        columns=[str(c) for c in df.columns],
        rows=_text(df),
        bands=banded,
        kept=kept,
        kept_total=kept_total,
    )


class Stat(BaseModel):
    label: str
    value: str


class ValueN(BaseModel):
    value: str
    count: int


class FieldProfile(BaseModel):
    """One field of the parcel universe or sales record in detail: notebook 1's "examine in ridiculous detail"."""

    field: str
    rows: int
    blank: int
    kind: Literal["number", "category", "date", "yes/no"]
    distinct: int = Field(description="Different values, not counting blank.")
    stats: list[Stat] = Field(description="Numbers: count, zero, lowest, percentiles, mean, highest. Dates: range.")
    values: list[ValueN] = Field(description="Most common first (dates: by year). At most 500, after the search.")
    more: int


PROFILE_VALUES = 500


def profile(
    project_dir: Path,
    name: str,
    field: str,
    search: str = "",
    sort: Literal["count", "value"] | None = None,
    desc: bool = True,
) -> FieldProfile:
    """A field's summary statistics (numbers) or its values with counts (everything else), read from one column."""
    import pandas as pd
    import pyarrow.parquet as pq

    from oakbox.wizard import _g, sort_counts

    if name not in ("universe", "sales"):
        raise LookupError(name)
    path = _rows_path(project_dir, name)
    if not path.is_file() or field not in pq.ParquetFile(path).schema_arrow.names:
        raise LookupError(field)
    s = pd.read_parquet(path, columns=[field])[field]
    rows, filled = len(s), s.dropna()
    stats: list[Stat] = []
    if pd.api.types.is_bool_dtype(filled):
        kind = "yes/no"
        counts = filled.map(lambda b: "yes" if b else "no").value_counts()
    elif pd.api.types.is_numeric_dtype(filled):
        kind = "number"
        x = pd.Series(filled.astype(float))
        year = "year" in field
        g = (lambda v: f"{v:.0f}") if year else _g
        if len(x):
            q = {p: float(x.quantile(p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9)}
            stats = [
                Stat(label="filled", value=f"{len(x):,}"),
                Stat(label="zero", value=f"{int((x == 0).sum()):,}"),
                Stat(label="lowest", value=g(float(x.min()))),
                Stat(label="10%", value=g(q[0.1])),
                Stat(label="25%", value=g(q[0.25])),
                Stat(label="median", value=g(q[0.5])),
                Stat(label="75%", value=g(q[0.75])),
                Stat(label="90%", value=g(q[0.9])),
                Stat(label="highest", value=g(float(x.max()))),
                Stat(label="mean", value=g(float(x.mean()))),
            ]
        counts = x.map(g).value_counts()
    elif pd.api.types.is_datetime64_any_dtype(filled):
        kind = "date"
        if len(filled):
            stats = [
                Stat(label="earliest", value=f"{filled.min():%Y-%m-%d}"),
                Stat(label="latest", value=f"{filled.max():%Y-%m-%d}"),
            ]
        counts = filled.dt.year.astype(str).value_counts().sort_index()
    else:
        kind = "category"
        counts = filled.astype(str).value_counts()
    q = search.strip().lower()
    hits = [(str(v), int(n)) for v, n in counts.items() if not q or q in str(v).lower()]
    hits = sort_counts(hits, sort, desc)
    return FieldProfile(
        field=field,
        rows=rows,
        blank=rows - len(filled),
        kind=kind,
        distinct=len(counts),
        stats=stats,
        values=[ValueN(value=v, count=n) for v, n in hits[:PROFILE_VALUES]],
        more=max(0, len(hits) - PROFILE_VALUES),
    )


def csv_chunks(project_dir: Path, name: str):
    """The whole set as CSV, a row group at a time."""
    import pyarrow.parquet as pq

    path = _rows_path(project_dir, name)
    if not path.is_file():
        raise LookupError(name)
    pf = pq.ParquetFile(path)
    for g in range(pf.num_row_groups):
        yield pf.read_row_group(g).to_pandas().to_csv(index=False, header=g == 0)
    if pf.num_row_groups == 0:
        yield ",".join(pf.schema_arrow.names) + "\n"


# ---------- The run (in its own process) ----------


def _emit(**kw) -> None:
    print(json.dumps(kw), flush=True)


def _write(df, path: Path) -> None:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(df.drop(columns=[c for c in ("geometry",) if c in df.columns]))
    for c in df.columns:  # mixed columns (a code that's sometimes a number) as text, so Parquet takes them
        if isinstance(df[c].dtype, pd.CategoricalDtype) and df[c].cat.categories.dtype == object:
            df[c] = df[c].astype(object)  # categories of mixed types (dates and text): the same
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and v != v) else str(v))
    df.reset_index(drop=True).to_parquet(path, index=False, row_group_size=ROW_GROUP)


def _summary(s, name: str = "") -> str:
    import pandas as pd

    from oakbox.wizard import _g

    s = s.dropna()
    if s.empty:
        return ""
    if pd.api.types.is_bool_dtype(s):
        return f"{int(s.sum()):,} yes · {int((~s.astype(bool)).sum()):,} no"
    if pd.api.types.is_datetime64_any_dtype(s):
        return f"{s.min():%Y-%m-%d} to {s.max():%Y-%m-%d}"
    if pd.api.types.is_numeric_dtype(s):
        x = s.astype(float)
        g = (lambda v: f"{v:.0f}") if "year" in name else _g  # 1987, not 1,987
        return f"{g(x.min())} · median {g(x.median())} · {g(x.max())}"
    counts = s.astype(str).value_counts()
    if len(counts) == len(s):
        return f"{len(s):,} values, all different"
    top = ", ".join(f"{v} ({n:,})" for v, n in counts.head(3).items())
    return f"{len(counts):,} values · most: {top}"


def _raw(files, entry, columns=None):
    """A file's rows as written (no shapes), every column as text."""
    import pandas as pd

    from oakbox.wizard import _stamp, _values

    cols = columns or [c.name for c in files.columns(entry.name)]
    stamp = _stamp(files.in_dir / entry.filename)
    return pd.DataFrame({c: _values(stamp, entry.layer, c, raw=True) for c in cols})


def _clear_cache_if_rows_change(pdir: Path, settings: dict) -> None:
    """Condo units change which rows the parcel universe has, and OpenAVMKit's enrichment cache refuses a
    different set of rows (it stops rather than recompute): clear it when condo handling changes."""
    ran = out_dir(pdir) / "settings.json"
    before = (
        json.loads(ran.read_text(encoding="utf-8")).get("data", {}).get("process", {}).get("condos")
        if ran.is_file()
        else None
    )
    now = settings.get("data", {}).get("process", {}).get("condos")
    if before != now and (pdir / "cache").is_dir():
        shutil.rmtree(pdir / "cache", ignore_errors=True)


def run(project_id: str) -> None:
    """Load and join, then write the receipt and the rows behind it (see the module's docstring)."""
    import warnings

    import pandas as pd

    from oakbox import projects, wizard
    from oakbox.datafiles import AREA_FIELDS

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    in_dir = pdir / "in"
    tmp = out_dir(pdir).with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    settings_text = (in_dir / "settings.json").read_text(encoding="utf-8")
    _clear_cache_if_rows_change(pdir, json.loads(settings_text))
    os.chdir(pdir)
    from importlib.metadata import version

    from openavmkit import pipeline as pl

    enriched = instrument(json.loads(settings_text), _emit)
    timings: list[list] = []
    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _emit(step="load", fraction=0.0, message="Loading data files")
        settings = pl.load_settings()
        dfs = pl.load_dataframes(settings)
        timings.append(["load_dataframes", round(time.time() - t0, 1)])
        _emit(step="join", fraction=0.2, message="Joining and enriching: map layers, distances, coordinates")
        t1 = time.time()
        sup = pl.process_dataframes(dfs, pl.load_settings())
        timings.append(["process_dataframes", round(time.time() - t1, 1)])
    _emit(step="receipt", fraction=0.85, message="Counting and saving")
    t2 = time.time()
    universe, sales = sup.universe, sup.sales
    recount(enriched, universe)
    files = wizard._Files(project, in_dir)
    base = wizard._base(project)
    keys = set(universe["key"].astype(str))
    rows_dir = tmp / "rows"

    def save(name: str, df) -> str | None:
        if len(df) == 0:
            return None
        _write(df, rows_dir / f"{name}.parquet")
        return name

    # The parcel universe: the base file, then each file joined to it.
    u_funnels: list[Funnel] = []
    predicted = 0
    if base is not None:
        raw = _raw(files, base)
        ids = pd.Series(files.ids(base.name, "key"))
        blank = ids == ""
        repeated = ids.duplicated(keep="first") & ~blank
        if base.dupes == "all":
            repeated = ids.duplicated(keep=False) & ~blank
        predicted = int((~blank & ~repeated).sum())
        what = "shapes" if files.geometry(base.name) else "rows"
        lines = [Line(n=len(raw), text=f"{what} in {base.filename}")]
        if blank.any():
            lines.append(
                Line(
                    op="−",
                    n=int(blank.sum()),
                    text="without a parcel ID: dropped",
                    rows=save("universe_no_id", raw[blank]),
                )
            )
        if repeated.any():
            how = "all dropped" if base.dupes == "all" else "the first kept"
            lines.append(
                Line(
                    op="−",
                    n=int(repeated.sum()),
                    text=f"repeated parcel IDs: {how}",
                    rows=save("universe_repeats", _repeats(raw, ids, repeated, blank, base, "key")),
                )
            )
        units_f = projects.units_file(project)
        borrowed = (
            int(universe["geometry_borrowed"].fillna(False).astype(bool).sum())
            if "geometry_borrowed" in universe
            else 0
        )
        if units_f is not None:
            # Condo units with no shape of their own: in the parcel universe with their building's (F3d).
            predicted += wizard._units_view(project, files, units_f).linked
            lines.append(Line(op="+", n=borrowed, text=f"units from {units_f.filename}, with their building's shape"))
        lines.append(Line(op="=", n=len(universe), text="parcels in the parcel universe"))
        u_funnels.append(Funnel(file=base.name, filename=base.filename, lines=lines))
    for f in project.files:
        if f.holds != "parcels" or f is base or f.name not in files.preview or f.match not in f.load:
            continue
        raw = _raw(files, f)
        ids = pd.Series(files.ids(f.name, f.match))
        blank = ids == ""
        extra = ids.duplicated(keep=False if f.dupes == "all" else "first") & ~blank
        orphan = ~blank & ~extra & ~ids.isin(keys)
        joined = ~blank & ~extra & ~orphan
        lines = [Line(n=len(raw), text=f"rows in {f.filename}")]
        if blank.any():
            lines.append(
                Line(op="−", n=int(blank.sum()), text="without a parcel ID", rows=save(f"{f.name}_no_id", raw[blank]))
            )
        if extra.any():
            how = "all dropped" if f.dupes == "all" else "the first kept"
            lines.append(
                Line(
                    op="−",
                    n=int(extra.sum()),
                    text=f"more than one row for a parcel: {how}",
                    rows=save(f"{f.name}_repeats", _repeats(raw, ids, extra, blank, f, f.match)),
                )
            )
        if orphan.any():
            lines.append(
                Line(
                    op="−",
                    n=int(orphan.sum()),
                    text="units that find no building: left out"
                    if f.units is not None
                    else "for a parcel not in the parcel universe",
                    rows=save(f"{f.name}_orphans", raw[orphan]),
                )
            )
        lines.append(Line(op="=", n=int(joined.sum()), text="parcels in the parcel universe with a row from it"))
        have = set(ids[joined])
        missing = universe[~universe["key"].astype(str).isin(list(have))]
        lines.append(
            Line(
                n=len(missing),
                text="parcels in the parcel universe without one",
                rows=save(f"{f.name}_missing", missing),
            )
        )
        note = None
        if "bldg_area_finished_sqft" in f.load or any(k in f.load for k in AREA_FIELDS if k.startswith("bldg")):
            note = "OpenAVMKit treats a parcel without a building size as vacant land: its building fields are 0."
        u_funnels.append(Funnel(file=f.name, filename=f.filename, lines=lines, note=note))

    # The sales record: the main sales file, then sales details joined to it.
    s_funnels: list[Funnel] = []
    # The parcels Data predicted: the parcel shapes, and the units that find their building.
    said_keys = (
        (set(pd.Series(files.ids(base.name, "key"))) - {""}) | wizard._unit_ids(files) if base is not None else keys
    )
    main = wizard._sales_file(project)
    said_valid = said_share = None
    if main is not None and main.name in files.preview:
        raw = _raw(files, main)
        ids = pd.Series(files.ids(main.name, main.match))
        rule = main.rules.get("valid_sale")
        if rule is not None and wizard._complete(rule):
            valid = pd.Series(wizard._rule_result(files, main, rule)[2].tolist())
            how = "not valid by your valid-sale rule: left out as they load"
        elif "valid_sale" in main.load:
            col = wizard._values(wizard._stamp(in_dir / main.filename), main.layer, main.load["valid_sale"][0])
            valid = pd.Series([v.lower() in wizard.YES for v in col])
            how = "not valid by your valid-sale column: left out as they load"
        else:
            valid = pd.Series([True] * len(raw))
            how = ""
        said_valid = int(valid.sum())
        lines = [Line(n=len(raw), text=f"sales in {main.filename}")]
        if (~valid).any():
            lines.append(
                Line(op="−", n=int((~valid).sum()), text=how, rows=save("sales_invalid", raw[~valid.to_numpy()]))
            )
        if len(sales) != said_valid:
            lines.append(Line(op="−", n=said_valid - len(sales), text="repeated sale IDs: the first kept"))
        lines.append(Line(op="=", n=len(sales), text="valid sales in the sales record"))
        if "vacant_sale" in sales:
            vacant = int(sales["vacant_sale"].fillna(False).astype(bool).sum())
            lines += [Line(n=len(sales) - vacant, text="improved"), Line(n=vacant, text="vacant")]
            if "is_teardown_sale" in sales:
                # Permits (F3g): sold, then demolished soon after: a sale of the land.
                torn = sales["is_teardown_sale"].fillna(False).astype(bool)
                days = settings.get("data", {}).get("process", {}).get("enrich", {}).get("permits", {})
                within = days.get("max_days_to_demo", 365)
                lines.append(
                    Line(
                        n=int(torn.sum()),
                        text=f"of them teardown sales: demolished within {within} days, so counted as vacant",
                        rows=save("sales_teardown", sales[torn.to_numpy()]),
                    )
                )
        unmatched = sales[~sales["key"].astype(str).isin(list(keys))]
        said_share = float(ids.loc[valid.to_numpy()].isin(list(said_keys)).mean()) if said_valid else None
        lines.append(
            Line(
                n=len(unmatched),
                text="don't find a parcel in the parcel universe: they can't be modeled",
                rows=save("sales_unmatched", unmatched),
            )
        )
        s_funnels.append(Funnel(file=main.name, filename=main.filename, lines=lines))

    # Fields: where each came from, how many have it, and what it looks like, from the settings it ran with:
    # a column loaded as it is, or worked out by a calc from one (a scale, a rule, an area in other units).
    loaded: dict[str, str] = {}
    sales_loaded: dict[str, str] = {}
    holds = {f.name: f.holds for f in project.files}
    for name, entry in settings.get("data", {}).get("load", {}).items():
        mine_ = sales_loaded if holds.get(name) == "sales" else loaded
        load = {k: (v[0] if isinstance(v, list) else v) for k, v in entry.get("load", {}).items()}
        for k, col in load.items():
            mine_.setdefault(k, f"{name} · {col}")
        for k, calc in entry.get("calc", {}).items():
            col = next((load[k + s] for s in ("_src", "_text") if k + s in load), None)
            col = col or next((c for x, c in load.items() if x.startswith(k + "_in_")), None)
            if k in load:
                mine_[k] = f"{name} · {load[k]}, cleaned up"
            elif k in ("valid_sale", "vacant_sale") and calc and calc[0] == "?":
                mine_[k] = f"{name} · your {k.split('_')[0]}-sale rule"
            elif k == "key_sale":
                mine_[k] = f"{name} · made from the parcel ID and sale date"
            else:
                mine_[k] = f"{name} · {col}" if col else f"{name} · worked out from its columns"
    for loc in project.wizard.locations:
        loaded.setdefault(loc, "location")
    stamped: dict[str, str] = {}
    measured: dict[str, tuple[str, float | None, str]] = {}
    for f in project.files:
        if f.holds == "overlay" and f.overlay is not None:
            if f.overlay.use == "stamp":
                for sf in f.overlay.fields:
                    stamped[sf.name] = f.filename
            elif f.overlay.use == "distance":
                measured[f.overlay.feature or f.name] = (f.filename, f.overlay.max_distance, f.overlay.unit)
    vacant_n = int(universe["is_vacant"].fillna(False).astype(bool).sum()) if "is_vacant" in universe else 0

    public = {c: SOURCES[r.key] for r in enriched for c in r.fields}

    def fields_of(df, mine: dict[str, str], is_universe: bool) -> list[FieldRow]:
        out = []
        for col in df.columns:
            if col == "geometry" or str(col).endswith(HELPER_SUFFIXES) or "_in_" in str(col):
                continue
            s = df[col]
            filled = int(s.notna().sum())
            note = None
            if col in stamped:
                group, source = "layers", stamped[col]
                if filled < len(df):
                    note = "only parcels in one of its shapes have it"
            elif any(
                str(col).endswith(f"_{name}") and str(col).split("_")[0] in ("dist", "within", "proximity")
                for name in measured
            ):
                name = next(n for n in measured if str(col).endswith(f"_{n}"))
                group, source = "layers", measured[name][0]
                if filled < len(df) and measured[name][1]:
                    note = f"within {measured[name][1]:g} {measured[name][2]}s; farther away is blank"
            elif col in public:
                group, source = "public", public[col]
            elif col in mine or col in ("key", "key_sale", "valid_sale", "vacant_sale"):
                group, source = "files", mine.get(col, "your files")
            else:
                group, source = "engine", "OpenAVMKit"
            if is_universe and str(col).startswith("bldg_") and vacant_n and pd.api.types.is_numeric_dtype(s):
                zeros = int((s == 0).sum())
                if zeros:
                    note = f"{zeros:,} are 0: no building (vacant land)"
                    s = s.where(s != 0)
            out.append(
                FieldRow(
                    field=str(col),
                    group=group,
                    filled=filled,
                    share=filled / len(df) if len(df) else 0,
                    summary=_summary(s, str(col)),
                    source=source,
                    note=note,
                )
            )
        order = {"files": 0, "layers": 1, "public": 2, "engine": 3}
        return sorted(out, key=lambda r: order[r.group])

    u_fields = fields_of(universe, loaded, True)
    s_fields = fields_of(sales, sales_loaded, False)
    if "land_area_given_sqft" in universe:
        missing = int(universe["land_area_given_sqft"].isna().sum())
        for r in u_fields:
            if r.field == "land_area_sqft" and missing:
                r.note = f"{missing:,} had none in their file: measured from the shape"

    checks = []
    if base is not None:
        checks.append(
            Said(
                what="Parcels in the parcel universe",
                said=f"{predicted:,}",
                got=f"{len(universe):,}",
                ok=predicted == len(universe),
            )
        )
    if said_valid is not None:
        checks.append(
            Said(what="Valid sales", said=f"{said_valid:,}", got=f"{len(sales):,}", ok=said_valid == len(sales))
        )
    if said_share is not None and len(sales):
        got = float(sales["key"].astype(str).isin(list(keys)).mean())
        checks.append(
            Said(
                what="Valid sales finding a parcel",
                said=f"{100 * said_share:.1f}%",
                got=f"{100 * got:.1f}%",
                ok=abs(got - said_share) < 0.001,
            )
        )
    for lv in wizard.layers(project, in_dir):
        o = next((f.overlay for f in project.files if f.name == lv.name), None)
        if o is None or o.use != "stamp" or not o.fields or o.fields[0].name not in universe:
            continue
        entry = next(f for f in project.files if f.name == lv.name)
        if base is None or not lv.projected:
            continue
        one, several, none = wizard._coverage(
            wizard._stamp(in_dir / base.filename), base.layer, wizard._stamp(in_dir / entry.filename), entry.layer
        )
        # Units take their building's shape, and its layers with it: compared over parcels with shapes of their own.
        own = (
            ~pd.Series(universe["geometry_borrowed"]).fillna(False).astype(bool)
            if "geometry_borrowed" in universe
            else None
        )
        stamped_col = pd.Series(universe[o.fields[0].name])
        got_n = int(stamped_col.loc[own].notna().sum() if own is not None else stamped_col.notna().sum())
        # Counted over the file's shapes (some dropped since, without an ID): "every parcel" when none were outside.
        said = "every parcel" if none == 0 else f"{one + several:,}"
        shaped = int(own.sum()) if own is not None else len(universe)
        got = "every parcel" if got_n == shaped else f"{got_n:,}"
        ok = said == got or abs(one + several - got_n) <= max(1, 0.001 * len(universe))
        what = f"Parcels in a {lv.name} shape" + (
            " (units take their building's)" if own is not None and not bool(own.all()) else ""
        )
        checks.append(Said(what=what, said=said, got=got, ok=ok))

    mine = [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]
    notes = list(dict.fromkeys(str(w.message) for w in mine))[:20]
    _write(universe, tmp / "universe.parquet")
    _write(sales, tmp / "sales.parquet")
    pd.to_pickle(sup, tmp / "sup.pickle")
    timings.append(["receipt", round(time.time() - t2, 1)])
    receipt = Receipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        universe=Dataset(rows=len(universe), funnels=u_funnels, fields=u_fields),
        sales=Dataset(rows=len(sales), funnels=s_funnels, fields=s_fields),
        checks=checks,
        notes=notes,
        notices=len(caught) - len(mine),
        timings=timings,
        enrichments=enriched,
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(settings_text, encoding="utf-8")
    final = out_dir(pdir)
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    _emit(step="done", fraction=1.0, message=f"{len(universe):,} parcels, {len(sales):,} valid sales")


# ---------- The job, from the app ----------


class Progress(BaseModel):
    step: str
    message: str
    fraction: float | None
    at: float = Field(description="Seconds since the run started.")


class Job(BaseModel):
    status: Literal["running", "failed", "stopped", "done"]
    started: float
    steps: list[Progress] = Field(default_factory=list)
    error: str | None = None


_jobs: dict[str, Job] = {}
_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def start(project_id: str, project_dir: Path, module: str = "bring_in") -> Job:
    """Run `python -m oakbox.<module> <project id>` in a process of its own, following the JSON step lines it
    prints. One run per module and project at a time; its log is out/oakbox/<module>.log."""
    key = f"{module}:{project_id}"
    with _lock:
        if key in _jobs and _jobs[key].status == "running":
            raise ValueError("It's already running.")
        log = project_dir / "out" / "oakbox" / f"{module}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(  # noqa: S603 - our own module, with the project's id
            [sys.executable, "-X", "utf8", "-m", f"oakbox.{module}", project_id],
            stdout=subprocess.PIPE,
            stderr=log.open("w", encoding="utf-8"),
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
        )
        job = Job(status="running", started=time.time())
        _jobs[key], _procs[key] = job, proc

    def follow() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # OpenAVMKit prints as it goes
            if "step" in msg:
                job.steps.append(
                    Progress(
                        step=msg["step"],
                        message=msg["message"],
                        fraction=msg.get("fraction"),
                        at=time.time() - job.started,
                    )
                )
        code = proc.wait()
        if job.status == "running":
            if code == 0:
                job.status = "done"
            else:
                job.status = "failed"
                tail = (
                    log.read_text(errors="replace", encoding="utf-8").strip().splitlines()[-1:] if log.is_file() else []
                )
                job.error = tail[0] if tail else f"stopped with code {code}"

    threading.Thread(target=follow, daemon=True).start()
    return job


def child_env() -> dict[str, str]:
    """A run's environment: Python's UTF-8 mode, so OpenAVMKit reads, writes and prints UTF-8 on Windows too (not
    the code page, cp1252, which can't write a "−"); and the user's keys for public data."""
    return {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "ignore::DeprecationWarning",
        **_keys(),
    }


def _keys() -> dict[str, str]:
    """The user's own keys for public data, from OAK box's settings, as OpenAVMKit reads them."""
    from oakbox import appsettings

    key = appsettings.load().census_api_key
    return {"CENSUS_API_KEY": key} if key else {}


def stop(project_id: str, module: str = "bring_in") -> None:
    key = f"{module}:{project_id}"
    proc = _procs.get(key)
    job = _jobs.get(key)
    if proc is None or job is None or job.status != "running":
        return
    job.status = "stopped"
    proc.terminate()


def job(project_id: str, module: str = "bring_in") -> Job | None:
    return _jobs.get(f"{module}:{project_id}")


class Plan(BaseModel):
    files: list[str] = Field(description="What's loaded, in words: the parcel universe, the sales record, the rest.")
    layers: list[str]
    enrichments: list[str] = Field(description="Public data downloaded as it runs (F3e).")
    fields: int


class View(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: Job | None
    receipt: Receipt | None
    stale: bool = Field(description="The settings changed since it ran.")
    changed: list[str]
    blocked: list[str] = Field(description="Data wizard problems that stop it running.")
    accepted: bool = Field(description="Looks right was pressed on this receipt, and nothing changed since.")
    plan: Plan


def plan(project, in_dir: Path) -> Plan:
    from oakbox import wizard

    files = wizard._Files(project, in_dir)
    base = wizard._base(project)
    out, layers = [], []
    for f in project.files:
        rows = files.preview[f.name].rows if f.name in files.preview else None
        n = f" ({rows:,} rows)" if rows is not None else ""
        if f is base:
            out.insert(0, f"the parcel universe: {f.filename}{n}")
        elif f.holds == "sales":
            out.append(
                f"the sales record: {f.filename}{n}" if f.match != "key_sale" else f"sale details: {f.filename}{n}"
            )
        elif f.holds == "parcels":
            how = "the first row per parcel" if f.dupes != "all" else "parcels with one row"
            out.append(f"joined to the parcel universe: {f.filename}{n}, {how}")
        elif f.holds == "overlay" and f.overlay is not None and f.overlay.use:
            use = "stamped onto parcels" if f.overlay.use == "stamp" else "distances measured to it"
            layers.append(f"{f.name}: {use}")
    loaded = {k for f in project.files if f.holds in ("parcels", "sales") for k in f.load} - {"key", "key_sale"}
    e = project.enrich
    public = []
    if e is not None:
        n = sum(1 for f in e.features.values() if f.on) if e.distances else 0
        public = [
            *([f"distances to {n} OpenStreetMap features"] if n else []),
            *(["building footprints (Overture Maps)"] if e.footprints else []),
            *(["census figures"] if e.census and e.fips else []),
            *(["elevation (USGS)"] if e.elevation else []),
        ]
    return Plan(files=out, layers=layers, enrichments=public, fields=len(loaded) + len(project.wizard.locations))


def view(project, project_dir: Path, problems: list[str]) -> View:
    current = json.loads((project_dir / "in" / "settings.json").read_text(encoding="utf-8"))
    r, ran = receipt(project_dir)
    j = job(project.id)
    stale = bool(r and ran and settings_hash(ran) != settings_hash(current))
    accepted = bool(r and not stale and project.accepted.get("bring_in") == settings_hash(current))
    status = j.status if j else ("done" if r else "never")
    return View(
        status=status,
        job=j,
        receipt=r,
        stale=stale,
        changed=changes(ran, current) if stale and ran else [],
        blocked=problems,
        accepted=accepted,
        plan=plan(project, project_dir / "in"),
    )


def accept(project, project_dir: Path) -> None:
    current = json.loads((project_dir / "in" / "settings.json").read_text(encoding="utf-8"))
    r, ran = receipt(project_dir)
    if r is None or ran is None or settings_hash(ran) != settings_hash(current):
        raise ValueError("Bring in data again first: the Data wizard changed since it ran.")
    project.accepted["bring_in"] = settings_hash(current)


def receipt(project_dir: Path) -> tuple[Receipt | None, dict | None]:
    base = out_dir(project_dir)
    if not (base / "receipt.json").is_file():
        return None, None
    ran = (
        json.loads((base / "settings.json").read_text(encoding="utf-8")) if (base / "settings.json").is_file() else None
    )
    return Receipt.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran


if __name__ == "__main__":
    from oakbox.net import use_system_certificates

    use_system_certificates()
    try:
        run(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - the app shows the last line of the log
        import traceback

        traceback.print_exc()
        print(f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

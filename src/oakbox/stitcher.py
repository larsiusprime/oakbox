"""Stitch (SPEC §3.2 stage 3): turn the imported files into one parcel table, one map and one sales table.

The same function does Stitch's **Check** (measure only) and step 1's first part
(measure, then write ``in/stitched/``), so the receipt always matches the
preview. OpenAVMKit then loads the stitched tables, keyed on ``key``.

Order for every file: filter rows, fix IDs, drop blank IDs, then collapse several
rows per parcel (parcel tables) or merge polygons (the map). Matching compares
distinct fixed IDs against the map's.
"""

# pandas-stubs can't tell a column from a frame after df[...], and pyarrow.compute's functions
# are generated at runtime, so these checks only produce noise in this data-wrangling module.
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false
# pyright: reportReturnType=false

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from oakbox.setup import BaseModel, Collapse, FileUse, IdFix, Setup, SourceFile
from oakbox.sources import imported_path

KEY = "key"
EXAMPLES = 8


class FixSuggestion(BaseModel):
    fixes: list[IdFix]
    description: str
    matched_after: int
    gain: int


class BreakdownRow(BaseModel):
    value: str
    count: int
    share_of_unmatched: float
    share_of_matched: float


class Breakdown(BaseModel):
    column: str
    rows: list[BreakdownRow]


class FileReport(BaseModel):
    file: str
    name: str
    use: FileUse
    rows_in: int
    filtered_out: int = 0
    filter_description: str | None = None
    blank_ids: int = 0
    rows_after: int = 0
    distinct_ids: int = 0
    collapsed_away: int = 0  # rows merged into another row of the same parcel
    polygons_merged: int = 0
    matched: int = 0
    only_here: int = 0
    only_here_examples: list[str] = []
    only_here_breakdown: Breakdown | None = None
    only_on_map: int = 0
    only_on_map_examples: list[str] = []
    suggestion: FixSuggestion | None = None
    rows_out: int = 0


class StitchedColumn(BaseModel):
    name: str
    source: str
    source_column: str


class StitchReport(BaseModel):
    checked_at: dt.datetime
    written: bool
    spine: FileReport | None
    files: list[FileReport]
    parcels: int
    sales: int
    sales_unmatched: int
    map_parcels_without_details: int = 0
    columns: list[StitchedColumn]
    warnings: list[str]


# ---------- ID fixes ----------

FIX_TEXT = {
    "trim": "remove spaces at the ends",
    "strip_leading_zeros": "remove leading zeros",
    "remove_non_alnum": "remove dashes, dots and spaces",
    "upper": "use capital letters",
    "pad_zeros": "pad with zeros",
}


def apply_fixes(ids: pd.Series, fixes: list[IdFix]) -> pd.Series:
    """Text IDs with the fixes applied in order. Always trims; an all-zero ID becomes blank."""
    s = ids.fillna("").astype(str).str.strip()
    for fx in fixes:
        if fx.op == "trim":
            s = s.str.strip()
        elif fx.op == "strip_leading_zeros":
            s = s.str.lstrip("0")
        elif fx.op == "remove_non_alnum":
            s = s.str.replace(r"[^0-9A-Za-z]", "", regex=True)
        elif fx.op == "upper":
            s = s.str.upper()
        elif fx.op == "pad_zeros" and fx.width:
            s = s.where(s == "", s.str.zfill(fx.width))
    return s.mask(s.str.fullmatch(r"0+"), "")


def describe_fixes(fixes: list[IdFix]) -> str:
    return ", then ".join(FIX_TEXT[f.op] + (f" to {f.width}" if f.width else "") for f in fixes)


CANDIDATES: list[list[IdFix]] = [
    [IdFix(op="strip_leading_zeros")],
    [IdFix(op="remove_non_alnum")],
    [IdFix(op="upper")],
    [IdFix(op="remove_non_alnum"), IdFix(op="strip_leading_zeros")],
    [IdFix(op="remove_non_alnum"), IdFix(op="upper")],
]


def _suggest(raw_here: pd.Series, raw_map: pd.Series, here_fixes, map_fixes, matched: int) -> FixSuggestion | None:
    """The candidate fix (applied to both files) that adds the most matches, if it's worth it."""
    here_u, map_u = raw_here.drop_duplicates(), raw_map.drop_duplicates()
    best = None
    for cand in CANDIDATES:
        if any(c.op in {f.op for f in here_fixes} for c in cand):
            continue
        a = set(apply_fixes(here_u, [*here_fixes, *cand]))
        b = set(apply_fixes(map_u, [*map_fixes, *cand]))
        a.discard("")
        n = len(a & b)
        if best is None or n > best[1]:
            best = (cand, n)
    if best is None:
        return None
    gain = best[1] - matched
    if gain < max(10, 0.005 * max(len(here_u), 1)):
        return None
    return FixSuggestion(fixes=best[0], description=describe_fixes(best[0]), matched_after=best[1], gain=gain)


# ---------- Reading and collapsing ----------


def _read(pdir: Path, f: SourceFile, with_geometry: bool = False) -> pd.DataFrame:
    path = imported_path(pdir, f)
    if with_geometry:
        import geopandas as gpd

        return gpd.read_parquet(path)
    cols = [c for c in pq.read_schema(path).names if c != "geometry"]
    return pq.read_table(path, columns=cols).to_pandas()


def _filter(df: pd.DataFrame, f: SourceFile, rep: FileReport) -> pd.DataFrame:
    if f.keep_rows is None or f.keep_rows.column not in df.columns:
        return df
    keep = df[f.keep_rows.column].astype(str).str.strip().isin(f.keep_rows.values)
    rep.filtered_out = int((~keep).sum())
    rep.filter_description = f"kept rows where {f.keep_rows.column} is {', '.join(f.keep_rows.values)}"
    return df[keep]


def collapse(df: pd.DataFrame, rule: Collapse | None, label: str) -> pd.DataFrame:
    """One row per key: sort, then aggregate each column ('first' unless the rule says otherwise)."""
    rule = rule or Collapse()
    sort = [k for k in rule.sort_by if k.column in df.columns]
    if sort:
        df = df.sort_values([k.column for k in sort], ascending=[not k.descending for k in sort], kind="mergesort")
    aggs: dict[str, tuple[str, str]] = {}
    for c in df.columns:
        if c == KEY:
            continue
        op = rule.fields.get(c, "first")
        name = f"{c}_count" if op == "count" else c
        aggs[name] = (c, op)
    out = df.groupby(KEY, sort=False).agg(**aggs).reset_index()
    return out


def _breakdown(df: pd.DataFrame, unmatched: pd.Series) -> Breakdown | None:
    """The low-cardinality column that best tells unmatched rows apart from matched ones."""
    best = None
    n_un, n_m = int(unmatched.sum()), int((~unmatched).sum())
    if n_un == 0 or n_m == 0:
        return None
    for c in df.columns:
        if c == KEY:
            continue
        s = df[c]
        if pd.api.types.is_float_dtype(s):
            continue
        s = s.astype(str).str.strip()
        if not 2 <= s.nunique() <= 30:
            continue
        un = s[unmatched].value_counts(normalize=True)
        m = s[~unmatched].value_counts(normalize=True)
        tv = 0.5 * un.subtract(m, fill_value=0).abs().sum()
        if best is None or tv > best[0]:
            best = (tv, c, s)
    if best is None or best[0] < 0.2:
        return None
    _, c, s = best
    counts = s[unmatched].value_counts()
    m_share = s[~unmatched].value_counts(normalize=True)
    rows = [
        BreakdownRow(
            value=str(v) or "(blank)",
            count=int(n),
            share_of_unmatched=n / n_un,
            share_of_matched=float(m_share.get(v, 0)),
        )
        for v, n in counts.head(6).items()
    ]
    return Breakdown(column=c, rows=rows)


# ---------- The stitch ----------


def run(
    pdir: Path,
    setup: Setup,
    write: bool = False,
    on_progress: Callable[[float, str], None] | None = None,
) -> StitchReport:
    def progress(fr: float, msg: str) -> None:
        if on_progress:
            on_progress(fr, msg)

    st = setup.stitch
    warnings: list[str] = []
    parcel_files = [f for f in setup.files_for("parcels") if f.imported]
    sale_files = [f for f in setup.files_for("sales") if f.imported]
    steps = 1 + len(parcel_files) + len(sale_files) + (2 if write else 0)
    done = 0

    def tick(msg: str) -> None:
        nonlocal done
        done += 1
        progress(done / steps, msg)

    # The spine: the parcel map.
    spine_file = setup.file(st.spine) if st.spine else None
    spine_rep = None
    map_raw = pd.Series([], dtype=str)
    geo = None
    if spine_file is not None:
        progress(0.01, f"Reading {spine_file.name}")
        df = _read(pdir, spine_file, with_geometry=write)
        spine_rep = FileReport(file=spine_file.id, name=spine_file.name, use="parcel_map", rows_in=len(df))
        df = _filter(df, spine_file, spine_rep)
        idc = spine_file.id_columns[0]
        map_raw = df[idc].fillna("").astype(str).str.strip()
        df[KEY] = apply_fixes(df[idc], st.id_fixes.get(spine_file.id, []))
        blank = df[KEY] == ""
        spine_rep.blank_ids = int(blank.sum())
        df = df[~blank]
        spine_rep.rows_after = len(df)
        spine_rep.distinct_ids = int(df[KEY].nunique())
        spine_rep.polygons_merged = spine_rep.rows_after - spine_rep.distinct_ids
        if write:
            geo = _merge_polygons(df, st.dissolve)
        spine_keys = pd.Index(df[KEY].unique())
        spine_rep.rows_out = len(spine_keys)
        tick("Parcel map measured")
    else:
        warnings.append("No parcel map. OAK box needs one to place parcels; using the first parcel table instead.")
        spine_keys = None

    # Parcel tables, attached by ID.
    parcels = None
    columns: list[StitchedColumn] = []
    reports = []
    for f in parcel_files:
        df = _read(pdir, f)
        rep = FileReport(file=f.id, name=f.name, use="parcels", rows_in=len(df))
        df = _filter(df, f, rep)
        idc = f.id_columns[0]
        raw = df[idc].fillna("").astype(str).str.strip()
        df = df.drop(columns=[idc]).assign(**{KEY: apply_fixes(raw, st.id_fixes.get(f.id, []))})
        blank = df[KEY] == ""
        rep.blank_ids = int(blank.sum())
        df, raw = df[~blank], raw[~blank]
        rep.rows_after = len(df)
        rep.distinct_ids = int(df[KEY].nunique())
        if spine_keys is None:
            spine_keys = pd.Index(df[KEY].unique())
        here = df[KEY].drop_duplicates()
        in_map = here.isin(spine_keys)
        rep.matched = int(in_map.sum())
        rep.only_here = int((~in_map).sum())
        rep.only_here_examples = sorted(here[~in_map].head(200))[:EXAMPLES]
        missing = ~spine_keys.isin(here)
        rep.only_on_map = int(missing.sum())
        rep.only_on_map_examples = sorted(spine_keys[missing][:200])[:EXAMPLES]
        if rep.only_here:
            rows_unmatched = ~df[KEY].isin(spine_keys)
            rep.only_here_breakdown = _breakdown(df, rows_unmatched)
        if spine_file is not None and rep.only_here:
            rep.suggestion = _suggest(
                raw, map_raw, st.id_fixes.get(f.id, []), st.id_fixes.get(spine_file.id, []), rep.matched
            )
        one = collapse(df, st.collapse.get(f.id), f.name)
        rep.collapsed_away = rep.rows_after - len(one)
        one = one[one[KEY].isin(spine_keys)]
        rep.rows_out = len(one)
        renames = {}
        taken = {c.name for c in columns} | {KEY}
        for c in one.columns:
            if c == KEY:
                continue
            name = c if c not in taken else f"{c}__{f.id}"
            renames[c] = name
            columns.append(StitchedColumn(name=name, source=f.id, source_column=c))
        one = one.rename(columns=renames)
        parcels = one if parcels is None else parcels.merge(one, on=KEY, how="outer")
        reports.append(rep)
        tick(f"{f.name} measured")

    # Sales: stacked, kept only when their parcel is on the map.
    sales_frames = []
    sales_unmatched = 0
    for f in sale_files:
        df = _read(pdir, f)
        rep = FileReport(file=f.id, name=f.name, use="sales", rows_in=len(df))
        df = _filter(df, f, rep)
        idc = f.id_columns[0]
        df = df.assign(**{KEY: apply_fixes(df[idc], st.id_fixes.get(f.id, []))})
        blank = df[KEY] == ""
        rep.blank_ids = int(blank.sum())
        df = df[~blank]
        rep.rows_after = len(df)
        rep.distinct_ids = int(df[KEY].nunique())
        on_map = df[KEY].isin(spine_keys) if spine_keys is not None else pd.Series(True, index=df.index)
        here = df[KEY].drop_duplicates()
        rep.matched = int(here.isin(spine_keys).sum()) if spine_keys is not None else len(here)
        rep.only_here = len(here) - rep.matched
        rep.only_here_examples = (
            sorted(here[~here.isin(spine_keys)].head(200))[:EXAMPLES] if spine_keys is not None else []
        )
        rep.rows_out = int(on_map.sum())
        sales_unmatched += len(df) - rep.rows_out
        sales_frames.append(df[on_map])
        reports.append(rep)
        tick(f"{f.name} measured")
    sales = pd.concat(sales_frames, ignore_index=True) if sales_frames else None

    # OpenAVMKit's universe is the parcel table when there is one, so map parcels without details drop out.
    if parcels is not None:
        n_parcels = len(parcels)
    else:
        n_parcels = len(spine_keys) if spine_keys is not None else 0
    map_only = (len(spine_keys) - n_parcels) if (spine_keys is not None and parcels is not None) else 0
    if write:
        out = pdir / "in" / "stitched"
        out.mkdir(parents=True, exist_ok=True)
        if geo is not None:
            progress(done / steps, "Writing the parcel map")
            geo.to_parquet(out / "geo_parcels.geoparquet", index=False)
        tick("Parcel map written")
        if parcels is not None:
            parcels.to_parquet(out / "parcels.parquet", index=False)
        if sales is not None:
            sales.to_parquet(out / "sales.parquet", index=False)
        tick("Parcel and sales tables written")

    return StitchReport(
        checked_at=dt.datetime.now(dt.UTC),
        written=write,
        spine=spine_rep,
        files=reports,
        parcels=n_parcels,
        sales=len(sales) if sales is not None else 0,
        sales_unmatched=sales_unmatched,
        map_parcels_without_details=map_only,
        columns=columns,
        warnings=warnings,
    )


def _merge_polygons(df, dissolve: bool):
    """One shape per key: polygons sharing a key are merged (or only the first is kept).

    Shapes are repaired first (real maps have self-intersections). An ID whose shapes
    still can't be merged keeps its first polygon rather than failing the stitch.
    """
    import shapely

    dup = df[KEY].duplicated(keep=False)
    if not dup.any():
        return df.reset_index(drop=True)
    single, multi = df[~dup], df[dup].copy()
    if not dissolve:
        merged = multi.drop_duplicates(subset=KEY, keep="first")
    else:
        multi["geometry"] = shapely.make_valid(multi.geometry.values)
        first = multi.drop_duplicates(subset=KEY, keep="first").set_index(KEY)
        shapes = {}
        for key, geoms in multi.groupby(KEY, sort=False).geometry:
            try:
                shapes[key] = shapely.union_all(geoms.values)
            except shapely.errors.GEOSException:
                shapes[key] = first.loc[key, "geometry"]
        first["geometry"] = [shapes[k] for k in first.index]
        merged = first.reset_index()
    return pd.concat([single, merged[single.columns]], ignore_index=True)

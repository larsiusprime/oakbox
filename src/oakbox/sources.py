"""Your files (SPEC §3.2 stage 2): look inside a file the user picked, then import it.

``inspect`` is quick and reads only the start of a file, for the preview.
``import_file`` writes the project's own copy as Parquet in ``in/sources/`` with
only the kept columns, IDs as text, and measures it (``FileProfile``). Every later
check and the stitch read that copy, never the original.
"""

# pandas-stubs can't tell a column from a frame after df[...], and pyarrow.compute's functions
# are generated at runtime, so these checks only produce noise in this data-wrangling module.
# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false
# pyright: reportReturnType=false

from __future__ import annotations

import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from oakbox import fixedwidth
from oakbox.setup import BaseModel, ColumnInfo, ColumnType, FileFormat, FileProfile, FileUse, SourceFile

SPATIAL = {"shapefile", "geopackage", "geojson", "filegdb", "geoparquet"}
SAMPLE_ROWS = 20
_ID_NAME = re.compile(r"(^|_)(parcel|par_?id|prop_?id|pid|pin|apn|account|acct|geo_?id|key)($|_)", re.I)
_SALE_NAME = re.compile(r"sale|price|deed|transfer", re.I)


class ExportMemberInfo(BaseModel):
    member: str
    label: str
    description: str
    size_bytes: int
    records: int
    used_by_default: bool
    use: FileUse | None


class ExportInfo(BaseModel):
    layout_id: str
    name: str
    members: list[ExportMemberInfo]
    unknown: list[str]


class Inspection(BaseModel):
    path: str
    name: str
    format: FileFormat | None
    size_bytes: int
    export: ExportInfo | None = None
    layers: list[str] = []
    member: str | None = None
    columns: list[ColumnInfo] = []
    sample: list[dict[str, str]] = []
    rows_estimate: int | None = None
    suggested_uses: list[FileUse] = []
    suggested_id_column: str | None = None
    problem: str | None = None


def detect_format(path: Path) -> FileFormat | None:
    suffix = path.suffix.lower()
    if path.is_dir() and suffix == ".gdb":
        return "filegdb"
    if suffix == ".parquet" or suffix == ".geoparquet":
        if suffix == ".geoparquet":
            return "geoparquet"
        meta = pq.read_schema(path).metadata or {}
        return "geoparquet" if b"geo" in meta else "parquet"
    if suffix in (".csv", ".txt", ".tsv"):
        return "csv"
    if suffix in (".xlsx", ".xls"):
        return "excel"
    if suffix == ".shp":
        return "shapefile"
    if suffix == ".gpkg":
        return "geopackage"
    if suffix in (".geojson", ".json"):
        return "geojson"
    if suffix == ".zip" and zipfile.is_zipfile(path):
        names = [n.lower() for n in zipfile.ZipFile(path).namelist()]
        if any(n.endswith(".shp") for n in names):
            return "shapefile"
        if any(".gdb/" in n for n in names):
            return "filegdb"
        return "fixed_width" if fixedwidth.detect_export(path) else None
    return None


def inspect(path_str: str, member: str | None = None) -> Inspection:
    path = Path(path_str).expanduser()
    if not path.exists():
        return Inspection(path=path_str, name=path.name, format=None, size_bytes=0, problem="File not found.")
    size = _size(path)
    fmt = detect_format(path)
    out = Inspection(path=str(path), name=path.name, format=fmt, size_bytes=size)
    if fmt is None:
        out.problem = "OAK box can't read this kind of file yet."
        return out
    if fmt == "fixed_width":
        export = fixedwidth.detect_export(path)
        assert export is not None
        out.export = ExportInfo(
            layout_id=export.layout_id,
            name=export.name,
            members=[ExportMemberInfo(**m.__dict__) for m in export.members],
            unknown=export.unknown,
        )
        if member is None:
            return out
        rows, fields = fixedwidth.sample_rows(path, member, export.layout_id, SAMPLE_ROWS)
        out.member = member
        out.sample = rows
        out.columns = [
            ColumnInfo(name=f["name"], type="number" if f["number"] else "text", description=f["description"])
            for f in fields
        ]
        out.rows_estimate = next((m.records for m in export.members if m.member == member), None)
        out.suggested_uses = (
            [fixedwidth.PACS_DEFAULTS[Path(member).name.upper()].use]
            if Path(member).name.upper() in fixedwidth.PACS_DEFAULTS
            else []
        )
        out.suggested_id_column = "prop_id"
        return out
    if fmt in ("geopackage", "filegdb"):
        import pyogrio

        out.layers = [str(name) for name, _ in pyogrio.list_layers(_ogr_path(path, fmt))]
        member = member or (out.layers[0] if out.layers else None)
    out.member = member
    df, rows = _read(path, fmt, member, nrows=SAMPLE_ROWS)
    out.rows_estimate = rows
    out.columns = [_column_info(df, c) for c in df.columns if c != "geometry"]
    if "geometry" in df.columns:
        out.columns.append(ColumnInfo(name="geometry", type="geometry"))
    out.sample = [{k: _cell(v) for k, v in row.items() if k != "geometry"} for row in df.to_dict("records")]
    out.suggested_uses = _suggest_uses(fmt, [c.name for c in out.columns])
    out.suggested_id_column = _suggest_id(df)
    return out


def _size(path: Path) -> int:
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return path.stat().st_size


def _ogr_path(path: Path, fmt: str) -> str:
    if path.suffix.lower() == ".zip":
        return f"/vsizip/{path}"
    return str(path)


def _read(path: Path, fmt: str, member: str | None, nrows: int | None = None, columns: list[str] | None = None):
    """Read a non-fixed-width file. Returns (frame, total row count if cheaply known)."""
    if fmt == "parquet":
        pf = pq.ParquetFile(path)
        if nrows is not None:
            batch = next(pf.iter_batches(batch_size=nrows, columns=columns))
            return batch.to_pandas(), pf.metadata.num_rows
        return pf.read(columns=columns).to_pandas(), pf.metadata.num_rows
    if fmt in SPATIAL:
        import geopandas as gpd
        import pyogrio

        if fmt == "geoparquet":
            if nrows is not None:
                pf = pq.ParquetFile(path)
                df = gpd.read_parquet(path, columns=columns)
                return df.head(nrows), pf.metadata.num_rows
            return gpd.read_parquet(path, columns=columns), None
        src = _ogr_path(path, fmt)
        info = pyogrio.read_info(src, layer=member)
        cols = [c for c in columns if c != "geometry"] if columns else None
        df = pyogrio.read_dataframe(src, layer=member, max_features=nrows, columns=cols)
        return df, int(info["features"])
    if fmt == "csv":
        sep = "\t" if path.suffix.lower() == ".tsv" else None
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            nrows=nrows,
            sep=sep,
            engine="python" if sep is None else "c",
            usecols=columns,
        )
        return df, None
    if fmt == "excel":
        df = pd.read_excel(path, dtype=str, keep_default_na=False, nrows=nrows, usecols=columns)
        return df, None
    raise ValueError(f"Unsupported format: {fmt}")


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _column_info(df: pd.DataFrame, col: str) -> ColumnInfo:
    s = df[col]
    kind: ColumnType = "text"
    if pd.api.types.is_bool_dtype(s):
        kind = "yes_no"
    elif pd.api.types.is_numeric_dtype(s):
        kind = "number"
    elif pd.api.types.is_datetime64_any_dtype(s):
        kind = "date"
    text = s.map(_cell)
    blank = int((text.str.strip() == "").sum())
    examples = list(dict.fromkeys(t for t in text if t.strip()))[:3]
    return ColumnInfo(name=str(col), type=kind, blank=blank, examples=examples)


def _suggest_uses(fmt: str, columns: list[str]) -> list[FileUse]:
    if fmt in SPATIAL and "geometry" in columns:
        return ["parcel_map"]
    uses: list[FileUse] = ["parcels"]
    if sum(bool(_SALE_NAME.search(c)) for c in columns) >= 2:
        uses.append("sales")
    return uses


def _suggest_id(df: pd.DataFrame) -> str | None:
    named = [c for c in df.columns if c != "geometry" and _ID_NAME.search(str(c))]
    if not named:
        return None
    return max(named, key=lambda c: (df[c].nunique(), -list(df.columns).index(c)))


# ---------- Import ----------


def source_path(pdir: Path, f: SourceFile) -> Path:
    """The original file. Relative paths (samples) are inside the project's in/ folder."""
    p = Path(f.path)
    return p if p.is_absolute() else pdir / "in" / p


def imported_path(pdir: Path, f: SourceFile) -> Path:
    suffix = ".geoparquet" if f.format in SPATIAL else ".parquet"
    return pdir / "in" / "sources" / f"{f.id}{suffix}"


def import_file(
    pdir: Path,
    f: SourceFile,
    on_progress: Callable[[float, str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> FileProfile:
    """Write the project's copy of ``f`` and measure it."""
    dest = imported_path(pdir, f)
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = source_path(pdir, f)
    ids = set(f.id_columns)
    if f.format == "fixed_width":
        assert f.member and f.layout
        columns = f.keep_columns or fixedwidth.default_columns(f.layout, f.member)
        columns = list(dict.fromkeys([*f.id_columns, *columns]))
        fixedwidth.convert(path, f.member, f.layout, columns, ids, dest, on_progress, cancelled)
    else:
        if on_progress:
            on_progress(0.1, "Reading")
        columns = None
        if f.keep_columns is not None:
            columns = list(dict.fromkeys([*f.id_columns, *f.keep_columns]))
            if f.format in SPATIAL:
                columns.append("geometry")
        df, _ = _read(path, f.format, f.member, columns=columns)
        if f.format in ("csv", "excel"):
            df = _numbers_from_text(df, keep_text=ids)
        for c in f.id_columns:
            df[c] = _as_id_text(df[c])
        if on_progress:
            on_progress(0.7, "Saving the project's copy")
        tmp = dest.with_suffix(".part")
        if f.format in SPATIAL:
            df.to_parquet(tmp, index=False)
        else:
            pa_table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_table(pa_table, tmp)
        tmp.replace(dest)
    if on_progress:
        on_progress(0.9, "Measuring")
    return profile(dest, f)


def _as_id_text(s: pd.Series) -> pd.Series:
    """IDs are text. Whole-number floats lose their '.0'; blanks stay blank."""
    if pd.api.types.is_float_dtype(s):
        return s.map(lambda v: "" if pd.isna(v) else (str(int(v)) if float(v).is_integer() else str(v)))
    return s.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).str.strip()


def _numbers_from_text(df: pd.DataFrame, keep_text: set[str]) -> pd.DataFrame:
    """Text columns that are all numbers become numbers, unless a value has a leading zero ('00' codes)."""
    for c in df.columns:
        if c in keep_text or c == "geometry":
            continue
        s = df[c].astype(str).str.strip()
        filled = s[s != ""]
        if filled.empty or filled.str.match(r"^-?0\d").any():
            continue
        nums = pd.to_numeric(filled.str.replace(",", "", regex=False), errors="coerce")
        if nums.notna().all():
            df[c] = pd.to_numeric(s.str.replace(",", "", regex=False).replace("", None), errors="coerce")
    return df


def profile(dest: Path, f: SourceFile) -> FileProfile:
    table = pq.read_table(dest)
    crs = None
    meta = table.schema.metadata or {}
    if b"geo" in meta:
        import json

        geo = json.loads(meta[b"geo"])
        col = geo.get("columns", {}).get(geo.get("primary_column", "geometry"), {})
        c = col.get("crs")
        crs = _crs_name(c)
    columns = []
    descriptions = {}
    if f.layout and f.member:
        descriptions = {x["name"]: x["description"] for x in fixedwidth.layout_file(f.layout, f.member)["fields"]}
    for name in table.column_names:
        arr = table.column(name)
        if name == "geometry":
            columns.append(ColumnInfo(name=name, type="geometry"))
            continue
        kind: ColumnType = "text"
        t = arr.type
        if pa.types.is_boolean(t):
            kind = "yes_no"
        elif pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_decimal(t):
            kind = "number"
        elif pa.types.is_timestamp(t) or pa.types.is_date(t):
            kind = "date"
        blank = arr.null_count
        if pa.types.is_string(t) or pa.types.is_large_string(t):
            blank += int(pc.sum(pc.equal(pc.utf8_trim_whitespace(arr.fill_null("")), "")).as_py() or 0) - arr.null_count
            blank = max(blank, arr.null_count)
        if pa.types.is_null(t):
            columns.append(ColumnInfo(name=name, type="text", blank=table.num_rows, distinct=0))
            continue
        try:
            distinct = int(pc.count_distinct(arr).as_py())
            examples = [_cell(v) for v in pc.unique(arr.slice(0, 5000)).to_pylist() if _cell(v).strip()][:3]
        except (pa.ArrowNotImplementedError, pa.ArrowInvalid):  # nested or binary columns
            distinct, examples = None, []
        columns.append(
            ColumnInfo(
                name=name,
                type=kind,
                blank=blank,
                distinct=distinct,
                examples=examples,
                description=descriptions.get(name, ""),
            )
        )
    distinct_ids = blank_ids = None
    if f.id_columns and f.id_columns[0] in table.column_names:
        ids = pc.utf8_trim_whitespace(table.column(f.id_columns[0]).cast(pa.string()).fill_null(""))
        blank_ids = int(pc.sum(pc.equal(ids, "")).as_py() or 0)
        distinct_ids = int(pc.count_distinct(pc.filter(ids, pc.not_equal(ids, ""))).as_py())
    return FileProfile(rows=table.num_rows, columns=columns, distinct_ids=distinct_ids, blank_ids=blank_ids, crs=crs)


def _crs_name(c) -> str | None:
    if c is None:
        return "EPSG:4326"
    if isinstance(c, dict):
        ident = c.get("id") or {}
        if ident.get("authority") and ident.get("code"):
            return f"{ident['authority']}:{ident['code']}"
        return c.get("name")
    return str(c)

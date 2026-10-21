"""F3c, choosing a file's fields (SPEC §3.0): what's in a file, and its data.load entry's ``load``.

Mirrors OpenAVMKit: an entry loads only the columns in its ``load``, each renamed to a field and
optionally cast (``[column, type]``, plus a date format or blank handling as a third item). The
field list is OpenAVMKit's own data dictionary. Reading a file here only previews it.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import NAME, BaseModel, DataFile, _ext

SAMPLE_ROWS = 1000
SAMPLES = 5
# Types OpenAVMKit casts to in data.load, and the third item each needs (SPEC F3c).
TYPES = ("string", "float", "int", "bool", "datetime")
BLANKS = ("na_false", "na_true")
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M")

ColumnType = Literal["text", "number", "yes/no", "date", "geometry"]


class Column(BaseModel):
    name: str
    type: ColumnType = Field(description="The column's own type in the file.")
    samples: list[str] = Field(description="A few distinct non-blank values from the first rows.")
    date_format: str | None = Field(
        default=None, description="The first common format that reads every sample, for text columns."
    )


class FileColumns(BaseModel):
    rows: int | None = Field(description="Row count, when the file's metadata has it (not CSV).")
    columns: list[Column]
    geometry: bool
    date_formats: list[str] = Field(default=list(DATE_FORMATS), description="Common date formats to offer.")


class DictionaryField(BaseModel):
    key: str
    name: str
    description: str
    type: str
    groups: list[str]


class DateCheck(BaseModel):
    parsed: list[str | None] = Field(description="Each sample as read with the format (ISO date), or null.")


def _kind(dtype: object) -> ColumnType:
    import pandas as pd

    if isinstance(dtype, pd.DatetimeTZDtype) or pd.api.types.is_datetime64_any_dtype(dtype):
        return "date"
    if pd.api.types.is_bool_dtype(dtype):
        return "yes/no"
    if pd.api.types.is_numeric_dtype(dtype):
        return "number"
    return "text"


def _head(path: Path, layer: str | None):
    """The first rows (without geometry), and the row count when it's cheap to know."""
    import pandas as pd

    ext = _ext(path)
    if ext in ("parquet", "geoparquet"):
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        names = [n for n in pf.schema_arrow.names if n != "geometry"]
        batch = next(pf.iter_batches(batch_size=SAMPLE_ROWS, columns=names), None)
        df = batch.to_pandas() if batch is not None else pd.DataFrame({n: [] for n in names})
        return df, pf.metadata.num_rows
    if ext == "csv":
        return pd.read_csv(path, nrows=SAMPLE_ROWS), None

    import pyogrio

    info = pyogrio.read_info(path, layer=layer)
    df = pyogrio.read_dataframe(path, layer=layer, max_features=SAMPLE_ROWS, read_geometry=False)
    return pd.DataFrame(df), int(info["features"]) if info.get("features", -1) >= 0 else None


def _csv_text(path: Path):
    """CSV values as written in the file, for samples (pandas would show 1987 as 1987.0 beside a blank)."""
    import pandas as pd

    return pd.read_csv(path, nrows=SAMPLE_ROWS, dtype=str, keep_default_na=False)


def _samples(series) -> list[str]:
    out: list[str] = []
    for value in series.dropna():
        text = str(value).strip()
        if text and text not in out:
            out.append(text[:40])
        if len(out) == SAMPLES:
            break
    return out


def columns(path: Path, layer: str | None) -> FileColumns:
    from oakbox.datafiles import has_geometry

    df, rows = _head(path, layer)
    text = _csv_text(path) if _ext(path) == "csv" else df
    out = []
    for name in df.columns:
        kind = _kind(df[name].dtype)
        samples = _samples(text[name])
        fmt = next((f for f in DATE_FORMATS if _reads(samples, f)), None) if kind == "text" and samples else None
        out.append(Column(name=str(name), type=kind, samples=samples, date_format=fmt))
    return FileColumns(rows=rows, columns=out, geometry=bool(has_geometry(path, layer)))


def _reads(samples: list[str], fmt: str) -> bool:
    return all(p is not None for p in check_dates(samples, fmt).parsed)


def check_dates(samples: list[str], fmt: str) -> DateCheck:
    """Read samples with a date format the way OpenAVMKit does (pd.to_datetime with that format)."""
    import pandas as pd

    parsed: list[str | None] = []
    for s in samples:
        try:
            parsed.append(pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d"))
        except (ValueError, TypeError):
            parsed.append(None)
    return DateCheck(parsed=parsed)


@cache
def dictionary() -> list[DictionaryField]:
    """OpenAVMKit's data dictionary: the fields a column can be loaded into (input or either, §7 B11)."""
    raw = json.loads(resources.files("openavmkit.resources.settings").joinpath("data_dictionary.json").read_text())
    return [
        DictionaryField(
            key=key,
            name=entry.get("name") or key,
            description=entry.get("description") or "",
            type=entry.get("type") or "string",
            groups=entry.get("groups") or [],
        )
        for key, entry in raw.items()
        if entry["source"] in ("input", "either")
    ]


def set_load(entry: DataFile, load: dict[str, list[str]]) -> None:
    """Replace an entry's load after checking it is something OpenAVMKit reads without guessing."""
    columns_used: set[str] = set()
    for field, spec in load.items():
        if not NAME.fullmatch(field):
            raise ValueError(f"{field}: names use lowercase letters, digits and underscores, and start with a letter.")
        if not 1 <= len(spec) <= 3 or not spec[0]:
            raise ValueError(f"{field}: give the column, then optionally its type and format.")
        if spec[0] in columns_used:
            raise ValueError(f"{spec[0]} is loaded twice.")
        columns_used.add(spec[0])
        if len(spec) >= 2 and spec[1] not in TYPES:
            raise ValueError(f"{field}: {spec[1]} isn't a type OpenAVMKit casts to.")
        kind = spec[1] if len(spec) >= 2 else None
        if kind == "datetime" and len(spec) != 3:
            raise ValueError(f"{field}: a date needs its format.")
        if kind == "bool" and (len(spec) != 3 or spec[2] not in BLANKS):
            raise ValueError(f"{field}: say what a blank means (na_false or na_true).")
        if kind not in ("datetime", "bool") and len(spec) == 3:
            raise ValueError(f"{field}: only dates and yes/no fields take a third item.")
    entry.load = dict(load)

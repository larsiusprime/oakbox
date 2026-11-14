"""Reading a project's files for the Fields wizard, cached on each file's size and time (``file_stamp``): a file's
columns and the values of one (``values_of``), its IDs cleaned as they join, and ``Files``, the project's files as
read now. Also the few questions about the project's files every step asks (the sales file, the base file).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from oakbox import fields
from oakbox.datafiles import (
    CleanStep,
    DataFile,
    clean_value,
    csv_encoding,
)
from oakbox.errors import NotFound
from oakbox.fields import Column, DictionaryField
from oakbox.projects import Project
from oakbox.wizard.models import WizardFile

# ---------- Reading the files (cached on the file's size and time) ----------


def file_stamp(path: Path) -> tuple[str, float, int]:
    st = path.stat()
    return str(path), st.st_mtime, st.st_size


@lru_cache(maxsize=64)
def _preview(stamp: tuple[str, float, int], layer: str | None) -> fields.FileColumns:
    return fields.columns(Path(stamp[0]), layer)


@lru_cache(maxsize=128)
def values_of(stamp: tuple[str, float, int], layer: str | None, column: str, raw: bool = False) -> tuple[str, ...]:
    """Every value of one column, as text, blanks as ''. Trimmed, unless raw (IDs: OpenAVMKit doesn't trim them)."""
    import pandas as pd

    from oakbox import readcache

    path = Path(stamp[0])
    ext = path.suffix.lower().lstrip(".")
    cached = readcache.ready(path) if ext == "csv" else None
    parquet = cached if cached is not None else path if ext in ("parquet", "geoparquet") else None
    if parquet is not None:
        fast = _text_column(parquet, column, raw)
        if fast is not None:
            return fast
    if cached is not None:
        # Its Parquet copy: every column as text, as the CSV reads (readcache).
        s = pd.read_parquet(cached, columns=[column])[column]
    elif ext == "csv":
        encoding = csv_encoding(path)
        s = pd.read_csv(path, usecols=lambda c: c == column, dtype=str, keep_default_na=False, encoding=encoding)[
            column
        ]
    elif ext in ("parquet", "geoparquet"):
        s = pd.read_parquet(path, columns=[column])[column]
    else:
        import pyogrio

        s = pyogrio.read_dataframe(path, layer=layer, columns=[column], read_geometry=False)[column]
    # As text, blanks (None, NaN) as ""; trimmed, unless raw and not blank. In pandas, not value by value: a
    # 220,000-row column in 0.03 s, not 0.3 s.
    text = s.astype(object).where(s.notna(), "").astype(str)
    trimmed = text.str.strip()
    return tuple((text.where(trimmed != "", "") if raw else trimmed).tolist())


def _text_column(path: Path, column: str, raw: bool) -> tuple[str, ...] | None:
    """A text column of a Parquet file (a CSV's copy: every column text) as values_of gives it, trimmed in Arrow:
    an 838,000-row column in 0.05 s, where pandas' strip takes 0.3 s. None: not text (read the usual way, so a
    number reads as it always has)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    col = pq.read_table(path, columns=[column]).column(0)
    if not (pa.types.is_string(col.type) or pa.types.is_large_string(col.type)):
        return None
    text = pc.fill_null(col, "")
    trimmed = pc.utf8_trim_whitespace(text)  # pyright: ignore[reportAttributeAccessIssue] - made at import
    out = pc.if_else(pc.equal(trimmed, ""), "", text) if raw else trimmed  # pyright: ignore[reportAttributeAccessIssue]
    return tuple(out.to_pandas().tolist())


@lru_cache(maxsize=64)
def cleaned_ids(stamp: tuple[str, float, int], layer: str | None, column: str, steps: str) -> tuple[str, ...]:
    """An ID column as OpenAVMKit will join on it: as written, after its clean-up steps (JSON)."""
    values = values_of(stamp, layer, column, raw=True)
    parsed = [CleanStep.model_validate(x) for x in json.loads(steps)]
    return tuple(clean_value(v, parsed) for v in values) if parsed else values


def steps_key(steps: list[CleanStep]) -> str:
    return json.dumps([x.model_dump() for x in steps])


class Files:
    """The project's files as read now, keyed by entry name."""

    def __init__(self, project: Project, in_dir: Path) -> None:
        self.project = project
        self.in_dir = in_dir
        self.preview: dict[str, fields.FileColumns] = {}
        self.source_preview: dict[str, fields.FileColumns] = {}  # a combined file's original (wizard/combine.py)
        self.problem: dict[str, str] = {}
        for f in project.files:
            if f.combine is not None:
                from oakbox.wizard.combine import ensure

                try:
                    ensure(in_dir, f)
                    self.source_preview[f.name] = _preview(file_stamp(in_dir / f.combine.source), f.layer)
                except Exception as e:  # noqa: BLE001 - shows on its row
                    self.problem[f.name] = f"Couldn't combine {f.combine.source}'s rows: {e}"
                    continue
            path = in_dir / f.filename
            if not path.is_file():
                self.problem[f.name] = f"{f.filename} is missing from the project folder."
                continue
            try:
                self.preview[f.name] = _preview(file_stamp(path), f.layer)
            except Exception as e:  # noqa: BLE001 - a damaged file shows on its row
                self.problem[f.name] = f"Couldn't read {f.filename}: {e}"

    def entry(self, name: str) -> DataFile:
        entry = self.project.file(name)
        if entry is None:
            raise NotFound(name)
        return entry

    def _path(self, f: DataFile, source: bool) -> Path:
        """A file as loaded; with source, a combined file's original (its rows as they are)."""
        return self.in_dir / (f.combine.source if source and f.combine is not None else f.filename)

    def columns(self, name: str, source: bool = False) -> list[Column]:
        p = self.source_preview.get(name) if source and name in self.source_preview else self.preview.get(name)
        return [c for c in p.columns if c.type != "geometry"] if p else []

    def column(self, name: str, column: str) -> Column | None:
        return next((c for c in self.columns(name) if c.name == column), None)

    def values(self, name: str, column: str, source: bool = False) -> tuple[str, ...]:
        f = self.entry(name)
        return values_of(file_stamp(self._path(f, source)), f.layer, column)

    def ids(self, name: str, field: str, steps: list[CleanStep] | None = None, source: bool = False) -> tuple[str, ...]:
        """A file's ID field as it joins: cleaned by its steps (or the given ones, for a preview). With source, a
        combined file's original's (its repeats, for the duplicates dialog)."""
        f = self.entry(name)
        spec = f.load.get(field)
        if spec is None or name not in self.preview:
            return ()
        use = f.clean.get(field, []) if steps is None else steps
        return cleaned_ids(file_stamp(self._path(f, source)), f.layer, spec[0], steps_key(use))

    def parcel_ids(self, name: str) -> list[str]:
        """A file's rows' parcel IDs (key), whatever ID it joins on: a second or third ID looked up in the parcel
        universe, as a run looks it up (a sales file joined on key2 gets key from the base file). "" where none."""
        f = self.entry(name)
        own = list(self.ids(name, f.match))
        if f.match == "key":
            return own
        base = self.project.base_file()
        if base is None or base.name == name:
            return [""] * len(own)
        to_key: dict[str, str] = {}
        for a, k in zip(self.ids(base.name, f.match), self.ids(base.name, "key"), strict=False):
            if a and k and a not in to_key:
                to_key[a] = k
        return [to_key.get(i, "") for i in own]

    def geometry(self, name: str) -> bool:
        p = self.preview.get(name)
        return bool(p and p.geometry)


# ---------- What the steps share about the project's files ----------


def dictionary_by_key() -> dict[str, DictionaryField]:
    return {d.key: d for d in fields.dictionary()}


def sales_file(project: Project) -> DataFile | None:
    """The main sales file: the one joined to the parcels. More sales details join it on the sale ID."""
    return next((f for f in project.files if f.holds == "sales" and f.match != "key_sale"), None)


def is_more_sales(f: DataFile | WizardFile) -> bool:
    """More sales details: a sales file joined to the main one on the sale ID."""
    return f.holds == "sales" and f.match == "key_sale"


def field_files(project: Project, sales: bool) -> list[DataFile]:
    holds = "sales" if sales else "parcels"
    return [f for f in project.files if f.holds == holds]


def row_count(files: Files, name: str) -> int | None:
    p = files.preview.get(name)
    if p is None:
        return None
    if p.rows is not None:
        return p.rows
    cols = files.columns(name)
    return len(files.values(name, cols[0].name)) if cols else None

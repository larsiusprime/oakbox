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

    path = Path(stamp[0])
    ext = path.suffix.lower().lstrip(".")
    if ext == "csv":
        s = pd.read_csv(path, usecols=lambda c: c == column, dtype=str, keep_default_na=False)[column]
    elif ext in ("parquet", "geoparquet"):
        s = pd.read_parquet(path, columns=[column])[column]
    else:
        import pyogrio

        s = pyogrio.read_dataframe(path, layer=layer, columns=[column], read_geometry=False)[column]
    text = ("" if v is None or (isinstance(v, float) and v != v) else str(v) for v in s.tolist())
    return tuple(v if raw and v.strip() else v.strip() for v in text)


@lru_cache(maxsize=64)
def _cleaned(stamp: tuple[str, float, int], layer: str | None, column: str, steps: str) -> tuple[str, ...]:
    """An ID column as OpenAVMKit will join on it: as written, after its clean-up steps (JSON)."""
    values = values_of(stamp, layer, column, raw=True)
    parsed = [CleanStep.model_validate(x) for x in json.loads(steps)]
    return tuple(clean_value(v, parsed) for v in values) if parsed else values


def _steps_key(steps: list[CleanStep]) -> str:
    return json.dumps([x.model_dump() for x in steps])


class Files:
    """The project's files as read now, keyed by entry name."""

    def __init__(self, project: Project, in_dir: Path) -> None:
        self.project = project
        self.in_dir = in_dir
        self.preview: dict[str, fields.FileColumns] = {}
        self.problem: dict[str, str] = {}
        for f in project.files:
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

    def columns(self, name: str) -> list[Column]:
        p = self.preview.get(name)
        return [c for c in p.columns if c.type != "geometry"] if p else []

    def column(self, name: str, column: str) -> Column | None:
        return next((c for c in self.columns(name) if c.name == column), None)

    def values(self, name: str, column: str) -> tuple[str, ...]:
        f = self.entry(name)
        return values_of(file_stamp(self.in_dir / f.filename), f.layer, column)

    def ids(self, name: str, field: str, steps: list[CleanStep] | None = None) -> tuple[str, ...]:
        """A file's ID field as it joins: cleaned by its steps (or the given ones, for a preview)."""
        f = self.entry(name)
        spec = f.load.get(field)
        if spec is None or name not in self.preview:
            return ()
        use = f.clean.get(field, []) if steps is None else steps
        return _cleaned(file_stamp(self.in_dir / f.filename), f.layer, spec[0], _steps_key(use))

    def geometry(self, name: str) -> bool:
        p = self.preview.get(name)
        return bool(p and p.geometry)


# ---------- What the steps share about the project's files ----------


def _by_key() -> dict[str, DictionaryField]:
    return {d.key: d for d in fields.dictionary()}


def sales_file(project: Project) -> DataFile | None:
    """The main sales file: the one joined to the parcels. More sales details join it on the sale ID."""
    return next((f for f in project.files if f.holds == "sales" and f.match != "key_sale"), None)


def _more_sales(f: DataFile | WizardFile) -> bool:
    """More sales details: a sales file joined to the main one on the sale ID."""
    return f.holds == "sales" and f.match == "key_sale"


def _field_files(project: Project, sales: bool) -> list[DataFile]:
    holds = "sales" if sales else "parcels"
    return [f for f in project.files if f.holds == holds]


def _rows(files: Files, name: str) -> int | None:
    p = files.preview.get(name)
    if p is None:
        return None
    if p.rows is not None:
        return p.rows
    cols = files.columns(name)
    return len(files.values(name, cols[0].name)) if cols else None

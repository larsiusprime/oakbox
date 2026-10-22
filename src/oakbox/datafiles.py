"""F2 and F3b (SPEC §3.0): put a file in the project's in/, declare it under data.load, rename, remove.

Mirrors OpenAVMKit: raw files live in the locality's in/, and each is an entry in
``data.load`` with its ``filename`` (and ``layer`` for a GeoPackage). Nothing here
reads the data itself; OpenAVMKit does that when it loads.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

# Exactly what OpenAVMKit's data.load reads (by extension, case-insensitively).
FORMATS = {"csv": "CSV", "parquet": "Parquet", "geoparquet": "Parquet", "gpkg": "GeoPackage", "shp": "Shapefile"}
# A shapefile can't be read without these next to the .shp.
SHAPEFILE_REQUIRED = ("shx", "dbf")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class BaseModel(_PydanticBase):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


Holds = Literal["parcels", "sales", "unused"]
Match = Literal["key", "key2"]


class DataFile(BaseModel):
    """One data.load entry, as OAK box wrote it."""

    name: str = Field(description="The data.load key.")
    filename: str = Field(description="File name inside in/.")
    layer: str | None = Field(default=None, description="GeoPackage layer.")
    load: dict[str, list[str]] = Field(
        default_factory=dict,
        description="data.load.<name>.load: field -> [column] or [column, type] or [column, type, extra] (F3c).",
    )
    calc: dict[str, list[Any]] = Field(
        default_factory=dict, description="data.load.<name>.calc: fields OpenAVMKit works out after loading (F3d)."
    )
    match: Match = Field(
        default="key", description="The ID it joins to the parcel universe on: key, or the second ID, key2 (F3d)."
    )
    holds: Holds | None = Field(
        default=None,
        description="What the file holds (F3d): one row per parcel, one row per sale, or not used. None: not chosen.",
    )


class FileCheck(BaseModel):
    """What OAK box can tell about a file before adding it, without reading its data."""

    path: str
    problem: str | None = None
    format: str | None = None
    size_bytes: int = 0
    files: list[str] = Field(default_factory=list, description="Files that move or copy together (shapefile sidecars).")
    layers: list[str] = Field(default_factory=list, description="GeoPackage layers.")
    suggested_name: str = ""
    filename: str = Field(default="", description="Its name in in/.")
    already_in_project: bool = Field(default=False, description="The file is already in this project's in/.")
    filename_taken: bool = Field(default=False, description="in/ already has a different file of this name.")


def _ext(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def companions(path: Path) -> list[Path]:
    """The file plus, for a shapefile, every file beside it with the same name (.shx, .dbf, .prj, .cpg, ...)."""
    if _ext(path) != "shp":
        return [path]
    prefix = path.stem.lower() + "."
    found = [p for p in path.parent.iterdir() if p.is_file() and p.name.lower().startswith(prefix)]
    return [path, *sorted(p for p in found if p != path)]


def suggest_name(filename: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()).strip("_") or "data"
    if not base[0].isalpha():
        base = f"data_{base}"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}_{n}", n + 1
    return name


def check(in_dir: Path, path_text: str, files: list[DataFile]) -> FileCheck:
    path = Path(path_text.strip().strip('"')).expanduser()
    out = FileCheck(path=str(path))
    if not path.is_file():
        out.problem = "There's no file at that path."
        return out
    ext = _ext(path)
    if ext not in FORMATS:
        listed = ", ".join(dict.fromkeys(FORMATS.values()))
        out.problem = f"OpenAVMKit can't read .{ext or '?'} files yet. It reads {listed}."
        return out
    out.format = FORMATS[ext]
    group = companions(path)
    if ext == "shp":
        have = {_ext(p) for p in group}
        missing = [x for x in SHAPEFILE_REQUIRED if x not in have]
        if missing:
            out.problem = "This shapefile is missing its " + " and ".join(f".{m}" for m in missing) + " file."
            return out
    if ext == "gpkg":
        import pyogrio

        try:
            out.layers = [str(name) for name, _ in pyogrio.list_layers(path)]
        except Exception as e:  # noqa: BLE001 - GDAL raises many kinds
            out.problem = f"This GeoPackage can't be opened: {e}"
            return out
        if not out.layers:
            out.problem = "This GeoPackage has no layers."
            return out
    out.files = [p.name for p in group]
    out.size_bytes = sum(p.stat().st_size for p in group)
    out.filename = path.name
    out.already_in_project = path.parent.resolve() == in_dir.resolve()
    out.filename_taken = not out.already_in_project and (in_dir / path.name).exists()
    out.suggested_name = suggest_name(path.name, {f.name for f in files})
    return out


def add(
    in_dir: Path,
    path_text: str,
    files: list[DataFile],
    mode: Literal["move", "copy"],
    name: str,
    layer: str | None = None,
    filename: str | None = None,
) -> DataFile:
    """Move or copy the file (with its sidecars) into in/ and return its data.load entry.

    Raises ValueError with a plain-language message when it can't.
    """
    found = check(in_dir, path_text, files)
    if found.problem:
        raise ValueError(found.problem)
    if not NAME.fullmatch(name):
        raise ValueError("Names use lowercase letters, digits and underscores, and start with a letter.")
    if name in {f.name for f in files}:
        raise ValueError(f"This project already has a file called {name}.")
    if found.layers:
        if layer is None and len(found.layers) == 1:
            layer = found.layers[0]
        if layer not in found.layers:
            raise ValueError("Choose which layer of the GeoPackage to use.")
    else:
        layer = None
    source = Path(found.path)
    if found.already_in_project:
        return DataFile(name=name, filename=source.name, layer=layer)

    target_stem = Path(filename).stem if filename else source.stem
    if not target_stem or Path(target_stem).name != target_stem:
        raise ValueError("Give the file a plain name, without folders.")
    moves = []
    for p in companions(source):
        rest = p.name[len(source.stem) :]  # e.g. ".shp", ".shp.xml"
        moves.append((p, in_dir / f"{target_stem}{rest}"))
    taken = [dest.name for _, dest in moves if dest.exists()]
    if taken:
        raise ValueError(f"The project already has a file called {taken[0]}. Choose another name.")

    in_dir.mkdir(parents=True, exist_ok=True)
    done: list[Path] = []
    try:
        for src, dest in moves:
            if mode == "move":
                shutil.move(str(src), dest)
            else:
                shutil.copy2(src, dest)
            done.append(dest)
    except OSError as e:
        if mode == "copy":  # leave nothing half-copied; moved files are already safe in in/
            for d in done:
                d.unlink(missing_ok=True)
        raise ValueError(f"Couldn't {mode} the file: {e.strerror or e}") from e
    return DataFile(name=name, filename=moves[0][1].name, layer=layer)


def data_load(files: list[DataFile]) -> dict:
    """The data.load block: per entry, the file (and layer) and the columns it loads."""
    out = {}
    for f in files:
        entry: dict = {"filename": f.filename}
        if f.layer:
            entry["layer"] = f.layer
        if f.load:
            entry["load"] = {field: spec[0] if len(spec) == 1 else spec for field, spec in f.load.items()}
        if f.calc:
            entry["calc"] = dict(f.calc)
        if f.holds == "sales":
            # Without this OpenAVMKit de-duplicates on key, the parcel ID, dropping repeat sales of a parcel.
            entry["dupes"] = {"subset": ["key_sale"], "sort_by": ["key_sale", "asc"], "drop": True}
        out[f.name] = entry
    return out


def column_names(path: Path, layer: str | None) -> list[str] | None:
    """The file's columns as OpenAVMKit sees them (geometry included), reading names only. None if unreadable."""
    from openavmkit.data import _snoop_column_names

    try:
        return [str(c) for c in _snoop_column_names(str(path), layer)]
    except Exception:  # noqa: BLE001 - a damaged file shows as unknown, not an error page
        return None


def has_geometry(path: Path, layer: str | None) -> bool | None:
    """Whether OpenAVMKit sees a geometry column."""
    names = column_names(path, layer)
    return None if names is None else "geometry" in names


def rename(files: list[DataFile], old: str, new: str) -> None:
    """Rename a data.load entry in place. The file keeps its name (SPEC F3b)."""
    entry = _entry(files, old)
    if new == old:
        return
    if not NAME.fullmatch(new):
        raise ValueError("Names use lowercase letters, digits and underscores, and start with a letter.")
    if new in {f.name for f in files}:
        raise ValueError(f"This project already has a file called {new}.")
    entry.name = new


def remove(in_dir: Path, files: list[DataFile], name: str, trash: bool) -> None:
    """Drop a data.load entry and, if asked, send its file (and sidecars) to the Recycle Bin."""
    entry = _entry(files, name)
    path = in_dir / entry.filename
    if trash and path.is_file():
        if any(f.filename == entry.filename for f in files if f is not entry):
            raise ValueError(f"Another entry also uses {entry.filename}, so it stays in the project folder.")
        from send2trash import send2trash

        for p in companions(path):
            send2trash(str(p))
    files.remove(entry)


def _entry(files: list[DataFile], name: str) -> DataFile:
    for f in files:
        if f.name == name:
            return f
    raise LookupError(name)

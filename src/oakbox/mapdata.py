"""The map window's data (SPEC §3.15): the 🌐 Parcel Universe's shapes and centres, and any field's values, in the
universe file's row order.

Made once in the background when the universe is set (or first asked for), from the universe file itself, so the map
is there during setup, before any run: each parcel simplified to about a metre (Guilford's 222,135 parcels: 1.4 million
corners, 11 MB), its centre, and the box around them all, in `out/oakbox/map/`. The map draws cells from the centres
when zoomed out and the shapes of the parcels in view when zoomed in, picked out in the browser (tested 2026-11-08).

A field's values come from whichever parcel file holds it, joined on the parcel ID as a run joins it; a file with
several rows a parcel (buildings) gives the parcel its first non-blank value.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import BaseModel, DataFile
from oakbox.errors import NotFound
from oakbox.projects import Project
from oakbox.steps import out_dir
from oakbox.wizard.files import Files, dictionary_by_key, file_stamp, values_of

VERSION = 1  # a new make when this changes
TOLERANCE_M = 1.0  # simplified to about a metre: no visible change at street zoom
CATEGORIES = 12  # most common values coloured; the rest are "other"
NUMERIC = 0.9  # a column is numbers when this share of its non-blank values read as one

# The Big five first in the field list (SPEC F3c), then the other fields, then each file's other columns.
BIG_FIVE = [
    "land_area_sqft",
    "bldg_area_finished_sqft",
    "bldg_year_built",
    "bldg_quality_num",
    "bldg_condition_num",
]


def map_dir(project_dir: Path) -> Path:
    return out_dir(project_dir, "map")


# ---------- Making it ----------


@dataclass
class Making:
    started: float
    error: str | None = None


_making: dict[str, Making] = {}
_guard = threading.Lock()


def _stamp_of(in_dir: Path, base: DataFile) -> list:
    stamp = file_stamp(in_dir / base.filename)
    return [stamp[0], stamp[1], stamp[2], base.layer]


def _made(project_dir: Path, stamp: list) -> dict | None:
    meta = map_dir(project_dir) / "meta.json"
    try:
        made = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return made if made.get("from") == stamp and made.get("v") == VERSION else None


def _make(project_dir: Path, path: Path, layer: str | None, stamp: list) -> None:
    import warnings

    import geopandas as gpd
    import numpy as np

    from oakbox.groups import _binary

    gdf = (
        gpd.read_parquet(path)
        if path.suffix.lower() in (".parquet", ".geoparquet")
        else gpd.read_file(path, layer=layer)
    )
    if gdf.crs is None:
        raise ValueError("the parcel file has no coordinate system (a .prj file), so it can't be placed")
    geoms = gdf.geometry
    if gdf.crs.is_geographic:
        geoms = geoms.simplify(TOLERANCE_M / 111_000, preserve_topology=True)
    else:
        unit = str(gdf.crs.axis_info[0].unit_name).lower() if gdf.crs.axis_info else "metre"
        geoms = geoms.simplify(TOLERANCE_M * (3.28084 if "foot" in unit else 1.0), preserve_topology=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # a centre worked out in degrees is near enough for a cell
        centres = geoms.centroid
    if not gdf.crs.is_geographic:
        centres = centres.to_crs(4326)
        geoms = geoms.to_crs(4326)
    xy = np.full((len(gdf), 2), np.nan, dtype="<f4")
    has = ~(centres.isna() | centres.is_empty).to_numpy()
    xy[has, 0] = centres.x.to_numpy()[has]
    xy[has, 1] = centres.y.to_numpy()[has]
    target = map_dir(project_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "shapes.bin.tmp").write_bytes(_binary(geoms.to_numpy()))
    (target / "centres.bin.tmp").write_bytes(xy.tobytes())
    (target / "shapes.bin.tmp").replace(target / "shapes.bin")
    (target / "centres.bin.tmp").replace(target / "centres.bin")
    w, s, e, n = (float(v) for v in geoms.total_bounds)
    (target / "meta.json").write_text(
        json.dumps({"from": stamp, "v": VERSION, "parcels": len(gdf), "bounds": [[w, s], [e, n]]}), encoding="utf-8"
    )


def _run(project_dir: Path, path: Path, layer: str | None, stamp: list, m: Making) -> None:
    try:
        _make(project_dir, path, layer, stamp)
    except Exception as e:  # noqa: BLE001 - told on the map
        m.error = str(e)
    finally:
        with _guard:
            if _making.get(str(project_dir)) is m and m.error is None:
                del _making[str(project_dir)]


def start(project: Project, project_dir: Path, in_dir: Path) -> None:
    """Make the map's data in the background, unless it's made for this universe file or under way."""
    base = project.base_file()
    if base is None or not (in_dir / base.filename).is_file():
        return
    stamp = _stamp_of(in_dir, base)
    if _made(project_dir, stamp) is not None:
        return
    with _guard:
        m = _making.get(str(project_dir))
        if m is not None and m.error is None:
            return  # under way
        m = _making[str(project_dir)] = Making(started=time.time())
    threading.Thread(target=_run, args=(project_dir, in_dir / base.filename, base.layer, stamp, m), daemon=True).start()


# ---------- What the map is told ----------


class MapField(BaseModel):
    id: str = Field(description="file:column, as asked for by column().")
    label: str
    file: str
    column: str
    field: str | None = Field(description="The field it's loaded as, if it is.")


class MapInfo(BaseModel):
    status: Literal["none", "making", "ready", "failed"] = Field(
        description="none: no 🌐 Parcel Universe yet; making: its shapes are being prepared."
    )
    error: str | None = None
    since: float | None = Field(default=None, description="When making started (seconds since 1970).")
    parcels: int = 0
    bounds: list[list[float]] | None = Field(default=None, description="[[west, south], [east, north]].")
    stamp: str = Field(default="", description="Changes when the shapes are made again: the files' cache key.")
    fields: list[MapField] = []
    sales: list[str] = Field(
        default=[], description="What the 💰 Sales Record can colour by: price, year, valid, vacant (as it has them)."
    )


def _short(name: str) -> str:
    """A field's name without its unit: "Building area (finished)", not "… in square feet" (the column says which)."""
    import re

    return re.sub(r" in (square feet|square meters|square metres|acres|hectares)$", "", name)


def _fields(project: Project, in_dir: Path) -> list[MapField]:
    files = Files(project, in_dir)
    names = {k: d.name for k, d in dictionary_by_key().items()}
    loaded: list[MapField] = []
    others: list[MapField] = []
    for f in project.files:
        if f.holds != "parcels" or f.name not in files.preview:
            continue
        by_column = {spec[0]: key for key, spec in f.load.items() if spec}
        ids = {spec[0] for key, spec in f.load.items() if spec and (key == "key" or key.startswith("key"))}
        for c in files.columns(f.name):
            if c.name in ids or c.name == "geometry":
                continue
            key = by_column.get(c.name)
            item = MapField(
                id=f"{f.name}:{c.name}",
                label=f"{_short(names.get(key, key))} ({c.name})" if key else c.name,
                file=f.name,
                column=c.name,
                field=key,
            )
            (loaded if key else others).append(item)
    rank = {k: i for i, k in enumerate(BIG_FIVE)}
    loaded.sort(key=lambda m: (rank.get(m.field or "", len(rank)), m.label.lower()))
    return loaded + others


def info(project: Project, project_dir: Path, in_dir: Path) -> MapInfo:
    base = project.base_file()
    if base is None or not (in_dir / base.filename).is_file():
        return MapInfo(status="none")
    stamp = _stamp_of(in_dir, base)
    made = _made(project_dir, stamp)
    if made is None:
        start(project, project_dir, in_dir)
        m = _making.get(str(project_dir))
        if m is not None and m.error:
            return MapInfo(status="failed", error=m.error)
        made = _made(project_dir, stamp)  # it may have finished just now
        if made is None:
            return MapInfo(status="making", since=m.started if m else None)
    return MapInfo(
        status="ready",
        parcels=made["parcels"],
        bounds=made["bounds"],
        stamp=f"{stamp[2]}-{int(stamp[1])}",
        fields=_fields(project, in_dir),
        sales=_sales_has(project),
    )


def _sales_has(project: Project) -> list[str]:
    from oakbox.wizard.files import sales_file
    from oakbox.wizard.rules import rule_complete

    entry = sales_file(project)
    if entry is None:
        return []
    out = []
    if entry.load.get("sale_price"):
        out.append("price")
    spec = entry.load.get("sale_date")
    if spec and len(spec) > 2:
        out.append("year")
    for key, name in (("valid_sale", "valid"), ("vacant_sale", "vacant")):
        rule = entry.rules.get(key)
        if entry.load.get(key) or (rule is not None and rule_complete(rule)):
            out.append(name)
    return out


def file_of(project_dir: Path, name: Literal["shapes", "centres"]) -> Path:
    p = map_dir(project_dir) / f"{name}.bin"
    if not p.is_file():
        raise NotFound(name)
    return p


# ---------- A field's values, for colouring ----------


class MapColumn(BaseModel):
    id: str
    kind: Literal["number", "category"]
    values: str = Field(
        description="Base64: numbers, float32 little-endian, NaN blank; categories, uint16 little-endian: an index "
        "into categories, 65535 blank, 65534 another value."
    )
    have: int = Field(description="Parcels with a value.")
    categories: list[str] = []
    counts: list[int] = Field(default=[], description="Parcels with each category, as categories.")
    quantiles: list[float] = Field(default=[], description="Numbers: the values at every 0.2% (the histogram's).")
    auto: list[float] = Field(default=[], description="Numbers: the automatic range, [low, high].")


def _as_number(text: str) -> float | None:
    v = text.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
    try:
        f = float(v)
    except ValueError:
        return None
    return f if f == f and abs(f) != float("inf") else None


@lru_cache(maxsize=16)
def _column(
    base_stamp: tuple[str, float, int],
    base_layer: str | None,
    universe_ids: tuple[str, ...],
    stamp: tuple[str, float, int],
    layer: str | None,
    column: str,
    row_ids: tuple[str, ...] | None,
) -> MapColumn:
    import numpy as np

    from oakbox.wizard.money import quantiles_and_auto

    values = values_of(stamp, layer, column)
    if row_ids is None:  # the universe file itself: its rows are the parcels
        per = list(values)
    else:
        first: dict[str, str] = {}
        for i, v in zip(row_ids, values, strict=False):
            if i and v and i not in first:
                first[i] = v
        per = [first.get(i, "") for i in universe_ids]
    filled = [v for v in per if v]
    numbers = [_as_number(v) for v in per]
    read = sum(1 for n in numbers if n is not None)
    if filled and read >= NUMERIC * len(filled):
        arr = np.array([np.nan if n is None else n for n in numbers], dtype="<f4")
        ordered = sorted(n for n in numbers if n is not None)
        q, auto = quantiles_and_auto(ordered) if ordered else ([], [])
        return MapColumn(
            id="",
            kind="number",
            values=base64.b64encode(arr.tobytes()).decode(),
            have=read,
            quantiles=q,
            auto=auto,
        )
    from collections import Counter

    counts = Counter(filled)
    top = [v for v, _ in counts.most_common(CATEGORIES)]
    index = {v: k for k, v in enumerate(top)}
    codes = np.array([index.get(v, 65534) if v else 65535 for v in per], dtype="<u2")
    return MapColumn(
        id="",
        kind="category",
        values=base64.b64encode(codes.tobytes()).decode(),
        have=len(filled),
        categories=top,
        counts=[counts[v] for v in top],
    )


def column(project: Project, in_dir: Path, field_id: str) -> MapColumn:
    """A field's value for every parcel, in the universe file's order (a parcel file joined on its ID)."""
    name, _, col = field_id.partition(":")
    files = Files(project, in_dir)
    base = project.base_file()
    entry = project.file(name)
    if base is None or entry is None or entry.holds != "parcels" or files.column(name, col) is None:
        raise NotFound(field_id)
    base_stamp = file_stamp(in_dir / base.filename)
    universe_ids = files.ids(base.name, "key")
    row_ids = None if entry.name == base.name else tuple(files.parcel_ids(entry.name))
    out = _column(base_stamp, base.layer, universe_ids, file_stamp(in_dir / entry.filename), entry.layer, col, row_ids)
    return out.model_copy(update={"id": field_id})


# ---------- The 💰 Sales Record, on the parcels ----------

YES = {"1", "y", "yes", "true", "t", "x", "valid", "vacant"}
NO = {"0", "n", "no", "false", "f", "invalid", "improved"}


class MapSales(BaseModel):
    """Each sale of the main sales file, at its parcel (a sale has no place of its own): base64 arrays, one entry a
    sale, in the file's order."""

    sales: int
    placed: int = Field(description="Sales whose parcel is in the 🌐 Parcel Universe: the ones on the map.")
    parcel: str = Field(description="int32: the parcel's index in the universe's order, -1 none.")
    price: str = Field(description="float32, NaN blank.")
    year: str = Field(description="float32: the sale date as a year and its fraction (2023.5 mid-2023), NaN blank.")
    valid: str = Field(description="int8: 1 valid, 0 not, -1 unknown.")
    vacant: str = Field(description="int8: 1 vacant, 0 not, -1 unknown.")
    price_quantiles: list[float] = []
    price_auto: list[float] = []
    year_quantiles: list[float] = []
    year_auto: list[float] = []
    has: list[str] = Field(description="Which of price, year, valid, vacant the sales file has.")


def _b64(a) -> str:
    return base64.b64encode(a.tobytes()).decode()


def _flag(files: Files, entry: DataFile, key: str):
    """A yes/no sale field per row (1, 0, -1 unknown): its rule run as a run runs it, else its column read; None when
    neither is set."""
    import numpy as np

    from oakbox.wizard.rules import rule_complete, rule_result

    rule = entry.rules.get(key)
    if rule is not None and rule_complete(rule):
        _, _, result = rule_result(files, entry, rule)
        return np.where(result.to_numpy(), 1, 0).astype("i1")
    spec = entry.load.get(key)
    if not spec:
        return None
    values = files.values(entry.name, spec[0])
    return np.array(
        [
            1 if v.lower() in YES else 0 if v.lower() in NO else (1 if (n := _as_number(v)) else 0 if n == 0 else -1)
            for v in values
        ],
        dtype="i1",
    )


def sales(project: Project, in_dir: Path) -> MapSales:
    import numpy as np

    from oakbox.wizard.files import sales_file
    from oakbox.wizard.money import quantiles_and_auto, read_numbers
    from oakbox.wizard.rules import parse_dates

    files = Files(project, in_dir)
    base = project.base_file()
    entry = sales_file(project)
    if base is None or entry is None or entry.name not in files.preview:
        raise NotFound("sales")
    index: dict[str, int] = {}
    for i, k in enumerate(files.ids(base.name, "key")):
        if k and k not in index:
            index[k] = i
    keys = files.parcel_ids(entry.name)
    n = len(keys)
    parcel = np.array([index.get(k, -1) if k else -1 for k in keys], dtype="<i4")
    stamp = file_stamp(in_dir / entry.filename)
    has = []
    price = np.full(n, np.nan, dtype="<f4")
    spec = entry.load.get("sale_price")
    if spec:
        if "sale_price" in entry.numbers:
            read = read_numbers(stamp, entry.layer, spec[0], entry.numbers["sale_price"].model_dump_json())
            price = np.array(read, dtype="<f4")
        else:
            price = np.array(
                [np.nan if (x := _as_number(v)) is None else x for v in files.values(entry.name, spec[0])], dtype="<f4"
            )
        has.append("price")
    year = np.full(n, np.nan, dtype="<f4")
    spec = entry.load.get("sale_date")
    if spec and len(spec) > 2:
        d = parse_dates(stamp, entry.layer, spec[0], spec[2])
        year = (d.dt.year + (d.dt.dayofyear - 1) / 365.25).to_numpy(dtype="<f4", na_value=np.nan)
        has.append("year")
    flags = {}
    for key, name in (("valid_sale", "valid"), ("vacant_sale", "vacant")):
        f = _flag(files, entry, key)
        if f is not None:
            has.append(name)
        flags[name] = f if f is not None else np.full(n, -1, dtype="i1")

    def spread(a):
        ok = sorted(float(x) for x in a[(parcel >= 0) & ~np.isnan(a)])
        return quantiles_and_auto(ok) if ok else ([], [])

    pq, pa = spread(price)
    yq, ya = spread(year)
    return MapSales(
        sales=n,
        placed=int((parcel >= 0).sum()),
        parcel=_b64(parcel),
        price=_b64(price),
        year=_b64(year),
        valid=_b64(flags["valid"]),
        vacant=_b64(flags["vacant"]),
        price_quantiles=pq,
        price_auto=pa,
        year_quantiles=yq,
        year_auto=ya,
        has=has,
    )


# ---------- Problems, where they are ----------


class MapProblemItem(BaseModel):
    id: str = Field(description="pr:blank_ids, pr:repeated_ids, or pr:differs:<field>.")
    label: str
    on: Literal["pu", "sr"] = Field(description="pu: marks parcels; sr: marks sales (at their parcels).")
    count: int
    of: int


class MapProblems(BaseModel):
    items: list[MapProblemItem]
    unplaced: int = Field(description="Sales whose parcel isn't in the 🌐 Parcel Universe: a problem with no place.")


class MapProblem(BaseModel):
    id: str
    on: Literal["pu", "sr"]
    flags: str = Field(description="int8 base64, a parcel (pu) or a sale (sr) each: 1 the problem, 0 not, -1 n/a.")
    count: int
    of: int


def _id_flags(project: Project, in_dir: Path):
    import numpy as np

    files = Files(project, in_dir)
    base = project.base_file()
    if base is None:
        return None, None
    ids = files.ids(base.name, "key")
    blank = np.array([0 if k else 1 for k in ids], dtype="i1")
    from collections import Counter

    counts = Counter(k for k in ids if k)
    repeated = np.array([1 if k and counts[k] > 1 else 0 for k in ids], dtype="i1")
    return blank, repeated


@lru_cache(maxsize=8)
def _problems(project_json: str, in_dir: str, stamps: tuple) -> MapProblems:
    from oakbox.wizard.files import sales_file

    project = Project.model_validate_json(project_json)
    folder = Path(in_dir)
    items: list[MapProblemItem] = []
    blank, repeated = _id_flags(project, folder)
    if blank is not None and repeated is not None:
        n = len(blank)
        if blank.sum():
            items.append(MapProblemItem(id="pr:blank_ids", label="", on="pu", count=int(blank.sum()), of=n))
        if repeated.sum():
            items.append(MapProblemItem(id="pr:repeated_ids", label="", on="pu", count=int(repeated.sum()), of=n))
    unplaced = 0
    entry = sales_file(project)
    if entry is not None and project.base_file() is not None:
        files = Files(project, folder)
        if entry.name in files.preview:
            base = project.base_file()
            known = set(files.ids(base.name, "key")) if base else set()
            unplaced = sum(1 for k in files.parcel_ids(entry.name) if not k or k not in known)
            for r in _as_sold_rows(project_json, in_dir, stamps):
                # Written differently (Guilford's grade codes against scores): not a difference, the step says so.
                if r.column and r.compared and r.compared > r.same and not r.written_differently:
                    items.append(
                        MapProblemItem(
                            id=f"pr:differs:{r.key}",
                            label=_short(r.name),
                            on="sr",
                            count=r.compared - r.same,
                            of=r.compared,
                        )
                    )
    return MapProblems(items=items, unplaced=unplaced)


def _stamps(project: Project, in_dir: Path) -> tuple:
    out = []
    for f in project.files:
        path = in_dir / f.filename
        if path.is_file():
            out.append(file_stamp(path))
    return tuple(out)


def problems(project: Project, in_dir: Path) -> MapProblems:
    """What problems the map can show where they are, with how many: worked out again only when the project or its
    files change (comparing the 💰 sales' values with their parcels' takes seconds on a county)."""
    return _problems(project.model_dump_json(), str(in_dir), _stamps(project, in_dir))


def problem(project: Project, in_dir: Path, problem_id: str) -> MapProblem:
    """Which parcels (or sales) have the problem: kept until the project or its files change."""
    return _problem(project.model_dump_json(), str(in_dir), _stamps(project, in_dir), problem_id)


@lru_cache(maxsize=16)
def _problem(project_json: str, folder: str, stamps: tuple, problem_id: str) -> MapProblem:
    import numpy as np

    from oakbox.wizard import as_sold

    project = Project.model_validate_json(project_json)
    in_dir = Path(folder)

    if problem_id in ("pr:blank_ids", "pr:repeated_ids"):
        blank, repeated = _id_flags(project, in_dir)
        if blank is None or repeated is None:
            raise NotFound(problem_id)
        a = blank if problem_id == "pr:blank_ids" else repeated
        return MapProblem(id=problem_id, on="pu", flags=_b64(a), count=int(a.sum()), of=len(a))
    if problem_id.startswith("pr:differs:"):
        flags = as_sold.differs(project, in_dir, problem_id.removeprefix("pr:differs:"))
        if flags is None:
            raise NotFound(problem_id)
        a = np.array(flags, dtype="i1")
        return MapProblem(id=problem_id, on="sr", flags=_b64(a), count=int((a == 1).sum()), of=int((a >= 0).sum()))
    raise NotFound(problem_id)


# ---------- A parcel's card ----------

UNIT_WORDS = {"sqft": "sq ft", "sqm": "m²", "acres": "acres", "hectares": "ha", "sqyd": "sq yd"}


class CardValue(BaseModel):
    label: str
    value: str
    field: str | None = Field(description="The field it's loaded as (its step links there); None: another column.")
    file: str
    column: str


class CardCompare(BaseModel):
    field: str
    label: str
    sold: str = Field(description="The sale's own value, as the 💰 Sales Record writes it.")
    today: str = Field(description="The parcel's, in the 🌐 Parcel Universe.")
    differs: bool
    written_differently: bool = Field(description="The two are written differently (codes against scores).")


class CardSale(BaseModel):
    row: int = Field(description="Its row in the sales file (0 the first).")
    date: str = Field(description="YYYY-MM-DD, or as written if it doesn't read as a date.")
    price: str
    valid: int = Field(description="1 valid, 0 not, -1 unknown.")
    vacant: int
    compared: list[CardCompare]


class ParcelCard(BaseModel):
    index: int
    key: str
    fields: list[CardValue] = Field(description="Its fields first (the Big five first), then the files' other columns.")
    rows: dict[str, int] = Field(description="Rows each parcel file has for it (a building file: one a building).")
    sales: list[CardSale] = Field(description="Its sales, the latest first.")


@lru_cache(maxsize=4)
def _sales_cached(project_json: str, in_dir: str, stamps: tuple) -> MapSales:
    return sales(Project.model_validate_json(project_json), Path(in_dir))


def sales_kept(project: Project, in_dir: Path) -> MapSales:
    """sales(), kept until the project or its files change (a parcel's card reads its sales' flags from it)."""
    return _sales_cached(project.model_dump_json(), str(in_dir), _stamps(project, in_dir))


@lru_cache(maxsize=4)
def _as_sold_rows(project_json: str, in_dir: str, stamps: tuple):
    from oakbox.wizard import as_sold

    return as_sold.view(Project.model_validate_json(project_json), Path(in_dir)).rows


@lru_cache(maxsize=256)
def _row(stamp: tuple[str, float, int], layer: str | None, row: int) -> dict[str, str]:
    """One row of a file, every column as text (blank ""): read alone, not column by column (a parcel file has
    hundreds). From its Parquet copy (or itself), only the row group holding it; a GeoPackage or shapefile, the one
    feature."""
    import pandas as pd

    from oakbox import readcache
    from oakbox.datafiles import csv_encoding

    path = Path(stamp[0])
    ext = path.suffix.lower().lstrip(".")
    source = readcache.ready(path) if ext == "csv" else path if ext in ("parquet", "geoparquet") else None
    if source is not None:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(source)
        names = [n for n in pf.schema_arrow.names if n != "geometry"]
        start = 0
        for g in range(pf.num_row_groups):
            size = pf.metadata.row_group(g).num_rows
            if row < start + size:
                df = pf.read_row_group(g, columns=names).slice(row - start, 1).to_pandas()
                break
            start += size
        else:
            return {}
    elif ext == "csv":
        df = pd.read_csv(
            path,
            skiprows=list(range(1, row + 1)),
            nrows=1,
            dtype=str,
            keep_default_na=False,
            encoding=csv_encoding(path),
        )
    else:
        import pyogrio

        df = pyogrio.read_dataframe(path, layer=layer, skip_features=row, max_features=1, read_geometry=False)
    if df.empty:
        return {}
    out = {}
    for c, v in df.iloc[0].items():
        out[str(c)] = "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v).strip()
    return out


@lru_cache(maxsize=16)
def _rows_by_parcel(stamp: tuple, ids: tuple[str, ...]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, k in enumerate(ids):
        if k:
            out.setdefault(k, []).append(i)
    return out


def card(project: Project, in_dir: Path, index: int) -> ParcelCard:
    """One parcel, as each file has it, and its sales with their own values beside the parcel's (SPEC §3.15)."""
    import numpy as np

    from oakbox.datafiles import AREA_FIELDS, SQFT_PER
    from oakbox.dates import date_format_of, iso_day
    from oakbox.wizard.as_sold import _numeric, _same
    from oakbox.wizard.files import sales_file

    files = Files(project, in_dir)
    base = project.base_file()
    if base is None:
        raise NotFound("parcel")
    universe = files.ids(base.name, "key")
    if not 0 <= index < len(universe):
        raise NotFound(f"parcel {index}")
    key = universe[index]
    names = {k: d.name for k, d in dictionary_by_key().items()}
    rank = {k: i for i, k in enumerate(BIG_FIVE)}
    loaded: list[tuple[tuple, CardValue]] = []
    others: list[CardValue] = []
    rows: dict[str, int] = {}
    today: dict[str, str] = {}  # field -> the parcel's value, for its sales
    for f in project.files:
        if f.holds != "parcels" or f.name not in files.preview:
            continue
        stamp = file_stamp(in_dir / f.filename)
        if f.name == base.name:
            mine = [index]
        else:
            ids = tuple(files.parcel_ids(f.name))
            mine = _rows_by_parcel(stamp, ids).get(key, []) if key else []
        rows[f.name] = len(mine)
        if not mine:
            continue
        values = _row(stamp, f.layer, mine[0])
        by_column = {spec[0]: k for k, spec in f.load.items() if spec}
        for c in files.columns(f.name):
            if c.name == "geometry":
                continue
            k = by_column.get(c.name)
            if k is not None and (k == "key" or k.startswith("key")):
                continue
            v = values.get(c.name, "")
            if k:
                today.setdefault(k, v)
                unit = f.area_units.get(k, "sqft") if k in AREA_FIELDS else None
                shown = f"{v} {UNIT_WORDS.get(unit, unit)}" if v and unit else v
                item = CardValue(label=_short(names.get(k, k)), value=shown, field=k, file=f.name, column=c.name)
                loaded.append(((rank.get(k, len(rank)), item.label.lower()), item))
            elif v:
                others.append(CardValue(label=c.name, value=v, field=None, file=f.name, column=c.name))
    loaded.sort(key=lambda x: x[0])
    out_sales: list[CardSale] = []
    entry = sales_file(project)
    if entry is not None and key and entry.name in files.preview:
        stamps = _stamps(project, in_dir)
        pj = project.model_dump_json()
        stamp = file_stamp(in_dir / entry.filename)
        mine = _rows_by_parcel(stamp, tuple(files.parcel_ids(entry.name))).get(key, [])
        d = _sales_cached(pj, str(in_dir), stamps) if mine else None
        valid = np.frombuffer(base64.b64decode(d.valid), dtype="i1") if d else None
        vacant = np.frombuffer(base64.b64decode(d.vacant), dtype="i1") if d else None
        compare_rows = [r for r in _as_sold_rows(pj, str(in_dir), stamps) if r.column] if mine else []
        date_col = (entry.load.get("sale_date") or [""])[0]
        price_col = (entry.load.get("sale_price") or [""])[0]
        date_fmt = date_format_of(files, entry, date_col) if date_col else None
        for i in mine:
            date = values_of(stamp, entry.layer, date_col)[i] if date_col else ""
            if date:
                date = iso_day(date, date_fmt)
            price = values_of(stamp, entry.layer, price_col)[i] if price_col else ""
            compared = []
            for r in compare_rows:
                sold = values_of(stamp, entry.layer, r.column)[i]
                now = today.get(r.key, "")
                if not sold or not now:
                    continue
                unit, today_unit = r.unit, r.today_unit
                factor = SQFT_PER[unit] / SQFT_PER[today_unit] if unit and today_unit else 1.0
                compared.append(
                    CardCompare(
                        field=r.key,
                        label=_short(r.name),
                        sold=f"{sold} {UNIT_WORDS.get(unit, unit)}" if unit else sold,
                        today=f"{now} {UNIT_WORDS.get(today_unit, today_unit)}" if today_unit else now,
                        differs=not _same(sold, now, _numeric(r.key), factor),
                        written_differently=r.written_differently,
                    )
                )
            out_sales.append(
                CardSale(
                    row=i,
                    date=date,
                    price=price,
                    valid=int(valid[i]) if valid is not None else -1,
                    vacant=int(vacant[i]) if vacant is not None else -1,
                    compared=compared,
                )
            )
        out_sales.sort(key=lambda s: s.date, reverse=True)
    return ParcelCard(index=index, key=key, fields=[x for _, x in loaded] + others, rows=rows, sales=out_sales)

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
                label=f"{names.get(key, key)} ({c.name})" if key else c.name,
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

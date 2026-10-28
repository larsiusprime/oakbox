"""F2 and F3b (SPEC §3.0): put a file in the project's in/, declare it under data.load, rename, remove.

Mirrors OpenAVMKit: raw files live in the locality's in/, and each is an entry in
``data.load`` with its ``filename`` (and ``layer`` for a GeoPackage). Nothing here
reads the data itself; OpenAVMKit does that when it loads.
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

# Exactly what OpenAVMKit's data.load reads (by extension, case-insensitively).
FORMATS = {
    "csv": "CSV",
    "parquet": "Parquet",
    "geoparquet": "Parquet",
    "gpkg": "GeoPackage",
    "shp": "Shapefile",
    "geojson": "GeoJSON",
}
# A shapefile can't be read without these next to the .shp.
SHAPEFILE_REQUIRED = ("shx", "dbf")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class BaseModel(_PydanticBase):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# overlay: a map layer (zoning, school zones, parks) joined onto the parcels by where they are (F3d Shapefiles).
Holds = Literal["parcels", "sales", "unused", "overlay"]
# The ID a file joins on: the universe's parcel ID or an extra ID; or, for more sales details, the sale ID.
Match = Literal["key", "key2", "key3", "key_sale"]
# The universe's extra IDs, after its parcel ID (key): the ones OpenAVMKit knows by name.
EXTRA_IDS = ("key2", "key3")
# Area: the wizard's fields are named in square feet (the dictionary's); a metric project writes them as
# square metres, OpenAVMKit's other "small" unit. A column in any of these is converted when it loads.
AreaUnit = Literal["sqft", "sqm", "acres", "hectares", "sqyd", "tsubo", "pyeong", "mu"]
SQFT_PER: dict[str, float] = {
    "sqft": 1.0,
    "sqm": 10.763910416709722,
    "acres": 43_560.0,
    "hectares": 107_639.10416709722,
    "sqyd": 9.0,
    "tsubo": 35.58317,  # Japan: 400/121 m²
    "pyeong": 35.58317,  # Korea: the same 400/121 m²
    "mu": 7_175.94,  # China: 2,000/3 m²
}
AREA_FIELDS = ("land_area_sqft", "bldg_area_finished_sqft", "bldg_area_footprint_sqft")


def area_key(field: str, units: str) -> str:
    """The name OpenAVMKit gives an area field in this project's units: land_area_sqft or land_area_sqm."""
    return field[: -len("_sqft")] + "_sqm" if units == "metric" and field in AREA_FIELDS else field


def small_unit(units: str) -> AreaUnit:
    return "sqm" if units == "metric" else "sqft"


def guess_area_unit(column: str) -> AreaUnit | None:
    """The unit a column's name gives away (ACRES, LAND_HA, LOT_SQM); None if it doesn't."""
    words = set(re.split(r"[^a-z0-9]+", column.lower()))
    flat = re.sub(r"[^a-z0-9]", "", column.lower())
    if words & {"acres", "acre", "ac", "acreage"} or "acre" in flat:
        return "acres"
    if words & {"ha", "hectares", "hectare"} or "hectare" in flat:
        return "hectares"
    if words & {"sqm", "m2", "sqmt"} or flat.endswith(("sqm", "m2")):
        return "sqm"
    if words & {"sqft", "sf", "ft2"} or flat.endswith(("sqft", "sf")):
        return "sqft"
    if "tsubo" in flat:
        return "tsubo"
    if "pyeong" in flat:
        return "pyeong"
    return None


StampKind = Literal["location", "category", "number"]
DistanceUnit = Literal["m", "km", "ft", "mile"]


class StampField(BaseModel):
    """A column of a map layer copied onto each parcel whose centre falls in one of its shapes."""

    column: str
    name: str = Field(description="What the parcels call it.")
    kind: StampKind = Field(default="location", description="location: an area (a category models group by).")


class Overlay(BaseModel):
    """A map layer used to describe the parcels (F3d Shapefiles), as OpenAVMKit's settings allow.

    stamp: enrich.geometry, the shape each parcel's centre falls in (predicate contains_centroid), copying
    the chosen columns. distance: enrich.distances, how far each parcel is from the nearest feature.
    """

    use: Literal["stamp", "distance"] | None = None
    fields: list[StampField] = Field(default_factory=list, description="stamp: the columns to copy.")
    feature: str = Field(default="", description="distance: names the columns, dist_to_<feature>.")
    max_distance: float | None = Field(default=None, gt=0, description="distance: past it, no distance.")
    unit: DistanceUnit = "km"
    store_top: bool = Field(default=False, description="distance: also to each of the top N features.")
    top_n: int = Field(default=0, ge=0)
    sort_field: Literal["area", "length"] | None = Field(default=None, description="Ranks the top N.")
    name_column: str | None = Field(default=None, description="Names each feature (for the top N).")


def overlay_load(o: Overlay) -> dict[str, list[str]]:
    """What a layer loads: the copied columns under their names, or the name column as "name"."""
    if o.use == "stamp":
        return {f.name: [f.column, "float" if f.kind == "number" else "string"] for f in o.fields}
    if o.use == "distance" and o.name_column:
        return {"name": [o.name_column, "string"]}
    return {}


def overlay_distance(name: str, o: Overlay) -> dict:
    """The layer's entry in enrich.distances."""
    out: dict = {"enabled": True, "source": name, "unit": o.unit}
    if o.max_distance is not None:
        out["max_distance"] = o.max_distance
    if o.store_top and o.top_n:
        out |= {"store_top": True, "top_n": o.top_n}
        if o.sort_field:
            out["sort_field"] = o.sort_field
    return out


class NumberFormat(BaseModel):
    """How to read a column of money written as text ($250,000.00, 250.000,00, $250K, (10)) as a number (F3d)."""

    decimal: Literal[".", ","] = Field(default=".", description="The decimal mark; the other one groups thousands.")
    suffixes: bool = Field(default=False, description="K and M stand for thousands and millions ($250K, $1.2M).")
    scale: float = Field(default=1, gt=0, description="Multiply by this once read: 1000 for $1,000s, 0.01 for cents.")


# Anything that isn't a plain number once cleaned up (N/A, TBD, -, blank) reads as missing: asfloat fails on
# text, so it's turned into "nan" first.
NOT_A_NUMBER = r"^(?![-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$).*$"


def number_helper(field: str) -> str:
    """The name the column's text is loaded under, before it's read as the field."""
    return f"{field}_text"


def number_calc(field: str, fmt: NumberFormat) -> list:
    """The OpenAVMKit calc that reads the text loaded as number_helper(field) as a number."""
    # Keep digits, the marks, parentheses, signs, E (1.11E+06) and K/M; drop $, spaces, currency codes, words.
    e: Any = [
        "replace_regex",
        number_helper(field),
        {r"[^0-9.,()+\-eEkKmM]": "", r"^\((.*)\)$": r"-\1"},  # (10) is -10, as accounts write it
    ]
    e = ["replace", e, {",": ""} if fmt.decimal == "." else {".": "", ",": "."}]
    text = e
    if fmt.suffixes:
        e = ["replace_regex", e, {"[kKmM]$": ""}]
    e = ["asfloat", ["replace_regex", e, {NOT_A_NUMBER: "nan"}]]
    if fmt.suffixes:
        times = ["replace_regex", text, {"^.*[kK]$": "K", "^.*[mM]$": "M", "^(?![KM]$).*$": "1"}]
        e = ["*", e, ["asfloat", ["replace", times, {"K": "1000", "M": "1000000"}]]]
    if fmt.scale != 1:
        e = ["*", e, fmt.scale]
    return e


ScaleKind = Literal["higher", "lower", "pct_good", "pct_depr", "life", "tiers"]


class Scale(BaseModel):
    """How a quality or condition column becomes a number where higher is better, as OpenAVMKit wants (F3d).

    higher: as written. lower: flipped within the column's range (low + high - x). pct_good: % good, as written
    (or x 100 from a fraction). pct_depr: % depreciation, written as 100 - x. life: remaining economic life in
    years, as written. tiers: a category, each value given a number."""

    kind: ScaleKind | None = Field(default=None, description="None: not said yet, so nothing is written.")
    fraction: bool = Field(default=False, description="% good or % depreciation written as 0-1, not 0-100.")
    low: float | None = Field(default=None, description="lower: the column's smallest value.")
    high: float | None = Field(default=None, description="lower: the column's largest value.")
    tiers: dict[str, float] = Field(default_factory=dict, description="tiers: each value (as written) -> its number.")


def scale_helper(field: str) -> str:
    """The name a column is loaded under before it's turned into the field."""
    return f"{field}_src"


def scale_calc(source: Any, s: Scale) -> list | None:
    """The OpenAVMKit calc turning `source` into the field, or None when it's used as written."""
    if s.kind == "tiers":
        # A value not ranked (or blank) reads as missing: map leaves it as written, which isn't a number.
        # Tiers are named as read, trimmed; the file's values may be padded (fixed-width exports).
        named = ["map", ["strip", source], {k.strip(): f"{v:g}" for k, v in s.tiers.items()}]
        return ["asfloat", ["replace_regex", named, {NOT_A_NUMBER: "nan"}]]
    pct = ["*", source, 100] if s.fraction else source
    if s.kind == "pct_depr":
        return ["-", 100, pct]
    if s.kind == "pct_good" and s.fraction:
        return pct
    if s.kind == "lower" and s.low is not None and s.high is not None:
        return ["-", s.low + s.high, source]
    return None


def scale_ready(s: Scale) -> bool:
    return s.kind is not None and (s.kind != "tiers" or bool(s.tiers))


# Quality and condition: the number and the category of each.
QC_FIELDS = ("bldg_quality_num", "bldg_quality_txt", "bldg_condition_num", "bldg_condition_txt")


def raw_name(column: str) -> str:
    """The name a column is loaded under when several fields are worked out from it."""
    slug = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_") or "column"
    return f"{slug if slug[0].isalpha() else 'col_' + slug}_raw"


CleanKind = Literal["zeros", "remove", "trim", "replace", "first", "last", "before", "after"]


class CleanStep(BaseModel):
    """One clean-up step on an ID, so IDs written differently in two files match (F3d reconcile)."""

    kind: CleanKind = Field(
        description="zeros: remove leading zeros; remove: remove the characters in text; trim: spaces at the ends; "
        "replace: text with to; first/last: keep the first/last n characters; before/after: the text before/after "
        "the first text."
    )
    text: str = ""
    to: str = ""
    n: int = Field(default=0, ge=0)


RuleOp = Literal["isin", "notin", "==", "!=", "contains", "isempty", "notempty", ">", "<", ">=", "<="]
NUMERIC_OPS = (">", "<", ">=", "<=")
BLANK = ""  # in an isin condition's values: the rows where the column is blank


class Condition(BaseModel):
    """One test on a column of the sales file, as an OpenAVMKit filter."""

    column: str
    op: RuleOp = "isin"
    values: list[str] = Field(
        default_factory=list,
        description='isin/notin: the values ("" for blank); ==, !=, contains, >, <, >=, <=: the first one.',
    )


class Rule(BaseModel):
    """A yes/no field worked out from other columns (valid sale, vacant sale): OpenAVMKit's ["?", filter] calc."""

    join: Literal["all", "any"] = "all"
    conditions: list[Condition] = Field(default_factory=list)


def rule_fields(load: dict[str, list[str]], rule: Rule) -> dict[str, tuple[str, str]]:
    """column -> (the field a rule reads it as, its type). A column already loaded is read as its field;
    any other is loaded under its own name, lowercased (OpenAVMKit only tests loaded columns). Names
    OpenAVMKit gives a meaning to get "_src" added."""
    from oakbox.fields import dictionary

    reserved = {d.key for d in dictionary()} | set(load)
    by_column = {spec[0]: field for field, spec in load.items()}
    out: dict[str, tuple[str, str]] = {}
    for c in rule.conditions:
        if c.column in out:
            continue
        numeric = any(x.column == c.column and x.op in NUMERIC_OPS for x in rule.conditions)
        kind = "float" if numeric else "string"
        if c.column in by_column:
            out[c.column] = (by_column[c.column], kind)
            continue
        name = re.sub(r"[^a-z0-9]+", "_", c.column.lower()).strip("_") or "column"
        if not name[0].isalpha():
            name = f"col_{name}"
        while name in reserved:
            name = f"{name}_src"
        reserved.add(name)
        out[c.column] = (name, kind)
    return out


def _literal(v: str, numeric: bool) -> Any:
    if numeric:
        try:
            return float(v)
        except ValueError:
            return v
    return f"str:{v}"


def rule_filter(rule: Rule, names: dict[str, tuple[str, str]]) -> list:
    """The rule as one OpenAVMKit filter."""
    parts = []
    for c in rule.conditions:
        field, kind = names[c.column]
        numeric = kind == "float"
        first = c.values[0] if c.values else ""
        if c.op in ("isin", "notin"):
            listed = [_literal(v, numeric) for v in c.values if v != BLANK]
            f: list = [c.op, field, listed]
            if BLANK in c.values:
                blank = ["isempty", field]
                f = ["or", f, blank] if c.op == "isin" else ["and", f, ["not", blank]]
        elif c.op == "isempty":
            f = ["isempty", field]
        elif c.op == "notempty":
            f = ["not", ["isempty", field]]
        elif c.op == "contains":
            # Blank rows contain nothing (str.contains gives NA for them).
            f = ["and", ["not", ["isempty", field]], ["contains_case_insensitive", field, f"str:{first}"]]
        else:
            f = [c.op, field, _literal(first, numeric or c.op in NUMERIC_OPS)]
        parts.append(f)
    if not parts:
        return []
    return parts[0] if len(parts) == 1 else ["and" if rule.join == "all" else "or", *parts]


def clean_value(v: str, steps: list[CleanStep]) -> str:
    """What OpenAVMKit's calc makes of one ID (as clean_calc writes it); blanks stay blank."""
    if not v.strip():
        return ""
    for st in steps:
        if st.kind == "zeros":
            v = v.lstrip("0")
        elif st.kind == "remove":
            for c in st.text:
                v = v.replace(c, "")
        elif st.kind == "trim":
            v = v.strip()
        elif st.kind == "replace" and st.text:
            v = v.replace(st.text, st.to)
        elif st.kind == "first":
            v = v[: st.n]
        elif st.kind == "last":
            v = v[-st.n :] if st.n else ""
        elif st.kind == "before" and st.text:
            v = v.split(st.text)[0]
        elif st.kind == "after" and st.text:
            head, sep, tail = v.partition(st.text)
            v = tail if sep else head
    return v


def clean_calc(field: str, steps: list[CleanStep]) -> list:
    """The steps as an OpenAVMKit calc on the field, innermost first. Blank IDs are kept blank (the string
    operations would turn them into the text '<NA>'), so they're still dropped."""
    e: Any = field
    for st in steps:
        if st.kind == "zeros":
            e = ["striplzero", e]
        elif st.kind == "remove" and st.text:
            e = ["replace", e, {c: "" for c in dict.fromkeys(st.text)}]
        elif st.kind == "trim":
            e = ["strip", e]
        elif st.kind == "replace" and st.text:
            e = ["replace", e, {st.text: st.to}]
        elif st.kind == "first":
            e = ["substr", e, {"right": st.n}]
        elif st.kind == "last":
            e = ["substr", e, {"left": -st.n}]
        elif st.kind in ("before", "after") and st.text:
            e = [f"split_{st.kind}", e, f"str:{st.text}"]
    return ["where", ["isempty", field], None, e]


Dupes = Literal["first", "all"]


class Units(BaseModel):
    """Rows of a parcel file with no shape of their own (condo units, townhome units, mobile-home pads...): each
    borrows its building's shape and gets a share of its land. OpenAVMKit's data.process.condos."""

    rule: Rule | None = Field(default=None, description="Which rows are units; None: every row.")
    link: Literal["prefix", "parent"] = Field(
        default="prefix",
        description="prefix: a unit's ID starts with its building's (7865782948-030 -> 7865782948). parent: a column "
        "holds the parcel ID of the unit's building.",
    )
    column: str | None = Field(default=None, description="The units file's column: the ID (prefix) or the parent ID.")
    base_column: str | None = Field(default=None, description="prefix: the parcel universe file's column to match.")
    prefix_len: int = Field(default=10, ge=1, le=64)
    land: Literal["field", "floor_area"] = Field(
        default="field",
        description="field: each unit's own land size (loaded as land size from this file). floor_area: the "
        "building's land shared by the units' finished area (loaded from this file).",
    )
    location: bool = Field(
        default=True, description="The building (condo_group) is also a location, like a neighborhood."
    )


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
        default="key", description="The ID it joins to the parcel universe on: key, or an extra ID (key2, key3; F3d)."
    )
    dupes: Dupes | None = Field(
        default=None,
        description="Repeated IDs in a parcel file (F3d): keep the first row of each, or drop them all. "
        "None: keep the first, the default, if there are only a few.",
    )
    dupes_sort: str | None = Field(default=None, description="The field rows are sorted by before keeping the first.")
    dupes_desc: bool = Field(default=False, description="Sort descending before keeping the first.")
    blank_ok: bool = Field(default=False, description="The rows with no ID have been acknowledged as dropped (F3d).")
    units: Units | None = Field(
        default=None, description="Parcel file: its rows without a shape are units of a shared parcel (F3d condos)."
    )
    holds: Holds | None = Field(
        default=None,
        description="What the file holds (F3d): one row per parcel, one row per sale, or not used. None: not chosen.",
    )
    clean: dict[str, list[CleanStep]] = Field(
        default_factory=dict, description="ID field -> clean-up steps, so it matches the other files (F3d reconcile)."
    )
    rules: dict[str, Rule] = Field(
        default_factory=dict, description="Yes/no field -> the rule it's worked out by (valid/vacant sale, F3d)."
    )
    area_units: dict[str, AreaUnit] = Field(
        default_factory=dict, description="Area field -> the unit its column is in; converted as it loads (F3d)."
    )
    overlay: Overlay | None = Field(default=None, description="A map layer's use (holds overlay, F3d).")
    numbers: dict[str, NumberFormat] = Field(
        default_factory=dict, description="Number field -> how its column's text is read (money written as text)."
    )
    scales: dict[str, Scale] = Field(
        default_factory=dict, description="Quality/condition number field -> how its column becomes higher-is-better."
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


def data_load(files: list[DataFile], units: str = "imperial") -> dict:
    """The data.load block: per entry, the file (and layer) and the columns it loads.

    Area fields are written in the project's small unit (sqft or sqm). A column in another unit is
    loaded under a name of its own and converted by a calc (land_area_sqft = land_area_sqft_in_acres × 43,560).
    """
    out = {}
    for f in files:
        entry: dict = {"filename": f.filename}
        if f.layer:
            entry["layer"] = f.layer
        load: dict[str, list[str]] = overlay_load(f.overlay) if f.holds == "overlay" and f.overlay else {}
        areas: dict[str, list] = {}
        numbers: dict[str, list] = {}
        scaled: dict[str, list] = {}
        qc_columns = Counter(spec[0] for k, spec in f.load.items() if k in QC_FIELDS)
        for field, spec in f.load.items():
            if field in QC_FIELDS and (field in f.scales or qc_columns[spec[0]] > 1):
                s = f.scales.get(field)
                if s is not None and not scale_ready(s):
                    continue  # which way it runs isn't said yet: nothing written rather than a guess
                # One column feeding several fields (a category that's also, ranked, the number): loaded once,
                # as text, and each field worked out from it.
                shared = qc_columns[spec[0]] > 1
                text: Any = None
                if shared:
                    load[raw_name(spec[0])] = [spec[0], "string"]
                    text = raw_name(spec[0])
                if s is None:  # the category, as text
                    scaled[field] = ["set", text]
                    continue
                if s.kind == "tiers":
                    if not shared:
                        load[scale_helper(field)] = [spec[0], "string"]
                        text = scale_helper(field)
                    scaled[field] = cast(list, scale_calc(text, s))
                    continue
                if shared:
                    number = ["asfloat", ["replace_regex", text, {NOT_A_NUMBER: "nan"}]]
                    scaled[field] = scale_calc(number, s) or number
                    continue
                c = scale_calc(scale_helper(field), s)
                if c is None:
                    load[field] = [spec[0], "float"]
                else:
                    load[scale_helper(field)] = [spec[0], "float"]
                    scaled[field] = c
                continue
            if field in f.numbers:
                load[number_helper(field)] = [spec[0], "string"]
                numbers[field] = number_calc(field, f.numbers[field])
                continue
            written = area_key(field, units)
            native = f.area_units.get(field, small_unit(units))
            if field in AREA_FIELDS and native != small_unit(units):
                helper = f"{written}_in_{native}"
                load[helper] = [spec[0], "float"]
                areas[written] = ["*", helper, SQFT_PER[native] / SQFT_PER[small_unit(units)]]
            else:
                load[written] = spec
        # Rules read a number field as the number it's read as, not as its text.
        read_as = {k: v for k, v in load.items() if k not in {number_helper(n) for n in numbers}}
        read_as |= {n: [f.load[n][0], "float"] for n in numbers}
        rules = {}
        for key, rule in f.rules.items():
            names = rule_fields(read_as, rule)
            for column, (field, kind) in list(names.items()):
                if field in numbers:
                    # Its own copy: OpenAVMKit drops a calculated field that another calc uses (as an
                    # ingredient), which would take the sale price itself away.
                    names[column] = (f"{field}_num", "float")
                    numbers[f"{field}_num"] = number_calc(field, f.numbers[field])
                    continue
                if field not in load:
                    load[field] = [column, kind]
                elif kind == "float" and load[field][1:2] == ["string"]:
                    load[field] = [column, "float"]
            rules[key] = ["?", rule_filter(rule, names)]
        if load:
            entry["load"] = {field: spec[0] if len(spec) == 1 else spec for field, spec in load.items()}
        # Cleaned IDs first: the other calcs (a made sale ID, valid/vacant rules) use them.
        calc = (
            {field: clean_calc(field, steps) for field, steps in f.clean.items() if steps}
            | numbers
            | scaled
            | areas
            | rules
            | f.calc
        )
        if calc:
            entry["calc"] = calc
        if f.holds == "parcels":
            # One row per parcel, as OpenAVMKit's own default for a keyed file, but written out (F3d).
            order = "desc" if f.dupes_desc else "asc"
            drop: bool | str = "all" if f.dupes == "all" else True
            entry["dupes"] = {"subset": [f.match], "sort_by": [f.dupes_sort or f.match, order], "drop": drop}
        if f.holds == "overlay" or (
            not load and f.holds not in ("parcels", "sales") and Path(f.filename).suffix.lower() != ".csv"
        ):
            # Every shape counts: without this OpenAVMKit keeps one per value of its first column, and fails on a
            # map file nothing is taken from yet (a layer not used yet), which has no column at all.
            entry["dupes"] = "allow"
        if f.holds == "sales":
            # Without this OpenAVMKit de-duplicates on key, the parcel ID, dropping repeat sales of a parcel.
            order = "desc" if f.dupes_desc else "asc"
            drop = "all" if f.dupes == "all" else True
            entry["dupes"] = {"subset": ["key_sale"], "sort_by": [f.dupes_sort or "key_sale", order], "drop": drop}
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

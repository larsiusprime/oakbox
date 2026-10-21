"""F3d, the Fields wizard (SPEC §3.0): one small question at a time, over all of a project's files.

It writes only what OpenAVMKit reads: each file's ``load`` (as F3c) and ``calc``, and what each
file holds, from which the merge lists are written (``projects._data``). Its own state is the
base file, the steps seen and skipped, and the fields already decided (``WizardState``).

Guesses are modest (SPEC D45): a column is preselected only when its name matches the field (its
key, its name, or a short alias list) and its values pass the field's check. A guess is made
once per field, when its step is first shown, and never replaces a choice.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import fields
from oakbox.datafiles import BaseModel, DataFile, Holds
from oakbox.fields import Column, DictionaryField
from oakbox.projects import Project

# ---------- The steps ----------


class Step(BaseModel):
    key: str
    parent: str | None = Field(default=None, description="The step this is part of (Building).")
    fields: list[str] = Field(default_factory=list, description="Asked on the step.")
    more: list[str] = Field(default_factory=list, description="Asked under More on the step.")
    sales: bool = Field(default=False, description="Its fields come from the sales file.")


STEPS: list[Step] = [
    Step(key="files"),
    Step(key="shapes"),
    Step(
        key="location",
        fields=["address", "neighborhood", "city", "school_district", "census_tract", "census_block_group"],
        more=["census_block", "block", "risk_flood", "risk_disaster", "is_opportunity_zone", "noise_mean", "noise_max"],
    ),
    Step(
        key="land",
        fields=["land_area_sqft", "zoning", "zoning_desc", "land_class", "min_buildable_size"],
        more=["condo_group", "floor_area_ratio", "is_below_buildable_size"],
    ),
    Step(key="building"),
    Step(
        key="building_basics",
        parent="building",
        fields=["bldg_type", "bldg_class", "bldg_desc", "bldg_count", "bldg_units", "bldg_stories"],
    ),
    Step(key="building_size", parent="building", fields=["bldg_area_finished_sqft", "bldg_area_footprint_sqft"]),
    Step(
        key="building_age",
        parent="building",
        fields=["bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years"],
    ),
    Step(
        key="building_quality",
        parent="building",
        fields=["bldg_quality_txt", "bldg_quality_num", "bldg_condition_txt", "bldg_condition_num"],
    ),
    Step(
        key="building_rooms",
        parent="building",
        fields=["bldg_rooms_bed", "bldg_rooms_bath", "bldg_rooms_bath_full", "bldg_rooms_bath_half"],
    ),
    Step(
        key="building_features",
        parent="building",
        fields=["bldg_style", "bldg_exterior", "bldg_heating", "bldg_ac", "bldg_foundation"],
        more=[
            "bldg_value_replacement",
            "bldg_value_depreciated",
            "bldg_depreciation_total",
            "bldg_depreciation_percent",
            "bldg_outbuilding_value",
        ],
    ),
    Step(key="sales", fields=["sale_price", "sale_date", "valid_sale", "vacant_sale"], sales=True),
    Step(
        key="assessed",
        fields=["assr_land_value", "assr_impr_value", "assr_market_value"],
        more=["true_land_value", "true_impr_value", "true_market_value"],
    ),
    Step(
        key="other",
        fields=["deed_book", "deed_page", "deed_grantor", "deed_grantee"],
        more=["mail_address", "mail_city", "mail_state", "mail_zip", "is_usps_vacant"],
    ),
    Step(key="review"),
]
STEP_KEYS = [s.key for s in STEPS]
SALES_FIELDS = {f for s in STEPS if s.sales for f in s.fields}
# Required by OpenAVMKit's sales merge; without a column, an assumption confirmed in a warning (F3d).
ASSUMABLE = {"valid_sale": True, "vacant_sale": False}
# Computed fields asked only when what they're computed from isn't loaded.
ONLY_WITHOUT = {"bldg_age_years": "bldg_year_built", "bldg_effective_age_years": "bldg_effective_year_built"}

# Common column names, beside the field's own key and name (normalised: lowercase letters and digits).
ALIASES: dict[str, list[str]] = {
    "address": ["situs", "situsaddr", "situsaddress", "siteaddr", "siteaddress", "propaddr", "addr", "locaddr"],
    "neighborhood": ["nbhd", "nbhdcd", "nbhdcode", "neighborhoodcode", "neighcode", "hood"],
    "city": ["situscity", "sitecity"],
    "school_district": ["school", "schooldist", "isd", "schooldistrict"],
    "census_tract": ["tract", "censustract"],
    "zoning": ["zone", "zonecode", "zoningcode"],
    "zoning_desc": ["zonedesc", "zoningdescription"],
    "land_area_sqft": ["landsqft", "lotsqft", "landsf", "lotsf", "lotsize", "landarea", "lotarea"],
    "bldg_type": ["imprvtype", "imprtype", "buildingtype", "improvementtype", "bldgtype"],
    "bldg_class": ["buildingclass", "bldgclass", "imprvclass"],
    "bldg_stories": ["stories", "numstories", "story"],
    "bldg_units": ["units", "numunits"],
    "bldg_count": ["numbldgs", "bldgs", "buildingcount"],
    "bldg_area_finished_sqft": ["livingarea", "livarea", "heatedarea", "finishedsqft", "gla", "bldgsqft", "sqft"],
    "bldg_area_footprint_sqft": ["footprint", "footprintsqft"],
    "bldg_year_built": ["yrblt", "yearbuilt", "yrbuilt", "actualyearbuilt", "ayb"],
    "bldg_effective_year_built": ["effyrblt", "effectiveyearbuilt", "eyb", "effyear", "effyearbuilt"],
    "bldg_quality_txt": ["quality", "qual", "grade"],
    "bldg_quality_num": ["quality", "qual", "grade", "qualitynum"],
    "bldg_condition_txt": ["condition", "cond"],
    "bldg_condition_num": ["condition", "cond", "conditionnum"],
    "bldg_rooms_bed": ["beds", "bedrooms", "bed", "bdrms"],
    "bldg_rooms_bath": ["baths", "bathrooms", "bath"],
    "bldg_rooms_bath_full": ["fullbaths", "fullbath"],
    "bldg_rooms_bath_half": ["halfbaths", "halfbath"],
    "bldg_heating": ["heat", "heating", "heattype"],
    "bldg_ac": ["ac", "aircond", "cooling", "airconditioning"],
    "bldg_exterior": ["extwall", "exterior", "exteriorwall"],
    "bldg_foundation": ["foundation"],
    "bldg_style": ["style"],
    "sale_price": ["price", "saleprice", "saleamt", "saleamount", "consideration"],
    "sale_date": ["saledate", "saledt", "deeddate"],
    "valid_sale": ["valid", "validsale", "salevalid", "qualified", "qualifiedsale", "salequalified", "armslength"],
    "vacant_sale": ["vacant", "vac", "vacantsale", "salevacant", "vacantatsale"],
    "assr_land_value": ["landval", "landvalue", "apprland", "appraisedland"],
    "assr_impr_value": ["imprval", "imprvval", "improvementvalue", "bldgval"],
    "assr_market_value": ["marketval", "mktval", "totalval", "apprval", "appraisedvalue", "marketvalue"],
    "deed_book": ["book", "deedbook"],
    "deed_page": ["page", "deedpage"],
    "deed_grantor": ["grantor", "seller"],
    "deed_grantee": ["grantee", "buyer"],
    "mail_address": ["mailaddr", "mailaddress", "mailingaddress"],
    "mail_city": ["mailcity"],
    "mail_state": ["mailstate"],
    "mail_zip": ["mailzip", "mailzipcode"],
}
# A parcel ID's name: most specific first.
ID_NAMES = re.compile(
    r"^(pin|apn|parcel(id|no|num|number)?|prop(erty)?(id|no|num)|account(no|num)?|acct(no|num)?|key|"
    r"geoid|folio|id)$"
)
SALE_ID_NAMES = re.compile(r"^(sale(id|key|no|num|number)|instrument(no|num)?|doc(ument)?(no|num|number)|deedid)$")
YES = {"true", "t", "1", "y", "yes", "1.0"}  # OpenAVMKit's reading (_boolify_column_in_df), plus 1.0 from a CSV
NO = {"false", "f", "0", "n", "no", "0.0"}
DATE_WORDS = {
    "%Y-%m-%d": "year-month-day",
    "%m/%d/%Y": "month/day/year",
    "%m/%d/%y": "month/day/2-digit year",
    "%d/%m/%Y": "day/month/year",
    "%Y%m%d": "yearmonthday",
    "%Y-%m-%d %H:%M:%S": "year-month-day and time",
    "%m/%d/%Y %H:%M": "month/day/year and time",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ---------- What the wizard sends ----------


class Check(BaseModel):
    ok: bool
    text: str = Field(description="Short: '✓ years 1890–2025', 'several rows per parcel'.")


class WizardFile(BaseModel):
    name: str
    filename: str
    missing: bool
    problem: str | None = Field(default=None, description="Why it can't be read.")
    rows: int | None
    geometry: bool
    holds: Holds | None
    id_column: str | None = Field(description="Loaded as key in this file.")
    id_check: Check | None
    key2_column: str | None
    columns: list[Column]
    base: bool


class SaleId(BaseModel):
    file: str | None = Field(description="The sales file.")
    column: str | None = Field(description="Its sale ID column (loaded as key_sale).")
    made: bool = Field(description="Made from parcel ID + sale date (an entry calc).")
    check: Check | None


class Source(BaseModel):
    file: str
    column: str


class WizardField(BaseModel):
    key: str
    name: str
    description: str
    type: str
    step: str
    more: bool
    sources: list[Source] = Field(description="Where it's loaded from; more than one is a conflict.")
    assumed: bool = Field(description="Valid/vacant sale with no column: all valid, none vacant (F3d).")
    check: Check | None
    hidden: bool = Field(description="Computed from a field that's loaded, so not asked (e.g. age from year built).")


class StepView(BaseModel):
    key: str
    parent: str | None
    status: Literal["todo", "done", "skipped"]
    fields: list[str]
    more: list[str]
    sales: bool


class NotLoaded(BaseModel):
    file: str
    columns: list[str]


class Wizard(BaseModel):
    steps: list[StepView]
    files: list[WizardFile]
    sale_id: SaleId
    fields: list[WizardField]
    used: dict[str, dict[str, str]] = Field(description="file -> column -> the field it's loaded as.")
    problems: list[str]
    not_loaded: list[NotLoaded]


# ---------- Reading the files (cached on the file's size and time) ----------


def _stamp(path: Path) -> tuple[str, float, int]:
    st = path.stat()
    return str(path), st.st_mtime, st.st_size


@lru_cache(maxsize=64)
def _preview(stamp: tuple[str, float, int], layer: str | None) -> fields.FileColumns:
    return fields.columns(Path(stamp[0]), layer)


@lru_cache(maxsize=128)
def _values(stamp: tuple[str, float, int], layer: str | None, column: str) -> tuple[str, ...]:
    """Every value of one column, as text, blanks as ''."""
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
    return tuple("" if v is None or (isinstance(v, float) and v != v) else str(v).strip() for v in s.tolist())


class _Files:
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
                self.preview[f.name] = _preview(_stamp(path), f.layer)
            except Exception as e:  # noqa: BLE001 - a damaged file shows on its row
                self.problem[f.name] = f"Couldn't read {f.filename}: {e}"

    def entry(self, name: str) -> DataFile:
        return next(f for f in self.project.files if f.name == name)

    def columns(self, name: str) -> list[Column]:
        p = self.preview.get(name)
        return [c for c in p.columns if c.type != "geometry"] if p else []

    def column(self, name: str, column: str) -> Column | None:
        return next((c for c in self.columns(name) if c.name == column), None)

    def values(self, name: str, column: str) -> tuple[str, ...]:
        f = self.entry(name)
        return _values(_stamp(self.in_dir / f.filename), f.layer, column)

    def geometry(self, name: str) -> bool:
        p = self.preview.get(name)
        return bool(p and p.geometry)


# ---------- Checks ----------


def _floats(samples: list[str]) -> list[float] | None:
    out = []
    for s in samples:
        try:
            out.append(float(s))
        except ValueError:
            return None
    return out


def field_check(d: DictionaryField, col: Column) -> tuple[Check, list[str] | None]:
    """Whether a column reads as a field's type, and the load spec to write when it does."""
    samples = col.samples
    if d.type in ("number", "percent"):
        nums = [] if col.type == "number" and not samples else _floats(samples)
        if nums is None:
            bad = next(s for s in samples if _floats([s]) is None)
            return Check(ok=False, text=f"not numbers: {bad}"), None
        if "year" in d.key and nums:
            if not all(1700 <= n <= 2100 for n in nums):
                return Check(ok=False, text="not years"), None
            return Check(ok=True, text=f"✓ years {int(min(nums))}–{int(max(nums))}"), [col.name, "float"]
        return Check(ok=True, text="✓ numbers"), [col.name, "float"]
    if d.type == "date":
        if col.type == "date":
            return Check(ok=True, text="✓ dates"), [col.name]
        if col.date_format:
            words = DATE_WORDS.get(col.date_format, col.date_format)
            return Check(ok=True, text=f"✓ reads as {words}"), [col.name, "datetime", col.date_format]
        return Check(ok=False, text="doesn't read as a date"), None
    if d.type == "boolean":
        lowered = [s.lower() for s in samples]
        if col.type != "yes/no" and any(v not in YES | NO for v in lowered):
            bad = next(s for s, v in zip(samples, lowered, strict=True) if v not in YES | NO)
            return Check(ok=False, text=f"not yes/no: {bad}"), None
        yes = sorted({s for s, v in zip(samples, lowered, strict=True) if v in YES}) or ["true"]
        return Check(ok=True, text=f"✓ {', '.join(yes)} = yes, blank = no"), [col.name, "bool", "na_false"]
    if d.key.endswith("_txt") and col.type == "number":
        return Check(ok=False, text="numbers: use the number field"), None
    return Check(ok=True, text="✓ text"), [col.name, "string"]


def _id_check(files: _Files, name: str, holds: Holds | None, base: str | None) -> Check | None:
    f = files.entry(name)
    spec = f.load.get("key")
    if not spec or name not in files.preview:
        return None
    values = files.values(name, spec[0])
    present = [v for v in values if v]
    blank = len(values) - len(present)
    distinct = set(present)
    blanks = f" · {blank:,} blank" if blank else ""
    if holds == "sales":
        if base is None or base == name:
            return Check(ok=True, text=f"{len(values):,} sales{blanks}")
        base_ids = _base_ids(files, base)
        found = sum(1 for v in present if v in base_ids)
        return Check(ok=found > 0, text=f"{_pct(found, len(values))} of sales match a parcel{blanks}")
    if len(distinct) < len(present):
        return Check(ok=False, text="several rows per parcel")
    if holds != "parcels":
        return Check(ok=True, text=f"one row per parcel{blanks}")
    if name == base:
        shapes = " · has shapes" if files.geometry(name) else ""
        return Check(ok=not blank, text=f"✓ {len(present):,} parcels, all different{shapes}{blanks}")
    base_ids = _base_ids(files, base)
    found = len(distinct & base_ids)
    return Check(ok=found > 0, text=f"✓ one row per parcel · {_pct(found, len(present))} match parcels{blanks}")


def _base_ids(files: _Files, base: str | None) -> set[str]:
    if base is None or base not in files.preview:
        return set()
    spec = files.entry(base).load.get("key")
    return {v for v in files.values(base, spec[0]) if v} if spec else set()


def _pct(n: int, total: int) -> str:
    if not total:
        return "0%"
    p = 100 * n / total
    return f"{p:.1f}%" if 99 < p < 100 or 0 < p < 1 else f"{p:.0f}%"


def _repeats(files: _Files, name: str, column: str) -> bool:
    present = [v for v in files.values(name, column) if v]
    return len(set(present)) < len(present)


# ---------- Guesses ----------


def _names(d: DictionaryField) -> set[str]:
    return {_norm(d.key), _norm(d.name), *ALIASES.get(d.key, [])}


def _guess_holds(files: _Files, name: str) -> Holds:
    cols = {_norm(c.name) for c in files.columns(name)}
    by_key = {d.key: d for d in fields.dictionary()}
    if cols & _names(by_key["sale_price"]) and cols & _names(by_key["sale_date"]):
        return "sales"
    return "parcels"


def _guess_id(files: _Files, name: str, holds: Holds, base_column: str | None) -> str | None:
    cols = files.columns(name)
    named = [c.name for c in cols if ID_NAMES.fullmatch(_norm(c.name))]
    if base_column and base_column in {c.name for c in cols} and base_column not in named:
        named.insert(0, base_column)
    named.sort(key=lambda c: (c != base_column, _id_rank(c)))
    for column in named[:4]:
        values = files.values(name, column)
        present = [v for v in values if v]
        if not present:
            continue
        if holds == "sales" or len(set(present)) >= 0.99 * len(present):
            return column
    return None


def _id_rank(column: str) -> int:
    n = _norm(column)
    for i, word in enumerate(("pin", "apn", "parcel", "prop", "account", "acct", "key", "geoid", "folio", "id")):
        if n.startswith(word):
            return i
    return 99


def _guess_sale_id(files: _Files, name: str) -> str | None:
    for c in files.columns(name):
        if SALE_ID_NAMES.fullmatch(_norm(c.name)):
            present = [v for v in files.values(name, c.name) if v]
            if present and len(set(present)) == len(present):
                return c.name
    return None


def _guess_field(files: _Files, d: DictionaryField, candidates: list[str], used: dict[str, dict[str, str]]):
    names = _names(d)
    for name in candidates:
        for col in files.columns(name):
            if col.name in used.get(name, {}) or _norm(col.name) not in names:
                continue
            check, spec = field_check(d, col)
            if check.ok and spec:
                return name, spec
    return None


# ---------- Reading and changing the wizard ----------


def _by_key() -> dict[str, DictionaryField]:
    return {d.key: d for d in fields.dictionary()}


def _sales_file(project: Project) -> DataFile | None:
    return next((f for f in project.files if f.holds == "sales"), None)


def _field_files(project: Project, sales: bool) -> list[DataFile]:
    holds = "sales" if sales else "parcels"
    return [f for f in project.files if f.holds == holds]


def _used(project: Project) -> dict[str, dict[str, str]]:
    return {f.name: {spec[0]: field for field, spec in f.load.items()} for f in project.files}


# OpenAVMKit's name for the parcel file with shapes: it requires an entry of this name (load_dataframes).
BASE_NAME = "geo_parcels"


def update_base(project: Project, in_dir: Path, rename: bool = False) -> None:
    """The base: the parcel file with shapes the others join to (F3d).

    It's the one already named geo_parcels if that's a parcel file with shapes, else the first
    parcel file with shapes. With ``rename`` (wizard changes only), the base's entry is renamed
    geo_parcels, as OpenAVMKit requires, and a non-base entry of that name gets another name.
    """
    files = _Files(project, in_dir)
    shaped = [f for f in project.files if f.holds == "parcels" and files.geometry(f.name)]
    base = next((f for f in shaped if f.name == BASE_NAME), shaped[0] if shaped else None)
    if base is not None and rename and base.name != BASE_NAME:
        from oakbox.datafiles import suggest_name

        holder = next((f for f in project.files if f.name == BASE_NAME), None)
        if holder is not None:
            holder.name = suggest_name(holder.filename, {f.name for f in project.files} | {BASE_NAME})
        base.name = BASE_NAME
    project.wizard.base = base.name if base else None


def renamed(project: Project, old: str, new: str) -> None:
    if project.wizard.base == old:
        project.wizard.base = new


def view(project: Project, in_dir: Path) -> Wizard:
    files = _Files(project, in_dir)
    by_key = _by_key()
    base = project.wizard.base
    used = _used(project)
    loaded = {field: f for f in project.files if f.holds in ("parcels", "sales") for field in f.load}

    out_files = []
    for f in project.files:
        key = f.load.get("key")
        key2 = f.load.get("key2")
        out_files.append(
            WizardFile(
                name=f.name,
                filename=f.filename,
                missing=not (in_dir / f.filename).is_file(),
                problem=files.problem.get(f.name),
                rows=len(files.values(f.name, key[0])) if key and f.name in files.preview else _rows(files, f.name),
                geometry=files.geometry(f.name),
                holds=f.holds,
                id_column=key[0] if key else None,
                id_check=_id_check(files, f.name, f.holds, base),
                key2_column=key2[0] if key2 else None,
                columns=files.columns(f.name),
                base=f.name == base,
            )
        )

    sales = _sales_file(project)
    sale_id = SaleId(file=None, column=None, made=False, check=None)
    if sales is not None:
        spec = sales.load.get("key_sale")
        made = "key_sale" in sales.calc
        check = None
        if spec and sales.name in files.preview:
            present = [v for v in files.values(sales.name, spec[0]) if v]
            dupes = len(present) - len(set(present))
            check = Check(ok=not dupes, text="✓ all different" if not dupes else f"{dupes:,} repeated")
        elif made:
            has_date = "sale_date" in sales.load
            check = Check(ok=has_date, text="from parcel ID + sale date" if has_date else "needs a sale date (Sales)")
        sale_id = SaleId(file=sales.name, column=spec[0] if spec else None, made=made, check=check)

    out_fields = []
    for step in STEPS:
        for more, keys in ((False, step.fields), (True, step.more)):
            for key in keys:
                d = by_key.get(key)
                if d is None:
                    continue
                sources = [
                    Source(file=f.name, column=f.load[key][0])
                    for f in _field_files(project, step.sales)
                    if key in f.load
                ]
                check = None
                if len(sources) == 1:
                    col = files.column(sources[0].file, sources[0].column)
                    check = field_check(d, col)[0] if col else Check(ok=False, text="not in the file")
                elif len(sources) > 1:
                    check = Check(ok=False, text="loaded from more than one file")
                assumed = bool(sales and key in ASSUMABLE and key in sales.calc)
                out_fields.append(
                    WizardField(
                        key=key,
                        name=d.name,
                        description=d.description,
                        type=d.type,
                        step=step.key,
                        more=more,
                        sources=sources,
                        assumed=assumed,
                        check=check,
                        hidden=key in ONLY_WITHOUT and ONLY_WITHOUT[key] in loaded,
                    )
                )

    steps = []
    for step in STEPS:
        status: Literal["todo", "done", "skipped"] = "todo"
        if step.key in project.wizard.skipped:
            status = "skipped"
        elif step.key in project.wizard.visited:
            status = "done"
        steps.append(
            StepView(
                key=step.key, parent=step.parent, status=status, fields=step.fields, more=step.more, sales=step.sales
            )
        )
    building = next(s for s in steps if s.key == "building")
    subs = [s for s in steps if s.parent == "building"]
    building.status = "done" if subs and all(s.status != "todo" for s in subs) else "todo"

    not_loaded = []
    for f in project.files:
        if f.holds in ("parcels", "sales"):
            rest = [c.name for c in files.columns(f.name) if c.name not in used.get(f.name, {})]
            if rest:
                not_loaded.append(NotLoaded(file=f.name, columns=rest))

    return Wizard(
        steps=steps,
        files=out_files,
        sale_id=sale_id,
        fields=out_fields,
        used=used,
        problems=_problems(project, out_files, sale_id, out_fields),
        not_loaded=not_loaded,
    )


def _rows(files: _Files, name: str) -> int | None:
    p = files.preview.get(name)
    if p is None:
        return None
    if p.rows is not None:
        return p.rows
    cols = files.columns(name)
    return len(files.values(name, cols[0].name)) if cols else None


def _problems(project: Project, files: list[WizardFile], sale_id: SaleId, flds: list[WizardField]) -> list[str]:
    out = []
    parcels = [f for f in files if f.holds == "parcels"]
    if not parcels:
        out.append("No file holds parcels.")
    elif not any(f.base for f in files):
        out.append("OpenAVMKit needs a parcel file with shapes.")
    elif not any(f.base and f.name == BASE_NAME for f in files):
        out.append(f"The parcel file with shapes must be named {BASE_NAME}. Open Your files to rename it.")
    for f in files:
        if f.holds in ("parcels", "sales") and f.id_column is None:
            out.append(f"{f.name} has no parcel ID column.")
        if f.id_check is not None and not f.id_check.ok and f.holds in ("parcels", "sales"):
            out.append(f"{f.name}: {f.id_check.text}.")
    if not any(f.holds == "sales" for f in files):
        out.append("No file holds sales.")
    else:
        if sale_id.column is None and not sale_id.made:
            out.append("The sales have no sale ID.")
        elif sale_id.check is not None and not sale_id.check.ok:
            out.append(f"Sale ID: {sale_id.check.text}.")
        for f in flds:
            if f.key in ("sale_price", "sale_date", "valid_sale", "vacant_sale") and not f.sources and not f.assumed:
                out.append(f"No {f.name.lower()}.")
    for f in flds:
        if f.check is not None and not f.check.ok:
            out.append(f"{f.name}: {f.check.text}.")
    return out


def visit(project: Project, in_dir: Path, step: str) -> None:
    """Show a step: fill in guesses for whatever on it hasn't been decided (F3d)."""
    if step not in STEP_KEYS:
        raise LookupError(step)
    files = _Files(project, in_dir)
    if step == "files":
        _guess_files(project, files, in_dir)
    else:
        spec = next(s for s in STEPS if s.key == step)
        by_key = _by_key()
        loaded = {field for f in project.files for field in f.load}
        for key in [*spec.fields, *spec.more]:
            if key in project.wizard.decided or key not in by_key:
                continue
            project.wizard.decided.append(key)
            if key in loaded or (key in ONLY_WITHOUT and ONLY_WITHOUT[key] in loaded):
                continue
            candidates = [f.name for f in _field_files(project, spec.sales)]
            found = _guess_field(files, by_key[key], candidates, _used(project))
            if found:
                files.entry(found[0]).load[key] = found[1]
                loaded.add(key)
    if step not in project.wizard.visited:
        project.wizard.visited.append(step)


def _guess_files(project: Project, files: _Files, in_dir: Path) -> None:
    for f in project.files:
        if f.holds is None and f.name in files.preview:
            f.holds = _guess_holds(files, f.name)
            if f.holds == "sales" and sum(1 for g in project.files if g.holds == "sales") > 1:
                f.holds = "parcels"
    update_base(project, in_dir, rename=True)
    files = _Files(project, in_dir)  # names may have changed
    base = project.wizard.base
    base_column = None
    for f in sorted(project.files, key=lambda f: f.name != base):
        if f.name not in files.preview or f.holds not in ("parcels", "sales") or "key" in f.load:
            continue
        # A parcel file whose ID-like column repeats (permits, buildings) gets it anyway, then isn't used.
        column = _guess_id(files, f.name, f.holds, base_column) or _guess_id(files, f.name, "sales", base_column)
        if column:
            f.load["key"] = [column, "string"]
            if f.name == base:
                base_column = column
            if f.holds == "parcels" and _repeats(files, f.name, column):
                f.holds = "unused"
    update_base(project, in_dir, rename=True)
    sales = _sales_file(project)
    if sales is not None and "key_sale" not in sales.load and "key_sale" not in sales.calc:
        column = _guess_sale_id(files, sales.name)
        if column:
            sales.load["key_sale"] = [column, "string"]
        else:
            sales.calc["key_sale"] = list(MADE_SALE_ID)


# The sale ID made from parcel ID + sale date, e.g. "0012-001-2023-01-09" (an OpenAVMKit calc).
MADE_SALE_ID = ["join", ["values", "key", "sale_date"], "str:-"]


def set_file(
    project: Project,
    in_dir: Path,
    name: str,
    holds: Holds | None,
    id_column: str | None,
    key2: str | None,
    key2_set: bool,
) -> None:
    """What a file holds and its parcel ID (step 1)."""
    files = _Files(project, in_dir)
    entry = files.entry(name)
    columns = {c.name for c in files.columns(name)}
    for column in (id_column, key2):
        if column is not None and column not in columns:
            raise ValueError(f"{name} has no column {column}.")
    if id_column is not None:
        _put(entry, "key", [id_column, "string"])
    if key2_set:
        entry.load.pop("key2", None)
        if key2:
            _put(entry, "key2", [key2, "string"])
    if holds is not None and holds != entry.holds:
        if holds == "sales" and any(f.holds == "sales" for f in project.files if f is not entry):
            raise ValueError("Only one file can hold sales for now. Set the other to Not used first.")
        if holds == "parcels" and "key" in entry.load and _repeats(files, name, entry.load["key"][0]):
            raise ValueError(f"{name} has several rows per parcel, so it can't be joined as parcels yet.")
        if entry.holds == "sales":  # what only a sales file has
            for key in ("key_sale", *ASSUMABLE):
                entry.calc.pop(key, None)
        entry.holds = holds
    elif entry.holds == "parcels" and id_column is not None and _repeats(files, name, id_column):
        entry.holds = "unused"
    update_base(project, in_dir, rename=True)


def _put(entry: DataFile, field: str, spec: list[str]) -> None:
    """Load a column as a field, taking it from whatever field had it."""
    for other, s in list(entry.load.items()):
        if s[0] == spec[0] and other != field:
            raise ValueError(f"{spec[0]} is already loaded as {other}.")
    entry.load[field] = spec


def set_sale_id(project: Project, column: str | None, make: bool) -> None:
    sales = _sales_file(project)
    if sales is None:
        raise ValueError("No file holds sales.")
    sales.load.pop("key_sale", None)
    sales.calc.pop("key_sale", None)
    if make:
        sales.calc["key_sale"] = list(MADE_SALE_ID)
    elif column:
        _put(sales, "key_sale", [column, "string"])


def set_field(project: Project, in_dir: Path, key: str, file: str | None, column: str | None, assume: bool) -> None:
    """Load a field from one file's column, from nowhere, or (valid/vacant sale) as an assumption."""
    by_key = _by_key()
    step = next((s for s in STEPS if key in s.fields or key in s.more), None)
    if step is None or key not in by_key:
        raise LookupError(key)
    allowed = _field_files(project, step.sales)
    sales = _sales_file(project)
    target: DataFile | None = None
    spec: list[str] | None = None
    if file is not None and column is not None:
        target = next((f for f in allowed if f.name == file), None)
        if target is None:
            raise ValueError(f"{key} comes from {'the sales file' if step.sales else 'a parcel file'}.")
        col = _Files(project, in_dir).column(file, column)
        if col is None:
            raise ValueError(f"{file} has no column {column}.")
        check, spec = field_check(by_key[key], col)
        if spec is None:
            raise ValueError(f"{column}: {check.text}.")
        for other, s in target.load.items():
            if s[0] == column and other != key:
                raise ValueError(f"{column} is already loaded as {other}.")
    elif assume and (key not in ASSUMABLE or sales is None):
        raise ValueError(f"{key} can't be assumed.")
    for f in allowed:
        f.load.pop(key, None)
    if sales is not None and key in ASSUMABLE:
        sales.calc.pop(key, None)
    if target is not None and spec is not None:
        target.load[key] = spec
    elif assume and sales is not None:
        sales.calc[key] = ["set", ASSUMABLE[key]]
    if key not in project.wizard.decided:
        project.wizard.decided.append(key)
    if step.key in project.wizard.skipped and (file or assume):
        project.wizard.skipped.remove(step.key)


def skip(project: Project, step: str) -> None:
    """'I don't have these': nothing loaded for the step's fields."""
    spec = next((s for s in STEPS if s.key == step), None)
    if spec is None or not spec.fields:
        raise LookupError(step)
    for key in [*spec.fields, *spec.more]:
        if key in ASSUMABLE:
            raise ValueError("Sales need a valid sale and a vacant sale field.")
    for f in _field_files(project, spec.sales):
        for key in [*spec.fields, *spec.more]:
            f.load.pop(key, None)
    for key in [*spec.fields, *spec.more]:
        if key not in project.wizard.decided:
            project.wizard.decided.append(key)
    if step not in project.wizard.skipped:
        project.wizard.skipped.append(step)
    if step not in project.wizard.visited:
        project.wizard.visited.append(step)

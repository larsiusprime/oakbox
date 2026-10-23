"""F3d, the Fields wizard (SPEC §3.0): one small question at a time, over all of a project's files.

It writes only what OpenAVMKit reads: each file's ``load`` (as F3c) and ``calc``, and what each
file holds, from which the merge lists are written (``projects._data``). Its own state is the
base file, the steps seen and skipped, and the fields already decided (``WizardState``).

Guesses are modest (SPEC D45): a column is preselected only when its name matches the field (its
key, its name, or a short alias list) and its values pass the field's check. A guess is made
once per field, when its step is first shown, and never replaces a choice.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from oakbox import fields
from oakbox.datafiles import (
    EXTRA_IDS,
    BaseModel,
    CleanStep,
    Condition,
    DataFile,
    Dupes,
    Holds,
    Match,
    Rule,
    clean_calc,
    clean_value,
    rule_fields,
    rule_filter,
)
from oakbox.fields import Column, DictionaryField
from oakbox.projects import Project

# ---------- The steps ----------


class Step(BaseModel):
    key: str
    parent: str | None = Field(default=None, description="The step this is part of (More details).")
    fields: list[str] = Field(default_factory=list, description="Asked on the step.")
    more: list[str] = Field(default_factory=list, description="Asked under More on the step.")
    sales: bool = Field(default=False, description="Its fields come from the sales file.")


STEPS: list[Step] = [
    Step(key="welcome"),
    Step(key="universe"),
    Step(key="sales", fields=["sale_price", "sale_date", "valid_sale", "vacant_sale"], sales=True),
    Step(key="details"),
    Step(
        key="big_five",
        parent="details",
        fields=[
            "bldg_area_finished_sqft",
            "land_area_sqft",
            "bldg_year_built",
            "bldg_effective_year_built",
            "bldg_quality_txt",
            "bldg_condition_txt",
        ],
        more=["bldg_age_years", "bldg_effective_age_years", "bldg_quality_num", "bldg_condition_num"],
    ),
    Step(
        key="location",
        parent="details",
        fields=["address", "neighborhood", "city", "school_district", "census_tract", "census_block_group"],
        more=["census_block", "block", "risk_flood", "risk_disaster", "is_opportunity_zone", "noise_mean", "noise_max"],
    ),
    Step(
        key="land",
        parent="details",
        fields=["zoning", "zoning_desc", "land_class", "min_buildable_size"],
        more=["condo_group", "floor_area_ratio", "is_below_buildable_size"],
    ),
    Step(
        key="building",
        parent="details",
        fields=["bldg_type", "bldg_class", "bldg_desc", "bldg_stories", "bldg_units", "bldg_count"],
        more=["bldg_area_footprint_sqft"],
    ),
    Step(
        key="rooms_features",
        parent="details",
        fields=["bldg_rooms_bed", "bldg_rooms_bath", "bldg_style", "bldg_exterior", "bldg_heating", "bldg_ac"],
        more=[
            "bldg_rooms_bath_full",
            "bldg_rooms_bath_half",
            "bldg_foundation",
            "bldg_value_replacement",
            "bldg_value_depreciated",
            "bldg_depreciation_total",
            "bldg_depreciation_percent",
            "bldg_outbuilding_value",
        ],
    ),
    Step(
        key="assessed",
        parent="details",
        fields=["assr_land_value", "assr_impr_value", "assr_market_value"],
        more=["true_land_value", "true_impr_value", "true_market_value"],
    ),
    Step(
        key="other",
        parent="details",
        fields=["deed_book", "deed_page", "deed_grantor", "deed_grantee"],
        more=["mail_address", "mail_city", "mail_state", "mail_zip", "is_usps_vacant"],
    ),
    Step(key="review"),
]
STEP_KEYS = [s.key for s in STEPS]
SALES_FIELDS = {f for s in STEPS if s.sales for f in s.fields}
# The "big five" a model needs: building size is required; land size comes from the shapes when
# missing; age is flagged when missing; quality and condition are nice to have.
REQUIRED = ["bldg_area_finished_sqft"]
RECOMMENDED = [("bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years")]
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
    "%m/%d/%Y %H:%M:%S": "month/day/year and time",
    "%d/%m/%Y %H:%M": "day/month/year and time",
    "%Y/%m/%d": "year/month/day",
    "%m-%d-%Y": "month-day-year",
    "%d-%b-%Y": "day-Mon-year (09-Jan-2024)",
    "%b %d %Y": "Mon day year (Jan 09 2024)",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ---------- What the wizard sends ----------


class Issue(BaseModel):
    text: str = Field(description="'1 repeated ID'; once resolved, with the choice: '1 repeated ID, first kept'.")
    resolved: bool = Field(description="A choice was made for it (the duplicates dialog).")
    blocking: bool = Field(default=False, description="OpenAVMKit can't run well until it's dealt with (blank IDs).")
    todo: str = Field(default="", description="While unresolved, as a to-do: '442 blank IDs to confirm'.")


class Check(BaseModel):
    ok: bool
    text: str = Field(description="Short: '✓ years 1890–2025', 'several rows per parcel'.")
    warn: bool = Field(default=False, description="Usable, but worth a look (repeats handled, blank IDs dropped).")
    issues: list[Issue] = Field(default_factory=list, description="What's worth a look, each short.")
    share: float | None = Field(default=None, description="Sales: the share that find a parcel (0-1), for Reconcile.")


class Repeats(BaseModel):
    """What a file's ID column holds, for the duplicates notice and dialog (F3d)."""

    rows: int
    blank: int = Field(description="Rows with no ID. OpenAVMKit drops them when it joins the parcel files.")
    distinct: int = Field(description="Different IDs: the rows kept when keeping the first of each.")
    repeated: int = Field(description="IDs on more than one row.")
    extra: int = Field(description="Rows beyond the first for a repeated ID.")
    singles: int = Field(description="IDs on exactly one row: the rows kept when dropping every repeat.")
    few: bool = Field(description="Under 1% of the rows and under 10 rows: stray repeats, kept-first by default.")
    policy: Dupes | None
    sort: str | None
    descending: bool
    blank_ok: bool = Field(description="The rows with no ID have been acknowledged.")


class RepeatRows(BaseModel):
    """Examples of repeated IDs, every row of each, for the duplicates dialog."""

    columns: list[str]
    rows: list[list[str]]


class WizardFile(BaseModel):
    name: str
    filename: str
    missing: bool
    problem: str | None = Field(default=None, description="Why it can't be read.")
    rows: int | None
    geometry: bool
    holds: Holds | None
    match: Match = Field(description="Which ID it joins to the parcel universe on: key, or an extra ID (key2, key3).")
    id_column: str | None = Field(description="Loaded as the ID it joins on (match).")
    id_check: Check | None
    repeats: Repeats | None = Field(description="Set when the ID repeats or is blank on some rows.")
    extra_ids: list[ExtraId] = Field(description="The universe's extra IDs (key2, key3).")
    columns: list[Column]
    base: bool
    clean: dict[str, list[CleanStep]] = Field(description="ID field -> its clean-up steps (Reconcile).")


class ExtraId(BaseModel):
    """An extra ID of the parcel universe, for files that join on a different key (F3d).

    Not checked: rows are kept or dropped by the parcel ID alone.
    """

    field: Literal["key2", "key3"]
    column: str


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
    rule: Rule | None = Field(default=None, description="Yes/no worked out from columns (valid/vacant sale).")
    date_format: str | None = Field(default=None, description="Dates: the format it's read with.")


Status = Literal["blank", "blocked", "attention", "done"]
# Worst first: More details shows the worst of its parts.
ORDER: dict[str, int] = {"blocked": 0, "attention": 1, "blank": 2, "done": 3}
AGE = ("bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years")


class Left(BaseModel):
    text: str = Field(description="Short, as a to-do: '442 blank IDs to confirm'.")
    blocking: bool = Field(default=True, description="❌ stops a run; otherwise ⚠ worth deciding.")


class StepView(BaseModel):
    key: str
    parent: str | None
    status: Status = Field(
        description="blank: not visited (or an optional step not confirmed yet); blocked: something here stops a "
        "run; attention: something to decide, or recommended and missing; done: complete."
    )
    left: list[Left] = Field(description="What's still to do here, worst first; Next is greyed while any remain.")
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
    problems: list[str] = Field(description="What stops OpenAVMKit from running.")
    warnings: list[str] = Field(description="Recommended fields that are missing.")
    not_loaded: list[NotLoaded]


# ---------- Reading the files (cached on the file's size and time) ----------


def _stamp(path: Path) -> tuple[str, float, int]:
    st = path.stat()
    return str(path), st.st_mtime, st.st_size


@lru_cache(maxsize=64)
def _preview(stamp: tuple[str, float, int], layer: str | None) -> fields.FileColumns:
    return fields.columns(Path(stamp[0]), layer)


@lru_cache(maxsize=128)
def _values(stamp: tuple[str, float, int], layer: str | None, column: str, raw: bool = False) -> tuple[str, ...]:
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
    values = _values(stamp, layer, column, raw=True)
    parsed = [CleanStep.model_validate(x) for x in json.loads(steps)]
    return tuple(clean_value(v, parsed) for v in values) if parsed else values


def _steps_key(steps: list[CleanStep]) -> str:
    return json.dumps([x.model_dump() for x in steps])


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

    def ids(self, name: str, field: str, steps: list[CleanStep] | None = None) -> tuple[str, ...]:
        """A file's ID field as it joins: cleaned by its steps (or the given ones, for a preview)."""
        f = self.entry(name)
        spec = f.load.get(field)
        if spec is None or name not in self.preview:
            return ()
        use = f.clean.get(field, []) if steps is None else steps
        return _cleaned(_stamp(self.in_dir / f.filename), f.layer, spec[0], _steps_key(use))

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


# Stray repeats: fewer than both of these. More means several rows per parcel (SPEC F3d).
FEW_SHARE, FEW_ROWS = 0.01, 10
# Sales finding a parcel: below MATCH_MIN blocks a run, below MATCH_OK is worth reconciling (F3d).
MATCH_MIN, MATCH_OK = 0.5, 0.95


def _repeats_of(files: _Files, name: str, field: str) -> Repeats:
    entry = files.entry(name)
    values = files.ids(name, field)
    present = [v for v in values if v]
    counts: dict[str, int] = {}
    for v in present:
        counts[v] = counts.get(v, 0) + 1
    extra = len(present) - len(counts)
    return Repeats(
        rows=len(values),
        blank=len(values) - len(present),
        distinct=len(counts),
        repeated=sum(1 for n in counts.values() if n > 1),
        extra=extra,
        singles=sum(1 for n in counts.values() if n == 1),
        few=extra < FEW_ROWS and extra < FEW_SHARE * max(len(present), 1),
        policy=entry.dupes,
        sort=entry.dupes_sort,
        descending=entry.dupes_desc,
        blank_ok=entry.blank_ok,
    )


def _id_check(files: _Files, name: str, holds: Holds | None, base: str | None) -> tuple[Check | None, Repeats | None]:
    """The result on one line ("219,381 parcels"), and anything worth a look as separate issues."""
    f = files.entry(name)
    match = "key" if name == base else f.match
    spec = f.load.get(match)
    if not spec or name not in files.preview:
        return None, None
    r = _repeats_of(files, name, match)
    present = [v for v in files.ids(name, match) if v]
    flagged = r if (r.extra or r.blank) else None
    issues: list[Issue] = []
    if r.extra and holds == "parcels" and (r.few or r.policy):
        repeated = _n(r.repeated, "repeated ID")
        if r.policy is None:  # nothing chosen yet (OpenAVMKit would keep the first)
            issues.append(Issue(text=repeated, resolved=False, todo=f"{repeated} to decide"))
        else:
            how = "all dropped" if r.policy == "all" else "first kept"
            issues.append(Issue(text=f"{repeated}, {how}", resolved=True))
    if r.blank:
        outcome = "won't match a parcel" if holds == "sales" else "dropped"
        # Blank IDs wreck joins: on a parcel file they block until confirmed as dropped.
        blocking = holds == "parcels" and not r.blank_ok
        blank = _n(r.blank, "blank ID")
        todo = f"{blank} to confirm"
        issues.append(Issue(text=f"{blank}, {outcome}", resolved=r.blank_ok, blocking=blocking, todo=todo))
    open_issues = any(not i.resolved for i in issues)
    blocked = any(i.blocking for i in issues)
    if holds == "sales":
        flagged = r if r.blank else None
        if base is None or base == name:
            return Check(ok=True, text=f"{r.rows:,} sales", warn=open_issues, issues=issues), flagged
        base_ids = _base_ids(files, base, match)
        found = sum(1 for v in present if v in base_ids)
        share = found / r.rows if r.rows else 0.0
        text = f"{_pct(found, r.rows)} of sales match a parcel"
        # Under half matching is a blocker; under 95% worth reconciling (SPEC F3d).
        warn = open_issues or share < MATCH_OK
        return Check(ok=share >= MATCH_MIN, text=text, warn=warn, issues=issues, share=share), flagged
    if holds != "parcels":
        text = "several rows per parcel" if r.extra and not r.few else "one row per parcel"
        return Check(ok=True, text=text, warn=open_issues, issues=issues), flagged
    if r.extra and not r.few and r.policy is None:
        text = f"{_n(r.repeated, 'repeated ID')} ({_n(r.extra, 'extra row')}): choose what to do"
        return Check(ok=False, text=text, issues=issues), flagged
    kept = r.singles if r.policy == "all" else r.distinct
    tick = "" if open_issues else "✓ "
    if name == base:
        text = f"{tick}{kept:,} parcels" + ("" if issues else ", all different")
        return Check(ok=not blocked, text=text, warn=open_issues, issues=issues), flagged
    base_ids = _base_ids(files, base, match)
    found = len(set(present) & base_ids)
    text = f"{tick}one row per parcel · {_pct(found, len(set(present)))} match parcels"
    return Check(ok=found > 0 and not blocked, text=text, warn=open_issues, issues=issues), flagged


def _base_ids(files: _Files, base: str | None, field: str = "key") -> set[str]:
    if base is None or base not in files.preview:
        return set()
    return {v for v in files.ids(base, field) if v}


def _n(n: int, word: str) -> str:
    """'1 ID', '3 IDs', '1,204 extra rows'."""
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def _pct(n: int, total: int) -> str:
    if not total:
        return "0%"
    p = 100 * n / total
    return f"{p:.1f}%" if 99 < p < 100 or 0 < p < 1 else f"{p:.0f}%"


# ---------- Guesses ----------


def _names(d: DictionaryField) -> set[str]:
    return {_norm(d.key), _norm(d.name), *ALIASES.get(d.key, [])}


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
    out = {f.name: {spec[0]: field for field, spec in f.load.items()} for f in project.files}
    for f in project.files:
        for key, rule in f.rules.items():
            for c in rule.conditions:
                out[f.name].setdefault(c.column, key)
    return out


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
    by_key = {d.key: d for d in fields.dictionary(project.jurisdiction)}
    base = project.wizard.base
    used = _used(project)
    loaded = {field: f for f in project.files if f.holds in ("parcels", "sales") for field in f.load}

    out_files = []
    for f in project.files:
        match: Match = "key" if f.name == base else f.match
        key = f.load.get(match)
        id_check, repeats = _id_check(files, f.name, f.holds, base)
        extra_ids = []
        if f.name == base and f.name in files.preview:
            for field in EXTRA_IDS:
                spec = f.load.get(field)
                if spec:
                    extra_ids.append(ExtraId(field=field, column=spec[0]))
        out_files.append(
            WizardFile(
                name=f.name,
                filename=f.filename,
                missing=not (in_dir / f.filename).is_file(),
                problem=files.problem.get(f.name),
                rows=len(files.values(f.name, key[0])) if key and f.name in files.preview else _rows(files, f.name),
                geometry=files.geometry(f.name),
                holds=f.holds,
                match=match,
                id_column=key[0] if key else None,
                id_check=id_check,
                repeats=repeats,
                extra_ids=extra_ids,
                columns=files.columns(f.name),
                base=f.name == base,
                clean=f.clean,
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
            check = Check(ok=has_date, text="from parcel ID + sale date" if has_date else "needs a sale date")
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
                ruled = next((f for f in _field_files(project, step.sales) if key in f.rules), None)
                rule = ruled.rules[key] if ruled else None
                if ruled and rule and rule.conditions:
                    sources.append(Source(file=ruled.name, column=rule.conditions[0].column))
                check = None
                date_format = None
                if ruled and rule is not None and len(sources) == 1:
                    check = _rule_check(files, ruled, key, rule)
                elif len(sources) == 1:
                    col = files.column(sources[0].file, sources[0].column)
                    spec = files.entry(sources[0].file).load.get(key, [])
                    if col and d.type == "date" and len(spec) == 3:
                        date_format = spec[2]
                        check = _date_check(files, sources[0].file, col.name, spec[2])
                    else:
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
                        rule=rule,
                        date_format=date_format,
                    )
                )

    problems = _problems(out_files, sale_id, out_fields)
    warnings = _warnings(out_files, out_fields)
    steps = []
    for step in STEPS:
        status, left = _status(project, step, out_files, sale_id, out_fields, problems, warnings)
        steps.append(
            StepView(
                key=step.key,
                parent=step.parent,
                status=status,
                left=left,
                fields=step.fields,
                more=step.more,
                sales=step.sales,
            )
        )
    details = next(s for s in steps if s.key == "details")
    subs = [s.status for s in steps if s.parent == "details"]
    worst = min(subs, key=lambda x: ORDER[x])
    if worst in ("blocked", "attention"):
        details.status = worst
    else:
        details.status = "done" if all(x == "done" for x in subs) else "blank"

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
        problems=problems,
        warnings=warnings,
        not_loaded=not_loaded,
    )


def _status(
    project: Project,
    step: Step,
    files: list[WizardFile],
    sale_id: SaleId,
    flds: list[WizardField],
    problems: list[str],
    warnings: list[str],
) -> tuple[Status, list[Left]]:
    """A step's mark, worked out from what's on it, and what's left to do there (SPEC F3d). Blank until visited."""
    w = project.wizard
    if step.key == "details" or step.key not in w.visited:
        return "blank", []  # More details is the worst of its parts, filled in by the caller
    if step.key == "welcome":
        return ("done" if "welcome" in w.confirmed else "blank"), []
    if step.key == "review":
        return ("blocked" if problems else "attention" if warnings else "done"), []
    mine = [f for f in flds if f.step == step.key and not f.hidden]
    left = [Left(text=f"{f.name}: {f.check.text}") for f in mine if f.check is not None and not f.check.ok]

    def ids(f: WizardFile | None, what: str) -> None:
        if f is None:
            left.append(Left(text=f"Add the {what} file"))
        elif f.id_check is None:
            left.append(Left(text="Pick the parcel ID"))
        else:
            todo = [i for i in f.id_check.issues if not i.resolved]
            left.extend(Left(text=i.todo or i.text, blocking=i.blocking) for i in todo)
            share = f.id_check.share
            if share is not None and share < MATCH_OK:
                left.append(Left(text=f"Reconcile the IDs: {f.id_check.text}", blocking=not f.id_check.ok))
            elif not f.id_check.ok and not any(i.blocking for i in todo):
                left.append(Left(text=f"Parcel ID: {f.id_check.text}"))

    if step.key == "universe":
        base = next((f for f in files if f.base), None)
        if base is not None and base.name != BASE_NAME:
            left.append(Left(text="Use this file as the parcel universe"))
        ids(base, "parcel")
    elif step.key == "sales":
        sales = next((f for f in files if f.holds == "sales"), None)
        ids(sales, "sales")
        if sales is not None:
            if sale_id.column is None and not sale_id.made:
                left.append(Left(text="Pick a sale ID, or make one"))
            elif sale_id.check is not None and not sale_id.check.ok:
                left.append(Left(text=f"Sale ID: {sale_id.check.text}"))
            for f in mine:
                if f.key in ("sale_price", "sale_date", *ASSUMABLE) and not f.sources and not f.assumed:
                    left.append(Left(text=f"Pick the {f.name.lower()}"))
    elif step.key == "big_five":
        by_key = {f.key: f for f in flds}
        left.extend(
            Left(text=f"Pick the {by_key[k].name.lower()}") for k in REQUIRED if k in by_key and not by_key[k].sources
        )
        # Age is the one to flag; quality and condition are nice to have, and many places lack them.
        if not any(by_key[k].sources for k in AGE if k in by_key):
            left.append(Left(text="Pick the year built (or an age)", blocking=False))
    left.sort(key=lambda i: not i.blocking)
    if any(i.blocking for i in left):
        return "blocked", left
    if left:
        return "attention", left
    if step.key in ("universe", "sales", "big_five"):
        return "done", left
    return ("done" if step.key in w.confirmed or step.key in w.skipped else "blank"), left


def confirm(project: Project, step: str) -> None:
    """Next (or Start) on a step: an optional step counts as complete once it's been moved on from."""
    if step not in STEP_KEYS:
        raise LookupError(step)
    if step not in project.wizard.confirmed:
        project.wizard.confirmed.append(step)


def _rows(files: _Files, name: str) -> int | None:
    p = files.preview.get(name)
    if p is None:
        return None
    if p.rows is not None:
        return p.rows
    cols = files.columns(name)
    return len(files.values(name, cols[0].name)) if cols else None


def _problems(files: list[WizardFile], sale_id: SaleId, flds: list[WizardField]) -> list[str]:
    out = []
    base = next((f for f in files if f.base), None)
    if base is None:
        out.append("No parcel universe yet: add a parcel file with shapes.")
    elif base.name != BASE_NAME:
        out.append(f"The parcel universe file must be named {BASE_NAME}. Open Parcel universe to fix it.")
    for f in files:
        if f.holds in ("parcels", "sales") and f.id_column is None:
            out.append(f"{f.name} has no ID column to join on.")
        blocking = [i for i in f.id_check.issues if i.blocking] if f.id_check else []
        for issue in blocking:
            out.append(f"{f.name}: {issue.text.split(',')[0]}. Resolve them on its step to drop those rows.")
        if f.id_check is not None and not f.id_check.ok and not blocking and f.holds in ("parcels", "sales"):
            out.append(f"{f.name}: {f.id_check.text}.")
    if not any(f.holds == "sales" for f in files):
        out.append("No sales file yet.")
    else:
        if sale_id.column is None and not sale_id.made:
            out.append("The sales have no sale ID.")
        elif sale_id.check is not None and not sale_id.check.ok:
            out.append(f"Sale ID: {sale_id.check.text}.")
        for f in flds:
            if f.key in ("sale_price", "sale_date", "valid_sale", "vacant_sale") and not f.sources and not f.assumed:
                out.append(f"No {f.name.lower()}.")
    by_key = {f.key: f for f in flds}
    for key in REQUIRED:
        if key in by_key and not by_key[key].sources:
            out.append(f"No {by_key[key].name.lower()}: a model needs it.")
    for f in flds:
        if f.check is not None and not f.check.ok:
            out.append(f"{f.name}: {f.check.text}.")
    return out


def _warnings(files: list[WizardFile], flds: list[WizardField]) -> list[str]:
    by_key = {f.key: f for f in flds}
    out = []
    for f in files:
        r = f.repeats
        if r is None or f.holds not in ("parcels", "sales"):
            continue
        if r.blank and not r.blank_ok and f.holds == "sales":
            what = _n(r.blank, "sale")
            out.append(
                f"{f.name}: {what} {'has' if r.blank == 1 else 'have'} no ID and will be dropped. "
                f"That can mean {f.id_column} isn't the right ID."
            )
        if f.holds == "parcels" and r.extra and r.few and r.policy is None:
            out.append(
                f"{f.name}: {_n(r.repeated, 'ID')} repeat{'s' if r.repeated == 1 else ''}. "
                "Resolve it on its step; until then OpenAVMKit keeps the first row of each."
            )
    for group in RECOMMENDED:
        if not any(by_key[k].sources for k in group if k in by_key):
            first = by_key.get(group[0])
            if first is not None:
                out.append(f"No {first.name.lower()}: recommended for a good model.")
    return out


def visit(project: Project, in_dir: Path, step: str) -> None:
    """Show a step: fill in guesses for whatever on it hasn't been decided (F3d)."""
    if step not in STEP_KEYS:
        raise LookupError(step)
    _guess(project, in_dir, step)
    if step not in project.wizard.visited:
        project.wizard.visited.append(step)


def _guess(project: Project, in_dir: Path, step: str) -> None:
    """Guesses for a step: once a file is there to guess from, and never over a choice."""
    files = _Files(project, in_dir)
    if step == "universe":
        _guess_universe(project, files)
    if step == "sales":
        _guess_sales(project, files)
    spec = next(s for s in STEPS if s.key == step)
    candidates = [f.name for f in _field_files(project, spec.sales)]
    if not candidates:
        return
    by_key = _by_key()
    loaded = {field for f in project.files for field in f.load}
    # A field is decided once chosen (even as none) or guessed; a guess that found nothing can
    # still find something in a file added later.
    for key in [*spec.fields, *spec.more]:
        if key in project.wizard.decided or key not in by_key:
            continue
        if key in loaded or (key in ONLY_WITHOUT and ONLY_WITHOUT[key] in loaded):
            continue
        found = _guess_field(files, by_key[key], candidates, _used(project))
        if found:
            files.entry(found[0]).load[key] = found[1]
            loaded.add(key)
            project.wizard.decided.append(key)


def _base(project: Project) -> DataFile | None:
    return next((f for f in project.files if f.name == project.wizard.base), None)


def _guess_universe(project: Project, files: _Files) -> None:
    base = _base(project)
    if base is not None and "key" not in base.load and base.name in files.preview:
        column = _guess_id(files, base.name, "parcels", None)
        if column:
            base.load["key"] = [column, "string"]


def _guess_sales(project: Project, files: _Files) -> None:
    sales = _sales_file(project)
    if sales is None or sales.name not in files.preview:
        return
    base = _base(project)
    names = {c.name for c in files.columns(sales.name)}
    if not any(k in sales.load for k in ("key", *EXTRA_IDS)):
        # The universe's ID column names in the sales file decide: its parcel ID first, then its extra IDs.
        found = next((k for k in ("key", *EXTRA_IDS) if base and base.load.get(k) and base.load[k][0] in names), None)
        if found and base:
            sales.load[found] = [base.load[found][0], "string"]
            sales.match = cast(Match, found)
        else:
            column = _guess_id(files, sales.name, "sales", None)
            if column:
                sales.load["key"] = [column, "string"]
    if "key_sale" not in sales.load and "key_sale" not in sales.calc:
        column = _guess_sale_id(files, sales.name)
        if column:
            sales.load["key_sale"] = [column, "string"]
        else:
            sales.calc["key_sale"] = made_sale_id(sales.match)


def repeat_rows(project: Project, in_dir: Path, name: str, limit: int = 5) -> RepeatRows:
    """Every row of a few repeated IDs, for the duplicates dialog: are they copies, or different records?"""
    files = _Files(project, in_dir)
    entry = files.entry(name)
    field = "key" if name == project.wizard.base else entry.match
    spec = entry.load.get(field)
    if spec is None or name not in files.preview:
        raise ValueError(f"{name} has no ID column yet.")
    values = files.ids(name, field)
    counts: dict[str, int] = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    ids = [v for v, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n > 1][:limit]
    loaded = [s[0] for s in entry.load.values()]
    shown = [spec[0], *[c for c in loaded if c != spec[0]]][:8]
    rest = [c.name for c in files.columns(name) if c.name not in shown]
    shown = (shown + rest)[:8]
    picked = [i for i, v in enumerate(values) if v in set(ids)]
    columns = {c: files.values(name, c) for c in shown}
    rows = [[columns[c][i] for c in shown] for i in sorted(picked, key=lambda i: ids.index(values[i]))]
    return RepeatRows(columns=shown, rows=rows[:40])


def made_sale_id(match: Match) -> list:
    """The sale ID made from the parcel ID + sale date, e.g. "0012-001-2023-01-09" (an OpenAVMKit calc)."""
    return ["join", ["values", match, "sale_date"], "str:-"]


def set_file(
    project: Project,
    in_dir: Path,
    name: str,
    holds: Holds | None,
    id_column: str | None,
    extra_field: str | None = None,
    extra_column: str | None = None,
    match: Match | None = None,
    universe: bool = False,
    dupes: Dupes | None = None,
    dupes_sort: str | None = None,
    dupes_desc: bool = False,
    blank_ok: bool | None = None,
) -> None:
    """A file's part (the parcel universe, sales, or more parcel details) and the ID it joins on.

    ``extra_field`` (key2, key3) with ``extra_column`` sets one of the universe's extra IDs; with
    no column it removes it (key3 then becomes key2).
    """
    files = _Files(project, in_dir)
    entry = files.entry(name)
    columns = {c.name for c in files.columns(name)}
    for column in (id_column, extra_column):
        if column is not None and column not in columns:
            raise ValueError(f"{name} has no column {column}.")
    if universe:
        if not files.geometry(name):
            raise ValueError(f"{name} has no shapes. The parcel universe file needs parcel geometry.")
        for f in project.files:
            if f is not entry and f.holds == "parcels" and f.name == project.wizard.base:
                f.holds = "unused"
                project.wizard.base = None
        entry.holds, entry.match, holds = "parcels", "key", None
    is_base = universe or entry.name == project.wizard.base
    if match is not None and not is_base and match != entry.match:
        old = entry.load.pop(entry.match, None)
        entry.match = match
        if old and id_column is None:
            id_column = old[0]
    if id_column is not None:
        field = "key" if is_base else entry.match
        if not is_base:
            for other in ("key", *EXTRA_IDS):
                if other != field:
                    entry.load.pop(other, None)
        _put(entry, field, [id_column, "string"])
    if extra_field is not None:
        if extra_field not in EXTRA_IDS or not is_base:
            raise ValueError("Extra IDs belong to the parcel universe: key2, then key3.")
        if extra_column is not None:
            if extra_field == "key3" and "key2" not in entry.load:
                raise ValueError("Add the 2nd ID first.")
            entry.load.pop(extra_field, None)
            _put(entry, extra_field, [extra_column, "string"])
        else:  # removed: the 3rd ID moves up to 2nd
            entry.load.pop(extra_field, None)
            if extra_field == "key2" and "key3" in entry.load:
                entry.load["key2"] = entry.load.pop("key3")
                for f in project.files:  # files joined on the 3rd ID follow it
                    if f is not entry and f.match == "key3":
                        f.match = "key2"
                        if "key3" in f.load:
                            f.load["key2"] = f.load.pop("key3")
    if holds is not None and holds != entry.holds:
        if holds == "sales":  # one sales file: a new one replaces it
            for f in project.files:
                if f is not entry and f.holds == "sales":
                    f.holds = "unused"
                    f.calc = {}
        if entry.holds == "sales":  # what only a sales file has
            for key in ("key_sale", *ASSUMABLE):
                entry.calc.pop(key, None)
        entry.holds = holds
    if entry.holds == "sales" and "key_sale" in entry.calc:
        entry.calc["key_sale"] = made_sale_id(entry.match)
    if dupes is not None:  # the duplicates dialog: what to do with repeated IDs
        if dupes_sort is not None and dupes_sort not in entry.load:
            raise ValueError(f"Sort by a field {name} loads; {dupes_sort} isn't one.")
        entry.dupes, entry.dupes_sort, entry.dupes_desc = dupes, dupes_sort, dupes_desc
    if blank_ok is not None:
        entry.blank_ok = blank_ok
    if id_column is not None and dupes is None:  # a new ID: its repeats and blanks are looked at afresh
        entry.dupes, entry.dupes_sort, entry.dupes_desc, entry.blank_ok = None, None, False, False
    update_base(project, in_dir, rename=True)
    # A file just given its part: guess its IDs and fields now, as showing the step would have.
    if universe:
        _guess(project, in_dir, "universe")
    elif holds == "sales":
        _guess(project, in_dir, "sales")
    elif holds == "parcels":  # more parcel details: the steps already seen may find more in it
        for step in STEPS:
            if step.fields and not step.sales and step.key in project.wizard.visited:
                _guess(project, in_dir, step.key)


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
        sales.calc["key_sale"] = made_sale_id(sales.match)
    elif column:
        _put(sales, "key_sale", [column, "string"])


def set_field(
    project: Project,
    in_dir: Path,
    key: str,
    file: str | None,
    column: str | None,
    assume: bool,
    date_format: str | None = None,
) -> None:
    """Load a field from one file's column, from nowhere, or (valid/vacant sale) as an assumption.

    A yes/no field from a column that isn't yes/no gets a rule to fill in: which values mean yes."""
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
        d = by_key[key]
        check, spec = field_check(d, col)
        if d.type == "date" and date_format:
            spec = [column, "datetime", date_format]
        elif spec is None and d.type == "boolean" and step.sales:
            spec = None  # becomes a rule, below
        elif spec is None:
            raise ValueError(f"{column}: {check.text}.")
        for other, s in target.load.items():
            if s[0] == column and other != key:
                raise ValueError(f"{column} is already loaded as {other}.")
    elif assume and (key not in ASSUMABLE or sales is None):
        raise ValueError(f"{key} can't be assumed.")
    for f in allowed:
        f.load.pop(key, None)
        f.rules.pop(key, None)
    if sales is not None and key in ASSUMABLE:
        sales.calc.pop(key, None)
    if target is not None and spec is None:
        target.rules[key] = Rule(conditions=[Condition(column=cast(str, column))])
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


# ---------- Reconcile: clean up IDs so the sales find their parcels (F3d) ----------


class Sample(BaseModel):
    raw: str = Field(description="As written in the file.")
    clean: str = Field(description="After the clean-up steps.")
    hit: bool = Field(description="Sales: finds a parcel. Parcels: has a sale.")


class Suggestion(BaseModel):
    text: str = Field(description="'Remove leading zeros from the parcel IDs; trim spaces from the sales IDs'.")
    base_steps: list[CleanStep]
    file_steps: list[CleanStep]
    share: float


class Reconcile(BaseModel):
    file: str = Field(description="The sales file.")
    base: str
    field: Match = Field(description="The ID they join on.")
    file_column: str
    base_column: str
    matched: int
    total: int
    parcels: int = Field(description="Distinct parcel IDs on the universe side, after its steps.")
    share: float
    saved_share: float = Field(description="The share with the steps as saved, before these changes.")
    file_samples: list[Sample]
    base_samples: list[Sample]
    suggestion: Suggestion | None
    writes: dict[str, list] = Field(description="entry -> the calc it writes for the ID (only files with steps).")


SampleView = Literal["unmatched", "random"]
SAMPLES = 6


def _sides(project: Project, in_dir: Path, name: str) -> tuple[_Files, DataFile, DataFile, Match]:
    files = _Files(project, in_dir)
    entry = files.entry(name)
    base = project.wizard.base
    if base is None or base == name or base not in files.preview:
        raise ValueError("Add the parcel universe first.")
    if entry.match not in entry.load or entry.match not in files.entry(base).load:
        raise ValueError(f"Pick the ID column of {name} first.")
    return files, entry, files.entry(base), entry.match


def _matched(file_ids: tuple[str, ...], base_set: set[str]) -> int:
    return sum(1 for v in file_ids if v and v in base_set)


# What the suggestion tries on each side, simplest first.
_TRIES: list[list[CleanStep]] = [
    [],
    [CleanStep(kind="trim")],
    [CleanStep(kind="zeros")],
    [CleanStep(kind="trim"), CleanStep(kind="zeros")],
    [CleanStep(kind="remove", text="-")],
    [CleanStep(kind="remove", text="- ")],
    [CleanStep(kind="remove", text="- "), CleanStep(kind="zeros")],
    [CleanStep(kind="remove", text="-. /"), CleanStep(kind="zeros")],
]


def _describe(steps: list[CleanStep]) -> str:
    names = {"zeros": "remove leading zeros", "trim": "trim spaces"}
    out = []
    for st in steps:
        if st.kind == "remove":
            out.append("remove hyphens" if st.text == "-" else f"remove {' '.join(repr(c) for c in st.text)}")
        else:
            out.append(names.get(st.kind, st.kind))
    return " and ".join(out)


def _suggest(files: _Files, entry: DataFile, base: DataFile, field: Match, now: float) -> Suggestion | None:
    """The simplest clean-up pair from a few common ones that matches clearly more sales. Only a suggestion."""
    total = len(files.ids(entry.name, field))
    if not total:
        return None
    base_sets = [{v for v in files.ids(base.name, field, t) if v} for t in _TRIES]
    file_counts = [Counter(v for v in files.ids(entry.name, field, t) if v) for t in _TRIES]
    best: tuple[float, int, int, int] | None = None
    for b, bset in enumerate(base_sets):
        for f, counts in enumerate(file_counts):
            share = sum(n for v, n in counts.items() if v in bset) / total
            score = (share, -(len(_TRIES[b]) + len(_TRIES[f])), b, f)
            if best is None or score[:2] > best[:2]:
                best = score
    if best is None or best[0] < now + 0.01:
        return None
    share, _, b, f = best
    parts = []
    if _TRIES[b]:
        parts.append(f"{_describe(_TRIES[b])} from the parcel IDs")
    if _TRIES[f]:
        parts.append(f"{_describe(_TRIES[f])} from the sales IDs")
    text = "; ".join(parts)
    return Suggestion(text=text[:1].upper() + text[1:], base_steps=_TRIES[b], file_steps=_TRIES[f], share=share)


def reconcile(
    project: Project,
    in_dir: Path,
    name: str,
    file_steps: list[CleanStep],
    base_steps: list[CleanStep],
    view: SampleView = "unmatched",
    seed: int = 0,
    suggest: bool = False,
) -> Reconcile:
    """How the sales match with these steps, and samples of each side: the live view of the dialog."""
    files, entry, base, field = _sides(project, in_dir, name)
    file_ids = files.ids(name, field, file_steps)
    base_ids = files.ids(base.name, field, base_steps)
    base_set = {v for v in base_ids if v}
    file_set = {v for v in file_ids if v}
    saved = _matched(files.ids(name, field), _base_ids(files, base.name, field))
    matched = _matched(file_ids, base_set)
    total = len(file_ids)
    rng = random.Random(seed)
    file_raw = _values(_stamp(in_dir / entry.filename), entry.layer, entry.load[field][0], raw=True)
    base_raw = _values(_stamp(in_dir / base.filename), base.layer, base.load[field][0], raw=True)

    def pick(raw: tuple[str, ...], ids: tuple[str, ...], keep) -> list[tuple[str, str]]:
        seen: dict[str, str] = {}
        for r, c in zip(raw, ids, strict=True):
            if r not in seen and keep(c):
                seen[r] = c
        chosen = rng.sample(list(seen.items()), min(SAMPLES, len(seen)))
        return sorted(chosen, key=lambda rc: rc[0])

    hit_file = (lambda c: not (c and c in base_set)) if view == "unmatched" else (lambda c: True)
    file_samples = [
        Sample(raw=r, clean=c, hit=bool(c) and c in base_set) for r, c in pick(file_raw, file_ids, hit_file)
    ]
    base_samples = [Sample(raw=r, clean=c, hit=c in file_set) for r, c in pick(base_raw, base_ids, bool)]
    writes = {n: clean_calc(field, st) for n, st in ((base.name, base_steps), (name, file_steps)) if st}
    return Reconcile(
        file=name,
        base=base.name,
        field=field,
        file_column=entry.load[field][0],
        base_column=base.load[field][0],
        matched=matched,
        total=total,
        parcels=len(base_set),
        share=matched / total if total else 0.0,
        saved_share=saved / total if total else 0.0,
        file_samples=file_samples,
        base_samples=base_samples,
        suggestion=_suggest(files, entry, base, field, matched / total if total else 0.0) if suggest else None,
        writes=writes,
    )


def set_reconcile(
    project: Project, in_dir: Path, name: str, file_steps: list[CleanStep], base_steps: list[CleanStep]
) -> None:
    """Save the clean-up steps on both sides of the join; OpenAVMKit runs them as calcs when it loads."""
    files, entry, base, field = _sides(project, in_dir, name)
    for f, steps in ((entry, file_steps), (base, base_steps)):
        if steps:
            f.clean[field] = steps
        else:
            f.clean.pop(field, None)


# ---------- Yes/no rules (valid and vacant sale) and dates: previews (F3d) ----------


class ValueCount(BaseModel):
    value: str = Field(description='"" for blank.')
    count: int


class RuleRow(BaseModel):
    cells: list[str]
    yes: bool


class RulePreview(BaseModel):
    key: str
    file: str
    yes: int
    total: int
    columns: list[str] = Field(description="The columns the rule tests, for the rows.")
    values: dict[str, list[ValueCount]] = Field(description="Per column tested, its values, most common first.")
    more: dict[str, int] = Field(description="Per column, how many other values there are.")
    rows: list[RuleRow] = Field(description="A few rows of each outcome.")
    calc: list = Field(description="The OpenAVMKit calc it writes.")
    load: dict[str, list[str]] = Field(description="Columns it loads so the calc can test them.")


VALUES_SHOWN = 60


@lru_cache(maxsize=64)
def _counts(stamp: tuple[str, float, int], layer: str | None, column: str) -> tuple[tuple[str, int], ...]:
    counts = Counter(_values(stamp, layer, column, raw=True))
    return tuple(sorted(counts.items(), key=lambda vc: (-vc[1], vc[0])))


def _rule_result(files: _Files, entry: DataFile, rule: Rule):
    """The rule run by OpenAVMKit's own filter code on the file's rows, typed as OpenAVMKit loads them."""
    import pandas as pd
    from openavmkit.filters import resolve_filter

    names = rule_fields(entry.load, rule)
    stamp = _stamp(files.in_dir / entry.filename)
    frame = {}
    for column, (field, kind) in names.items():
        values = pd.Series(_values(stamp, entry.layer, column, raw=True))
        if kind == "float":
            frame[field] = pd.to_numeric(values.str.strip(), errors="coerce")
        else:
            frame[field] = values.mask(values.str.strip() == "").astype("string")
    df = pd.DataFrame(frame)
    filt = rule_filter(rule, names)
    if not filt or df.empty:
        return names, filt, pd.Series(False, index=df.index)
    # OpenAVMKit reads a missing result as no (na_false).
    return names, filt, resolve_filter(df, filt).fillna(False).astype(bool)


def _complete(rule: Rule) -> bool:
    return bool(rule.conditions) and all(c.values or c.op in ("isempty", "notempty") for c in rule.conditions)


def _rule_check(files: _Files, entry: DataFile, key: str, rule: Rule) -> Check:
    if any(files.column(entry.name, c.column) is None for c in rule.conditions):
        return Check(ok=False, text="a column it tests isn't in the file")
    if not _complete(rule):
        return Check(ok=False, text="choose which values mean yes")
    try:
        _, _, result = _rule_result(files, entry, rule)
    except Exception as e:  # noqa: BLE001 - a rule OpenAVMKit can't run shows on its row
        return Check(ok=False, text=f"OpenAVMKit can't run this: {e}")
    yes, total = int(result.sum()), len(result)
    word = {"valid_sale": "valid", "vacant_sale": "vacant"}.get(key, "yes")
    text = f"{yes:,} of {total:,} {word} ({_pct(yes, total)})"
    # All or nothing is legal, but usually means the wrong values were picked.
    return Check(ok=True, text=("✓ " if 0 < yes < total else "") + text, warn=yes in (0, total))


def _rule_entry(project: Project, key: str) -> DataFile:
    sales = _sales_file(project)
    d = _by_key().get(key)
    if sales is None:
        raise ValueError("Add the sales file first.")
    if d is None or d.type != "boolean":
        raise LookupError(key)
    return sales


def rule_preview(project: Project, in_dir: Path, key: str, rule: Rule) -> RulePreview:
    """What a rule makes of the sales file: how many yes, the values of the columns it tests, a few rows."""
    entry = _rule_entry(project, key)
    files = _Files(project, in_dir)
    for c in rule.conditions:
        if files.column(entry.name, c.column) is None:
            raise ValueError(f"{entry.name} has no column {c.column}.")
    stamp = _stamp(in_dir / entry.filename)
    columns = list(dict.fromkeys(c.column for c in rule.conditions))
    values, more = {}, {}
    for column in columns:
        counts = _counts(stamp, entry.layer, column)
        values[column] = [ValueCount(value="" if not v.strip() else v, count=n) for v, n in counts[:VALUES_SHOWN]]
        more[column] = max(0, len(counts) - VALUES_SHOWN)
    names, filt, result = _rule_result(files, entry, rule) if _complete(rule) else ({}, [], None)
    rows: list[RuleRow] = []
    if result is not None and columns:
        cells = {c: _values(stamp, entry.layer, c, raw=True) for c in columns}
        rng = random.Random(0)
        for want in (True, False):
            idx = [i for i, x in enumerate(result.tolist()) if x == want]
            for i in sorted(rng.sample(idx, min(4, len(idx)))):
                rows.append(RuleRow(cells=[cells[c][i] for c in columns], yes=want))
    total = len(_values(stamp, entry.layer, columns[0], raw=True)) if columns else 0
    load = {field: [column, kind] for column, (field, kind) in names.items() if field not in entry.load}
    return RulePreview(
        key=key,
        file=entry.name,
        yes=int(result.sum()) if result is not None else 0,
        total=total,
        columns=columns,
        values=values,
        more=more,
        rows=rows,
        calc=["?", filt] if filt else [],
        load=load,
    )


def set_rule(project: Project, in_dir: Path, key: str, rule: Rule) -> None:
    """Work a yes/no field out from the sales file's columns (OpenAVMKit's ["?", filter] calc)."""
    entry = _rule_entry(project, key)
    files = _Files(project, in_dir)
    for c in rule.conditions:
        if files.column(entry.name, c.column) is None:
            raise ValueError(f"{entry.name} has no column {c.column}.")
    if not rule.conditions:
        raise ValueError("A rule needs at least one test.")
    entry.load.pop(key, None)
    entry.calc.pop(key, None)
    entry.rules[key] = rule
    if key not in project.wizard.decided:
        project.wizard.decided.append(key)


class DateSample(BaseModel):
    raw: str
    read: str | None = Field(description="As OpenAVMKit reads it (year-month-day), or None if it doesn't.")


class DateFormat(BaseModel):
    format: str
    words: str


class DatePreview(BaseModel):
    format: str
    words: str
    total: int
    blank: int
    read: int
    failed: int
    first: str | None
    last: str | None
    samples: list[DateSample] = Field(description="Ones that don't read first, then a spread of ones that do.")
    also: list[DateFormat] = Field(description="Other formats that read every date too, but differently.")
    formats: list[DateFormat]


@lru_cache(maxsize=128)
def _parse(stamp: tuple[str, float, int], layer: str | None, column: str, fmt: str):
    """The column read with a date format the way OpenAVMKit does (pd.to_datetime with format=)."""
    import pandas as pd

    values = pd.Series(_values(stamp, layer, column, raw=True))
    try:
        return pd.to_datetime(values.mask(values.str.strip() == ""), format=fmt)
    except (ValueError, TypeError):
        return pd.to_datetime(values.mask(values.str.strip() == ""), format=fmt, errors="coerce", exact=True)


def _date_stats(files: _Files, name: str, column: str, fmt: str) -> tuple[int, int, int]:
    """(rows, blank, read)."""
    entry = files.entry(name)
    stamp = _stamp(files.in_dir / entry.filename)
    values = _values(stamp, entry.layer, column, raw=True)
    blank = sum(1 for v in values if not v.strip())
    read = int(_parse(stamp, entry.layer, column, fmt).notna().sum())
    return len(values), blank, read


def _also(files: _Files, name: str, column: str, fmt: str) -> list[str]:
    """Formats that also read every date but give different dates (day/month or month/day): worth a look."""
    entry = files.entry(name)
    stamp = _stamp(files.in_dir / entry.filename)
    col = files.column(name, column)
    samples = col.samples if col else []
    mine = _parse(stamp, entry.layer, column, fmt)
    out = []
    for other in fields.DATE_FORMATS:
        if other == fmt or not samples or not all(p for p in fields.check_dates(samples, other).parsed):
            continue
        theirs = _parse(stamp, entry.layer, column, other)
        if theirs.notna().sum() == mine.notna().sum() and not theirs.equals(mine):
            out.append(other)
    return out


def _date_check(files: _Files, name: str, column: str, fmt: str) -> Check:
    total, blank, read = _date_stats(files, name, column, fmt)
    words = DATE_WORDS.get(fmt, fmt)
    failed = total - blank - read
    if read == 0:
        return Check(ok=False, text=f"doesn't read as {words}")
    if failed:
        return Check(ok=True, warn=True, text=f"reads as {words} · {failed:,} don't read")
    also = _also(files, name, column, fmt)
    if also:
        return Check(ok=True, warn=True, text=f"reads as {words}, or as {DATE_WORDS.get(also[0], also[0])}?")
    return Check(ok=True, text=f"✓ reads as {words}")


def date_preview(project: Project, in_dir: Path, name: str, column: str, fmt: str) -> DatePreview:
    """A column read with a date format: how many read, the range, samples, and look-alike formats."""
    files = _Files(project, in_dir)
    if files.column(name, column) is None:
        raise ValueError(f"{name} has no column {column}.")
    entry = files.entry(name)
    stamp = _stamp(in_dir / entry.filename)
    total, blank, read = _date_stats(files, name, column, fmt)
    parsed = _parse(stamp, entry.layer, column, fmt)
    values = _values(stamp, entry.layer, column, raw=True)
    as_text = [None if p is None or p != p else p.strftime("%Y-%m-%d") for p in parsed.tolist()]
    bad = list(dict.fromkeys(v for v, p in zip(values, as_text, strict=True) if v.strip() and p is None))[:4]
    good_idx = [i for i, p in enumerate(as_text) if p is not None]
    step = max(1, len(good_idx) // 6)
    good = [good_idx[i] for i in range(0, len(good_idx), step)][: 8 - len(bad)]
    samples = [DateSample(raw=v, read=None) for v in bad] + [DateSample(raw=values[i], read=as_text[i]) for i in good]
    ok = parsed.dropna()
    return DatePreview(
        format=fmt,
        words=DATE_WORDS.get(fmt, fmt),
        total=total,
        blank=blank,
        read=read,
        failed=total - blank - read,
        first=ok.min().strftime("%Y-%m-%d") if len(ok) else None,
        last=ok.max().strftime("%Y-%m-%d") if len(ok) else None,
        samples=samples,
        also=[DateFormat(format=f, words=DATE_WORDS.get(f, f)) for f in _also(files, name, column, fmt)],
        formats=[DateFormat(format=f, words=DATE_WORDS.get(f, f)) for f in fields.DATE_FORMATS],
    )

"""Step 3, Check sales: notebook 2 (clean), with each call shown before it runs and every sale set aside listed after
(SPEC F6).

The calls (the sales window, time adjustment, fills, where "near" is for sales scrutiny, which checks run, rare
categories) are the project's `clean` state, written into settings.json with the rest. The run starts from step 2's
hand-off (out/1-assemble-sup.pickle) and runs OpenAVMKit's own clean stage in a process of its own,
`python -m oakbox.clean <project id>`: fills, equity clusters, sales processing (window, validity, time adjustment),
sales scrutiny, rare categories, then out/2-clean-sup.pickle and out/look/2-clean-*. Scrutiny drops what it sets aside
except the sales the user kept (in/oakbox/keep.csv); the user's exclusions are in/oakbox/exclude.csv. The receipt,
and the sales set aside with their groups for the review, are in out/oakbox/clean/.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from pydantic import Field, field_validator, model_validator

from oakbox import assemble, atomic, bring_in, cells, fields, names, steps
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound

if TYPE_CHECKING:
    import pandas as pd

    from oakbox.projects import Project

MODULE = "clean"
UNKNOWN = assemble.UNKNOWN
NO_PARCEL = "(none)"  # the model group of a sale whose parcel isn't in the parcel universe
NO_PARCEL_NAME = "No parcel (not in the parcel universe)"
KEEP_FILE = "in/oakbox/keep.csv"
EXCLUDE_FILE = "in/oakbox/exclude.csv"
HEURISTICS = (
    "nominal_price",
    "dupe_deed_date",
    "dupe_date_price",
    "bulk_deed",
    "false_vacant",
    "built_after_sale",
    "vacant_priced_improved",
    "same_surname",
)
CHECKS = ("cluster", *HEURISTICS)
YEARS_BEFORE = 5  # OpenAVMKit's default sales window: sales from 5 years before the valuation date
# Fields OpenAVMKit always tidies itself (0 = no building / no year), never offered a fill.
YEAR_AGE = ("bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years")
NEVER_PROPOSED = ("bldg_area_finished_sqft", "bldg_area_finished_sqm", *YEAR_AGE)

FillMethod = Literal["median", "mean", "mode", "zero", "min", "max", "leave"]
FillChoice = Literal["auto", "median", "mean", "mode", "zero", "min", "max", "leave"]
FillScope = Literal["all", "impr", "vacant"]
FieldKind = Literal["building", "land", "other"]
Period = Literal["M", "Q"]


def group_of(v) -> str:
    """A model_group value as text: a sale with no parcel has none."""
    text = "" if v is None else str(v)
    return NO_PARCEL if text in ("", "None", "nan", "<NA>") else text


def model_groups_of(df) -> pd.Series:
    return df["model_group"].map(group_of) if "model_group" in df else df.index.to_series().map(lambda _: NO_PARCEL)


def empty_frame(*columns: str) -> pd.DataFrame:
    import pandas as pd

    return pd.DataFrame({c: pd.Series(dtype=object) for c in columns})


def out_dir(project_dir: Path) -> Path:
    return steps.out_dir(project_dir, MODULE)


# ---------- The calls: the project's state, and the settings it writes ----------


class Fill(BaseModel):
    """A field's fill, by its kind. A building's field fills improved parcels only (OpenAVMKit has made it 0 on vacant
    ones); a land field every parcel alike (a fact about the land or its area, census figures among them, is the same
    built on or not); any other every parcel alike, or improved and vacant parcels each their own (split)."""

    method: FillChoice = Field(
        default="auto",
        description="Every parcel's; a building's field's, or split, improved parcels'. auto: proposed (propose); "
        "leave: no fill (the field stays blank).",
    )
    split: bool = Field(default=False, description="Improved and vacant parcels each their own (an Other field only).")
    vacant: FillChoice = Field(default="auto", description="Split: vacant parcels'.")
    kind: FieldKind = Field(default="other", description="The field's kind, as last seen (decide keeps it up to date).")

    @model_validator(mode="before")
    @classmethod
    def _from_scope(cls, data: object) -> object:
        """Fills from before (a method for every parcel, only improved, or only vacant): a split."""
        if isinstance(data, dict) and "scope" in data:
            data = dict(data)
            scope = data.pop("scope")
            if scope == "impr":
                data |= {"split": True, "vacant": "leave"}
            elif scope == "vacant":
                data |= {"split": True, "vacant": data.get("method", "auto"), "method": "leave"}
        return data


def fill_words(field: str, f: Fill) -> str:
    """A fill in a few words, for the receipt: "median", "median (improved)", "median (improved), zero (vacant)"."""
    parts = fill_parts(field, f)
    if len(parts) == 1 and parts[0][1] == "all":
        return parts[0][0]
    return ", ".join(f"{m} ({'improved' if sc == 'impr' else 'vacant'})" for m, sc in parts) or "leave"


def fill_parts(field: str, f: Fill) -> list[tuple[FillMethod, FillScope]]:
    """What a fill asks of OpenAVMKit: each method and the parcels it's for (auto as proposed; leave: nothing)."""
    auto = propose(field)
    method = cast(FillMethod, auto if f.method == "auto" else f.method)
    if f.kind == "building":
        parts: list[tuple[FillMethod, FillScope]] = [(method, "impr")]
    elif f.split and f.kind == "other":
        parts = [(method, "impr"), (cast(FillMethod, auto if f.vacant == "auto" else f.vacant), "vacant")]
    else:
        parts = [(method, "all")]
    return [(m, sc) for m, sc in parts if m != "leave"]


class SaleMark(BaseModel):
    action: Literal["keep", "exclude"]
    note: str = ""


class TimeFile(BaseModel):
    """A model group's own time adjustment, as the user gave it (a copy in in/oakbox/time_adjustment/)."""

    path: str = Field(description="Relative to the project folder.")
    name: str = Field(description="The file's name, as chosen.")
    digest: str = Field(description="Of its contents: a new file puts the step out of date.")
    first: str
    last: str
    periods: int


IndexOn = Literal["impr", "land"]


class CleanState(BaseModel):
    sales_from: int | None = Field(default=None, description="Improved sales from this year on; None: the default.")
    time_adjust: bool = True
    period: Period = Field(default="Q", description="Months or quarters to start from (OpenAVMKit goes coarser).")
    borrow: dict[str, str] = Field(
        default_factory=dict, description="Group -> the group whose time adjustment it uses."
    )
    time_files: dict[str, TimeFile] = Field(default_factory=dict, description="Group -> its own time adjustment.")
    per: dict[str, IndexOn] = Field(
        default_factory=dict,
        description="Group -> what its index is of (impr: price per finished area; land: per land area); "
        "missing: OpenAVMKit works it out from the sales.",
    )
    fills: dict[str, Fill] = Field(default_factory=dict, description="Per field with blanks; written once proposed.")
    fills_auto: bool = Field(
        default=False,
        description="Fills are auto unless chosen (decide): a project from before, whose proposals were written down "
        "as if chosen, has each that's still its proposal made auto once.",
    )
    location: str | None = Field(
        default=None, description='Where "near" is for scrutiny and the equity clusters; "" none; None: not decided.'
    )
    checks: dict[str, bool] = Field(default_factory=dict, description="cluster and the heuristics; missing: on.")
    collapse: bool = False
    collapse_fields: list[str] = Field(default_factory=list, description="Categories folded when collapse is on.")
    collapse_sales_min: int = 5
    nominal_below: int = Field(default=1_000, description="A price under this is a nominal deed, not a price.")
    collapse_univ_min: int = 20
    marks: dict[str, SaleMark] = Field(default_factory=dict, description="key_sale -> kept or excluded by the user.")
    name_format: names.FormatId | None = Field(
        default=None, description="How deed names are written (names.FORMATS, or custom); None: not decided."
    )

    @field_validator("name_format", mode="before")
    @classmethod
    def _known_format(cls, v: object) -> object:
        """A format this OAK box doesn't know (renamed since) reads as not decided: the guess is shown again."""
        return v if v in get_args(names.FormatId) else None

    name_pattern: str | None = Field(default=None, description="The custom format: a regex with a surname group.")


def valuation_year(project: Project) -> int:
    return project.valuation_date.year if project.valuation_date else int(project.tax_year)


def window(project: Project) -> int:
    """The first year sales count from: improved and vacant alike (vacant land isn't modeled on its own yet, so it
    has no window of its own)."""
    return project.clean.sales_from or valuation_year(project) - YEARS_BEFORE


def settings(project: Project) -> dict:
    """The parts of settings.json this step writes, merged into the rest (projects.base_settings); nothing until
    the step is used (its proposals are written down then: decide)."""
    c: CleanState = project.clean
    if c.location is None:
        return {}
    start = window(project)
    fill: dict[str, list[str]] = {}
    for field, f in sorted(c.fills.items()):
        for method, scope in fill_parts(field, f):
            # "+": added to OpenAVMKit's own fill lists, not replacing them.
            fill.setdefault("+" + method + {"all": "", "impr": "_impr", "vacant": "_vacant"}[scope], []).append(field)
    ta: dict[str, Any] = {"use": c.time_adjust, "period": c.period}
    if c.borrow:
        ta["borrow"] = dict(sorted(c.borrow.items()))
    if c.per:
        ta["per"] = dict(sorted(c.per.items()))
    if c.time_files:
        ta["from_file"] = {g: f.path for g, f in sorted(c.time_files.items())}
        # A comment to OpenAVMKit ("__"), but part of what the steps' hashes see: a new file with the same name.
        ta["__file_digests"] = {g: f.digest for g, f in sorted(c.time_files.items())}
    # Which values were filled (out/filled.parquet): Fill blanks and the receipts mark them.
    process: dict[str, Any] = {"time_adjustment": ta, "write_filled": True}
    if fill:
        process["fill"] = fill
    if c.collapse and c.collapse_fields:
        process["collapse_sparse_categories"] = {
            f: {"sales_min": c.collapse_sales_min, "univ_min": c.collapse_univ_min} for f in c.collapse_fields
        }
    scrutiny: dict[str, Any] = {
        # OAK box drops what scrutiny sets aside, except what the user kept: nothing reaches modeling unseen.
        "drop": {"clusters": True, "heuristics": True},
        "passes": 2,
        "clusters_enabled": c.checks.get("cluster", True),
        "heuristics": {h: c.checks.get(h, True) for h in HEURISTICS},
        # Each sale set aside diagnosed as the five-pattern table reads; one fitting none is flagged, left in.
        "patterns": "strict",
        "nominal_price": {"below": c.nominal_below},
        # Every flagged sale with its reason (out/sales_scrutiny/flags.parquet): Sales set aside reads it.
        "write_flags": True,
    }
    pattern = names.pattern(project)
    if pattern:
        scrutiny["same_surname"] = {"pattern": pattern}
    analysis: dict[str, Any] = {"sales_scrutiny": scrutiny, "report": {"formats": ["md"]}}
    scrutiny |= {"keep_file": KEEP_FILE, "invalid_key_file": EXCLUDE_FILE}
    loc = c.location or None
    scrutiny["location"] = loc
    for study in ("horizontal_equity", "land_equity", "impr_equity"):
        analysis[study] = {"location": loc}
    return {
        "modeling": {"metadata": {"use_sales_from": {"improved": start, "vacant": start}}},
        "data": {"process": process},
        "analysis": analysis,
    }


TIME_DIR = "in/oakbox/time_adjustment"


class TimeFileCheck(BaseModel):
    ok: bool
    problems: list[str] = Field(description="Every problem found, in words; empty when it can be used.")
    file: TimeFile | None = None


def time_file(project: Project, project_dir: Path, group: str, source: Path) -> TimeFileCheck:
    """Check a time adjustment file with OpenAVMKit's own reader; if it can be used, keep a copy for the group."""
    from openavmkit.time_adjustment import read_schedule

    if group not in {g.id for g in project.groups}:
        raise NotFound(group)
    if not source.is_file():
        return TimeFileCheck(ok=False, problems=[f"There's no file at {source}."])
    schedule, problems = read_schedule(str(source))
    if schedule is None:
        return TimeFileCheck(ok=False, problems=problems)
    data = source.read_bytes()
    rel = f"{TIME_DIR}/{group}.csv"
    target = project_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    import pandas as pd

    raw = pd.read_csv(source, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    periods = raw[next(c for c in raw.columns if c.strip().lower() == "period")].str.strip()
    f = TimeFile(
        path=rel,
        name=source.name,
        digest=hashlib.sha256(data).hexdigest()[:16],
        first=str(periods.iloc[0]),  # as the file writes them
        last=str(periods.iloc[-1]),
        periods=len(raw),
    )
    project.clean.time_files[group] = f
    project.clean.borrow.pop(group, None)
    return TimeFileCheck(ok=True, problems=[], file=f)


def merge(base: dict, more: dict) -> dict:
    """base with more's keys added, dicts merged all the way down."""
    out = dict(base)
    for k, v in more.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def write_marks(project: Project, project_dir: Path) -> None:
    """The user's keeps and exclusions, as OpenAVMKit reads them (a key_sale column), with their notes."""
    c: CleanState = project.clean
    if c.location is None:
        return  # the step wasn't used yet: nothing to write
    for path, action in ((KEEP_FILE, "keep"), (EXCLUDE_FILE, "exclude")):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["key_sale", "note"])
        for key, m in sorted(c.marks.items()):
            if m.action == action:
                w.writerow([key, m.note])
        atomic.save_text(project_dir / path, buf.getvalue())


# The ratio study's settings that only the models' figures read: a change there leaves Check sales as it was.
MODEL_ONLY = ("study_set_predictions", "outside_models")


def _analysis_key(settings: dict) -> dict:
    out = {k: v for k, v in settings.get("analysis", {}).items() if k != "report"}
    if isinstance(out.get("ratio_study"), dict):
        out["ratio_study"] = {k: v for k, v in out["ratio_study"].items() if k not in MODEL_ONLY}
        # Nothing of Check sales' own left: as if there were none. The models' settings add the section later (when
        # the prepared fields are there), and an empty one left Check sales out of date, so Prepare wouldn't run.
        if not out["ratio_study"]:
            del out["ratio_study"]
    return out


def settings_key(settings: dict, project: Project, project_dir: Path) -> dict:
    """What this run depends on: the Model groups run it starts from, and this step's calls and the user's keeps and
    exclusions."""
    process = settings.get("data", {}).get("process", {})
    return {
        "assemble": assemble.STEP.ran_at(project_dir),
        "process": {k: process.get(k) for k in bring_in.CLEAN_PROCESS if k not in FIELD_PROCESS},
        "use_sales_from": settings.get("modeling", {}).get("metadata", {}).get("use_sales_from"),
        "analysis": _analysis_key(settings),
        # Only the sales kept against scrutiny: an exclusion is a filter downstream (OpenAVMKit's own loader leaves
        # them out for the models), never a reason to run this again (2026-11-11).
        "marks": {k: m.action for k, m in sorted(project.clean.marks.items()) if m.action == "keep"},
    }


def excluded(project: Project) -> set[str]:
    """The sales excluded by hand now (Check sales' review, Outliers): left out wherever sales are read."""
    return {k for k, m in project.clean.marks.items() if m.action == "exclude"}


# The parts of data.process that prepare the fields for the models: the user's fills and rare categories.
# Their calls are made in step 5 (prepare.py), and Check sales' run leaves them out.
FIELD_PROCESS = ("fill", "collapse_sparse_categories")


def without_fields(settings: dict, project: Project) -> dict:
    """The settings Check sales runs with: OpenAVMKit's own fills, but not the user's, and no folding."""
    out = copy.deepcopy(settings)
    process = out.get("data", {}).get("process", {})
    mine = set(project.clean.fills)
    fill = process.get("fill", {})
    for key in list(fill):
        fill[key] = [f for f in fill[key] if (f.get("field") if isinstance(f, dict) else f) not in mine]
    process.pop("collapse_sparse_categories", None)
    return out


# ---------- Before running: the calls, with their defaults and what they do in numbers ----------


class YearCount(BaseModel):
    year: int
    improved: int
    vacant: int


class GroupSetup(BaseModel):
    id: str
    name: str
    color: str
    sales: int = Field(description="Valid sales in the window.")
    per_year: float | None = Field(description="Price change a year found last run, percent; None: none or not run.")
    borrow: str | None = Field(default=None, description="The group whose time adjustment it uses.")
    file: TimeFile | None = Field(default=None, description="Its own time adjustment file.")
    modeled: bool = Field(default=True, description="Modeled (Model groups › Check them): shown greyed when not.")
    per: IndexOn | None = Field(default=None, description="What its index is of, as chosen; None: automatic.")


class FillRow(BaseModel):
    field: str
    name: str
    blanks: int
    kind: FieldKind = Field(description="OpenAVMKit's classification: a building's field is 0 on vacant parcels.")
    fill: Fill
    auto: FillMethod = Field(description="What auto is: the fill proposed from what a blank means.")


class FillPart(BaseModel):
    blanks: int
    value: float | None = Field(description="What goes into them; None: they stay blank (left, or nothing to take).")
    left: bool = Field(default=False, description="Left blank, as chosen.")


class FillCell(BaseModel):
    """A field's fill in one model group: every parcel's (a building's field, or split: improved parcels')."""

    main: FillPart | None = Field(description="None: no blanks there.")
    vacant: FillPart | None = Field(default=None, description="Split: vacant parcels' (None: no blanks there).")


class FillPreviewRow(BaseModel):
    field: str
    name: str
    cells: list[FillCell] = Field(description="One per group, in groups' order.")


class FillPreview(BaseModel):
    groups: list[Choice] = Field(description="The model groups with parcels (value: id; label: name).")
    rows: list[FillPreviewRow]


class Choice(BaseModel):
    value: str
    label: str


class Notice(BaseModel):
    text: str
    link: str | None = Field(default=None, description="Where it's fixed: a tab and step, 'fields:sales'.")


class Fold(BaseModel):
    field: str
    name: str
    values: int = Field(description="Different values the field has.")
    folded: list[str] = Field(description="The values that would become Other, fewest parcels first.")
    parcels: int = Field(description="Parcels whose value would become Other.")


class CleanSetup(BaseModel):
    valuation_year: int
    default_from: int
    sales_from: int
    years: list[YearCount]
    total: int = Field(description="Valid sales from Data.")
    in_window: int
    time_adjust: bool
    period: Period
    groups: list[GroupSetup]
    fills: list[FillRow]
    fill_preview: FillPreview
    auto: list[str] = Field(description="What OpenAVMKit always fills itself, with how many.")
    location: str | None = Field(description='The location in use; "" none.')
    location_proposed: str
    locations: list[Choice]
    similar: list[str] = Field(description="The numbers sales are compared on, by name.")
    checks: dict[str, bool]
    deed: bool = Field(description="A deed ID is loaded (the same-deed check needs one).")
    names: bool = Field(default=False, description="Buyer and seller names are loaded (the same-surname check).")
    year_built: bool = Field(default=False, description="Year built is loaded (the vacant / built checks).")
    collapse: bool
    collapse_sales_min: int
    nominal_below: int = Field(default=1_000, description="A price under this is a nominal deed.")
    collapse_univ_min: int
    collapse_fields: list[str]
    folds: list[Fold] = Field(description="What would fold at the thresholds set, per field (when it's on).")


_setup_cache: dict[str, tuple[tuple, Any]] = {}


def _look(project_dir: Path, name: str) -> Path:
    return steps.look(project_dir, f"1-assemble-{name}")


def _data(project_dir: Path):
    """Step 2's hand-off as tables (the universe and the hydrated sales), cached while the files don't change."""
    import pandas as pd

    paths = [_look(project_dir, "universe"), _look(project_dir, "sales-hydrated")]
    stamp = tuple(p.stat().st_mtime_ns for p in paths)
    hit = _setup_cache.get(str(project_dir))
    if hit and hit[0] == stamp:
        return hit[1]
    universe = pd.read_parquet(paths[0])
    if "geometry" in universe:
        universe = universe.drop(columns="geometry")
    sales = pd.read_parquet(paths[1])
    if "geometry" in sales:
        sales = sales.drop(columns="geometry")
    _setup_cache[str(project_dir)] = (stamp, (universe, sales))
    return universe, sales


def _years(df) -> pd.Series:
    import pandas as pd

    return cast("pd.Series", pd.to_datetime(df["sale_date"], errors="coerce").dt.year)


def _valid(sales) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    valid = sales[cells.yes(sales, "valid_sale")] if "valid_sale" in sales else sales
    return valid, _years(valid), cells.yes(valid, "vacant_sale")


def _fill_rows(project: Project, project_dir: Path, universe) -> list[FillRow]:
    """Every number the models can use that's still blank somewhere after step 1, its kind and its fill."""
    from openavmkit.utilities.settings import get_fields_impr, get_fields_land, get_fields_numeric

    s = steps.engine_settings(project_dir)
    template = {f for fs in s.get("data", {}).get("process", {}).get("fill", {}).values() for f in fs}
    mine = set(project.clean.fills)
    numeric = [
        f
        for f in get_fields_numeric(s, universe, include_boolean=False) or []
        if f in universe and f not in YEAR_AGE and (f not in template or f in mine)
    ]
    building = set((get_fields_impr(s, universe) or {}).get("numeric", []))
    land = set((get_fields_land(s, universe) or {}).get("numeric", []))
    names = fields.names()
    c: CleanState = project.clean
    rows = []
    for f in numeric:
        blanks = int(cells.numbers(universe, f).isna().sum())
        if not blanks:
            continue
        auto = propose(f)
        kind: FieldKind = "building" if f in building else "land" if f in land else "other"
        fill = c.fills.get(f, Fill()).model_copy(update={"kind": kind})
        if not c.fills_auto:
            # Written down before auto: a proposal kept as it was is auto (a building's or land field's, split or not).
            if fill.method == auto and (kind != "other" or not fill.split):
                fill = fill.model_copy(update={"method": "auto", "split": False, "vacant": "auto"})
        rows.append(FillRow(field=f, name=names.get(f, f), blanks=blanks, kind=kind, fill=fill, auto=auto))
    return rows


def _put_in(x: pd.Series, blank: pd.Series, has: pd.Series, method: FillMethod) -> FillPart | None:
    """What a fill puts into these blanks from these values, as OpenAVMKit works it out (_fill_thing)."""
    n = int(blank.sum())
    if not n:
        return None
    if method == "leave":
        return FillPart(blanks=n, value=None, left=True)
    there = cast("pd.Series", x[has])
    if method == "zero":
        value: float | None = 0.0
    elif method == "mode":
        mode = there.mode()
        value = float(mode.iloc[0]) if len(mode) else 0.0  # nothing to count: 0
    elif not len(there):
        value = None  # nothing to take a median (mean, smallest, largest) from: they stay blank
    else:
        value = float(getattr(there, method)())
    return FillPart(blanks=n, value=value)


def fill_preview(project: Project, universe, rows: list[FillRow]) -> FillPreview:
    """What each model group gets: a group fills from its own parcels' values (improved or vacant ones' for those)."""
    import pandas as pd

    groups = model_groups_of(universe).replace({NO_PARCEL: UNKNOWN})
    present = set(groups)
    cols = [Choice(value=g.id, label=g.name) for g in project.groups if g.id in present]
    if UNKNOWN in present:
        cols.append(Choice(value=UNKNOWN, label="Unassigned"))
    vacant = (
        universe["is_vacant"].astype("boolean").fillna(False).astype(bool)
        if "is_vacant" in universe
        else pd.Series(False, index=universe.index)
    )
    out = []
    for row in rows:
        x = cells.numbers(universe, row.field)
        f = row.fill
        main_m = cast(FillMethod, row.auto if f.method == "auto" else f.method)
        vac_m = cast(FillMethod, row.auto if f.vacant == "auto" else f.vacant)
        split = f.split and f.kind == "other"
        cs = []
        for col in cols:
            g = groups == col.value
            if f.kind == "building" or split:
                main = _put_in(x, g & ~vacant & x.isna(), g & ~vacant & x.notna(), main_m)
                vac = _put_in(x, g & vacant & x.isna(), g & vacant & x.notna(), vac_m) if split else None
            else:
                main, vac = _put_in(x, g & x.isna(), g & x.notna(), main_m), None
            cs.append(FillCell(main=main, vacant=vac))
        out.append(FillPreviewRow(field=row.field, name=row.name, cells=cs))
    return FillPreview(groups=cols, rows=out)


def propose(field: str) -> FillMethod:
    """A field's auto fill, from what a blank means in it."""
    if field in NEVER_PROPOSED:
        return "leave"  # blank means no building: 0 already says so
    if field.startswith("land_area_alloc"):
        return "leave"  # only condo units have a share of land: blank for the rest is right
    if field in ("renovation_num", "is_renovated"):
        return "zero"  # blank means no renovation permit: 0 is none
    if field.startswith("days_to_"):
        return "leave"  # blank means no permit: there's no date to count from
    return "median"  # census, elevation, the rest: the group's median, as a stand-in


def _auto(project_dir: Path, universe) -> list[str]:
    from openavmkit.utilities.settings import get_fields_boolean, get_fields_categorical

    s = steps.engine_settings(project_dir)
    out = []
    zero = sum(int(universe[f].isna().sum()) for f in YEAR_AGE if f in universe)
    cats = [f for f in get_fields_categorical(s, universe, include_boolean=False) or [] if f in universe]
    cat_blanks = sum(int(universe[f].isna().sum()) for f in cats)
    bools = [f for f in get_fields_boolean(s, universe) or [] if f in universe]
    bool_blanks = sum(int(universe[f].isna().sum()) for f in bools)
    out.append(f"Year built and age: worked out from each other; still blank, 0 (no building): {zero:,} values.")
    out.append(f'Categories: blanks become "UNKNOWN": {cat_blanks:,} values in {len(cats)} fields.')
    out.append(f"Yes/no fields: blanks become no: {bool_blanks:,} values in {len(bools)} fields.")
    return out


def location_fields(project_dir: Path, universe) -> list[str]:
    from openavmkit.utilities.settings import get_locations

    s = steps.engine_settings(project_dir)
    found = [f for f in get_locations(s, universe) or [] if f in universe]
    for f in ("census_block_group", "census_tract"):
        if f in universe and f not in found:
            found.append(f)
    return found


def _proposed_location(locations: list[str]) -> str:
    """The user's first location field; else census block group; else none."""
    own = [f for f in locations if not f.startswith("census_")]
    if own:
        return own[0]
    return "census_block_group" if "census_block_group" in locations else ""


def _collapsible(project_dir: Path, universe, locations: list[str]) -> list[str]:
    """Categories the models use, not locations (folding neighbourhoods would change what they mean)."""
    from openavmkit.utilities.settings import get_fields_categorical

    s = steps.engine_settings(project_dir)
    cats = get_fields_categorical(s, universe, include_boolean=False) or []
    import pandas as pd

    n = max(len(universe), 1)
    return [
        f
        for f in cats
        if f in universe
        and f not in locations
        and f != "model_group"
        and not f.startswith(("key", "address"))
        and not f.endswith(("_date", "_year"))
        and not pd.api.types.is_datetime64_any_dtype(universe[f])  # a date, not a category
        and universe[f].nunique() < 0.5 * n  # an ID or an address, not a category
    ]


def folds(project: Project, project_dir: Path) -> list[Fold]:
    """What rare categories would fold, per field, at the thresholds set: a value with fewer valid sales than
    collapse_sales_min, or fewer parcels than collapse_univ_min, becomes Other (as OpenAVMKit counts them)."""
    import pandas as pd

    universe, sales = _data(project_dir)
    valid, year, vacant = _valid(sales)
    used = out_dir(project_dir) / "used.parquet"
    if used.is_file():
        # The sales for modeling, as Check sales left them: what OpenAVMKit counts when it folds.
        keys = set(pd.read_parquet(used)["key_sale"].astype(str))
        valid = cast("pd.DataFrame", valid[valid["key_sale"].astype(str).isin(list(keys))])
    else:
        valid = valid[year >= window(project)]
    c: CleanState = project.clean
    names = fields.names()
    out = []
    collapsible = _collapsible(project_dir, universe, location_fields(project_dir, universe))
    for f in [f for f in c.collapse_fields if f in collapsible] or collapsible:
        if f not in universe:
            continue
        parcels = {str(k): int(n) for k, n in universe[f].astype(str).value_counts().items()}
        counted = cast("pd.Series", valid[f]).astype(str).value_counts() if f in valid else None
        sold = {str(k): int(n) for k, n in counted.items()} if counted is not None else {}
        rare = [v for v, n in parcels.items() if sold.get(v, 0) < c.collapse_sales_min or n < c.collapse_univ_min]
        rare.sort(key=lambda v: (parcels[v], v))
        out.append(
            Fold(
                field=f,
                name=names.get(f, f),
                values=len(parcels),
                folded=rare,
                parcels=sum(parcels[v] for v in rare),
            )
        )
    return out


def _last_run(project_dir: Path) -> dict[str, float | None]:
    r, _ = STEP.ran(project_dir)
    return {g.id: g.per_year for g in r.groups} if r else {}


def setup(project: Project, project_dir: Path) -> CleanSetup:
    universe, sales = _data(project_dir)
    valid, year, vacant = _valid(sales)
    start = window(project)
    years = sorted(set(int(y) for y in year.dropna()))
    counts = [
        YearCount(
            year=y,
            improved=int(((year == y) & ~vacant).sum()),
            vacant=int(((year == y) & vacant).sum()),
        )
        for y in years
    ]
    inside = year >= start
    last = _last_run(project_dir)
    groups = []
    modeled = assemble.modeled(project, project_dir)
    for g in [*project.groups]:
        n = int((inside & (valid["model_group"] == g.id)).sum()) if "model_group" in valid else 0
        groups.append(
            GroupSetup(
                id=g.id,
                name=g.name,
                color=g.color,
                sales=n,
                per_year=last.get(g.id),
                borrow=project.clean.borrow.get(g.id),
                file=project.clean.time_files.get(g.id),
                modeled=g.id in modeled,
                per=project.clean.per.get(g.id),
            )
        )
    unknown = int((inside & (valid["model_group"] == UNKNOWN)).sum()) if "model_group" in valid else 0
    if unknown:
        groups.append(GroupSetup(id=UNKNOWN, name="Unassigned", color="#9a9a9a", sales=unknown, per_year=None))
    locations = location_fields(project_dir, universe)
    proposed = _proposed_location(locations)
    location = project.clean.location if project.clean.location is not None else proposed
    names = fields.names()
    unit = "sqft" if project.units == "imperial" else "sqm"
    similar = [
        names.get(f, f)
        for f in (f"land_area_{unit}", f"bldg_area_finished_{unit}", "bldg_quality_num", "bldg_age_years")
        if f in universe
    ]
    if "bldg_condition_num" in universe:
        similar.append(names.get("bldg_condition_num", "condition"))
    c: CleanState = project.clean
    collapsible = _collapsible(project_dir, universe, locations)
    collapse_fields = [f for f in c.collapse_fields if f in collapsible] or collapsible
    return CleanSetup(
        valuation_year=valuation_year(project),
        default_from=valuation_year(project) - YEARS_BEFORE,
        sales_from=start,
        years=counts,
        total=len(valid),
        in_window=int(inside.sum()),
        time_adjust=c.time_adjust,
        period=c.period,
        groups=groups,
        fills=(rows := _fill_rows(project, project_dir, universe)),
        fill_preview=fill_preview(project, universe, rows),
        auto=_auto(project_dir, universe),
        location=location,
        location_proposed=proposed,
        locations=[Choice(value=f, label=names.get(f, f)) for f in locations],
        similar=similar,
        checks={k: c.checks.get(k, True) for k in CHECKS},
        deed=bool(steps.read_settings(project_dir).get("analysis", {}).get("sales_scrutiny", {}).get("deed_id")),
        names=any(c in sales for c in ("deed_grantor", "deed_grantor_surname"))
        and any(c in sales for c in ("deed_grantee", "deed_grantee_surname")),
        year_built="bldg_year_built" in sales or "bldg_year_built" in universe,
        collapse=c.collapse,
        collapse_sales_min=c.collapse_sales_min,
        nominal_below=c.nominal_below,
        collapse_univ_min=c.collapse_univ_min,
        collapse_fields=collapse_fields,
        folds=folds(project, project_dir) if c.collapse else [],
    )


def decide(project: Project, project_dir: Path) -> None:
    """Write down what was proposed (fills, the location, the categories to fold), so the settings say it all."""
    universe, _ = _data(project_dir)
    c: CleanState = project.clean
    for row in _fill_rows(project, project_dir, universe):
        c.fills[row.field] = row.fill  # auto unless chosen; its kind kept up to date
    c.fills_auto = True
    locations = location_fields(project_dir, universe)
    if c.location is None:
        c.location = _proposed_location(locations)
    collapsible = _collapsible(project_dir, universe, locations)
    # Kept to what can fold now (dates and IDs never do).
    c.collapse_fields = [f for f in c.collapse_fields if f in collapsible] or collapsible
    if c.name_format is None:
        c.name_format = names.view(project, project_dir / "in").guess


# ---------- The run ----------


class FunnelLine(BaseModel):
    sign: Literal["", "-", "+", "="]
    count: int
    text: str
    check: str | None = Field(default=None, description="The check whose sales See them shows.")


class GroupResult(BaseModel):
    id: str
    name: str
    color: str
    in_window: int
    set_aside: int
    used: int
    clusters: int
    per_year: float | None = Field(description="Price change a year, percent; None: no time adjustment.")
    first: str | None
    last: str | None
    curve: list[float] = Field(description="The price index over time (first = 1), about 40 points.")


class PatternTable(BaseModel):
    """The sales scrutiny flagged far from their group, by pattern: the five-pattern table, for one model group or
    all ("")."""

    group: str
    name: str
    sales: int = Field(description="Sales checked: in the window and valid.")
    counts: dict[str, int] = Field(description="Pattern (1 to 5, other) -> sales.")


class Filled(BaseModel):
    field: str
    name: str
    count: int
    how: str


class CleanReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    start: int
    used: int
    set_aside: int = Field(description="Sales scrutiny set aside, kept or not: to look at.")
    flagged_in: int = Field(default=0, description="Flagged but left in: no pattern fits them; the user decides.")
    patterns: list[PatternTable] = Field(default_factory=list, description="All groups first, then each.")
    funnel: list[FunnelLine]
    groups: list[GroupResult]
    filled: list[Filled]
    written: list[assemble.Written]
    notes: list[str] = Field(default_factory=list)


CHECK_WORDS = {
    "excluded": "excluded by you",
    "nominal_price": "a nominal price (a $10 deed), not a price",
    "dupe_deed_date": "same deed, same day (a sale of several parcels)",
    "dupe_date_price": "same day, same price",
    "bulk_deed": "a deed for several parcels, its other sales not valid",
    "false_vacant": "sold as vacant, but the building is older than the sale",
    "built_after_sale": "sold as improved, but the building was built after the sale",
    "vacant_priced_improved": "sold as vacant, but priced like the improved sales near it",
    "same_surname": "buyer and seller share a surname",
    "cluster": "far from their group's price per area",
}
PATTERNS = ("1", "2", "3", "4", "5", "other")
ORDER = ["excluded", *HEURISTICS, "cluster"]


def time_curve(path: Path) -> tuple[float | None, str | None, str | None, list[float]]:
    import pandas as pd

    if not path.is_file():
        return None, None, None, []
    s = pd.read_csv(path)
    if len(s) < 2:
        return None, None, None, []
    first, last = pd.to_datetime(s["period"].iloc[0]), pd.to_datetime(s["period"].iloc[-1])
    years = max((last - first).days / 365.25, 0.1)
    index = cells.numbers(s, "start_indexed").dropna()
    if len(index) < 2:
        return None, None, None, []  # too few sales: no adjustment
    a, b = float(index.iloc[0]), float(index.iloc[-1])
    per_year = round(((b / a) ** (1 / years) - 1) * 100, 1) if a > 0 and b > 0 else None
    step = max(1, len(s) // 40)
    curve = [round(float(v), 4) for v in index.iloc[::step].tolist()]
    if per_year is not None and abs(per_year) < 0.05 and len(set(curve)) <= 1:
        per_year = None  # flat: no adjustment (too few sales)
    return per_year, str(first.date()), str(last.date()), curve


def run(project_id: str) -> None:
    """Notebook 2's clean stage, with a count at each part; then the receipt and the review's tables."""
    import warnings
    from importlib.metadata import version

    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    src = steps.handoff(pdir, "1-assemble")
    if not src.is_file():
        raise RuntimeError("Write step 2 first (Model groups): this starts from its hand-off.")
    tmp = steps.workdir(out_dir(pdir))
    steps.note_excluded(tmp, excluded(project))
    depends = STEP.now(project, pdir)  # what it starts from, before anything can change
    settings_text = steps.settings_path(pdir).read_text(encoding="utf-8")
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit import progress
    from openavmkit.data import SalesUniversePair, get_hydrated_sales_from_sup

    names = {g.id: g.name for g in project.groups} | {UNKNOWN: "Unassigned"}
    said: dict[str, str] = {}

    def step(name: str, fraction: float, message: str) -> None:
        said["base"] = message
        steps.emit(step=name, fraction=fraction, message=message)
        progress.report(name, fraction, message)

    def inside(e) -> None:
        # Which model group a part is on: "single_family (6 of 6)", said with the group's name.
        if e.message == said.get("base"):
            return
        detail = e.message.removeprefix(said.get("base", "") + ": ")
        for gid, name in names.items():
            if detail.startswith(gid + " ("):
                detail = name + detail[len(gid) :]
        steps.emit(detail=detail, sub=e.sub)

    t0 = time.time()
    pl.delete_checkpoints("2-clean")
    with warnings.catch_warnings(record=True) as caught, progress.reporting(inside, stage="clean"), steps.heartbeat():
        warnings.simplefilter("always")
        step("load", 0.0, "Reading step 2's hand-off")
        sup = cast(SalesUniversePair, pd.read_pickle(src))
        settings = without_fields(pl.load_settings(), project)
        start_sales = _valid_keys(get_hydrated_sales_from_sup(sup))
        before = get_hydrated_sales_from_sup(sup)
        step("fill", 0.05, "Filling blanks OpenAVMKit always fills")
        sup = pl.fill_unknown_values_sup(sup, settings)
        step("clusters", 0.1, "Grouping similar parcels (equity clusters)")
        sup = pl.mark_horizontal_equity_clusters_per_model_group_sup(
            sup=sup, settings=settings, do_land_clusters=True, do_impr_clusters=True
        )
        step("sales", 0.45, "The sales window, validity and time adjustment")
        sup = pl.process_sales(sup=sup, settings=settings)
        processed = _valid_keys(sup.sales)
        hydrated = get_hydrated_sales_from_sup(sup)
        step("scrutiny", 0.6, "Checking sales against similar sales nearby")
        sup = pl.run_sales_scrutiny(sup=sup, settings=settings)
        step("write", 0.93, "Writing notebook 2's output")
        pl.write_notebook_output_sup(sup, "2-clean")
    steps.written(caught, "notebook 2's output")
    steps.emit(step="receipt", fraction=0.97, message="Counting")

    used = _valid_keys(sup.sales)
    flags = _flags(pdir)
    receipt = _receipt(project, pdir, before, start_sales, processed, used, flags, hydrated, sup.sales, t0, caught)
    receipt.engine = version("openavmkit")
    _review_tables(tmp, hydrated, sup.sales, flags, project.units)
    _related_table(tmp, before, settings)
    # Step 5 prepares the fields from this (the user's fills, rare categories) and writes 2-clean again, so what
    # starts from Check sales as it ran (Check my values) reads its own copies here, never out/2-clean-*.
    pd.to_pickle(sup, tmp / "sup.pickle")
    _keep_look(pdir, tmp)
    pd.DataFrame({"key_sale": sorted(used)}).to_parquet(tmp / "used.parquet", index=False)
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(
        json.dumps({"settings": json.loads(settings_text), "hash": depends}),
        encoding="utf-8",
    )
    steps.publish(tmp, out_dir(pdir))
    steps.emit(
        step="done", fraction=1.0, message=f"{receipt.used:,} sales for modeling, {receipt.set_aside:,} set aside"
    )


SALES_KEPT = "sales_hydrated.parquet"  # the sales it kept, each with its parcel's fields (out/look/'s, as it wrote it)
UNIVERSE_KEPT = "universe.parquet"  # the parcel universe as it left it, without the shapes


def _keep_look(pdir: Path, tmp: Path) -> None:
    """Copies of the tables notebook 2 just wrote (out/look/2-clean-*), before Prepare the fields writes them again:
    the hydrated sales as they are, the universe without its shapes (only its fields are read)."""
    import pyarrow.parquet as pq

    look = steps.look_dir(pdir)
    if (look / "2-clean-sales-hydrated.parquet").is_file():
        shutil.copyfile(look / "2-clean-sales-hydrated.parquet", tmp / SALES_KEPT)
    if (look / "2-clean-universe.parquet").is_file():
        names = pq.read_schema(look / "2-clean-universe.parquet").names
        table = pq.read_table(look / "2-clean-universe.parquet", columns=[c for c in names if c != "geometry"])
        meta = {k: v for k, v in (table.schema.metadata or {}).items() if k != b"geo"}  # no shapes: not GeoParquet
        pq.write_table(table.replace_schema_metadata(meta), tmp / UNIVERSE_KEPT)


def _valid_keys(sales) -> set[str]:
    v = sales[sales["valid_sale"].fillna(False).astype(bool)] if "valid_sale" in sales else sales
    return set(v["key_sale"].astype(str))


def _flags(project_dir: Path):
    import pandas as pd

    path = project_dir / "out" / "sales_scrutiny" / "flags.parquet"
    if not path.is_file():
        return empty_frame("key_sale", "key", "check", "kept", "dropped")
    f = pd.read_parquet(path)
    f["key_sale"] = f["key_sale"].astype(str)
    return f


def _receipt(
    project: Project, pdir, before, start, processed, used, flags, hydrated, sales, t0, caught
) -> CleanReceipt:
    import pandas as pd

    start_year = window(project)
    b = before.copy()
    b["key_sale"] = b["key_sale"].astype(str)
    b = b[b["key_sale"].isin(list(start))].drop_duplicates("key_sale").set_index("key_sale")
    year = _years(b)
    gone = start - processed
    early = {k for k in gone if k in b.index and year[k] < start_year}
    price = cells.numbers(b, "sale_price")
    no_price = {k for k in gone - early if k in b.index and not (price[k] > 0)}
    keys = set(sales["key"].astype(str)) if "key" in sales else set()
    in_univ = b["key"].astype(str).isin(list(keys)) if "key" in b else pd.Series(True, index=b.index)
    no_parcel = {k for k in gone - early - no_price if k in b.index and not bool(in_univ[k])}
    other = gone - early - no_price - no_parcel
    funnel = [FunnelLine(sign="", count=len(start), text="valid sales from Data")]
    funnel.append(FunnelLine(sign="-", count=len(early), text=f"before {start_year} (the sales window)"))
    for n, text in (
        (no_price, "with no price"),
        (no_parcel, "for parcels not in the parcel universe"),
        (other, "invalid by your rules or OpenAVMKit's own"),
    ):
        if n:
            funnel.append(FunnelLine(sign="-", count=len(n), text=text))
    # Scrutiny: each sale set aside counted once, at the first check; the ones kept come back after.
    empty = len(flags) == 0
    dropped = set() if empty else set(flags.loc[flags["dropped"].astype(bool), "key_sale"])
    kept = set() if empty else set(flags.loc[flags["kept"].astype(bool), "key_sale"])
    excluded = set() if empty else set(flags.loc[flags["check"] == "excluded", "key_sale"]) & dropped
    only = _flag_only(flags)
    counted: set[str] = set()
    for check in ORDER[1:]:
        rows = flags[(flags["check"] == check) & ~only] if not empty else flags
        ks = set() if empty else set(rows["key_sale"]) & (dropped | kept)
        ks -= counted | excluded
        counted |= ks
        funnel.append(FunnelLine(sign="-", count=len(ks), text=CHECK_WORDS[check], check=check))
    funnel.append(FunnelLine(sign="+", count=len(kept & counted), text="kept by you"))
    funnel.append(FunnelLine(sign="-", count=len(excluded), text="excluded by you"))
    unexplained = processed - used - dropped
    if unexplained:
        funnel.append(FunnelLine(sign="-", count=len(unexplained), text="other"))
    funnel.append(FunnelLine(sign="=", count=len(used), text="sales for modeling"))

    # Per model group.
    h = hydrated.copy()
    h["key_sale"] = h["key_sale"].astype(str)
    h = h[h["key_sale"].isin(processed)]
    final = sales[sales["key_sale"].astype(str).isin(used)]
    group_of = dict(zip(h["key_sale"], model_groups_of(h), strict=False))
    groups = []
    ids = [(g.id, g.name, g.color) for g in project.groups]
    ids += [(UNKNOWN, "Unassigned", "#9a9a9a"), (NO_PARCEL, NO_PARCEL_NAME, "#cfcfcf")]
    for gid, name, color in ids:
        n = int((model_groups_of(h) == gid).sum())
        if gid in (UNKNOWN, NO_PARCEL) and n == 0:
            continue
        aside = sum(1 for k in dropped if group_of.get(k) == gid)
        used_n = sum(1 for k in final["key_sale"].astype(str) if group_of.get(k) == gid)
        clusters = (
            int(flags.loc[(flags["check"] == "cluster") & (flags["model_group"] == gid), "ss_id"].nunique())
            if len(flags) and "model_group" in flags
            else 0
        )
        if "ss_id" in final and "model_group" in h:
            mine = final[final["key_sale"].astype(str).map(group_of) == gid]
            clusters = max(clusters, int(mine["ss_id"].dropna().nunique()))
        per_year, first, last, curve = time_curve(
            pdir / "out" / "time_adjustment" / gid / "time_adjustment_schedule.csv"
        )
        if not project.clean.time_adjust or gid == NO_PARCEL:
            per_year, curve = None, []
        groups.append(
            GroupResult(
                id=gid,
                name=name,
                color=color,
                in_window=n,
                set_aside=aside,
                used=used_n,
                clusters=clusters,
                per_year=per_year,
                first=first,
                last=last,
                curve=curve,
            )
        )
    filled = []
    fp = pdir / "out" / "filled.parquet"
    if fp.is_file():
        f = pd.read_parquet(fp)
        names = fields.names()
        for col in f.columns:
            if col == "key":
                continue
            n = int(f[col].sum())
            how = project.clean.fills.get(col)
            words = fill_words(col, how) if how else "0" if col in YEAR_AGE else "OpenAVMKit's own"
            filled.append(Filled(field=col, name=names.get(col, col), count=n, how=words))
    written = []
    for path in [steps.handoff(pdir, "2-clean"), *sorted(steps.look_dir(pdir).glob("2-clean-*"))]:
        if path.is_file():
            written.append(
                assemble.Written(
                    path=path.relative_to(pdir).as_posix(),
                    what=steps.what_written(path.name),
                    bytes=path.stat().st_size,
                )
            )
    mine = steps.engine_notes(caught)
    aside = len(counted)
    flagged_in = set() if empty else set(flags.loc[only, "key_sale"]) & used
    return CleanReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine="",
        start=len(start),
        used=len(used),
        set_aside=aside,
        flagged_in=len(flagged_in),
        patterns=_pattern_tables(project, flags, h, excluded),
        funnel=funnel,
        groups=groups,
        filled=filled,
        written=written,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )


def _flag_only(flags) -> pd.Series:
    import pandas as pd

    if "flag_only" not in flags:
        return pd.Series(False, index=flags.index)
    return flags["flag_only"].astype("boolean").fillna(False).astype(bool)


def _pattern_tables(project: Project, flags, h, excluded: set[str]) -> list[PatternTable]:
    """Each pattern's sales among those checked, all groups and per group (the article's Results table)."""
    names = {g.id: g.name for g in project.groups} | {UNKNOWN: "Unassigned"}
    groups = model_groups_of(h)
    cluster = flags[flags["check"] == "cluster"] if len(flags) else flags
    cluster = cluster[~cluster["key_sale"].isin(list(excluded))] if len(cluster) else cluster
    out = []
    for gid in ["", *[g.id for g in project.groups], UNKNOWN]:
        sales = int(len(h)) if gid == "" else int((groups == gid).sum())
        mine = cluster if gid == "" or not len(cluster) else cluster[cluster["model_group"].astype(str) == gid]
        if gid and sales == 0:
            continue
        counts = {p: 0 for p in PATTERNS}
        if len(mine):
            for pattern, n in mine.drop_duplicates("key_sale")["pattern"].astype(str).value_counts().items():
                for one in str(pattern).split(","):
                    if one in counts:
                        counts[one] += int(n)
        out.append(PatternTable(group=gid, name=names.get(gid, "All model groups"), sales=sales, counts=counts))
    return out


# ---------- The review's tables: the sales set aside, and each one's group (salereview.py reads them) ----------

SALE_COLUMNS = ["key_sale", "key", "address", "sale_date", "sale_price", "sale_price_time_adj", "model_group"]


def _review_tables(out: Path, hydrated, sales, flags, units: str) -> None:
    """review.parquet: one row per sale set aside (a check flagged it), with its own data; members.parquet: every
    sale in the clusters those were compared in, with its price per area."""
    import pandas as pd

    unit = "sqft" if units == "imperial" else "sqm"
    h = hydrated.copy()
    h["key_sale"] = h["key_sale"].astype(str)
    cols = [
        c
        for c in [
            *SALE_COLUMNS,
            f"bldg_area_finished_{unit}",
            f"land_area_{unit}",
            "bldg_year_built",
            "vacant_sale",
            "latitude",
            "longitude",
            "deed_grantor",
            "deed_grantee",
        ]
        if c in h
    ]
    h = h[cols].drop_duplicates("key_sale")
    if len(flags) == 0:
        empty_frame("key_sale", "check").to_parquet(out / "review.parquet", index=False)
        empty_frame("key_sale", "ss_id").to_parquet(out / "members.parquet", index=False)
        return
    f = flags.drop(columns=[c for c in ("key", "model_group") if c in flags and c in h.columns])
    review = f.merge(h, on="key_sale", how="left")
    review.to_parquet(out / "review.parquet", index=False)
    # Each flagged cluster's sales: the ones still in (their ss_id) and the flagged ones (theirs).
    clusters = set(flags.loc[flags["check"] == "cluster", "ss_id"].dropna().astype(str))
    s = sales[["key_sale", "ss_id"]].copy() if "ss_id" in sales else empty_frame("key_sale", "ss_id")
    s["key_sale"] = s["key_sale"].astype(str)
    s = s[s["ss_id"].astype(str).isin(list(clusters))]
    fl = flags.loc[flags["check"] == "cluster", ["key_sale", "ss_id"]].astype(str)
    members = cast("pd.DataFrame", pd.concat([s.astype({"ss_id": str}), fl], ignore_index=True))
    members = members[~members["key_sale"].duplicated()]
    members = members.merge(h, on="key_sale", how="left")
    price = cells.numbers(members, "sale_price_time_adj").fillna(cells.numbers(members, "sale_price"))
    vacant = cells.numbers(members, "vacant_sale").fillna(0).astype(bool)
    area = cells.numbers(members, f"bldg_area_finished_{unit}").where(
        ~vacant, cells.numbers(members, f"land_area_{unit}")
    )
    members["price"] = price
    members["price_per_area"] = price / area.where(area > 0)
    members["flagged"] = members["key_sale"].isin(list(fl["key_sale"]))
    members.to_parquet(out / "members.parquet", index=False)


RELATED_COLUMNS = ["key_sale", "address", "sale_date", "sale_price", "latitude", "longitude", "deed_grantor"]
RELATED_COLUMNS += ["deed_grantee", "model_group", "bldg_area_finished_sqft", "bldg_area_finished_sqm"]
RELATED_COLUMNS += ["land_area_sqft", "land_area_sqm"]


def _related_table(out: Path, before, settings: dict) -> None:
    """related.parquet: every sale as it came in (out of the window too), for the sales related to one set aside:
    the same deed, the same day nearby, the same buyer."""
    deed = settings.get("analysis", {}).get("sales_scrutiny", {}).get("deed_id")
    cols = [c for c in RELATED_COLUMNS if c in before]
    r = before[cols].copy()
    r["key_sale"] = r["key_sale"].astype(str)
    if deed and deed in before:
        r["deed"] = before[deed].astype("string")
    r.drop_duplicates("key_sale").to_parquet(out / "related.parquet", index=False)


# ---------- The step's state ----------


class CleanView(steps.RunView):
    receipt: CleanReceipt | None
    accepted: bool


STEP = steps.Step(
    MODULE,
    "Check sales",
    CleanReceipt,
    key=lambda project, pdir: settings_key(steps.read_settings(pdir), project, pdir),
    after=assemble.STEP,
    again="Check sales again first: something changed since it ran.",
    place="Sales",
)


def blocked(project: Project, project_dir: Path) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    if not _look(project_dir, "sales-hydrated").is_file():
        return ["Write step 2 first (Model groups): this starts from its hand-off."]
    return []


def view(project: Project, project_dir: Path) -> CleanView:
    s = STEP.state(project, project_dir)
    return CleanView(
        status=s.status,
        job=s.job,
        receipt=s.receipt,
        stale=s.stale,
        blocked=blocked(project, project_dir),
        accepted=s.accepted,
        excluded_since=steps.excluded_since(out_dir(project_dir), excluded(project)) if s.receipt else 0,
    )


def start(project: Project, project_dir: Path) -> None:
    STEP.start(project.id, project_dir, blocked(project, project_dir))


if __name__ == "__main__":
    steps.main(run)

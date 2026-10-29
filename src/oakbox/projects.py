"""Projects: one jurisdiction x one tax year, stored as an ordinary folder.

Layout (SPEC §3.0 F1, §6)::

    <storage location>/<project name>/
        oakbox.json        OAK box's own state: the project's facts and input files
        in/                the user's data files + settings.json for OpenAVMKit
        out/               OpenAVMKit outputs
        cache/             enrichment cache

The folder is an OpenAVMKit locality, so the engine runs on it directly. Projects
can live anywhere (the storage location can change), so they are found by id
through OAK box's list of known projects (``appsettings``), plus a scan of the
storage location and the folder the first builds used.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import uuid
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field, model_validator

from oakbox import appsettings
from oakbox.datafiles import DataFile, Rule, clean_calc, data_load, overlay_distance, rule_fields, rule_filter
from oakbox.enrichments import Enrichments
from oakbox.enrichments import settings as enrich_settings


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


Units = Literal["imperial", "metric"]
# How numbers are written: the thousands separator and the decimal mark (SPEC F1).
NumberStyle = Literal["1,234.56", "1.234,56", "1 234,56", "1'234.56", "1 234.56"]


@cache
def locales() -> dict:
    """Per country, its currency, number style and units (from Unicode CLDR: packaging/make_locales.py)."""
    return json.loads(resources.files("oakbox").joinpath("locales.json").read_text(encoding="utf-8"))


def country_defaults(country: str) -> dict:
    """What a project in this country starts with; the user can change each (SPEC F1)."""
    return locales()["countries"].get(country, {"currency": "USD", "numbers": "1,234.56", "units": "metric"})


class NewProject(BaseModel):
    """What the user enters to create a project (SPEC §3.0 F1)."""

    name: str = Field(description="Project name; also the folder name. Free text.")
    country: str = Field(description="ISO 3166-1 alpha-2 code, e.g. 'US'.")
    region: str = Field(description="For the US, an ISO 3166-2 state code without 'US-' (e.g. 'TX'); else free text.")
    jurisdiction: str = Field(description="What the office calls itself; OpenAVMKit's locality.name.")
    tax_year: int
    valuation_date: dt.date
    units: Units | None = Field(default=None, description="None: the country's (country_defaults).")
    currency: str | None = Field(default=None, description="ISO 4217 code. None: the country's.")
    numbers: NumberStyle | None = Field(default=None, description="How numbers are written. None: the country's.")


class Locale(BaseModel):
    """The project's units, currency and number style: set from the country, changeable (SPEC F1)."""

    units: Units | None = None
    currency: str | None = None
    numbers: NumberStyle | None = None


class CustomField(BaseModel):
    """A field the user names and classifies (F3d Land use & building type): loaded from a parcel file's column
    under its name; the column is in the file's load."""

    name: str
    group: Literal["land", "building", "other"] = Field(description="OpenAVMKit's land, impr or other fields.")
    type: Literal["category", "number"]


class WizardState(BaseModel):
    """The Fields wizard's own state (SPEC §3.0 F3d). Everything it chooses is in the files' entries."""

    base: str | None = Field(default=None, description="The parcel file the others join to.")
    visited: list[str] = Field(default_factory=list, description="Steps shown at least once.")
    skipped: list[str] = Field(default_factory=list, description='Steps answered with "I don\'t have these".')
    confirmed: list[str] = Field(default_factory=list, description="Steps moved on from with Next (or Start).")
    decided: list[str] = Field(
        default_factory=list, description="Fields chosen or guessed once, so a guess never replaces them."
    )
    locations: list[str] = Field(
        default_factory=list, description="Fields the user named as locations (areas parcels belong to), in order."
    )
    absent: list[str] = Field(
        default_factory=list, description="Fields said not to exist (no condition: effective age carries it)."
    )
    custom: list[CustomField] = Field(default_factory=list, description="Fields the user named and classified.")
    condos: bool | None = Field(
        default=None,
        description="Condo units: whether some parcels are units without a shape of their own; None: not asked yet.",
    )


class ModelGroup(BaseModel):
    """Parcels valued together (SPEC §3.5): OpenAVMKit's modeling.model_groups entry. First match wins."""

    id: str = Field(description="The model_group value OpenAVMKit gives its parcels; kept when renamed.")
    name: str
    color: str = Field(description="On the map and in the list.")
    rule: Rule = Field(
        default_factory=lambda: Rule(join="any"),
        description="Conditions on parcel universe fields (a condition's column is the field).",
    )
    numeric: list[str] = Field(default_factory=list, description="Fields the rule tests that are numbers.")


def group_filter(g: ModelGroup) -> list:
    """The group's rule as an OpenAVMKit filter ([] while it has no complete condition)."""
    conditions = [c for c in g.rule.conditions if c.values or c.op in ("isempty", "notempty")]
    if not conditions:
        return []
    rule = g.rule.model_copy(update={"conditions": conditions})
    names = {c.column: (c.column, "float" if c.column in g.numeric else "string") for c in conditions}
    return rule_filter(rule, names)


class Center(BaseModel):
    """The point polar coordinates are measured from (OpenAVMKit's locality.center), in degrees."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Project(BaseModel):
    id: str
    name: str
    created_at: dt.datetime
    country: str = "US"
    region: str = ""
    jurisdiction: str = ""
    tax_year: int
    valuation_date: dt.date | None = None
    units: Units = "imperial"
    currency: str = Field(default="USD", description="ISO 4217 code: what prices and values are in.")
    numbers: NumberStyle = Field(default="1,234.56", description="How the files write numbers.")
    center: Center | None = Field(default=None, description="None: the middle of the parcels (OpenAVMKit's default).")
    sample: str | None = None
    files: list[DataFile] = Field(default_factory=list, description="data.load entries (SPEC §3.0 F2).")
    wizard: WizardState = Field(default_factory=WizardState)
    groups: list[ModelGroup] = Field(default_factory=list, description="Model groups, in order (SPEC §3.5).")
    assemble_exports: list[Literal["gpkg", "shp", "csv"]] = Field(
        default_factory=list, description="Formats notebook 1's output is also written in, beside Parquet."
    )
    groups_start: Literal["scratch", "suggested"] | None = Field(
        default=None, description="How model groups were started; None: not yet."
    )
    enrich: Enrichments | None = Field(default=None, description="Enrichments (F3e); None: the step not shown yet.")

    @model_validator(mode="before")
    @classmethod
    def _country_defaults(cls, data: object) -> object:
        """Projects from before currency and number style were asked: the country's."""
        if isinstance(data, dict):
            d = country_defaults(str(data.get("country") or "US"))
            for key in ("currency", "numbers"):
                if data.get(key) is None:
                    data = {**data, key: d[key]}
        return data

    accepted: dict[str, str] = Field(
        default_factory=dict, description="Step -> the settings it was run with when Looks right was pressed."
    )


# ---------- Finding projects ----------


def _register(project_id: str, folder: Path) -> None:
    s = appsettings.load()
    if s.projects.get(project_id) != str(folder):
        s.projects[project_id] = str(folder)
        appsettings.save(s)


def _read(folder: Path) -> Project | None:
    """The project in a folder; None for damaged files and for sample projects of earlier builds (SPEC D19)."""
    try:
        project = Project.model_validate_json((folder / "oakbox.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return None if project.sample is not None else project


def _discover() -> dict[str, Path]:
    """Known projects whose folders still exist, plus any found in the storage folders."""
    s = appsettings.load()
    found = {pid: Path(folder) for pid, folder in s.projects.items() if (Path(folder) / "oakbox.json").exists()}
    for root in {appsettings.storage_location(), appsettings.legacy_storage()}:
        if not root.is_dir():
            continue
        for meta in root.glob("*/oakbox.json"):
            project = _read(meta.parent)
            if project is not None and project.id not in found:
                found[project.id] = meta.parent
    if found != {pid: Path(f) for pid, f in s.projects.items()}:
        s.projects = {pid: str(f) for pid, f in found.items()}
        appsettings.save(s)
    return found


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    folder = appsettings.load().projects.get(project_id)
    if folder is None or not (Path(folder) / "oakbox.json").exists():
        folder = _discover().get(project_id)
    if folder is None:
        raise FileNotFoundError(f"Project not found: {project_id}")
    return Path(folder)


def list_projects() -> list[Project]:
    projects = [p for folder in _discover().values() if (p := _read(folder)) is not None]
    return sorted(projects, key=lambda p: p.created_at, reverse=True)


def load(project_id: str) -> Project:
    return Project.model_validate_json((project_dir(project_id) / "oakbox.json").read_text(encoding="utf-8"))


def save(project: Project, folder: Path | None = None) -> None:
    from oakbox import atomic

    folder = folder or project_dir(project.id)
    atomic.save_text(folder / "oakbox.json", project.model_dump_json(indent=2))


# ---------- Creating ----------

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def folder_name(name: str) -> str:
    """A folder name that works on Windows and Linux: unsafe characters become spaces."""
    clean = " ".join(_UNSAFE.sub(" ", name).split()).rstrip(". ")
    return clean or "Project"


def _new_folder(name: str) -> Path:
    root = appsettings.storage_location()
    base = folder_name(name)
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base} ({n})", n + 1
    return folder


def slug(country: str, region: str, jurisdiction: str) -> str:
    """OpenAVMKit's locality slug: <country>-<region>-<jurisdiction>, lowercase, no dashes inside a part."""
    parts = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in (country, region, jurisdiction)]
    return "-".join(p or "x" for p in parts)


def _start(project: Project, folder: Path) -> Project:
    (folder / "in").mkdir(parents=True, exist_ok=True)
    (folder / "out").mkdir(exist_ok=True)
    save(project, folder)
    _register(project.id, folder)
    write_settings(project)
    return project


def create(new: NewProject) -> Project:
    """A new, empty project (SPEC §3.0 F1): its folder, in/, out/ and a settings.json with only the locality."""
    d = country_defaults(new.country)
    project = Project(
        id=uuid.uuid4().hex[:12],
        created_at=dt.datetime.now(dt.UTC),
        **new.model_dump(exclude={"units", "currency", "numbers"}),
        units=new.units or d["units"],
        currency=new.currency or d["currency"],
        numbers=new.numbers or d["numbers"],
    )
    return _start(project, _new_folder(new.name))


BUCKETS = {"land": "land", "building": "impr", "other": "other"}


def _classification(project: Project) -> dict:
    locations, categorical, numeric = list(project.wizard.locations), list(project.wizard.locations), []
    fc: dict = {}
    # The user's own fields, in OpenAVMKit's land / impr / other buckets.
    loaded = {k for f in project.files for k in f.load}
    for c in project.wizard.custom:
        if c.name in loaded:
            kind = "numeric" if c.type == "number" else "categorical"
            fc.setdefault(BUCKETS[c.group], {}).setdefault(kind, []).append(c.name)
    for f in project.files:
        if f.holds == "overlay" and f.overlay and f.overlay.use == "stamp":
            for x in f.overlay.fields:
                if x.kind == "location":
                    locations.append(x.name)
                (numeric if x.kind == "number" else categorical).append(x.name)
    u = units_file(project)
    if u is not None and u.units is not None and u.units.column:
        # The building each unit is in, a land category (and a location, like a neighborhood); its land share.
        land = fc.setdefault("land", {})
        land.setdefault("categorical", []).append(CONDO_GROUP)
        land.setdefault("numeric", []).append("land_area_alloc_sqft")
        if u.units.location:
            locations.append(CONDO_GROUP)
    if locations:
        fc.setdefault("important", {})["locations"] = locations
    if categorical:
        fc.setdefault("other", {}).setdefault("categorical", []).extend(categorical)
    if numeric:
        fc.setdefault("other", {}).setdefault("numeric", []).extend(numeric)
    return {"field_classification": fc} if fc else {}


def base_settings(project: Project) -> dict:
    """What a project writes so far: the locality, the valuation date, and each data file's data.load entry."""
    return {
        "__generated_by": "OAK box. Edit the project in OAK box rather than this file.",
        "locality": {
            "name": project.jurisdiction,
            "state": project.region,
            "units": project.units,
            "slug": slug(project.country, project.region, project.jurisdiction),
            **({"center": project.center.model_dump()} if project.center else {}),
        },
        # Locations the user named, and fields copied from map layers: OpenAVMKit's location fields,
        # categories and numbers. Lists here add to OpenAVMKit's defaults rather than replacing them.
        **_classification(project),
        "modeling": {
            "metadata": {"valuation_date": project.valuation_date.isoformat() if project.valuation_date else None},
            **_model_groups(project),
        },
        **({"data": _data(project)} if project.files else {}),
        **_analysis(project),
    }


DEED_BOOK_PAGE = "deed_book_and_page"


def _deed(project: Project) -> str | None:
    """The field sales scrutiny reads as the deed ID: the deed ID, or the book and page together (F3f)."""
    sales = [f for f in project.files if f.holds == "sales"]
    loaded = {k for f in sales for k in f.load}
    if "deed_id" in loaded:
        return "deed_id"
    if {"deed_book", "deed_page"} <= loaded:
        return DEED_BOOK_PAGE
    return None


def _analysis(project: Project) -> dict:
    deed = _deed(project)
    return {"analysis": {"sales_scrutiny": {"deed_id": deed}}} if deed else {}


def _model_groups(project: Project) -> dict:
    groups = {g.id: {"name": g.name, "filter": f} for g in project.groups if (f := group_filter(g))}
    return {"model_groups": groups} if groups else {}


def _data(project: Project) -> dict:
    """data.load, plus the merge lists once any file says what it holds (F3d): the base first.

    A parcel file joined on an extra ID merges on it (key2, key3). Sales joined on an extra ID get
    the parcel ID (key) from the base by a reference-table lookup on that ID.
    """
    out: dict = {"load": data_load(project.files, project.units)}
    base = project.wizard.base
    parcels: list = [f for f in project.files if f.holds == "parcels"]
    # The main sales file first; more sales details (joined on the sale ID) after it.
    sales = sorted((f for f in project.files if f.holds == "sales"), key=lambda f: f.match == "key_sale")
    if parcels or sales:
        parcels.sort(key=lambda f: f.name != base)
        universe = [f.name if f.name == base or f.match == "key" else {"id": f.name, "on": f.match} for f in parcels]
        process: dict = {"merge": {"universe": universe, "sales": [f.name for f in sales]}}
        lookups = [
            {"id": base, "key_ref_table": f.match, "key_target": f.match, "add_fields": ["key"]}
            for f in sales
            if base and f.match in ("key2", "key3")
        ]
        if lookups:
            process["enrich"] = {"ref_tables": {"sales": lookups}}
        out["process"] = process
    _condos(project, out)
    _permits(project, out)
    if _deed(project) == DEED_BOOK_PAGE:
        # Book and page as one deed ID, "123-45"; blank when either is (no deed is no deed).
        f = next(f for f in project.files if f.holds == "sales" and "deed_page" in f.load)
        joined = ["+", ["+", ["asstr", "deed_book"], "str:-"], ["asstr", "deed_page"]]
        blank = ["or", ["isempty", "deed_book"], ["isempty", "deed_page"]]
        out["load"].setdefault(f.name, {}).setdefault("calc", {})[DEED_BOOK_PAGE] = ["where", blank, None, joined]
    # Map layers (F3d Shapefiles): joined by where each parcel is, or measured to.
    layers = [f for f in project.files if f.holds == "overlay" and f.overlay and f.overlay.use]
    stamps = [f for f in layers if f.overlay and f.overlay.use == "stamp" and f.overlay.fields]
    dists = [f for f in layers if f.overlay and f.overlay.use == "distance" and f.overlay.feature]
    # Enrichments (F3e): public data, and distances to OpenStreetMap features beside the layers' own.
    public, osm = enrich_settings(project.enrich, project.units, {f.overlay.feature for f in dists if f.overlay})
    if stamps or dists or public or osm:
        enrich = out.setdefault("process", {}).setdefault("enrich", {})
        if stamps:
            enrich["geometry"] = [
                {"id": f.name, "predicate": "contains_centroid", "fields": [x.name for x in f.overlay.fields]}
                for f in stamps
                if f.overlay
            ]
        enrich |= public
        if dists or osm:
            enrich["distances"] = (
                {"enabled": True}
                | {f.overlay.feature: overlay_distance(f.name, f.overlay) for f in dists if f.overlay}
                | osm
            )
    return out


CONDO_LINK, CONDO_PARENT, CONDO_UNIT, CONDO_GROUP = "condo_link", "condo_parent", "condo_unit", "condo_group"


def units_file(project: Project) -> DataFile | None:
    """The parcel file whose rows without a shape are units of a shared parcel (one per project: OpenAVMKit has one
    condos block)."""
    return next((f for f in project.files if f.holds == "parcels" and f.units is not None), None)


def _condos(project: Project, out: dict) -> None:
    """data.process.condos, and what it needs loaded (F3d condos).

    OpenAVMKit tests `select` on every parcel file, so each gets a yes/no field `condo_unit`: the units file's
    rule (or every row) there, and no everywhere else. The link ID is loaded under one name in the units file and
    the parcel universe file (prefix), or the parent ID in the units file, cleaned as the parcel ID is (parent).
    """
    u = units_file(project)
    base = next((f for f in project.files if f.name == project.wizard.base), None)
    if u is None or base is None or u.units is None or u.units.column is None:
        return
    units = u.units
    load = out["load"]
    entry = load.setdefault(u.name, {})
    eload = entry.setdefault("load", {})
    ecalc = entry.setdefault("calc", {})
    select: list = ["not", ["isempty", "key"]]
    if units.rule and units.rule.conditions:
        names = rule_fields(u.load, units.rule)
        for column, (field, kind) in names.items():
            eload.setdefault(field, [column, kind])
        select = rule_filter(units.rule, names) or select
    if units.link == "prefix":
        if not units.base_column:
            return
        eload[CONDO_LINK] = [units.column, "string"]
        load.setdefault(base.name, {}).setdefault("load", {})[CONDO_LINK] = [units.base_column, "string"]
        link = {"method": "id_prefix", "id_field": CONDO_LINK, "prefix_len": units.prefix_len, "from": base.name}
    else:
        eload[CONDO_PARENT] = [units.column, "string"]
        steps = base.clean.get("key", [])
        if steps:
            ecalc[CONDO_PARENT] = clean_calc(CONDO_PARENT, steps)
        link = {"method": "parent_id", "parent_field": CONDO_PARENT, "from_key": "key", "from": base.name}
    ecalc[CONDO_UNIT] = ["?", select]
    # Every other parcel file: no unit (its rows all have an ID, so "blank ID" is never true).
    for f in project.files:
        if f is not u and (f is base or f.holds == "parcels") and f.name in load:
            load[f.name].setdefault("calc", {})[CONDO_UNIT] = ["?", ["isempty", "key"]]
    land_field = "land_area_sqft" if project.units == "imperial" else "land_area_sqm"
    share = {
        "equal": {"method": "equal"},
        "field": {"method": "field", "field": land_field},
        # The finished area may come from another file (building cards): OpenAVMKit shares it after the merge.
        "floor_area": {"method": "floor_area", "floor_field": "bldg_area_finished_sqft"},
        "none": {"method": "none"},
    }[units.land]
    out.setdefault("process", {})["condos"] = {
        "enabled": True,
        "select": ["==", CONDO_UNIT, True],
        "link": link,
        "group_field": CONDO_GROUP,
        "borrow_geometry": True,
        "land_share": share,
    }


PERMIT_FIELDS = ("date", "permit_type", "is_teardown", "is_renovation", "renovation_num", "renovation_txt")


def permits_file(project: Project) -> DataFile | None:
    return next((f for f in project.files if f.holds == "permits"), None)


def permits_ready(f: DataFile) -> bool:
    p = f.permits
    return bool(p and p.date and p.date_format and p.type and "key" in f.load)


def _permits(project: Project, out: dict) -> None:
    """The permits file's fields, worked out from its type column, and data.process.enrich.permits (F3g).

    OpenAVMKit reads key, date, is_teardown, is_renovation, renovation_num (3 major, 1 minor) and renovation_txt
    from each permit."""
    f = permits_file(project)
    if f is None or not permits_ready(f) or f.permits is None:
        return
    p = f.permits
    entry = out["load"].setdefault(f.name, {"filename": f.filename})
    entry.setdefault("load", {}).update(
        {"date": [p.date, "datetime", p.date_format], "permit_type": [p.type, "string"]}
    )

    def of(meaning: str) -> list:
        return ["isin", "permit_type", [f"str:{v}" for v, m in p.means.items() if m == meaning]]

    major, minor = of("major"), of("minor")
    entry.setdefault("calc", {}).update(
        {
            "is_teardown": ["?", of("teardown")],
            "is_renovation": ["?", ["or", major, minor]],
            "renovation_num": ["where", major, 3, ["where", minor, 1, 0]],
            "renovation_txt": ["asstr", "permit_type"],
        }
    )
    loaded = {k for x in project.files if x.holds in ("parcels", "sales") for k in x.load}
    out.setdefault("process", {}).setdefault("enrich", {})["permits"] = {
        "sources": [f.name],
        "max_days_to_demo": p.max_days,
        # It needs the year built to start from.
        "calc_effective_age": p.effective_age and "bldg_year_built" in loaded,
    }


def write_settings(project: Project) -> Path:
    path = project_dir(project.id) / "in" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = base_settings(project)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return path


# ---------- Project actions (SPEC §3.0 F1b) ----------


def disk_usage(project_id: str) -> tuple[int, int]:
    """(bytes, files) in the project folder."""
    total = files = 0
    for f in project_dir(project_id).rglob("*"):
        if f.is_file():
            total += f.stat().st_size
            files += 1
    return total, files


def delete(project_id: str) -> None:
    """Send the project folder to the Recycle Bin (desktop trash on Linux), and forget it."""
    from send2trash import send2trash

    folder = project_dir(project_id)
    send2trash(str(folder))
    s = appsettings.load()
    s.projects.pop(project_id, None)
    appsettings.save(s)


def show_in_folder(project_id: str) -> None:
    _open_in_file_manager(project_dir(project_id))


def show_file(path: Path) -> None:
    """Show a file in the file manager: selected in Explorer and Finder; elsewhere its folder opens."""
    if not path.is_file():
        _open_in_file_manager(path.parent)
    elif sys.platform == "win32":
        # As one string: Explorer wants exactly /select,"<path>", which list quoting doesn't produce.
        subprocess.Popen(f'explorer /select,"{path}"')  # noqa: S602, S607
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        _open_in_file_manager(path.parent)


def _open_in_file_manager(folder: Path) -> None:
    if sys.platform == "win32":
        import os

        os.startfile(folder)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(folder)])
    else:
        raise OSError("No file manager found to open the folder.")

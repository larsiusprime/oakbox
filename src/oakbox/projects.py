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
from oakbox.datafiles import DataFile, data_load


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
    return json.loads(resources.files("oakbox").joinpath("locales.json").read_text())


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


class WizardState(BaseModel):
    """The Fields wizard's own state (SPEC §3.0 F3d). Everything it chooses is in the files' entries."""

    base: str | None = Field(default=None, description="The parcel file the others join to.")
    visited: list[str] = Field(default_factory=list, description="Steps shown at least once.")
    skipped: list[str] = Field(default_factory=list, description='Steps answered with "I don\'t have these".')
    confirmed: list[str] = Field(default_factory=list, description="Steps moved on from with Next (or Start).")
    decided: list[str] = Field(
        default_factory=list, description="Fields chosen or guessed once, so a guess never replaces them."
    )


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
    sample: str | None = None
    files: list[DataFile] = Field(default_factory=list, description="data.load entries (SPEC §3.0 F2).")
    wizard: WizardState = Field(default_factory=WizardState)

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


# ---------- Finding projects ----------


def _register(project_id: str, folder: Path) -> None:
    s = appsettings.load()
    if s.projects.get(project_id) != str(folder):
        s.projects[project_id] = str(folder)
        appsettings.save(s)


def _read(folder: Path) -> Project | None:
    """The project in a folder; None for damaged files and for sample projects of earlier builds (SPEC D19)."""
    try:
        project = Project.model_validate_json((folder / "oakbox.json").read_text())
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
    return Project.model_validate_json((project_dir(project_id) / "oakbox.json").read_text())


def save(project: Project, folder: Path | None = None) -> None:
    folder = folder or project_dir(project.id)
    path = folder / "oakbox.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2))
    tmp.replace(path)


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


def base_settings(project: Project) -> dict:
    """What a project writes so far: the locality, the valuation date, and each data file's data.load entry."""
    return {
        "__generated_by": "OAK box. Edit the project in OAK box rather than this file.",
        "locality": {
            "name": project.jurisdiction,
            "state": project.region,
            "units": project.units,
            "slug": slug(project.country, project.region, project.jurisdiction),
        },
        "modeling": {
            "metadata": {"valuation_date": project.valuation_date.isoformat() if project.valuation_date else None}
        },
        **({"data": _data(project)} if project.files else {}),
    }


def _data(project: Project) -> dict:
    """data.load, plus the merge lists once any file says what it holds (F3d): the base first.

    A parcel file joined on an extra ID merges on it (key2, key3). Sales joined on an extra ID get
    the parcel ID (key) from the base by a reference-table lookup on that ID.
    """
    out: dict = {"load": data_load(project.files, project.units)}
    base = project.wizard.base
    parcels: list = [f for f in project.files if f.holds == "parcels"]
    sales = [f for f in project.files if f.holds == "sales"]
    if parcels or sales:
        parcels.sort(key=lambda f: f.name != base)
        universe = [f.name if f.name == base or f.match == "key" else {"id": f.name, "on": f.match} for f in parcels]
        process: dict = {"merge": {"universe": universe, "sales": [f.name for f in sales]}}
        lookups = [
            {"id": base, "key_ref_table": f.match, "key_target": f.match, "add_fields": ["key"]}
            for f in sales
            if base and f.match != "key"
        ]
        if lookups:
            process["enrich"] = {"ref_tables": {"sales": lookups}}
        out["process"] = process
    return out


def write_settings(project: Project) -> Path:
    path = project_dir(project.id) / "in" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = base_settings(project)
    path.write_text(json.dumps(settings, indent=2))
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

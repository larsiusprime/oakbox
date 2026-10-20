"""Projects: one jurisdiction x one tax year, stored as an ordinary folder.

Layout (SPEC §3.0 F1, §6)::

    <storage location>/<project name>/
        oakbox.json        OAK box's own state: project facts, step status
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
from pathlib import Path
from typing import Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from oakbox import appsettings
from oakbox.answers import WizardAnswers
from oakbox.datafiles import DataFile, data_load
from oakbox.settings_gen import generate

StepId = Literal["bring_in_data", "model_groups", "check_sales", "check_values"]
STEP_ORDER: tuple[StepId, ...] = ("bring_in_data", "model_groups", "check_sales", "check_values")
StepState = Literal["not_run", "running", "done", "failed", "stale"]


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class StepStatus(BaseModel):
    state: StepState = "not_run"
    finished_at: dt.datetime | None = None
    message: str = ""


Units = Literal["imperial", "metric"]


class NewProject(BaseModel):
    """What the user enters to create a project (SPEC §3.0 F1)."""

    name: str = Field(description="Project name; also the folder name. Free text.")
    country: str = Field(description="ISO 3166-1 alpha-2 code, e.g. 'US'.")
    region: str = Field(description="For the US, an ISO 3166-2 state code without 'US-' (e.g. 'TX'); else free text.")
    jurisdiction: str = Field(description="What the office calls itself; OpenAVMKit's locality.name.")
    tax_year: int
    valuation_date: dt.date
    units: Units


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
    sample: str | None = None
    answers: WizardAnswers | None = Field(default=None, description="Sample projects only, until data setup exists.")
    files: list[DataFile] = Field(default_factory=list, description="data.load entries (SPEC §3.0 F2).")
    steps: dict[StepId, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in STEP_ORDER})


# ---------- Finding projects ----------


def _register(project_id: str, folder: Path) -> None:
    s = appsettings.load()
    if s.projects.get(project_id) != str(folder):
        s.projects[project_id] = str(folder)
        appsettings.save(s)


def _read(folder: Path) -> Project | None:
    try:
        return Project.model_validate_json((folder / "oakbox.json").read_text())
    except (OSError, ValueError):
        return None


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
    project = Project(
        id=uuid.uuid4().hex[:12],
        created_at=dt.datetime.now(dt.UTC),
        **new.model_dump(),
    )
    return _start(project, _new_folder(new.name))


def create_from_sample(answers: WizardAnswers, sample: str) -> Project:
    """A project pre-filled from a sample county."""
    p = answers.place
    project = Project(
        id=uuid.uuid4().hex[:12],
        name=f"{p.name} {p.tax_year} (sample)",
        created_at=dt.datetime.now(dt.UTC),
        country="US",
        region=p.state,
        jurisdiction=p.name,
        tax_year=p.tax_year,
        valuation_date=answers.dates.valuation_date,
        units=p.units,
        sample=sample,
        answers=answers,
    )
    return _start(project, _new_folder(project.name))


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
        **({"data": {"load": data_load(project.files)}} if project.files else {}),
    }


def write_settings(project: Project) -> Path:
    path = project_dir(project.id) / "in" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = generate(project.answers) if project.answers is not None else base_settings(project)
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
    folder = project_dir(project_id)
    if sys.platform == "win32":
        import os

        os.startfile(folder)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    elif shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(folder)])
    else:
        raise OSError("No file manager found to open the folder.")


def mark_step(project: Project, step: StepId, state: StepState, message: str = "") -> Project:
    """Record a step's outcome. A finished step makes every later step stale."""
    project.steps[step] = StepStatus(
        state=state,
        message=message,
        finished_at=dt.datetime.now(dt.UTC) if state in ("done", "failed") else None,
    )
    if state == "done":
        for later in STEP_ORDER[STEP_ORDER.index(step) + 1 :]:
            if project.steps[later].state == "done":
                project.steps[later] = StepStatus(state="stale", message="An earlier step was re-run.")
    save(project)
    return project

"""Projects: the regions to choose from, the projects with a run going, creating, opening and deleting a project,
its locale, disk use and folder, and checking and adding an input file (SPEC §3.0 F1, F1b, F2)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import datafiles, projects, steps, wizard
from oakbox.datafiles import BaseModel
from oakbox.routes.common import editing, load_project

router = APIRouter()


class InputFile(BaseModel):
    """An input file as the Input files tab shows it (SPEC §3.0 F3)."""

    name: str
    filename: str
    layer: str | None = None
    format: str
    size_bytes: int = Field(description="0 when the file is missing from in/.")
    missing: bool = Field(description="The file isn't in in/.")
    geometry: bool | None = Field(description="OpenAVMKit sees a geometry column. None if missing or unreadable.")
    fields_loaded: int = Field(description="Columns in the entry's load (F3c).")
    columns: int | None = Field(
        description="Columns in the file, not counting geometry. None if missing or unreadable."
    )


class ProjectDetail(BaseModel):
    project: projects.Project
    folder: str
    files: list[InputFile]


class Region(BaseModel):
    code: str
    name: str


class Currency(BaseModel):
    code: str
    name: str
    symbol: str


class CountryDefaults(BaseModel):
    currency: str
    numbers: projects.NumberStyle
    units: projects.Units


class Regions(BaseModel):
    """ISO 3166-1 countries and, where OAK box lists them, ISO 3166-2 subdivisions; each country's
    currency, number style and units, and the currencies to choose from (SPEC F1)."""

    countries: list[Region]
    subdivisions: dict[str, list[Region]]
    defaults: dict[str, CountryDefaults] = Field(default_factory=dict)
    currencies: list[Currency] = Field(default_factory=list)


class FilePath(BaseModel):
    path: str


class AddFile(BaseModel):
    path: str
    mode: Literal["move", "copy"]
    name: str = Field(description="The data.load key.")
    layer: str | None = None
    filename: str | None = Field(default=None, description="A new name in in/, when the original is taken.")


class DiskUsage(BaseModel):
    bytes: int
    files: int
    folder: str


def _regions() -> Regions:
    from importlib import resources

    regions = Regions.model_validate_json(
        resources.files("oakbox").joinpath("iso3166.json").read_text(encoding="utf-8")
    )
    loc = projects.locales()
    regions.defaults = {k: CountryDefaults(**v) for k, v in loc["countries"].items()}
    regions.currencies = [Currency(**c) for c in loc["currencies"]]
    return regions


def _view(in_dir: Path, f: datafiles.DataFile) -> InputFile:
    path = in_dir / f.filename
    present = path.is_file()
    names = datafiles.column_names(path, f.layer) if present else None
    return InputFile(
        name=f.name,
        filename=f.filename,
        layer=f.layer,
        format=datafiles.FORMATS.get(path.suffix.lower().lstrip("."), ""),
        size_bytes=sum(p.stat().st_size for p in datafiles.companions(path)) if present else 0,
        missing=not present,
        geometry=None if names is None else "geometry" in names,
        fields_loaded=len(f.load),
        columns=None if names is None else len([n for n in names if n != "geometry"]),
    )


@router.get("/api/regions")
def regions() -> Regions:
    return _regions()


@router.get("/api/running")
def running_projects() -> list[str]:
    """The projects with a run going now (any step), for the plate's project list."""
    return steps.running_projects()


@router.get("/api/projects")
def list_projects() -> list[projects.Project]:
    return projects.list_projects()


@router.post("/api/projects")
def create_project(body: projects.NewProject) -> projects.Project:
    regions = _regions()
    if not body.name.strip() or not body.jurisdiction.strip():
        raise HTTPException(422, "Give the project a name and say which jurisdiction it is.")
    if body.country not in {c.code for c in regions.countries}:
        raise HTTPException(422, "Choose a country from the list.")
    listed = regions.subdivisions.get(body.country)
    if listed is not None and body.region not in {r.code for r in listed}:
        raise HTTPException(422, "Choose a state from the list.")
    if not body.region.strip():
        raise HTTPException(422, "Say which state, province or region this is.")
    if body.currency is not None and body.currency not in {c.code for c in regions.currencies}:
        raise HTTPException(422, "Choose a currency from the list.")
    if not 1900 <= body.tax_year <= 2200:
        raise HTTPException(422, "The tax year doesn't look right.")
    return projects.create(
        body.model_copy(update={"name": body.name.strip(), "jurisdiction": body.jurisdiction.strip()})
    )


@router.patch("/api/projects/{project_id}/locale")
def set_locale(project_id: str, body: projects.Locale) -> projects.Project:
    """Change the project's units, currency or number style (SPEC F1)."""
    with editing(project_id, settings=True) as project:
        if body.currency is not None and body.currency not in {c["code"] for c in projects.locales()["currencies"]}:
            raise HTTPException(422, "Choose a currency from the list.")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(project, key, value)
    return project


@router.get("/api/projects/{project_id}/disk")
def project_disk(project_id: str) -> DiskUsage:
    load_project(project_id)
    size, files = projects.disk_usage(project_id)
    return DiskUsage(bytes=size, files=files, folder=str(projects.project_dir(project_id)))


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> None:
    with projects.lock(project_id):  # a change saved after it would bring oakbox.json back
        load_project(project_id)
        try:
            projects.delete(project_id)
        except OSError as e:
            raise HTTPException(500, f"Couldn't move the project to the Recycle Bin: {e}") from e


@router.post("/api/projects/{project_id}/show-in-folder")
def show_in_folder(project_id: str) -> None:
    load_project(project_id)
    try:
        projects.show_in_folder(project_id)
    except OSError as e:
        raise HTTPException(500, str(e)) from e


@router.post("/api/projects/{project_id}/files/check")
def check_file(project_id: str, body: FilePath) -> datafiles.FileCheck:
    """What OAK box can tell about a file before adding it (SPEC §3.0 F2)."""
    project = load_project(project_id)
    return datafiles.check(projects.project_dir(project_id) / "in", body.path, project.files)


@router.post("/api/projects/{project_id}/files")
def add_file(project_id: str, body: AddFile) -> projects.Project:
    """Move or copy a file into in/ and add its data.load entry (SPEC §3.0 F2)."""
    with editing(project_id, settings=True) as project:
        try:
            entry = datafiles.add(
                projects.project_dir(project_id) / "in",
                body.path,
                project.files,
                body.mode,
                body.name.strip(),
                body.layer,
                body.filename,
            )
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        project.files.append(entry)
        wizard.update_base(project, projects.project_dir(project_id) / "in")
    return project


@router.get("/api/projects/{project_id}")
def get_project(project_id: str) -> ProjectDetail:
    with projects.lock(project_id):  # refresh_settings may write settings.json
        project = load_project(project_id)
        folder = projects.project_dir(project_id)
        projects.refresh_settings(project)
    return ProjectDetail(project=project, folder=str(folder), files=[_view(folder / "in", f) for f in project.files])

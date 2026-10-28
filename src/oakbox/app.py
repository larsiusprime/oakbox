"""The app service: a local HTTP API for the UI, plus the built UI itself.

Binds to 127.0.0.1 only. The UI talks to it over JSON and server-sent events
(SPEC §6). Types are pydantic models, exported as OpenAPI for the TypeScript
client.
"""

from __future__ import annotations

import mimetypes
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from oakbox import __version__, appsettings, bring_in, datafiles, fields, groups, projects, wizard
from oakbox.datafiles import CleanStep

WEB_DIST = Path(__file__).parent / "web"

# Python guesses content types from the Windows registry, where other software often
# maps .js to text/plain; browsers then refuse to run the UI's module scripts. Pin the
# types of everything the UI ships.
UI_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
}


def pin_ui_content_types() -> None:
    for ext, content_type in UI_TYPES.items():
        mimetypes.add_type(content_type, ext)


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


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


class EntryName(BaseModel):
    name: str


class EntryLoad(BaseModel):
    load: dict[str, list[str]]


class WizardFileChoice(BaseModel):
    """Step 1 of the Fields wizard, for one file (F3d). Leave a value out to keep it."""

    holds: datafiles.Holds | None = None
    universe: bool = Field(default=False, description="Make this the parcel universe file (it needs shapes).")
    match: datafiles.Match | None = Field(default=None, description="Join on the parcel ID (key) or second ID (key2).")
    id_column: str | None = Field(default=None, description="The column loaded as the ID it joins on.")
    extra_field: Literal["key2", "key3"] | None = Field(
        default=None, description="One of the universe's extra IDs: set to extra_column, or removed if it's null."
    )
    extra_column: str | None = None
    dupes: datafiles.Dupes | None = Field(
        default=None, description="Repeated IDs: keep the first of each, or drop all."
    )
    dupes_sort: str | None = Field(default=None, description="With first: the field to sort by before keeping.")
    dupes_desc: bool = False
    blank_ok: bool | None = Field(default=None, description="Acknowledge the rows with no ID (they're dropped).")


class WizardReconcile(BaseModel):
    file_steps: list[CleanStep] = Field(default_factory=list, description="Clean-up steps for the sales file's ID.")
    base_steps: list[CleanStep] = Field(default_factory=list, description="And for the parcel universe's.")


class WizardReconcilePreview(WizardReconcile):
    view: wizard.SampleView = "unmatched"
    seed: int = Field(default=0, description="Change it for new samples.")
    suggest: bool = Field(default=False, description="Also try a few common clean-ups (slower).")


class WizardSaleId(BaseModel):
    column: str | None = None
    make: bool = Field(default=False, description="Make one from parcel ID + sale date.")


class WizardLocation(BaseModel):
    file: str | None = None
    column: str | None = Field(default=None, description="None removes the location field.")


class WizardDates(BaseModel):
    column: str
    format: str


class GroupsStart(BaseModel):
    how: Literal["scratch", "suggested"]


class GroupsBody(BaseModel):
    groups: list[projects.ModelGroup]


class WizardCustom(BaseModel):
    file: str | None = None
    column: str | None = Field(default=None, description="None removes the field.")
    group: Literal["land", "building", "other"] = "other"
    type: Literal["category", "number"] = "category"


class InspectBody(BaseModel):
    groups: list[projects.ModelGroup]
    index: int


class WizardFieldChoice(BaseModel):
    file: str | None = None
    column: str | None = None
    assume: bool = Field(default=False, description="Valid/vacant sale only: all valid, none vacant.")
    date_format: str | None = Field(default=None, description="Dates: the format to read it with.")
    area_unit: datafiles.AreaUnit | None = Field(default=None, description="Areas: the unit the column is in.")
    number_format: datafiles.NumberFormat | None = Field(
        default=None, description="Money written as text: how to read it. None: worked out from the column."
    )
    scale: datafiles.Scale | None = Field(
        default=None, description="Quality/condition number: how the column becomes higher-is-better."
    )
    absent: bool = Field(default=False, description="Condition: there isn't one (effective age carries it).")


class WizardColumnRef(BaseModel):
    file: str
    column: str
    scale: datafiles.Scale | None = Field(default=None, description="None: the saved one, or a first one.")


class WizardNumbers(BaseModel):
    key: str
    column: str
    format: datafiles.NumberFormat | None = Field(default=None, description="None: the saved one, or as detected.")


class DateFormatCheck(BaseModel):
    samples: list[str]
    format: str


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


class Versions(BaseModel):
    version: str
    openavmkit: str


def _openavmkit_version() -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as package_version

    try:
        return package_version("openavmkit")
    except PackageNotFoundError:
        return "unknown"


class Display(BaseModel):
    """How the app looks (SPEC D43, View menu)."""

    density: Literal["compact", "comfortable"] | None = Field(
        default=None, description="None: compact, or comfortable on touch screens."
    )
    large_text: bool = False
    high_contrast: bool = False


class AppSettingsView(BaseModel):
    storage_location: str
    default_storage_location: str
    display: Display


class StorageLocation(BaseModel):
    storage_location: str | None = Field(default=None, description="None resets to the default.")


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

    regions = Regions.model_validate_json(resources.files("oakbox").joinpath("iso3166.json").read_text())
    loc = projects.locales()
    regions.defaults = {k: CountryDefaults(**v) for k, v in loc["countries"].items()}
    regions.currencies = [Currency(**c) for c in loc["currencies"]]
    return regions


def _settings_view() -> AppSettingsView:
    s = appsettings.load()
    return AppSettingsView(
        storage_location=str(appsettings.storage_location()),
        default_storage_location=str(appsettings.default_storage()),
        display=Display(density=s.density, large_text=s.large_text, high_contrast=s.high_contrast),
    )


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


def _warm_engine() -> None:
    import openavmkit.data  # noqa: F401


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Importing OpenAVMKit takes seconds; start it now so the first project opened doesn't wait.
    threading.Thread(target=_warm_engine, daemon=True).start()
    yield


def create_app() -> FastAPI:
    pin_ui_content_types()
    app = FastAPI(title="OAK box", version=__version__, lifespan=_lifespan)

    @app.get("/api/version")
    def version() -> Versions:
        return Versions(version=__version__, openavmkit=_openavmkit_version())

    @app.put("/api/app-settings/display")
    def put_display(body: Display) -> AppSettingsView:
        """Density, large text and high contrast (SPEC D43, View menu)."""
        s = appsettings.load()
        s.density, s.large_text, s.high_contrast = body.density, body.large_text, body.high_contrast
        appsettings.save(s)
        return _settings_view()

    @app.get("/api/regions")
    def regions() -> Regions:
        return _regions()

    @app.get("/api/app-settings")
    def get_app_settings() -> AppSettingsView:
        return _settings_view()

    @app.put("/api/app-settings/storage-location")
    def put_storage_location(body: StorageLocation) -> AppSettingsView:
        """Where new projects are kept. Existing projects stay where they are."""
        s = appsettings.load()
        if body.storage_location:
            folder = Path(body.storage_location).expanduser()
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise HTTPException(422, f"OAK box can't use that folder: {e.strerror or e}") from e
            s.storage_location = str(folder)
        else:
            s.storage_location = None
        appsettings.save(s)
        return _settings_view()

    @app.get("/api/projects")
    def list_projects() -> list[projects.Project]:
        return projects.list_projects()

    @app.post("/api/projects")
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

    @app.patch("/api/projects/{project_id}/locale")
    def set_locale(project_id: str, body: projects.Locale) -> projects.Project:
        """Change the project's units, currency or number style (SPEC F1)."""
        project = _load(project_id)
        if body.currency is not None and body.currency not in {c["code"] for c in projects.locales()["currencies"]}:
            raise HTTPException(422, "Choose a currency from the list.")
        for key, value in body.model_dump(exclude_none=True).items():
            setattr(project, key, value)
        projects.save(project)
        projects.write_settings(project)
        return project

    def _load(project_id: str) -> projects.Project:
        try:
            return projects.load(project_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Project not found") from None

    @app.get("/api/projects/{project_id}/disk")
    def project_disk(project_id: str) -> DiskUsage:
        _load(project_id)
        size, files = projects.disk_usage(project_id)
        return DiskUsage(bytes=size, files=files, folder=str(projects.project_dir(project_id)))

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> None:
        _load(project_id)
        try:
            projects.delete(project_id)
        except OSError as e:
            raise HTTPException(500, f"Couldn't move the project to the Recycle Bin: {e}") from e

    @app.post("/api/projects/{project_id}/show-in-folder")
    def show_in_folder(project_id: str) -> None:
        _load(project_id)
        try:
            projects.show_in_folder(project_id)
        except OSError as e:
            raise HTTPException(500, str(e)) from e

    @app.post("/api/projects/{project_id}/files/check")
    def check_file(project_id: str, body: FilePath) -> datafiles.FileCheck:
        """What OAK box can tell about a file before adding it (SPEC §3.0 F2)."""
        project = _load(project_id)
        return datafiles.check(projects.project_dir(project_id) / "in", body.path, project.files)

    @app.post("/api/projects/{project_id}/files")
    def add_file(project_id: str, body: AddFile) -> projects.Project:
        """Move or copy a file into in/ and add its data.load entry (SPEC §3.0 F2)."""
        project = _load(project_id)
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
        projects.save(project)
        projects.write_settings(project)
        return project

    @app.put("/api/projects/{project_id}/files/{name}/name")
    def rename_file(project_id: str, name: str, body: EntryName) -> None:
        """Rename a data.load entry; the file keeps its name (SPEC §3.0 F3b)."""
        project = _load(project_id)
        try:
            datafiles.rename(project.files, name, body.name.strip())
            wizard.renamed(project, name, body.name.strip())
        except LookupError as e:
            raise HTTPException(404, "No such input file") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        projects.save(project)
        projects.write_settings(project)

    @app.delete("/api/projects/{project_id}/files/{name}")
    def remove_file(project_id: str, name: str, trash: bool = False) -> None:
        """Drop a data.load entry; with trash, its file goes to the Recycle Bin (SPEC §3.0 F3b)."""
        project = _load(project_id)
        try:
            datafiles.remove(projects.project_dir(project_id) / "in", project.files, name, trash)
        except LookupError as e:
            raise HTTPException(404, "No such input file") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        except OSError as e:
            raise HTTPException(500, f"Couldn't move the file to the Recycle Bin: {e}") from e
        wizard.update_base(project, projects.project_dir(project_id) / "in")
        projects.save(project)
        projects.write_settings(project)

    @app.post("/api/projects/{project_id}/files/{name}/show")
    def show_file(project_id: str, name: str) -> None:
        """Show an input file in the file manager (SPEC §3.0 F3b)."""
        entry = _entry(_load(project_id), name)
        try:
            projects.show_file(projects.project_dir(project_id) / "in" / entry.filename)
        except OSError as e:
            raise HTTPException(500, str(e)) from e

    def _entry(project: projects.Project, name: str) -> datafiles.DataFile:
        entry = next((f for f in project.files if f.name == name), None)
        if entry is None:
            raise HTTPException(404, "No such input file")
        return entry

    @app.get("/api/projects/{project_id}/files/{name}/columns")
    def file_columns(project_id: str, name: str) -> fields.FileColumns:
        """The file's columns, their types and sample values, read without changing it (SPEC §3.0 F3c)."""
        entry = _entry(_load(project_id), name)
        path = projects.project_dir(project_id) / "in" / entry.filename
        if not path.is_file():
            raise HTTPException(404, f"{entry.filename} is missing from the project folder.")
        try:
            return fields.columns(path, entry.layer)
        except Exception as e:  # noqa: BLE001 - a damaged file: say so in the view
            raise HTTPException(422, f"Couldn't read {entry.filename}: {e}") from e

    @app.put("/api/projects/{project_id}/files/{name}/load")
    def set_load(project_id: str, name: str, body: EntryLoad) -> None:
        """Replace the entry's load: field -> [column, type, extra] (SPEC §3.0 F3c)."""
        project = _load(project_id)
        try:
            fields.set_load(_entry(project, name), body.load)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        projects.save(project)
        projects.write_settings(project)

    # ---------- F3d: the Fields wizard ----------

    def _wizard(project: projects.Project) -> wizard.Wizard:
        return wizard.view(project, projects.project_dir(project.id) / "in")

    def _change(project_id: str, change) -> wizard.Wizard:
        project = _load(project_id)
        try:
            change(project, projects.project_dir(project_id) / "in")
        except LookupError as e:
            raise HTTPException(404, f"No such step or field: {e}") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        projects.save(project)
        projects.write_settings(project)
        return _wizard(project)

    @app.get("/api/projects/{project_id}/wizard")
    def get_wizard(project_id: str) -> wizard.Wizard:
        """Every step, file and field of the Fields wizard as it stands (SPEC §3.0 F3d)."""
        return _wizard(_load(project_id))

    @app.post("/api/projects/{project_id}/wizard/steps/{step}/visit")
    def visit_step(project_id: str, step: str) -> wizard.Wizard:
        """A step is shown: fill in guesses for what on it hasn't been decided yet (F3d)."""
        return _change(project_id, lambda p, d: wizard.visit(p, d, step))

    @app.post("/api/projects/{project_id}/wizard/steps/{step}/confirm")
    def confirm_step(project_id: str, step: str) -> wizard.Wizard:
        """Next (or Start) on a step: an optional step is complete once moved on from (F3d)."""
        return _change(project_id, lambda p, _d: wizard.confirm(p, step))

    @app.post("/api/projects/{project_id}/wizard/steps/{step}/skip")
    def skip_step(project_id: str, step: str) -> wizard.Wizard:
        """'I don't have these': nothing loaded for the step's fields (F3d)."""
        return _change(project_id, lambda p, _d: wizard.skip(p, step))

    @app.put("/api/projects/{project_id}/wizard/files/{name}")
    def wizard_file(project_id: str, name: str, body: WizardFileChoice) -> wizard.Wizard:
        """A file's part (parcel universe, sales, more parcel details) and the ID it joins on (F3d)."""
        project = _load(project_id)
        _entry(project, name)
        return _change(
            project_id,
            lambda p, d: wizard.set_file(
                p,
                d,
                name,
                body.holds,
                body.id_column,
                body.extra_field,
                body.extra_column,
                body.match,
                body.universe,
                body.dupes,
                body.dupes_sort,
                body.dupes_desc,
                body.blank_ok,
            ),
        )

    @app.get("/api/projects/{project_id}/wizard/files/{name}/repeats")
    def wizard_repeats(project_id: str, name: str) -> wizard.RepeatRows:
        """Every row of a few repeated IDs, for the duplicates dialog (F3d)."""
        project = _load(project_id)
        _entry(project, name)
        try:
            return wizard.repeat_rows(project, projects.project_dir(project_id) / "in", name)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.post("/api/projects/{project_id}/wizard/files/{name}/reconcile")
    def wizard_reconcile_preview(project_id: str, name: str, body: WizardReconcilePreview) -> wizard.Reconcile:
        """How the sales would match the parcels with these clean-up steps, with samples; nothing is saved (F3d)."""
        project = _load(project_id)
        _entry(project, name)
        try:
            return wizard.reconcile(
                project,
                projects.project_dir(project_id) / "in",
                name,
                body.file_steps,
                body.base_steps,
                body.view,
                body.seed,
                body.suggest,
            )
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.put("/api/projects/{project_id}/wizard/files/{name}/reconcile")
    def wizard_reconcile(project_id: str, name: str, body: WizardReconcile) -> wizard.Wizard:
        """Save the clean-up steps for the sales file's ID and the parcel universe's (F3d)."""
        return _change(project_id, lambda p, d: wizard.set_reconcile(p, d, name, body.file_steps, body.base_steps))

    @app.put("/api/projects/{project_id}/wizard/sale-id")
    def wizard_sale_id(project_id: str, body: WizardSaleId) -> wizard.Wizard:
        """The sales file's sale ID: a column, or made from parcel ID + sale date (F3d)."""
        return _change(project_id, lambda p, _d: wizard.set_sale_id(p, body.column, body.make))

    @app.put("/api/projects/{project_id}/wizard/fields/{key}")
    def wizard_field(project_id: str, key: str, body: WizardFieldChoice) -> wizard.Wizard:
        """Load a field from a file's column, from nowhere, or as an assumption (F3d)."""
        return _change(
            project_id,
            lambda p, d: wizard.set_field(
                p,
                d,
                key,
                body.file,
                body.column,
                body.assume,
                body.date_format,
                body.area_unit,
                body.number_format,
                body.scale,
                body.absent,
            ),
        )

    @app.post("/api/projects/{project_id}/wizard/fields/{key}/rule")
    def wizard_rule_preview(project_id: str, key: str, body: datafiles.Rule) -> wizard.RulePreview:
        """What a yes/no rule makes of the sales file, without saving it (F3d)."""
        project = _load(project_id)
        try:
            return wizard.rule_preview(project, projects.project_dir(project_id) / "in", key, body)
        except LookupError as e:
            raise HTTPException(404, f"No such field: {e}") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.put("/api/projects/{project_id}/wizard/fields/{key}/rule")
    def wizard_rule(project_id: str, key: str, body: datafiles.Rule) -> wizard.Wizard:
        """Work a yes/no field (valid sale, vacant sale) out from the sales file's columns (F3d)."""
        return _change(project_id, lambda p, d: wizard.set_rule(p, d, key, body))

    @app.get("/api/projects/{project_id}/wizard/locations")
    def wizard_locations(project_id: str) -> list[wizard.LocationField]:
        """The location fields the user named (F3d)."""
        return wizard.locations(_load(project_id), projects.project_dir(project_id) / "in")

    @app.put("/api/projects/{project_id}/wizard/locations/{name}")
    def wizard_location(project_id: str, name: str, body: WizardLocation) -> wizard.Wizard:
        """Load a parcel file's column as a location field the user names; no column removes it (F3d)."""
        return _change(project_id, lambda p, d: wizard.set_location(p, d, name, body.file, body.column))

    @app.put("/api/projects/{project_id}/wizard/custom/{name}")
    def wizard_custom(project_id: str, name: str, body: WizardCustom) -> wizard.Wizard:
        """Load a parcel file's column as a field the user names and classifies (land, building or other); no column
        removes it (F3d)."""
        return _change(
            project_id, lambda p, d: wizard.set_custom(p, d, name, body.file, body.column, body.group, body.type)
        )

    @app.put("/api/projects/{project_id}/wizard/layers/{name}")
    def wizard_layer(project_id: str, name: str, body: datafiles.Overlay | None = None) -> wizard.Wizard:
        """Use a file as a map layer (stamped onto parcels, or measured to); no body sets it aside (F3d)."""
        return _change(project_id, lambda p, d: wizard.set_overlay(p, d, name, body))

    @app.get("/api/projects/{project_id}/wizard/layers/{name}/map")
    def wizard_layer_map(project_id: str, name: str) -> wizard.LayerMap:
        """A map layer's shapes in degrees, and the parcel centres, for its map (F3d)."""
        project = _load(project_id)
        try:
            return wizard.layer_map(project, projects.project_dir(project_id) / "in", name)
        except LookupError as e:
            raise HTTPException(404, f"No such layer: {e}") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.get("/api/projects/{project_id}/wizard/map")
    def wizard_map(project_id: str) -> wizard.MapView:
        """Where the parcels are, and the centre polar coordinates are measured from (F3d)."""
        return wizard.map_view(_load(project_id), projects.project_dir(project_id) / "in")

    @app.put("/api/projects/{project_id}/center")
    def set_center(project_id: str, body: projects.Center | None = None) -> wizard.MapView:
        """Set the centre polar coordinates are measured from; none: the middle of the parcels (F3d)."""
        project = _load(project_id)
        project.center = body
        projects.save(project)
        projects.write_settings(project)
        return wizard.map_view(project, projects.project_dir(project_id) / "in")

    @app.post("/api/projects/{project_id}/wizard/files/{name}/dates")
    def wizard_dates(project_id: str, name: str, body: WizardDates) -> wizard.DatePreview:
        """A column read with a date format, as OpenAVMKit reads it (F3d)."""
        project = _load(project_id)
        _entry(project, name)
        try:
            return wizard.date_preview(project, projects.project_dir(project_id) / "in", name, body.column, body.format)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.post("/api/projects/{project_id}/wizard/files/{name}/numbers")
    def wizard_numbers(project_id: str, name: str, body: WizardNumbers) -> wizard.NumberPreview:
        """A money column read with a format, as OpenAVMKit reads it, with checks on the amounts (F3d)."""
        project = _load(project_id)
        _entry(project, name)
        try:
            return wizard.number_preview(
                project, projects.project_dir(project_id) / "in", name, body.key, body.column, body.format
            )
        except LookupError as e:
            raise HTTPException(404, f"{body.key} isn't an amount of money.") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.get("/api/projects/{project_id}/wizard/fields/{key}/candidates")
    def wizard_candidates(project_id: str, key: str) -> list[wizard.Candidate]:
        """Columns that look like quality or condition, checked over every row, side by side (F3d)."""
        try:
            return wizard.candidates(_load(project_id), projects.project_dir(project_id) / "in", key)
        except LookupError as e:
            raise HTTPException(404, f"{key} isn't quality or condition.") from e

    @app.post("/api/projects/{project_id}/wizard/fields/{key}/scale")
    def wizard_scale(project_id: str, key: str, body: WizardColumnRef) -> wizard.ScalePreview:
        """A quality/condition numbers column read with a meaning, against age and price (F3d)."""
        try:
            return wizard.scale_preview(
                _load(project_id),
                projects.project_dir(project_id) / "in",
                key,
                body.file,
                body.column,
                body.scale,
            )
        except LookupError as e:
            raise HTTPException(404, f"{key} isn't quality or condition.") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @app.post("/api/projects/{project_id}/wizard/fields/{key}/tiers")
    def wizard_tiers(project_id: str, key: str, body: WizardColumnRef) -> wizard.TiersPreview:
        """A category's tiers, worst to best, each with a number and what it sells for (F3d)."""
        try:
            return wizard.tiers_preview(
                _load(project_id), projects.project_dir(project_id) / "in", key, body.file, body.column
            )
        except LookupError as e:
            raise HTTPException(404, f"{key} isn't quality or condition.") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    # ---------- Step 1, Bring in data (SPEC §3.3) ----------

    def _bring_in_view(project: projects.Project) -> bring_in.View:
        return bring_in.view(project, projects.project_dir(project.id), _wizard(project).problems)

    @app.get("/api/projects/{project_id}/bring-in")
    def bring_in_state(project_id: str) -> bring_in.View:
        """Ready, running, or the receipt of the last run, and whether it's out of date."""
        return _bring_in_view(_load(project_id))

    @app.post("/api/projects/{project_id}/bring-in/run")
    def bring_in_run(project_id: str) -> bring_in.View:
        """Load and join the files with OpenAVMKit, in a process of its own."""
        project = _load(project_id)
        problems = _wizard(project).problems
        if problems:
            raise HTTPException(422, f"Fix on Data first: {problems[0]}")
        projects.write_settings(project)
        try:
            bring_in.start(project_id, projects.project_dir(project_id))
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        return _bring_in_view(project)

    @app.post("/api/projects/{project_id}/bring-in/stop")
    def bring_in_stop(project_id: str) -> bring_in.View:
        bring_in.stop(project_id)
        return _bring_in_view(_load(project_id))

    @app.post("/api/projects/{project_id}/bring-in/accept")
    def bring_in_accept(project_id: str) -> bring_in.View:
        """Looks right: model groups can start from this."""
        project = _load(project_id)
        try:
            bring_in.accept(project, projects.project_dir(project_id))
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        projects.save(project)
        return _bring_in_view(project)

    @app.get("/api/projects/{project_id}/bring-in/rows/{name}")
    def bring_in_rows(project_id: str, name: str, offset: int = 0, limit: int = bring_in.PAGE) -> bring_in.Rows:
        """A page of the rows behind a count (or of the parcel universe or sales record), read a page at a time."""
        _load(project_id)
        try:
            return bring_in.page(projects.project_dir(project_id), name, offset, limit)
        except LookupError as e:
            raise HTTPException(404, f"No rows called {name}: bring in data first.") from e

    @app.get("/api/projects/{project_id}/bring-in/rows/{name}/csv")
    def bring_in_csv(project_id: str, name: str) -> StreamingResponse:
        """The whole set as CSV, written a chunk at a time."""
        _load(project_id)
        pdir = projects.project_dir(project_id)
        try:
            chunks = bring_in.csv_chunks(pdir, name)
            first = next(chunks)
        except (LookupError, StopIteration) as e:
            raise HTTPException(404, f"No rows called {name}: bring in data first.") from e

        def body():
            yield first
            yield from chunks

        return StreamingResponse(
            body(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'}
        )

    # ---------- Step 2, Model groups (SPEC §3.5) ----------

    def _groups_view(project: projects.Project) -> groups.GroupsView:
        return groups.view(project, projects.project_dir(project.id))

    @app.get("/api/projects/{project_id}/groups")
    def groups_state(project_id: str) -> groups.GroupsView:
        """The model groups, and the parcel universe's fields a rule can test."""
        return _groups_view(_load(project_id))

    @app.post("/api/projects/{project_id}/groups/start")
    def groups_start(project_id: str, body: GroupsStart) -> groups.GroupsView:
        """Start from scratch (no groups yet) or from a suggested set made from the property-type fields."""
        project = _load(project_id)
        pdir = projects.project_dir(project_id)
        try:
            project.groups = groups.suggest(pdir) if body.how == "suggested" else []
        except LookupError as e:
            raise HTTPException(409, str(e)) from e
        project.groups_start = body.how
        projects.save(project)
        projects.write_settings(project)
        return _groups_view(project)

    @app.put("/api/projects/{project_id}/groups")
    def groups_save(project_id: str, body: GroupsBody) -> groups.GroupsView:
        """Save the groups, in order, and write them into the settings."""
        project = _load(project_id)
        project.groups = groups.clean(projects.project_dir(project_id), body.groups)
        project.groups_start = project.groups_start or "scratch"
        projects.save(project)
        projects.write_settings(project)
        return _groups_view(project)

    @app.post("/api/projects/{project_id}/groups/preview")
    def groups_preview(project_id: str, body: GroupsBody) -> groups.GroupsPreview:
        """Where each parcel lands under these groups (saved or not), each group's counts and checks, and what
        moved since the saved groups."""
        project = _load(project_id)
        try:
            return groups.preview(project, projects.project_dir(project_id), body.groups)
        except LookupError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/projects/{project_id}/groups/inspect")
    def groups_inspect(project_id: str, body: InspectBody) -> groups.ParcelInspect:
        """One parcel: its fields, its sales, and why it's in its group under these groups."""
        _load(project_id)
        try:
            return groups.inspect(projects.project_dir(project_id), body.groups, body.index)
        except LookupError as e:
            raise HTTPException(404, f"No parcel {body.index}.") from e

    @app.get("/api/projects/{project_id}/groups/values/{field}")
    def groups_values(project_id: str, field: str) -> groups.GroupValues:
        """A field's values, with parcels, vacant parcels and valid sales for each."""
        _load(project_id)
        try:
            return groups.values(projects.project_dir(project_id), field)
        except LookupError as e:
            raise HTTPException(404, f"No field {field} in the parcel universe.") from e

    @app.get("/api/projects/{project_id}/groups/shapes")
    def groups_shapes(project_id: str) -> FileResponse:
        """The parcel shapes as GeoJSON, in the parcel universe's order (a preview's indexes)."""
        _load(project_id)
        try:
            return FileResponse(groups.shapes_path(projects.project_dir(project_id)), media_type="application/geo+json")
        except LookupError as e:
            raise HTTPException(409, str(e)) from e

    @app.get("/api/dictionary")
    def dictionary(jurisdiction: str = "") -> list[fields.DictionaryField]:
        """OpenAVMKit's data dictionary: the fields a column can be loaded into (SPEC §3.0 F3c).

        With the project's jurisdiction, names say it where OpenAVMKit writes "{jurisdiction}".
        """
        return fields.dictionary(jurisdiction)

    @app.post("/api/date-format")
    def date_format(body: DateFormatCheck) -> fields.DateCheck:
        """Read sample values with a date format, as OpenAVMKit would (SPEC §3.0 F3c)."""
        return fields.check_dates(body.samples, body.format)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> ProjectDetail:
        project = _load(project_id)
        folder = projects.project_dir(project_id)
        return ProjectDetail(
            project=project, folder=str(folder), files=[_view(folder / "in", f) for f in project.files]
        )

    if WEB_DIST.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Any:
            candidate = WEB_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app

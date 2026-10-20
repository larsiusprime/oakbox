"""The app service: a local HTTP API for the UI, plus the built UI itself.

Binds to 127.0.0.1 only. The UI talks to it over JSON and server-sent events
(SPEC §6). Types are pydantic models, exported as OpenAPI for the TypeScript
client.
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from oakbox import __version__, appsettings, projects
from oakbox.jobs import JobManager
from oakbox.samples import SAMPLES

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


class SampleInfo(BaseModel):
    id: str
    name: str
    description: str


class JobInfo(BaseModel):
    id: str
    project_id: str
    step: str
    state: Literal["running", "done", "failed", "cancelled"]


class ProjectDetail(BaseModel):
    project: projects.Project
    running_job: JobInfo | None = None


class Stat(BaseModel):
    value: float | None = None
    low: float | None = None
    high: float | None = None


class RatioStats(BaseModel):
    count: int
    median_ratio: Stat
    cod: Stat
    prd: Stat


class VerticalStats(BaseModel):
    prd: Stat
    prb: Stat
    vei: float | None = None
    vei_significance: float | None = None


class HorizontalStats(BaseModel):
    parcels: int
    clusters: int
    median_chd: float | None = None


class GroupStudy(BaseModel):
    count_sales: int
    count_parcels: int
    ratio: RatioStats
    vertical: VerticalStats | None = None
    horizontal: HorizontalStats | None = None


class ValueStudy(BaseModel):
    field: str
    window: dict[str, str]
    confidence_interval: float
    groups: dict[str, GroupStudy]
    overall: GroupStudy


class Region(BaseModel):
    code: str
    name: str


class Regions(BaseModel):
    """ISO 3166-1 countries and, where OAK box lists them, ISO 3166-2 subdivisions."""

    countries: list[Region]
    subdivisions: dict[str, list[Region]]


class AppSettingsView(BaseModel):
    storage_location: str
    default_storage_location: str


class StorageLocation(BaseModel):
    storage_location: str | None = Field(default=None, description="None resets to the default.")


class DiskUsage(BaseModel):
    bytes: int
    files: int
    folder: str


def _regions() -> Regions:
    from importlib import resources

    return Regions.model_validate_json(resources.files("oakbox").joinpath("iso3166.json").read_text())


def _settings_view() -> AppSettingsView:
    return AppSettingsView(
        storage_location=str(appsettings.storage_location()),
        default_storage_location=str(appsettings.default_storage()),
    )


def _job_info(job) -> JobInfo:
    return JobInfo(id=job.id, project_id=job.project_id, step=job.step, state=job.state)


def create_app() -> FastAPI:
    pin_ui_content_types()
    app = FastAPI(title="OAK box", version=__version__)
    jobs = JobManager()

    @app.get("/api/version")
    def version() -> dict[str, str]:
        return {"version": __version__}

    @app.get("/api/samples")
    def list_samples() -> list[SampleInfo]:
        return [SampleInfo(id=s.id, name=s.name, description=s.description) for s in SAMPLES.values()]

    @app.post("/api/samples/{sample_id}")
    def create_from_sample(sample_id: str) -> JobInfo:
        """Create a project from a sample and start downloading its data."""
        sample = SAMPLES.get(sample_id)
        if sample is None:
            raise HTTPException(404, "Unknown sample")
        project = projects.create_from_sample(sample.answers(), sample.id)
        return _job_info(jobs.start(project.id, "download_sample"))

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
        if not 1900 <= body.tax_year <= 2200:
            raise HTTPException(422, "The tax year doesn't look right.")
        return projects.create(
            body.model_copy(update={"name": body.name.strip(), "jurisdiction": body.jurisdiction.strip()})
        )

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
        if jobs.running_for(project_id) is not None:
            raise HTTPException(409, "Stop the running step before deleting this project.")
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

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> ProjectDetail:
        project = _load(project_id)
        job = jobs.running_for(project_id)
        return ProjectDetail(project=project, running_job=_job_info(job) if job else None)

    @app.post("/api/projects/{project_id}/steps/{step}/run")
    def run_step(project_id: str, step: projects.StepId) -> JobInfo:
        project = _load(project_id)
        if project.answers is None:
            raise HTTPException(409, "This project has no data set up yet.")
        index = projects.STEP_ORDER.index(step)
        for earlier in projects.STEP_ORDER[:index]:
            if project.steps[earlier].state != "done":
                raise HTTPException(409, f"Run '{earlier}' first.")
        try:
            return _job_info(jobs.start(project_id, step))
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> JobInfo:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        jobs.cancel(job_id)
        return _job_info(job)

    @app.get("/api/jobs/{job_id}/events")
    def job_events(job_id: str) -> StreamingResponse:
        """Server-sent events: every event so far, then new ones until the job ends."""
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")

        def stream():
            seen = 0
            while True:
                job.wait_for(seen, timeout=15)
                events = job.events[seen:]
                seen += len(events)
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"
                if job.state != "running" and seen >= len(job.events):
                    yield f"event: end\ndata: {json.dumps({'state': job.state})}\n\n"
                    return
                if not events:
                    yield ": keep-alive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/projects/{project_id}/results/value-studies")
    def value_studies(project_id: str) -> list[ValueStudy]:
        project = _load(project_id)
        out = projects.project_dir(project_id) / "out" / "studies"
        results: list[ValueStudy] = []
        for field in project.answers.value_fields if project.answers else []:
            path = out / f"{field}.json"
            if path.exists():
                results.append(ValueStudy.model_validate(json.loads(path.read_text())))
        return results

    if WEB_DIST.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Any:
            candidate = WEB_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app

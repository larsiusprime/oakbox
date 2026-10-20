"""The app service: a local HTTP API for the UI, plus the built UI itself.

Binds to 127.0.0.1 only. The UI talks to it over JSON and server-sent events
(SPEC §6). Types are pydantic models, exported as OpenAPI for the TypeScript
client.
"""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict

from oakbox import __version__, fixedwidth, projects, sources
from oakbox.jobs import JobManager
from oakbox.samples import SAMPLES
from oakbox.settings_gen import generate
from oakbox.setup import Basics, FileUse, RowFilter, SourceFile, StageId, Stitch
from oakbox.stitcher import StitchReport

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


class CreateProject(BaseModel):
    name: str


class InspectRequest(BaseModel):
    path: str
    member: str | None = None


class FileDecisions(BaseModel):
    """What the user decides about one file on the Your files stage."""

    name: str
    uses: list[FileUse]
    id_columns: list[str]
    keep_columns: list[str] | None = None
    keep_rows: RowFilter | None = None


class AddFile(FileDecisions):
    path: str
    member: str | None = None


class AddExport(BaseModel):
    path: str
    members: list[str]


class StageCheck(BaseModel):
    """A stage's latest Check, and whether it still matches the current decisions."""

    fresh: bool
    ran: bool
    stitch: StitchReport | None = None


class HoodItem(BaseModel):
    title: str
    content: Any


class EngineCounts(BaseModel):
    parcels: int
    sales: int


class BringInReceipt(BaseModel):
    report: StitchReport
    engine: EngineCounts


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


def _job_info(job) -> JobInfo:
    return JobInfo(id=job.id, project_id=job.project_id, step=job.step, state=job.state)


CHECK_JOBS: dict[str, str] = {"files": "check_files", "stitch": "check_stitch"}


def _file_id(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")[:40] or "file"
    fid, n = base, 2
    while fid in taken:
        fid, n = f"{base}-{n}", n + 1
    return fid


def _stage_check(project: projects.Project, stage: StageId) -> StageCheck:
    data = projects.read_check(project.id, stage)
    if data is None:
        return StageCheck(fresh=False, ran=False)
    fresh = data.get("hash") == projects.decisions_hash(project.setup, stage)
    report = StitchReport.model_validate(data["report"]) if "report" in data else None
    return StageCheck(fresh=fresh, ran=True, stitch=report)


def _confirm_problem(project: projects.Project, stage: StageId) -> str | None:
    """Why a stage can't be confirmed yet, in plain words, or None."""
    blocked = projects.blocking_stage(project, before=stage)
    if blocked is not None:
        return f"Finish '{blocked}' first."
    setup = project.setup
    if stage == "basics" and not setup.basics.complete():
        return "Fill in the name, state, tax year and valuation date."
    if stage == "files":
        if not setup.files:
            return "Add at least one file."
        if not setup.files_for("parcel_map"):
            return "One file must be the parcel map."
        if any(not f.id_columns for f in setup.files):
            return "Every file needs its parcel ID column."
        if not _stage_check(project, "files").fresh:
            return "Run Check first, so every file is imported and measured."
    if stage == "stitch" and not _stage_check(project, "stitch").fresh:
        return "Run Check first, so you can see how the files fit together."
    if stage == "columns" and not setup.columns.value_fields:
        return "Matching columns arrives in the next version of OAK box. Only the sample can continue for now."
    if stage == "sales_basics" and setup.sales_basics is None:
        return "Sales basics arrives in the next version of OAK box. Only the sample can continue for now."
    return None


def _under_the_hood(project: projects.Project, stage: StageId) -> list[HoodItem]:
    setup = project.setup
    try:
        settings = generate(setup)
    except ValueError:
        settings = None
    load = (settings or {}).get("data", {}).get("load", {})
    if stage == "basics":
        return [
            HoodItem(
                title="settings.json: locality",
                content=(settings or {}).get("locality", setup.basics.model_dump(mode="json")),
            )
        ]
    if stage == "files":
        pdir = projects.project_dir(project.id)
        return [
            HoodItem(
                title="Files and their imported copies",
                content=[
                    {
                        **projects.stage_decisions(setup, "files")[i],
                        "imported_copy": str(sources.imported_path(pdir, f)),
                    }
                    for i, f in enumerate(setup.files)
                ],
            )
        ]
    if stage == "stitch":
        items = [
            HoodItem(
                title="Stitch plan (OAK box writes in/stitched/ from it)", content=setup.stitch.model_dump(mode="json")
            )
        ]
        if settings:
            items.append(
                HoodItem(
                    title="settings.json: what OpenAVMKit loads",
                    content={
                        "load": {k: {"filename": v["filename"]} for k, v in load.items()},
                        "merge": settings["data"]["process"]["merge"],
                    },
                )
            )
        return items
    if stage == "columns":
        return [HoodItem(title="settings.json: data.load.parcels", content=load.get("parcels"))]
    return [HoodItem(title="settings.json: data.load.sales", content=load.get("sales"))]


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
        project = projects.create_from_sample(sample.id)
        return _job_info(jobs.start(project.id, "download_sample"))

    @app.post("/api/projects")
    def create_project(body: CreateProject) -> projects.Project:
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Give the project a name.")
        return projects.create(name)

    @app.post("/api/inspect")
    def inspect_file(body: InspectRequest) -> sources.Inspection:
        """A quick look inside a file: format, columns, first rows, suggestions. Reads only the start."""
        return sources.inspect(body.path, body.member)

    def _editable(project_id: str) -> projects.Project:
        project = _load(project_id)
        job = jobs.running_for(project_id)
        if job is not None:
            raise HTTPException(409, f"Wait for '{job.step}' to finish first.")
        return project

    @app.put("/api/projects/{project_id}/basics")
    def put_basics(project_id: str, body: Basics) -> projects.Project:
        project = _editable(project_id)
        new = project.setup.model_copy(deep=True)
        new.basics = body
        return projects.change_setup(project, new, "Basics changed.")

    @app.post("/api/projects/{project_id}/files")
    def add_file(project_id: str, body: AddFile) -> projects.Project:
        project = _editable(project_id)
        insp = sources.inspect(body.path, body.member)
        if insp.format is None or insp.problem:
            raise HTTPException(422, insp.problem or "OAK box can't read this file.")
        new = project.setup.model_copy(deep=True)
        f = SourceFile(
            id=_file_id(body.member or body.name or Path(body.path).name, {x.id for x in new.files}),
            path=insp.path,
            size_bytes=insp.size_bytes,
            format=insp.format,
            **body.model_dump(exclude={"path"}),
        )
        new.files.append(f)
        if "parcel_map" in f.uses and new.stitch.spine is None:
            new.stitch.spine = f.id
        return projects.change_setup(project, new, "Files changed.")

    @app.post("/api/projects/{project_id}/exports")
    def add_export(project_id: str, body: AddExport) -> projects.Project:
        """Add the chosen files of a recognised fixed-width export, with OAK box's starting choices."""
        project = _editable(project_id)
        export = fixedwidth.detect_export(Path(body.path))
        if export is None:
            raise HTTPException(422, "This isn't an export OAK box recognises.")
        by_member = {m.member: m for m in export.members}
        new = project.setup.model_copy(deep=True)
        for member in body.members:
            m = by_member.get(member)
            if m is None:
                raise HTTPException(422, f"{member} isn't in this export.")
            d = fixedwidth.PACS_DEFAULTS.get(Path(member).name.upper())
            f = SourceFile(
                id=_file_id(member, {x.id for x in new.files}),
                name=f"{Path(member).name} ({m.label.lower()})",
                path=body.path,
                member=member,
                format="fixed_width",
                layout=export.layout_id,
                description=m.description,
                uses=[d.use] if d else ["parcels"],
                id_columns=[fixedwidth.ID_COLUMN["pacs"]],
                keep_columns=fixedwidth.default_columns(export.layout_id, member),
                keep_rows=d.keep_rows if d else None,
                size_bytes=m.size_bytes,
            )
            new.files.append(f)
            if d is not None:
                new.stitch.collapse[f.id] = d.collapse
        return projects.change_setup(project, new, "Files changed.")

    @app.put("/api/projects/{project_id}/files/{file_id}")
    def put_file(project_id: str, file_id: str, body: FileDecisions) -> projects.Project:
        project = _editable(project_id)
        new = project.setup.model_copy(deep=True)
        try:
            f = new.file(file_id)
        except KeyError:
            raise HTTPException(404, "File not found") from None
        before = (f.keep_columns, f.id_columns)
        for k, v in body.model_dump().items():
            setattr(f, k, v if k != "keep_rows" else body.keep_rows)
        if (f.keep_columns, f.id_columns) != before:
            f.imported = False  # the project's copy must be re-made
        if "parcel_map" in f.uses and new.stitch.spine is None:
            new.stitch.spine = f.id
        if "parcel_map" not in f.uses and new.stitch.spine == f.id:
            new.stitch.spine = next((x.id for x in new.files if "parcel_map" in x.uses), None)
        return projects.change_setup(project, new, "Files changed.")

    @app.delete("/api/projects/{project_id}/files/{file_id}")
    def delete_file(project_id: str, file_id: str) -> projects.Project:
        project = _editable(project_id)
        new = project.setup.model_copy(deep=True)
        new.files = [f for f in new.files if f.id != file_id]
        new.stitch.id_fixes.pop(file_id, None)
        new.stitch.collapse.pop(file_id, None)
        if new.stitch.spine == file_id:
            new.stitch.spine = next((x.id for x in new.files if "parcel_map" in x.uses), None)
        return projects.change_setup(project, new, "Files changed.")

    @app.put("/api/projects/{project_id}/stitch")
    def put_stitch(project_id: str, body: Stitch) -> projects.Project:
        project = _editable(project_id)
        new = project.setup.model_copy(deep=True)
        new.stitch = body
        return projects.change_setup(project, new, "The stitch plan changed.")

    @app.post("/api/projects/{project_id}/stages/{stage}/check")
    def run_check(project_id: str, stage: StageId) -> JobInfo:
        _load(project_id)
        job = CHECK_JOBS.get(stage)
        if job is None:
            raise HTTPException(422, "This stage's check is instant; there's nothing to run.")
        try:
            return _job_info(jobs.start(project_id, job))
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.get("/api/projects/{project_id}/stages/{stage}/check")
    def get_check(project_id: str, stage: StageId) -> StageCheck:
        return _stage_check(_load(project_id), stage)

    @app.post("/api/projects/{project_id}/stages/{stage}/confirm")
    def confirm(project_id: str, stage: StageId) -> projects.Project:
        project = _editable(project_id)
        problem = _confirm_problem(project, stage)
        if problem:
            raise HTTPException(409, problem)
        return projects.confirm_stage(project, stage)

    @app.get("/api/projects/{project_id}/stages/{stage}/under-the-hood")
    def under_the_hood(project_id: str, stage: StageId) -> list[HoodItem]:
        return _under_the_hood(_load(project_id), stage)

    @app.get("/api/projects/{project_id}/steps/bring_in_data/receipt")
    def bring_in_receipt(project_id: str) -> BringInReceipt:
        data = projects.read_check(project_id, "receipt-bring_in_data")
        if data is None:
            raise HTTPException(404, "Step 1 hasn't run yet.")
        return BringInReceipt.model_validate(data)

    @app.get("/api/projects")
    def list_projects() -> list[projects.Project]:
        return projects.list_projects()

    def _load(project_id: str) -> projects.Project:
        try:
            return projects.load(project_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Project not found") from None

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> ProjectDetail:
        project = _load(project_id)
        job = jobs.running_for(project_id)
        return ProjectDetail(project=project, running_job=_job_info(job) if job else None)

    @app.post("/api/projects/{project_id}/steps/{step}/run")
    def run_step(project_id: str, step: projects.StepId) -> JobInfo:
        project = _load(project_id)
        blocked = projects.blocking_stage(project)
        if blocked is not None:
            raise HTTPException(409, f"Finish the setup stage '{blocked}' first.")
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
        out = projects.project_dir(project_id) / "out" / "studies"
        project = _load(project_id)
        results: list[ValueStudy] = []
        for field in project.setup.columns.value_fields:
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

"""Step 1, Bring in data (SPEC §3.3): its run, skipping a part of it, and the rows and fields it brought in."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from oakbox import bring_in, projects, wizard
from oakbox.errors import NotFound
from oakbox.routes.common import bring_in_view, load_project, wizard_view

router = APIRouter()


# ---------- Step 1, Bring in data (SPEC §3.3) ----------


@router.post("/api/projects/{project_id}/bring-in/run")
def bring_in_run(project_id: str) -> bring_in.View:
    """Load and join the files with OpenAVMKit, in a process of its own."""
    with projects.lock(project_id):  # the settings it starts with are the project's as it stands
        project = load_project(project_id)
        problems = wizard_view(project).problems
        if problems:
            raise HTTPException(422, f"Fix on Data first: {problems[0]}")
        projects.write_settings(project)
        try:
            bring_in.STEP.start(project_id, projects.project_dir(project_id), [])
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
    return bring_in_view(project)


@router.post("/api/projects/{project_id}/bring-in/skip/{part}")
def bring_in_skip(project_id: str, part: str) -> bring_in.View:
    """Skip one part of the run while it runs (an enrichment): it stops at its next checkpoint, its fields left
    out, and the run carries on."""
    project = load_project(project_id)
    try:
        bring_in.skip(project_id, projects.project_dir(project_id), part)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return bring_in_view(project)


@router.get("/api/projects/{project_id}/bring-in/rows/{name}")
def bring_in_rows(project_id: str, name: str, offset: int = 0, limit: int = bring_in.PAGE) -> bring_in.Rows:
    """A page of the rows behind a count (or of the parcel universe or sales record), read a page at a time."""
    load_project(project_id)
    try:
        return bring_in.page(projects.project_dir(project_id), name, offset, limit)
    except NotFound as e:
        raise HTTPException(404, f"No rows called {name}: bring in data first.") from e


@router.get("/api/projects/{project_id}/bring-in/fields/{name}/{field}")
def bring_in_field(
    project_id: str,
    name: str,
    field: str,
    search: str = "",
    sort: wizard.ValueSort | None = None,
    desc: bool = True,
) -> bring_in.FieldProfile:
    """One field of the parcel universe or the sales record in detail: its statistics, or its values (sorted
    by count or value when asked)."""
    load_project(project_id)
    try:
        return bring_in.profile(projects.project_dir(project_id), name, field, search, sort, desc)
    except NotFound as e:
        raise HTTPException(404, f"No field {field} in {name}: bring in data first.") from e


@router.get("/api/projects/{project_id}/bring-in/rows/{name}/csv")
def bring_in_csv(project_id: str, name: str) -> StreamingResponse:
    """The whole set as CSV, written a chunk at a time."""
    load_project(project_id)
    pdir = projects.project_dir(project_id)
    try:
        chunks = bring_in.csv_chunks(pdir, name)
        first = next(chunks)
    except (NotFound, StopIteration) as e:
        raise HTTPException(404, f"No rows called {name}: bring in data first.") from e

    def body():
        yield first
        yield from chunks

    return StreamingResponse(
        body(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'}
    )

"""Step 3, Check sales (notebook 2's clean stage): its calls, the sales set aside, and the time adjustment
preview."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import clean, projects, time_preview
from oakbox.datafiles import BaseModel
from oakbox.routes.common import clean_view, load_project

router = APIRouter()


class BorrowBody(BaseModel):
    group: str
    source: str | None = Field(description="The group whose time adjustment it uses; null: its own.")


class TimeFileBody(BaseModel):
    path: str = Field(description="The CSV file on this computer.")


class FillChange(BaseModel):
    field: str
    method: clean.FillMethod
    scope: clean.FillScope = "all"


class CleanPatch(BaseModel):
    """Only the calls named change; null resets a year to the default."""

    sales_from: int | None = None
    time_adjust: bool | None = None
    period: clean.Period | None = None
    location: str | None = None
    checks: dict[str, bool] | None = None
    collapse: bool | None = None
    collapse_sales_min: int | None = Field(default=None, ge=1)
    nominal_below: int | None = Field(default=None, ge=1)
    collapse_univ_min: int | None = Field(default=None, ge=1)
    fill: FillChange | None = None


class MarkBody(BaseModel):
    action: Literal["keep", "exclude"] | None = Field(description="null: undo.")
    note: str = ""


# ---------- Step 3, Check sales: notebook 2 (clean) ----------


@router.get("/api/projects/{project_id}/clean/setup")
def clean_setup(project_id: str) -> clean.CleanSetup:
    """The calls before running, each with its default and what it does in numbers."""
    project = load_project(project_id)
    blocked = clean_view(project).blocked
    if blocked:
        raise HTTPException(409, blocked[0])
    try:
        return clean.setup(project, projects.project_dir(project_id))
    except FileNotFoundError as e:
        raise HTTPException(409, "Write step 2 first (Model groups): this starts from its hand-off.") from e


@router.patch("/api/projects/{project_id}/clean/setup")
def clean_change(project_id: str, body: CleanPatch) -> clean.CleanSetup:
    """Change a call. Proposals are written down at the first change, so the settings say them all."""
    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    c = project.clean
    blocked = clean_view(project).blocked
    if blocked:
        raise HTTPException(409, blocked[0])
    try:
        clean.decide(project, pdir)
    except FileNotFoundError as e:
        raise HTTPException(409, "Write step 2 first (Model groups): this starts from its hand-off.") from e
    for name in body.model_fields_set:
        value = getattr(body, name)
        if name == "checks":
            c.checks |= value or {}
        elif name == "fill":
            if value is not None:
                c.fills[value.field] = clean.Fill(method=value.method, scope=value.scope)
        else:
            setattr(c, name, value)
    projects.save(project)
    projects.write_settings(project)
    return clean.setup(project, pdir)


@router.post("/api/projects/{project_id}/clean/show")
def clean_show(project_id: str, what: Literal["output", "schedule", "scrutiny"] = "output", group: str = "") -> None:
    """Show what it wrote in the file manager: notebook 2's output, a group's time adjustment schedule, or the
    sales scrutiny reports."""
    load_project(project_id)
    out = projects.project_dir(project_id) / "out"
    if what == "schedule":
        projects.show_file(out / "time_adjustment" / group / "time_adjustment_schedule.csv")
    elif what == "scrutiny":
        projects.show_file(out / "sales_scrutiny" / "flags.parquet")
    else:
        first = next(iter(sorted((out / "look").glob("2-clean-universe*"))), None)
        projects.show_file(first or out / "look")


@router.get("/api/projects/{project_id}/clean/review")
def clean_review(
    project_id: str,
    group: str = "",
    check: str = "",
    status: Literal["", "undecided", "kept", "excluded"] = "",
    offset: int = 0,
    limit: int = 100,
    pattern: str = "",
) -> clean.ReviewPage:
    """The sales set aside, furthest from their group first; filtered by model group, check, status and pattern
    (1 to 5, other)."""
    project = load_project(project_id)
    return clean.review(
        project,
        projects.project_dir(project_id),
        group or None,
        check or None,
        status or None,
        offset,
        limit,
        pattern or None,
    )


@router.get("/api/projects/{project_id}/clean/review/{key_sale}")
def clean_sale(project_id: str, key_sale: str) -> clean.SaleDetail:
    """One sale set aside: its numbers, and the sales it was compared with."""
    project = load_project(project_id)
    try:
        return clean.detail(project, projects.project_dir(project_id), key_sale)
    except LookupError as e:
        raise HTTPException(404, f"No sale {key_sale} was set aside.") from e


@router.put("/api/projects/{project_id}/clean/marks/{key_sale}")
def clean_mark(project_id: str, key_sale: str, body: MarkBody) -> clean.CleanView:
    """Keep a sale set aside (with a note), exclude a sale, or undo either: it applies on the next run."""
    project = load_project(project_id)
    try:
        clean.mark(project, key_sale, body.action, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    projects.save(project)
    projects.write_settings(project)
    return clean_view(project)


@router.put("/api/projects/{project_id}/clean/time/borrow")
def clean_time_borrow(project_id: str, body: BorrowBody) -> clean.CleanSetup:
    """A model group uses another group's time adjustment (null: works it out from its own sales). Either way its
    own file, if it had one, is set aside."""
    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    ids = {g.id for g in project.groups}
    if body.group not in ids or (body.source is not None and (body.source not in ids or body.source == body.group)):
        raise HTTPException(422, "Pick two different model groups.")
    clean.decide(project, pdir)
    project.clean.time_files.pop(body.group, None)
    if body.source is None:
        project.clean.borrow.pop(body.group, None)
    else:
        project.clean.borrow[body.group] = body.source
    projects.save(project)
    projects.write_settings(project)
    return clean.setup(project, pdir)


@router.post("/api/projects/{project_id}/clean/time/file/{group}")
def clean_time_file(project_id: str, group: str, body: TimeFileBody) -> clean.TimeFileCheck:
    """Check a model group's own time adjustment file (OpenAVMKit reads it); if it can be used, keep it."""
    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    try:
        clean.decide(project, pdir)
        check = clean.time_file(project, pdir, group, Path(body.path).expanduser())
    except LookupError as e:
        raise HTTPException(404, f"No model group {group}.") from e
    if check.ok:
        projects.save(project)
        projects.write_settings(project)
    return check


@router.get("/api/projects/{project_id}/clean/time")
def clean_time(project_id: str) -> time_preview.TimePreview:
    """The time adjustment preview: how prices moved per model group, before Check sales runs."""
    project = load_project(project_id)
    return time_preview.view(project, projects.project_dir(project_id))


@router.post("/api/projects/{project_id}/clean/time/run")
def clean_time_run(project_id: str) -> time_preview.TimePreview:
    """Work out the time adjustment alone (seconds), with the calls as they are now."""
    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    try:
        clean.decide(project, pdir)
        projects.save(project)
        projects.write_settings(project)
        time_preview.start(project, pdir)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(409, str(e)) from e
    return time_preview.view(project, pdir)

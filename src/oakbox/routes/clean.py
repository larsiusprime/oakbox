"""Step 3, Check sales (notebook 2's clean stage): its calls, the sales set aside, and the time adjustment
preview."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import clean, projects, salereview, time_preview
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound
from oakbox.routes.common import clean_view, editing, load_project

router = APIRouter()


class BorrowBody(BaseModel):
    group: str
    source: str | None = Field(description="The group whose time adjustment it uses; null: its own.")


class TimeFileBody(BaseModel):
    path: str = Field(description="The CSV file on this computer.")


class FillChange(BaseModel):
    """Only what's named changes."""

    field: str
    method: clean.FillChoice | None = None
    split: bool | None = None
    vacant: clean.FillChoice | None = None


class IndexOnChange(BaseModel):
    group: str
    per: clean.IndexOn | None = Field(description="null: automatic (OpenAVMKit works it out from the sales).")


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
    index_on: IndexOnChange | None = None


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
    with editing(project_id, settings=True) as project:
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
                    old = c.fills.get(value.field, clean.Fill())
                    named = {k: getattr(value, k) for k in ("method", "split", "vacant")}
                    c.fills[value.field] = old.model_copy(update={k: v for k, v in named.items() if v is not None})
            elif name == "index_on":
                if value is not None and value.per is None:
                    c.per.pop(value.group, None)
                elif value is not None:
                    c.per[value.group] = value.per
            else:
                setattr(c, name, value)
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
) -> salereview.ReviewPage:
    """The sales set aside, furthest from their group first; filtered by model group, check, status and pattern
    (1 to 5, other)."""
    project = load_project(project_id)
    return salereview.review(
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
def clean_sale(project_id: str, key_sale: str) -> salereview.SaleDetail:
    """One sale set aside: its numbers, and the sales it was compared with."""
    project = load_project(project_id)
    try:
        return salereview.detail(project, projects.project_dir(project_id), key_sale)
    except NotFound as e:
        raise HTTPException(404, f"No sale {key_sale} was set aside.") from e


@router.put("/api/projects/{project_id}/clean/marks/{key_sale}")
def clean_mark(project_id: str, key_sale: str, body: MarkBody) -> clean.CleanView:
    """Keep a sale set aside (with a note), exclude a sale, or undo either: it applies on the next run."""
    with editing(project_id, settings=True) as project:
        try:
            salereview.mark(project, key_sale, body.action, body.note)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return clean_view(project)


@router.put("/api/projects/{project_id}/clean/time/borrow")
def clean_time_borrow(project_id: str, body: BorrowBody) -> clean.CleanSetup:
    """A model group uses another group's time adjustment (null: works it out from its own sales). Either way its
    own file, if it had one, is set aside."""
    with editing(project_id, settings=True) as project:
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
    return clean.setup(project, pdir)


@router.post("/api/projects/{project_id}/clean/time/file/{group}")
def clean_time_file(project_id: str, group: str, body: TimeFileBody) -> clean.TimeFileCheck:
    """Check a model group's own time adjustment file (OpenAVMKit reads it); if it can be used, keep it."""
    with projects.lock(project_id):  # saved only when the file can be used
        project = load_project(project_id)
        pdir = projects.project_dir(project_id)
        try:
            clean.decide(project, pdir)
            check = clean.time_file(project, pdir, group, Path(body.path).expanduser())
        except NotFound as e:
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


@router.get("/api/projects/{project_id}/clean/time/{group}")
def clean_time_group(project_id: str, group: str) -> time_preview.TimeDetail:
    """One group's index over time and every sale it's worked out from, as the last preview found them."""
    load_project(project_id)
    try:
        return time_preview.detail(projects.project_dir(project_id), group)
    except NotFound as e:
        raise HTTPException(404, f"No time adjustment worked out for {e}") from e


@router.post("/api/projects/{project_id}/clean/time/run")
def clean_time_run(project_id: str) -> time_preview.TimePreview:
    """Work out the time adjustment alone (seconds), with the calls as they are now."""
    with projects.lock(project_id):  # saved before the run starts, which reads it
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

"""Step 4, Check my values (F8): the ratio study's calls, and each sale studied for its chart and map."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from oakbox import projects, ratio
from oakbox.routes.common import load_project

router = APIRouter()


# ---------- Step 4, Check my values (F8) ----------


@router.get("/api/projects/{project_id}/ratio/setup")
def ratio_setup(project_id: str) -> ratio.RatioSetup:
    """The values to check, the window (proposed), the price, the targets and each group's class."""
    project = load_project(project_id)
    try:
        return ratio.setup(project, projects.project_dir(project_id))
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


@router.patch("/api/projects/{project_id}/ratio/setup")
def ratio_change(project_id: str, body: ratio.RatioPatch) -> ratio.RatioSetup:
    project = load_project(project_id)
    try:
        ratio.change(project, body)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    projects.save(project)
    try:
        return ratio.setup(project, projects.project_dir(project_id))
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{project_id}/ratio/map")
def ratio_map(project_id: str, field: str, group: str = "") -> list[ratio.MapPoint]:
    """Each sale studied with its place and ratio, for the map."""
    load_project(project_id)
    return ratio.map_points(projects.project_dir(project_id), field, group or None)


@router.get("/api/projects/{project_id}/ratio/points")
def ratio_points(project_id: str, field: str, group: str = "") -> list[tuple[float, float, bool]]:
    """Each sale studied: its price, its ratio, and whether it was trimmed."""
    load_project(project_id)
    return ratio.points(projects.project_dir(project_id), field, group or None)

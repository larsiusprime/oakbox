"""Step 2, Model groups (SPEC §3.5), and the end of notebook 1: tagging the groups and writing its output."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from oakbox import assemble, groups, projects
from oakbox.datafiles import BaseModel
from oakbox.routes.common import assemble_view, load_project

router = APIRouter()


class GroupsStart(BaseModel):
    how: Literal["scratch", "suggested"]


class GroupsBody(BaseModel):
    groups: list[projects.ModelGroup]


class AssembleExports(BaseModel):
    exports: list[Literal["gpkg", "shp", "csv"]]


class InspectBody(BaseModel):
    groups: list[projects.ModelGroup]
    index: int


# ---------- Step 2, Model groups (SPEC §3.5) ----------


def _groups_view(project: projects.Project) -> groups.GroupsView:
    return groups.view(project, projects.project_dir(project.id))


@router.get("/api/projects/{project_id}/groups")
def groups_state(project_id: str) -> groups.GroupsView:
    """The model groups, and the parcel universe's fields a rule can test."""
    return _groups_view(load_project(project_id))


@router.post("/api/projects/{project_id}/groups/start")
def groups_start(project_id: str, body: GroupsStart) -> groups.GroupsView:
    """Start from scratch (no groups yet) or from a suggested set made from the property-type fields."""
    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    try:
        project.groups = groups.suggest(pdir) if body.how == "suggested" else []
    except LookupError as e:
        raise HTTPException(409, str(e)) from e
    project.groups_start = body.how
    projects.save(project)
    projects.write_settings(project)
    return _groups_view(project)


@router.put("/api/projects/{project_id}/groups")
def groups_save(project_id: str, body: GroupsBody) -> groups.GroupsView:
    """Save the groups, in order, and write them into the settings."""
    project = load_project(project_id)
    project.groups = groups.clean(projects.project_dir(project_id), body.groups)
    project.groups_start = project.groups_start or "scratch"
    projects.save(project)
    projects.write_settings(project)
    return _groups_view(project)


@router.post("/api/projects/{project_id}/groups/preview")
def groups_preview(project_id: str, body: GroupsBody) -> groups.GroupsPreview:
    """Where each parcel lands under these groups (saved or not), each group's counts and checks, and what
    moved since the saved groups."""
    project = load_project(project_id)
    try:
        return groups.preview(project, projects.project_dir(project_id), body.groups)
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/api/projects/{project_id}/groups/inspect")
def groups_inspect(project_id: str, body: InspectBody) -> groups.ParcelInspect:
    """One parcel: its fields, its sales, and why it's in its group under these groups."""
    load_project(project_id)
    try:
        return groups.inspect(projects.project_dir(project_id), body.groups, body.index)
    except LookupError as e:
        raise HTTPException(404, f"No parcel {body.index}.") from e


@router.get("/api/projects/{project_id}/groups/values/{field}")
def groups_values(project_id: str, field: str) -> groups.GroupValues:
    """A field's values, with parcels, vacant parcels and valid sales for each."""
    load_project(project_id)
    try:
        return groups.values(projects.project_dir(project_id), field)
    except LookupError as e:
        raise HTTPException(404, f"No field {field} in the parcel universe.") from e


@router.get("/api/projects/{project_id}/groups/shapes")
def groups_shapes(project_id: str) -> FileResponse:
    """The parcel shapes as GeoJSON, in the parcel universe's order (a preview's indexes)."""
    load_project(project_id)
    try:
        return FileResponse(groups.shapes_path(projects.project_dir(project_id)), media_type="application/geo+json")
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{project_id}/groups/centres")
def groups_centres(project_id: str) -> FileResponse:
    """Each parcel's centre, [longitude, latitude] or null, in the parcel universe's order (a map drawn as dots)."""
    load_project(project_id)
    try:
        return FileResponse(groups.centres_path(projects.project_dir(project_id)), media_type="application/json")
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


# ---------- The end of notebook 1: tag model groups and write its output ----------


@router.put("/api/projects/{project_id}/assemble/exports")
def assemble_exports(project_id: str, body: AssembleExports) -> assemble.AssembleView:
    """Also write the output as GeoPackage, zipped Shapefile or CSV, for map viewers and spreadsheets."""
    project = load_project(project_id)
    project.assemble_exports = sorted(set(body.exports))
    projects.save(project)
    return assemble_view(project)


@router.post("/api/projects/{project_id}/assemble/show")
def assemble_show(project_id: str) -> None:
    """Show the written files (out/look/) in the file manager."""
    load_project(project_id)
    look = projects.project_dir(project_id) / "out" / "look"
    first = next(iter(sorted(look.glob("1-assemble-universe*"))), None)
    projects.show_file(first or look)

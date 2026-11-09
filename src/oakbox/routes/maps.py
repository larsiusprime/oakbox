"""The map window (SPEC §3.15): what it can show, the 🌐 Parcel Universe's shapes and centres, a field's values."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from oakbox import mapdata, projects
from oakbox.routes.common import load_project

router = APIRouter()


@router.get("/api/projects/{project_id}/map")
def map_info(project_id: str) -> mapdata.MapInfo:
    """Whether the map's shapes are ready (they're made in the background, started here if not), and the fields it
    can colour the parcels by."""
    project = load_project(project_id)
    return mapdata.info(project, projects.project_dir(project_id), projects.inputs_dir(project_id))


@router.get("/api/projects/{project_id}/map/shapes")
def map_shapes(project_id: str) -> FileResponse:
    """Every parcel's shape, in the universe file's order: binary, as groups._binary lays it out."""
    load_project(project_id)
    path = mapdata.file_of(projects.project_dir(project_id), "shapes")
    return FileResponse(path, media_type="application/octet-stream")


@router.get("/api/projects/{project_id}/map/centres")
def map_centres(project_id: str) -> FileResponse:
    """Every parcel's centre, longitude and latitude as float32 (NaN with no shape), in the universe file's order."""
    load_project(project_id)
    path = mapdata.file_of(projects.project_dir(project_id), "centres")
    return FileResponse(path, media_type="application/octet-stream")


@router.get("/api/projects/{project_id}/map/column")
def map_column(project_id: str, field: str) -> mapdata.MapColumn:
    """A field's value for each parcel (field: file:column, from the map's field list)."""
    project = load_project(project_id)
    return mapdata.column(project, projects.inputs_dir(project_id), field)

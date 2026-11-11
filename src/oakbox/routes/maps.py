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
def map_column(project_id: str, field: str, per: str = "") -> mapdata.MapColumn:
    """A field's value for each parcel (field: file:column, from the map's field list); per: divided by each
    parcel's building or land size (bldg, land)."""
    project = load_project(project_id)
    in_dir = projects.inputs_dir(project_id)
    c = mapdata.column(project, in_dir, field)
    return mapdata.per_size(project, in_dir, c, per) if per else c


@router.get("/api/projects/{project_id}/map/sales")
def map_sales(project_id: str, per: str = "") -> mapdata.MapSales:
    """Each sale at its parcel: its price, date, and whether it's valid and vacant (as the rules or columns say);
    per: its price divided by its parcel's building or land size (bldg, land)."""
    project = load_project(project_id)
    in_dir = projects.inputs_dir(project_id)
    d = mapdata.sales_kept(project, in_dir)
    return mapdata.sales_per_size(project, in_dir, d, per) if per else d


@router.get("/api/projects/{project_id}/map/problems")
def map_problems(project_id: str) -> mapdata.MapProblems:
    """The problems the map can show where they are (blank and repeated IDs, sales whose value differs from their
    parcel's), with how many."""
    project = load_project(project_id)
    return mapdata.problems(project, projects.inputs_dir(project_id))


@router.get("/api/projects/{project_id}/map/problem")
def map_problem(project_id: str, id: str) -> mapdata.MapProblem:  # noqa: A002 - the API's name for it
    """Which parcels (or sales) have one problem."""
    project = load_project(project_id)
    return mapdata.problem(project, projects.inputs_dir(project_id), id)


@router.get("/api/projects/{project_id}/map/parcel/{index}")
def map_parcel(project_id: str, index: int) -> mapdata.ParcelCard:
    """One parcel's card: its fields as each parcel file has it, and its sales beside it."""
    project = load_project(project_id)
    return mapdata.card(project, projects.inputs_dir(project_id), index)

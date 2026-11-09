"""6. Models › Outliers (SPEC F9): the outlying sales, one sale's context, what the misses have in common, the calls,
and the patches."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from oakbox import outliers, projects
from oakbox.errors import NotFound
from oakbox.routes.common import editing, load_project

router = APIRouter()


@router.get("/api/projects/{project_id}/outliers")
def outliers_view(project_id: str, group: str | None = None) -> outliers.OutlierView:
    """A model group's outliers (the first group with any, unless named), and every sale of it on the map."""
    project = load_project(project_id)
    return outliers.view(project, projects.project_dir(project_id), group)


@router.put("/api/projects/{project_id}/outliers/band")
def outliers_band(project_id: str, body: outliers.OutlierBand) -> outliers.OutlierView:
    """The ratio band outside which a sale is an outlier."""
    with editing(project_id) as project:
        project.outliers.low, project.outliers.high = body.low, body.high
    return outliers.view(project, projects.project_dir(project_id), None)


@router.get("/api/projects/{project_id}/outliers/sale/{key_sale}")
def outliers_sale(project_id: str, key_sale: str) -> outliers.OutlierDetail:
    """One sale: its comps, how it's unlike the others, what can be patched, where it can be moved."""
    project = load_project(project_id)
    try:
        return outliers.detail(project, projects.project_dir(project_id), key_sale)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/projects/{project_id}/outliers/common/{group}")
def outliers_common(project_id: str, group: str) -> outliers.OutlierCommon:
    """What a group's misses have in common: the fields the models' error lines up with, and the map."""
    project = load_project(project_id)
    try:
        return outliers.common(project, projects.project_dir(project_id), group)
    except NotFound as e:
        raise HTTPException(404, str(e)) from e


@router.put("/api/projects/{project_id}/outliers/call/{key_sale}")
def outliers_call(project_id: str, key_sale: str, body: outliers.OutlierCallBody) -> outliers.OutlierView:
    """The call on an outlying sale: invalid, the data, the group or the model. On the list until Apply my calls."""
    pdir = projects.project_dir(project_id)
    with editing(project_id, settings=True) as project:
        try:
            outliers.decide(project, pdir, key_sale, body)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return outliers.view(project, pdir, None)


@router.post("/api/projects/{project_id}/outliers/apply")
def outliers_apply(project_id: str) -> outliers.OutlierView:
    """Apply my calls: each done where it belongs (Check sales, Model groups, the patches). The steps they change are
    out of date after."""
    pdir = projects.project_dir(project_id)
    with editing(project_id, settings=True) as project:
        outliers.apply(project, pdir)
    return outliers.view(project, pdir, None)


@router.delete("/api/projects/{project_id}/outliers/call/{key_sale}")
def outliers_undo(project_id: str, key_sale: str) -> outliers.OutlierView:
    """Take back the call on a sale, and what it did."""
    with editing(project_id, settings=True) as project:
        outliers.undo(project, key_sale)
    return outliers.view(project, projects.project_dir(project_id), None)


@router.get("/api/projects/{project_id}/patches")
def patches_list(project_id: str) -> list[outliers.OutlierPatchRow]:
    """Every correction made to the parcels' data, in order."""
    return outliers.patch_rows(load_project(project_id))


@router.delete("/api/projects/{project_id}/patches/{i}")
def patches_remove(project_id: str, i: int) -> list[outliers.OutlierPatchRow]:
    with editing(project_id, settings=True) as project:
        try:
            outliers.remove_patch(project, i)
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
    return outliers.patch_rows(project)


@router.get("/api/projects/{project_id}/patches/csv")
def patches_csv(project_id: str) -> Response:
    """Every patch as CSV, for whoever keeps the data."""
    project = load_project(project_id)
    return Response(
        outliers.patches_csv(project),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="patches.csv"'},
    )

"""Step 4, Check my values (F8): the ratio study's calls, and each sale studied for its chart and map."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from oakbox import final, projects, ratio, report
from oakbox.errors import NotReady
from oakbox.routes.common import editing, load_project

router = APIRouter()


# ---------- Step 4, Check my values (F8) ----------


@router.get("/api/projects/{project_id}/ratio/setup")
def ratio_setup(project_id: str) -> ratio.RatioSetup:
    """The values to check, the window (proposed), the price, the targets and each group's class."""
    project = load_project(project_id)
    try:
        return ratio.setup(project, projects.project_dir(project_id))
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


@router.patch("/api/projects/{project_id}/ratio/setup")
def ratio_change(project_id: str, body: ratio.RatioPatch) -> ratio.RatioSetup:
    with editing(project_id) as project:
        try:
            ratio.change(project, body)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    try:
        return ratio.setup(project, projects.project_dir(project_id))
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{project_id}/ratio/map")
def ratio_map(project_id: str, field: str, group: str = "") -> list[ratio.MapPoint]:
    """Each sale studied with its place and ratio, for the map."""
    load_project(project_id)
    return ratio.map_points(projects.project_dir(project_id), field, group or None)


@router.get("/api/projects/{project_id}/ratio/boxes")
def ratio_boxes(project_id: str, field: str, group: str = "", region: str = "") -> ratio.VeiBoxes:
    """Each VEI group's ratios as a box, by sale and by the price level of the sale's region, for their charts."""
    load_project(project_id)
    return ratio.vei_boxes(projects.project_dir(project_id), field, group or None, region or None)


@router.get("/api/projects/{project_id}/ratio/similar")
def ratio_similar(project_id: str, field: str, group: str = "") -> ratio.SimilarPoints:
    """Every parcel with its group of similar parcels' spread of values (CHD), for Similar parcels' map."""
    load_project(project_id)
    return ratio.similar_points(projects.project_dir(project_id), field, group or None)


@router.get("/api/projects/{project_id}/ratio/regions")
def ratio_regions(project_id: str, field: str, region: str, group: str = "") -> ratio.RegionPoints:
    """Each sale studied by its region, and each region's median ratio, for Neighbourhood price levels' map."""
    load_project(project_id)
    return ratio.region_points(projects.project_dir(project_id), field, region, group or None)


@router.get("/api/projects/{project_id}/ratio/similar/group")
def ratio_similar_group(project_id: str, field: str, cluster: str) -> ratio.SimilarGroup:
    """One group of similar parcels: each parcel's ID, place and value, for the card on Similar parcels' map."""
    load_project(project_id)
    return ratio.similar_group(projects.project_dir(project_id), field, cluster)


@router.get("/api/projects/{project_id}/final/parcels")
def final_parcels(project_id: str) -> final.ParcelPoints:
    """Every parcel's place, model value, roll value and finished area, as columns, for Model values' map."""
    load_project(project_id)
    out = final.parcel_points(projects.project_dir(project_id))
    if out is None:
        raise HTTPException(404, "Finalize first: there are no model values yet.")
    return out


@router.get("/api/projects/{project_id}/final/sales")
def final_sales(project_id: str, which: final.SetKey = "oof", group: str = "") -> list[ratio.MapPoint]:
    """Each sale a set of sales judges the model values on, with its place and ratio, for the map."""
    load_project(project_id)
    return final.sale_points(projects.project_dir(project_id), which, group or None)


@router.get("/api/projects/{project_id}/ratio/points")
def ratio_points(project_id: str, field: str, group: str = "") -> list[tuple[float, float, bool]]:
    """Each sale studied: its price, its ratio, and whether it was trimmed."""
    load_project(project_id)
    return ratio.points(projects.project_dir(project_id), field, group or None)


# ---------- Step 7, Report (SPEC §4) ----------


@router.get("/api/projects/{project_id}/report")
def report_view(project_id: str) -> report.ReportView:
    """Whether there are values to report, the sets the report judges them on, its title, the export formats."""
    project = load_project(project_id)
    return report.view(project, projects.project_dir(project_id))


@router.patch("/api/projects/{project_id}/report")
def report_change(project_id: str, body: report.ReportPatch) -> report.ReportView:
    with editing(project_id) as project:
        try:
            report.change(project, body)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return report.view(project, projects.project_dir(project_id))


class ExportBody(BaseModel):
    format: report.Format


@router.post("/api/projects/{project_id}/report/export")
def report_export(project_id: str, body: ExportBody) -> report.ExportResult:
    """Every parcel's model value, beside the roll's, written to out/oakbox/report/export/."""
    project = load_project(project_id)
    try:
        return report.export(project, projects.project_dir(project_id), body.format)
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{project_id}/report/html", response_class=HTMLResponse)
def report_html(project_id: str) -> HTMLResponse:
    """The report as it is now (also written to out/oakbox/report/), to read, print or save as PDF."""
    project = load_project(project_id)
    try:
        path = report.write(project, projects.project_dir(project_id))
    except NotReady as e:
        raise HTTPException(409, str(e)) from e
    return HTMLResponse(path.read_text(encoding="utf-8"))


class ShowBody(BaseModel):
    path: str


@router.post("/api/projects/{project_id}/report/show")
def report_show(project_id: str, body: ShowBody) -> None:
    """Show a file the report step wrote in the file manager."""
    load_project(project_id)
    pdir = projects.project_dir(project_id)
    path = (pdir / body.path).resolve()
    if not path.is_relative_to(report.out_dir(pdir).resolve()):
        raise HTTPException(422, "Only the report's own files.")
    try:
        projects.show_file(path)
    except OSError as e:
        raise HTTPException(500, str(e)) from e


@router.post("/api/projects/{project_id}/report/open")
def report_open(project_id: str) -> str:
    """Write the report and open it in the computer's browser, to print or save as PDF. Its path, from the project."""
    import webbrowser

    project = load_project(project_id)
    pdir = projects.project_dir(project_id)
    try:
        path = report.write(project, pdir)
    except NotReady as e:
        raise HTTPException(409, str(e)) from e
    webbrowser.open(path.as_uri())
    return str(path.relative_to(pdir))

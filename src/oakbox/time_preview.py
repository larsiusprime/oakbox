"""A preview of time adjustment, before Check sales runs (SPEC F6): OpenAVMKit's own sales processing (the window,
validity, time adjustment per model group) on step 2's hand-off, nothing else. Seconds, not the whole run.

It runs in a process of its own (`python -m oakbox.time_preview <project id>`), in a scratch folder
(out/oakbox/time_preview/work/), because OpenAVMKit writes each group's schedule under the folder it runs in: the
last run's schedules stay as they were. The result is out/oakbox/time_preview/preview.json.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import assemble, cells, clean, steps
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound

if TYPE_CHECKING:
    from oakbox.projects import Project

MODULE = "time_preview"


def out_dir(project_dir: Path) -> Path:
    return steps.out_dir(project_dir, MODULE)


def settings_key(settings: dict, project_dir: Path) -> dict:
    """What the preview depends on: the data and model groups, the window, the time adjustment, validity rules."""
    process = settings.get("data", {}).get("process", {})
    return {
        "assemble": assemble.STEP.ran_at(project_dir),
        "use_sales_from": settings.get("modeling", {}).get("metadata", {}).get("use_sales_from"),
        "time_adjustment": process.get("time_adjustment"),
        "invalid_sales": process.get("invalid_sales"),
    }


def settings_hash(settings: dict, project_dir: Path) -> str:
    return steps.key_hash(settings_key(settings, project_dir))


class TimeGroup(BaseModel):
    id: str
    name: str
    color: str
    sales: int = Field(description="Valid sales in the window.")
    per_year: float | None = Field(description="Price change a year, percent; None: no adjustment (see why).")
    first: str | None
    last: str | None
    curve: list[float]
    per: Literal["impr", "land"] | None = Field(
        default=None, description="What the index is of: price per finished area (impr) or per land area."
    )
    per_chosen: bool = Field(default=False, description="What the index is of was chosen, not worked out.")
    period: Literal["M", "Q", "Y"] | None = Field(default=None, description="The period OpenAVMKit settled on.")
    periods: int = Field(default=0, description="Periods with sales of a size.")
    periods_ok: int = Field(default=0, description="Of them, periods with 5 or more: the ones the index is from.")
    why: str | None = Field(default=None, description="Why there's no adjustment, when there's none.")


class TimeSale(BaseModel):
    key_sale: str
    address: str | None
    date: str
    price: float
    per_area: float = Field(description="Price per area, of what the index is of.")
    adjusted: float | None = Field(description="The price brought forward by the time adjustment.")
    lon: float | None = Field(default=None, description="Where it is (its parcel's), for the step's map.")
    lat: float | None = None


class IndexPoint(BaseModel):
    day: str
    value: float


class TimeDetail(BaseModel):
    """One group's index over time, and every sale it's worked out from: the expanded chart."""

    index: list[IndexPoint] = Field(description="The index, a week apart.")
    sales: list[TimeSale]
    unit: Literal["sqft", "sqm"] = Field(default="sqft", description="What prices are per.")


MIN_PER_PERIOD = 5  # OpenAVMKit's min_sale_count: a period with fewer sales is interpolated across


class TimeResult(BaseModel):
    ran_at: str
    seconds: float
    groups: list[TimeGroup]


def run(project_id: str) -> None:
    import warnings

    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    src = steps.handoff(pdir, "1-assemble")
    if not src.is_file():
        raise RuntimeError("Write step 2 first (Model groups): this starts from its hand-off.")
    base = out_dir(pdir)
    work = base / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    settings_path = steps.settings_path(pdir)
    settings_text = settings_path.read_text(encoding="utf-8")
    os.chdir(work)
    from openavmkit import pipeline as pl
    from openavmkit import progress
    from openavmkit.data import SalesUniversePair, get_hydrated_sales_from_sup

    names = {g.id: g.name for g in project.groups} | {clean.UNKNOWN: "Unassigned"}
    base_message = "Working out how prices moved, per model group"

    def inside(e) -> None:
        if e.message == base_message:
            return
        detail = e.message.removeprefix(base_message + ": ")
        for gid, name in names.items():
            if detail.startswith(gid + " ("):
                detail = name + detail[len(gid) :]
        steps.emit(detail=detail, sub=e.sub)

    t0 = time.time()
    with warnings.catch_warnings(), progress.reporting(inside, stage="time_preview"), steps.heartbeat():
        warnings.simplefilter("ignore")
        steps.emit(step="load", fraction=0.0, message="Reading step 2's hand-off")
        sup = cast(SalesUniversePair, pd.read_pickle(src))
        settings = pl.load_settings(str(settings_path))
        # The groups' own files are named from the project folder; this runs in a scratch folder.
        ta = settings.get("data", {}).get("process", {}).get("time_adjustment", {})
        ta["from_file"] = {g: str(pdir / f) for g, f in ta.get("from_file", {}).items()}
        steps.emit(step="time", fraction=0.2, message=base_message)
        progress.report("time", 0.2, base_message)
        sup = pl.process_sales(sup=sup, settings=settings)
    hydrated = get_hydrated_sales_from_sup(sup)
    valid = hydrated[cells.yes(hydrated, "valid_sale")]
    groups = []
    details: dict[str, dict] = {}
    from oakbox import assemble

    modeled = assemble.modeled(project, pdir)
    for gid, name, color in [(g.id, g.name, g.color) for g in project.groups if g.id in modeled]:
        n = int((valid["model_group"].astype(str) == gid).sum()) if "model_group" in valid else 0
        schedule = work / "out" / "time_adjustment" / gid / "time_adjustment_schedule.csv"
        per_year, first, last, curve = clean.time_curve(schedule)
        g = TimeGroup(id=gid, name=name, color=color, sales=n, per_year=per_year, first=first, last=last, curve=curve)
        mine = cast(pd.DataFrame, valid[valid["model_group"].astype(str) == gid]) if "model_group" in valid else None
        if mine is not None and n:
            details[gid] = _diagnose(g, mine, settings, project.clean.period, schedule, project.clean.per.get(gid))
        elif per_year is None:
            g.why = "No sales in the window."
        groups.append(g)
    result = TimeResult(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1), groups=groups
    )
    (base / "detail.json").write_text(json.dumps(details), encoding="utf-8")
    (base / "preview.json").write_text(
        json.dumps({"hash": settings_hash(json.loads(settings_text), pdir), "result": result.model_dump()}),
        encoding="utf-8",
    )
    steps.emit(step="done", fraction=1.0, message="Done")


def _diagnose(g: TimeGroup, sales, settings: dict, period: str, schedule: Path, chosen: str | None = None) -> dict:
    """What OpenAVMKit's index for a group is of, the period it settled on, how many periods it's from, and why
    there's none when there's none (its own reasons, worked out as it works them out); and the group's sales and
    index for the expanded chart."""
    import pandas as pd
    from openavmkit.time_adjustment import determine_time_resolution, determine_value_driver
    from openavmkit.utilities.settings import area_unit

    unit = area_unit(settings)
    s = sales.copy()
    s["sale_date"] = pd.to_datetime(s["sale_date"], errors="coerce")
    s = s[s["sale_date"].notna()]
    s["sale_year"] = s["sale_date"].dt.year
    s["sale_year_month"] = s["sale_date"].dt.to_period("M").astype(str)
    s["sale_year_quarter"] = s["sale_date"].dt.to_period("Q").astype(str)
    price = cells.numbers(s, "sale_price")
    area = {k: cells.numbers(s, f"{f}_{unit}") for k, f in (("impr", "bldg_area_finished"), ("land", "land_area"))}
    sized = {k: int(a.gt(0).sum()) for k, a in area.items()}
    try:
        g.per = cast(Literal["impr", "land"], chosen or determine_value_driver(s, settings))
        g.per_chosen = chosen is not None
    except Exception:  # its own checks can fail on odd data: then the reason below says what's known
        g.per = "impr" if sized["impr"] else "land"
    per_area = price / area[g.per].where(area[g.per].gt(0))
    s["_per"] = per_area
    with_size = s[s["_per"].gt(0)]
    if len(with_size):
        try:
            g.period = cast(
                Literal["M", "Q", "Y"], determine_time_resolution(with_size, "_per", MIN_PER_PERIOD, period)
            )
        except Exception:
            g.period = None
        if g.period:
            column = {"M": "sale_year_month", "Q": "sale_year_quarter", "Y": "sale_year"}[g.period]
            counts = with_size.groupby(column).size()
            g.periods, g.periods_ok = len(counts), int(counts.ge(MIN_PER_PERIOD).sum())
    if g.per_year is None:
        what = "a finished area" if g.per == "impr" else "a land size"
        if not len(with_size):
            g.why = f"No sale has {what}: the index is of price per area, so there's nothing to work it out from."
        elif g.periods_ok == 0:
            word = {"M": "month", "Q": "quarter", "Y": "year"}.get(g.period or "Y", "year")
            g.why = (
                f"No {word} has {MIN_PER_PERIOD} sales with {what} (the index needs {MIN_PER_PERIOD} a period, even "
                f"by year): {len(with_size):,} of its {g.sales:,} sales have one."
            )
        else:
            g.why = "OpenAVMKit found no change in prices over the window."
    index: list[dict] = []
    if schedule.is_file():
        t = pd.read_csv(schedule)
        if "start_indexed" in t:
            t = t[cells.numbers(t, "start_indexed").notna()].iloc[::7]
            index = [
                {"day": str(p)[:10], "value": float(v)} for p, v in zip(t["period"], t["start_indexed"], strict=True)
            ]
    adjusted = cells.numbers(s, "sale_price_time_adj") if "sale_price_time_adj" in s else None
    out = [
        TimeSale(
            key_sale=str(k),
            address=cells.text(a),
            date=str(d.date()),
            price=float(p),
            per_area=float(pa),
            adjusted=cells.number(adjusted[i]) if adjusted is not None else None,
            lon=cells.number(lon),
            lat=cells.number(lat),
        ).model_dump()
        for i, k, a, d, p, pa, lon, lat in zip(
            s.index,
            s["key_sale"],
            s["address"] if "address" in s else [None] * len(s),
            s["sale_date"],
            price,
            per_area,
            cells.numbers(s, "longitude") if "longitude" in s else [None] * len(s),
            cells.numbers(s, "latitude") if "latitude" in s else [None] * len(s),
            strict=True,
        )
        if pa > 0
    ]
    return {"index": index, "sales": out, "unit": unit}


def detail(project_dir: Path, group: str) -> TimeDetail:
    path = out_dir(project_dir) / "detail.json"
    data = json.loads(path.read_text(encoding="utf-8")).get(group) if path.is_file() else None
    if data is None:
        raise NotFound(group)
    try:
        return TimeDetail.model_validate(data)
    except ValueError as e:  # written by an older OAK box: work it out again
        raise NotFound(group) from e


class TimePreview(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: steps.Job | None
    result: TimeResult | None
    stale: bool = Field(description="The window, the time adjustment, or the data changed since it ran.")


def view(project: Project, project_dir: Path) -> TimePreview:
    j = steps.job(project.id, MODULE)
    path = out_dir(project_dir) / "preview.json"
    result, stale = None, False
    if path.is_file():
        saved = json.loads(path.read_text(encoding="utf-8"))
        result = TimeResult.model_validate(saved["result"])
        stale = saved.get("hash") != settings_hash(steps.read_settings(project_dir), project_dir)
    return TimePreview(status=j.status if j else ("done" if result else "never"), job=j, result=result, stale=stale)


def start(project: Project, project_dir: Path) -> None:
    j = steps.job(project.id, MODULE)
    if j and j.status == "running":
        return
    blocked = clean.blocked(project, project_dir)
    if blocked:
        raise ValueError(blocked[0])
    steps.start(project.id, project_dir, MODULE)


if __name__ == "__main__":
    steps.main(run)

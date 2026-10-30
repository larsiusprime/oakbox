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
from typing import Literal, cast

from pydantic import Field

from oakbox import assemble, cells, clean, steps
from oakbox.datafiles import BaseModel

MODULE = "time_preview"


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "time_preview"


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
    per_year: float | None = Field(description="Price change a year, percent; None: no adjustment (too few sales).")
    first: str | None
    last: str | None
    curve: list[float]


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
    src = pdir / "out" / "1-assemble-sup.pickle"
    if not src.is_file():
        raise RuntimeError("Write step 2 first (Model groups): this starts from its hand-off.")
    base = out_dir(pdir)
    work = base / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    settings_path = pdir / "in" / "settings.json"
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
    for gid, name, color in [(g.id, g.name, g.color) for g in project.groups]:
        n = int((valid["model_group"].astype(str) == gid).sum()) if "model_group" in valid else 0
        per_year, first, last, curve = clean.time_curve(
            work / "out" / "time_adjustment" / gid / "time_adjustment_schedule.csv"
        )
        groups.append(
            TimeGroup(id=gid, name=name, color=color, sales=n, per_year=per_year, first=first, last=last, curve=curve)
        )
    result = TimeResult(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"), seconds=round(time.time() - t0, 1), groups=groups
    )
    (base / "preview.json").write_text(
        json.dumps({"hash": settings_hash(json.loads(settings_text), pdir), "result": result.model_dump()}),
        encoding="utf-8",
    )
    steps.emit(step="done", fraction=1.0, message="Done")


class TimePreview(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: steps.Job | None
    result: TimeResult | None
    stale: bool = Field(description="The window, the time adjustment, or the data changed since it ran.")


def view(project, project_dir: Path) -> TimePreview:
    j = steps.job(project.id, MODULE)
    path = out_dir(project_dir) / "preview.json"
    result, stale = None, False
    if path.is_file():
        saved = json.loads(path.read_text(encoding="utf-8"))
        result = TimeResult.model_validate(saved["result"])
        stale = saved.get("hash") != settings_hash(steps.read_settings(project_dir), project_dir)
    return TimePreview(status=j.status if j else ("done" if result else "never"), job=j, result=result, stale=stale)


def start(project, project_dir: Path) -> None:
    j = steps.job(project.id, MODULE)
    if j and j.status == "running":
        return
    blocked = clean.blocked(project, project_dir)
    if blocked:
        raise ValueError(blocked[0])
    steps.start(project.id, project_dir, MODULE)


if __name__ == "__main__":
    steps.main(run)

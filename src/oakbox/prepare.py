"""Step 5 begins: prepare the fields for the models (SPEC F7). The user's fills (blanks the models can't take) and the
folding of rare categories, applied to Check sales' hand-off, then notebook 2's output written again.

These are notebook 2's last calls in OpenAVMKit's order (its clean stage fills first and folds last), but nothing in
Check sales depends on them: they only change what the models learn from. So Check sales runs without them
(clean.without_fields) and keeps its hand-off (out/oakbox/clean/sup.pickle); this runs OpenAVMKit's own
`fill_unknown_values_sup` and `collapse_sparse_categories_sup` on it, in a process of its own
(`python -m oakbox.prepare <project id>`), and writes out/2-clean-sup.pickle and out/look/2-clean-*: the same
hand-off notebook 2 writes with the same settings. The receipt (out/oakbox/prepare/) says what was filled and folded.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import Field

from oakbox import assemble, clean, fields, steps
from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    from oakbox.projects import Project

MODULE = "prepare"


def out_dir(project_dir: Path) -> Path:
    return steps.out_dir(project_dir, MODULE)


def settings_key(settings: dict, project: Project, project_dir: Path) -> dict:
    """What this run depends on: the Check sales run it starts from, and the fills and folding."""
    process = settings.get("data", {}).get("process", {})
    return {
        "clean": clean.STEP.ran_at(project_dir),
        "fields": {k: process.get(k) for k in clean.FIELD_PROCESS},
    }


# ---------- The receipt ----------


class FieldFold(BaseModel):
    field: str
    name: str
    folded: list[str] = Field(description="The values that became Other.")
    parcels: int


class PrepareReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    filled: list[clean.Filled]
    folded: list[FieldFold]
    written: list[assemble.Written]
    notes: list[str] = Field(default_factory=list)


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    src = clean.out_dir(pdir) / "sup.pickle"
    if not src.is_file():
        raise RuntimeError("Check sales first: this starts from what it wrote.")
    tmp = steps.workdir(out_dir(pdir))
    depends = STEP.now(project, pdir)  # what it starts from, before anything can change
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import SalesUniversePair

    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught, steps.heartbeat():
        warnings.simplefilter("always")
        steps.emit(step="load", fraction=0.0, message="Reading what Check sales wrote")
        sup = cast(SalesUniversePair, pd.read_pickle(src))
        settings = pl.load_settings()
        before = sup.universe.copy()
        steps.emit(step="fill", fraction=0.2, message="Filling blanks")
        sup = pl.fill_unknown_values_sup(sup, settings)
        steps.emit(step="collapse", fraction=0.5, message="Folding rare categories")
        sup = pl.collapse_sparse_categories_sup(sup, settings)
        steps.emit(step="write", fraction=0.7, message="Writing notebook 2's output")
        pl.write_notebook_output_sup(sup, "2-clean")
    steps.written(caught, "notebook 2's output")
    steps.emit(step="receipt", fraction=0.95, message="Counting")

    names = fields.names()
    filled: list[clean.Filled] = []
    fp = pdir / "out" / "filled.parquet"
    if fp.is_file():
        f = pd.read_parquet(fp)
        for col in f.columns:
            if col not in project.clean.fills:
                continue  # OpenAVMKit's own tidy-ups (UNKNOWN categories) ran in Check sales
            how = project.clean.fills.get(col)
            words = clean.fill_words(col, how) if how else "OpenAVMKit's own"
            filled.append(clean.Filled(field=col, name=names.get(col) or col, count=int(f[col].sum()), how=words))
    folded: list[FieldFold] = []
    for field in settings.get("data", {}).get("process", {}).get("collapse_sparse_categories", {}):
        if field == "strict" or field not in before or field not in sup.universe:
            continue
        was, now = before[field].astype(str), sup.universe[field].astype(str)
        changed = was != now
        if changed.any():
            folded.append(
                FieldFold(
                    field=field,
                    name=names.get(field) or field,
                    folded=sorted(set(was[changed])),
                    parcels=int(changed.sum()),
                )
            )
    written = []
    for path in [steps.handoff(pdir, "2-clean"), *sorted(steps.look_dir(pdir).glob("2-clean-*"))]:
        if path.is_file():
            written.append(
                assemble.Written(
                    path=path.relative_to(pdir).as_posix(),
                    what=steps.what_written(path.name),
                    bytes=path.stat().st_size,
                )
            )
    mine = steps.engine_notes(caught)
    receipt = PrepareReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        filled=filled,
        folded=folded,
        written=written,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": depends}), encoding="utf-8")
    steps.publish(tmp, out_dir(pdir))
    n = sum(x.count for x in filled)
    steps.emit(step="done", fraction=1.0, message=f"{n:,} values filled, {len(folded)} fields folded")


# ---------- The step's state ----------


class PrepareView(steps.RunView):
    receipt: PrepareReceipt | None
    accepted: bool


STEP = steps.Step(
    MODULE,
    "Prepare the fields",
    PrepareReceipt,
    key=lambda project, pdir: settings_key(steps.read_settings(pdir), project, pdir),
    after=clean.STEP,
    again="Prepare the fields again first: something changed since it ran.",
    place="Variables › What changed",
)


def blocked(project: Project, project_dir: Path) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    if not (clean.out_dir(project_dir) / "sup.pickle").is_file():
        return ["Run Check sales again first: this starts from what it wrote."]
    return []


def view(project: Project, project_dir: Path) -> PrepareView:
    s = STEP.state(project, project_dir)
    return PrepareView(
        status=s.status,
        job=s.job,
        receipt=s.receipt,
        stale=s.stale,
        blocked=blocked(project, project_dir),
        accepted=s.accepted,
    )


def start(project: Project, project_dir: Path) -> None:
    STEP.start(project.id, project_dir, blocked(project, project_dir))


if __name__ == "__main__":
    steps.main(run)

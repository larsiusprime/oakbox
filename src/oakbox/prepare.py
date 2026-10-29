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
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from oakbox import assemble, bring_in, clean
from oakbox.datafiles import BaseModel

MODULE = "prepare"


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "prepare"


def settings_key(settings: dict, project, project_dir: Path) -> dict:
    """What this run depends on: the Check sales run it starts from, and the fills and folding."""
    process = settings.get("data", {}).get("process", {})
    r, _ = clean._ran(project_dir)
    return {
        "clean": r.ran_at if r else None,
        "fields": {k: process.get(k) for k in clean.FIELD_PROCESS},
    }


def settings_hash(settings: dict, project, project_dir: Path) -> str:
    text = json.dumps(settings_key(settings, project, project_dir), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


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
    tmp = out_dir(pdir).with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    settings_text = (pdir / "in" / "settings.json").read_text(encoding="utf-8")
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import SalesUniversePair

    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bring_in._emit(step="load", fraction=0.0, message="Reading what Check sales wrote")
        sup = cast(SalesUniversePair, pd.read_pickle(src))
        settings = pl.load_settings()
        before = sup.universe.copy()
        bring_in._emit(step="fill", fraction=0.2, message="Filling blanks")
        sup = pl.fill_unknown_values_sup(sup, settings)
        bring_in._emit(step="collapse", fraction=0.5, message="Folding rare categories")
        sup = pl.collapse_sparse_categories_sup(sup, settings)
        bring_in._emit(step="write", fraction=0.7, message="Writing notebook 2's output")
        pl.write_notebook_output_sup(sup, "2-clean")
    bring_in.written(caught, "notebook 2's output")
    bring_in._emit(step="receipt", fraction=0.95, message="Counting")

    names = clean._names()
    filled: list[clean.Filled] = []
    fp = pdir / "out" / "filled.parquet"
    if fp.is_file():
        f = pd.read_parquet(fp)
        for col in f.columns:
            if col not in project.clean.fills:
                continue  # OpenAVMKit's own tidy-ups (UNKNOWN categories) ran in Check sales
            how = project.clean.fills.get(col)
            words = (
                f"{how.method}{'' if how.scope == 'all' else ' (' + how.scope + ' only)'}"
                if how
                else "OpenAVMKit's own"
            )
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
    for path in [pdir / "out" / "2-clean-sup.pickle", *sorted((pdir / "out" / "look").glob("2-clean-*"))]:
        if path.is_file():
            written.append(
                assemble.Written(
                    path=path.relative_to(pdir).as_posix(), what=clean._what(path.name), bytes=path.stat().st_size
                )
            )
    mine = [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]
    receipt = PrepareReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        filled=filled,
        folded=folded,
        written=written,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    s = json.loads(settings_text)
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": settings_hash(s, project, pdir)}), encoding="utf-8")
    final = out_dir(pdir)
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    n = sum(x.count for x in filled)
    bring_in._emit(step="done", fraction=1.0, message=f"{n:,} values filled, {len(folded)} fields folded")


# ---------- The step's state ----------


class PrepareView(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: bring_in.Job | None
    receipt: PrepareReceipt | None
    stale: bool = Field(description="Check sales ran again, or a fill or the folding changed, since it ran.")
    blocked: list[str]
    accepted: bool


def _ran(project_dir: Path) -> tuple[PrepareReceipt | None, dict | None]:
    base = out_dir(project_dir)
    if not (base / "receipt.json").is_file():
        return None, None
    ran = (
        json.loads((base / "settings.json").read_text(encoding="utf-8")) if (base / "settings.json").is_file() else None
    )
    return PrepareReceipt.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran


def current_hash(project, project_dir: Path) -> str:
    return settings_hash(clean._settings(project_dir), project, project_dir)


def view(project, project_dir: Path) -> PrepareView:
    r, ran = _ran(project_dir)
    j = bring_in.job(project.id, MODULE)
    now = current_hash(project, project_dir)
    stale = bool(r and ran and ran.get("hash") != now)
    blocked = []
    c = clean.view(project, project_dir)
    if not c.accepted or not (clean.out_dir(project_dir) / "sup.pickle").is_file():
        blocked.append("Press Looks right on Check sales first: this starts from what it wrote.")
    return PrepareView(
        status=j.status if j else ("done" if r else "never"),
        job=j,
        receipt=r,
        stale=stale,
        blocked=blocked,
        accepted=bool(r and not stale and project.accepted.get(MODULE) == now),
    )


def start(project, project_dir: Path) -> None:
    v = view(project, project_dir)
    if v.blocked:
        raise ValueError(v.blocked[0])
    bring_in.start(project.id, project_dir, MODULE)


def accept(project, project_dir: Path) -> None:
    v = view(project, project_dir)
    if v.receipt is None or v.stale:
        raise ValueError("Prepare the fields again first: something changed since it ran.")
    project.accepted[MODULE] = current_hash(project, project_dir)


if __name__ == "__main__":
    from oakbox.net import use_system_certificates

    use_system_certificates()
    try:
        run(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - the app shows the last line of the log
        import traceback

        traceback.print_exc()
        print(f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

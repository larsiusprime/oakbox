"""The end of notebook 1 (assemble): OpenAVMKit tags each parcel with its model group and writes the notebook's
output, the hand-off to cleaning (SPEC §3.5, step 2's run).

It starts from what Bring in data left (out/oakbox/bring_in/sup.pickle), so nothing is loaded again, and runs
OpenAVMKit's own `tag_model_groups_sup` and `write_notebook_output_sup("1-assemble")`, in a process of its own:
`python -m oakbox.assemble <project id>`. That writes out/1-assemble-sup.pickle and, in out/look/, the parcel
universe, the sales and the hydrated sales (Parquet, and GeoPackage, zipped Shapefile or CSV when asked for) to
look at in a map viewer. The receipt (out/oakbox/assemble/) counts what each model group got.
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

from oakbox import bring_in
from oakbox.datafiles import BaseModel

MODULE = "assemble"
UNKNOWN = "UNKNOWN"  # OpenAVMKit's model group for parcels no group's rule meets


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "assemble"


def settings_key(settings: dict, exports: list[str]) -> dict:
    """What this run depends on: what Bring in data depends on, the model groups, and the formats written."""
    return {
        **bring_in.settings_key(settings),
        "model_groups": settings.get("modeling", {}).get("model_groups"),
        "exports": sorted(exports),
    }


def settings_hash(settings: dict, exports: list[str]) -> str:
    text = json.dumps(settings_key(settings, exports), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ---------- The receipt ----------


class GroupCount(BaseModel):
    id: str = Field(description=f'The model_group value; "{UNKNOWN}" for parcels in no group.')
    name: str
    parcels: int
    vacant: int = Field(description="Parcels without a building.")
    sales: int = Field(description="Valid improved sales.")
    vacant_sales: int
    preview: int | None = Field(description="Parcels the builder's preview put in it, to compare.")


class Written(BaseModel):
    path: str = Field(description="Relative to the project folder.")
    what: str
    bytes: int


class AssembleReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    groups: list[GroupCount]
    parcels: int
    sales: int
    written: list[Written]
    matches_preview: bool
    notes: list[str] = Field(default_factory=list, description="OpenAVMKit's own warnings, if any.")


WHAT = {
    "1-assemble-sup.pickle": "the parcel universe and sales together: what notebook 2 (clean) starts from",
    "1-assemble-universe": "the parcel universe, with each parcel's model group",
    "1-assemble-sales-hydrated": "the sales, each with its parcel's fields and model group",
    "1-assemble-sales": "the sales record",
}


def _what(name: str) -> str:
    for prefix, what in WHAT.items():
        if name.startswith(prefix):
            return what
    return ""


def _emit(**kw) -> None:
    print(json.dumps(kw), flush=True)


def run(project_id: str) -> None:
    """Tag model groups and write notebook 1's output; then the receipt."""
    import warnings
    from importlib.metadata import version

    import pandas as pd

    from oakbox import groups as groups_mod
    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    src = bring_in.out_dir(pdir) / "sup.pickle"
    if not src.is_file():
        raise RuntimeError("Bring in data first: this starts from what it loaded.")
    tmp = out_dir(pdir).with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    settings_text = (pdir / "in" / "settings.json").read_text(encoding="utf-8")
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import SalesUniversePair, get_hydrated_sales_from_sup

    t0 = time.time()
    exports = set(project.assemble_exports)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _emit(step="load", fraction=0.0, message="Reading what Bring in data loaded")
        sup = cast("SalesUniversePair", pd.read_pickle(src))
        _emit(step="tag", fraction=0.2, message="Tagging each parcel with its model group")
        sup = pl.tag_model_groups_sup(sup, pl.load_settings(), verbose=False)
        _emit(step="write", fraction=0.6, message="Writing notebook 1's output")
        pl.write_notebook_output_sup(
            sup, "1-assemble", parquet=True, gpkg="gpkg" in exports, shp="shp" in exports, csv="csv" in exports
        )
    bring_in.written(caught, "notebook 1's output")
    _emit(step="receipt", fraction=0.9, message="Counting")

    universe = sup.universe
    hydrated = get_hydrated_sales_from_sup(sup)
    valid = hydrated[hydrated["valid_sale"].fillna(False).astype(bool)] if "valid_sale" in hydrated else hydrated
    vacant_sale = (
        pd.Series(valid["vacant_sale"]).fillna(False).astype(bool) if "vacant_sale" in valid else pd.Series(False)
    )
    is_vacant = universe["is_vacant"].fillna(False).astype(bool) if "is_vacant" in universe else None

    # The builder's preview on the same parcel universe, to check it against what OpenAVMKit did.
    u, _ = groups_mod._data(pdir)
    assigned, _ = groups_mod.assign(u, groups_mod.numeric_fields(pdir, project.groups))
    preview = {g.id: int((assigned == i).sum()) for i, g in enumerate(project.groups)}
    preview[UNKNOWN] = int((assigned == -1).sum())

    counts = []
    for gid, name in [*((g.id, g.name) for g in project.groups), (UNKNOWN, "Unassigned")]:
        in_group = universe["model_group"] == gid
        sold = valid["model_group"] == gid
        counts.append(
            GroupCount(
                id=gid,
                name=name,
                parcels=int(in_group.sum()),
                vacant=int((in_group & is_vacant).sum()) if is_vacant is not None else 0,
                sales=int((sold & ~vacant_sale).sum()),
                vacant_sales=int((sold & vacant_sale).sum()),
                preview=preview.get(gid),
            )
        )
    written = []
    for path in [pdir / "out" / "1-assemble-sup.pickle", *sorted((pdir / "out" / "look").glob("1-assemble-*"))]:
        if path.is_file():
            rel = path.relative_to(pdir).as_posix()
            written.append(Written(path=rel, what=_what(path.name), bytes=path.stat().st_size))
    mine = [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]
    receipt = AssembleReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        groups=counts,
        parcels=len(universe),
        sales=len(valid),
        written=written,
        matches_preview=all(c.parcels == c.preview for c in counts),
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(
        json.dumps({"settings": json.loads(settings_text), "exports": sorted(exports)}), encoding="utf-8"
    )
    final = out_dir(pdir)
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    n = sum(1 for c in counts if c.id != UNKNOWN and c.parcels)
    _emit(step="done", fraction=1.0, message=f"{len(universe):,} parcels in {n} model groups")


# ---------- The step's state ----------


class AssembleView(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: bring_in.Job | None
    receipt: AssembleReceipt | None
    stale: bool = Field(description="The data, the model groups or the formats changed since it ran.")
    blocked: list[str] = Field(description="What stops it running.")
    exports: list[Literal["gpkg", "shp", "csv"]]
    accepted: bool


def _ran(project_dir: Path) -> tuple[AssembleReceipt | None, dict | None]:
    base = out_dir(project_dir)
    if not (base / "receipt.json").is_file():
        return None, None
    ran = (
        json.loads((base / "settings.json").read_text(encoding="utf-8")) if (base / "settings.json").is_file() else None
    )
    return AssembleReceipt.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran


def current_hash(project, project_dir: Path) -> str:
    settings = json.loads((project_dir / "in" / "settings.json").read_text(encoding="utf-8"))
    return settings_hash(settings, list(project.assemble_exports))


def view(project, project_dir: Path) -> AssembleView:
    settings = json.loads((project_dir / "in" / "settings.json").read_text(encoding="utf-8"))
    r, ran = _ran(project_dir)
    j = bring_in.job(project.id, MODULE)
    now = settings_hash(settings, list(project.assemble_exports))
    stale = bool(r and ran and settings_hash(ran["settings"], ran.get("exports", [])) != now)
    blocked = []
    if not project.groups:
        blocked.append("Add at least one model group, and save.")
    b, b_ran = bring_in.receipt(project_dir)
    if b is None or b_ran is None or bring_in.settings_hash(b_ran) != bring_in.settings_hash(settings):
        blocked.append("Bring in data again first: Data changed since it ran.")
    return AssembleView(
        status=j.status if j else ("done" if r else "never"),
        job=j,
        receipt=r,
        stale=stale,
        blocked=blocked,
        exports=list(project.assemble_exports),
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
        raise ValueError("Run it again first: the data or the model groups changed since it ran.")
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

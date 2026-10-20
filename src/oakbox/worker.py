"""Worker: runs one Oakbox job in its own process.

Usage: python -m oakbox.worker <project-id> <job>

Jobs are the engine steps (bring_in_data, ...) and the setup stages' longer
checks (check_files imports and measures the user's files; check_stitch measures
the stitch plan). Only engine steps import OpenAVMKit.

The app service starts one worker per job (SPEC §6): OpenAVMKit changes the
working directory, uses a lot of memory and can crash, so it never runs inside
the app process. The worker writes one JSON event per line to stdout:

    {"type": "progress", "step": ..., "fraction": ..., "message": ...}
    {"type": "done", "message": ...}
    {"type": "error", "message": ..., "detail": ...}

Cancellation: the app creates ``out/.oakbox-cancel``; the engine checks for it
at every progress point.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any

from oakbox import projects, sources, stitcher
from oakbox.samples import SAMPLES, download

CANCEL_FILE = ".oakbox-cancel"


_events = sys.stdout


def emit(kind: str, **fields: Any) -> None:
    _events.write(json.dumps({"type": kind, **fields}, default=str) + "\n")
    _events.flush()


def _route_engine_output_to_stderr() -> None:
    """Keep stdout for events only: everything else written to fd 1 goes to stderr.

    Works at the file-descriptor level, so native libraries (LightGBM, CatBoost)
    that print directly are redirected too.
    """
    global _events
    sys.stdout.flush()
    _events = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr


def _cancel_check(pdir: Path):
    flag = pdir / "out" / CANCEL_FILE
    return lambda: flag.exists()


def _on_progress(event) -> None:
    emit("progress", step=event.step, fraction=event.fraction, message=event.message)


def _reporter(step: str):
    return lambda fraction, message: emit("progress", step=step, fraction=fraction, message=message)


def run(project_id: str, step: str) -> str:
    """Run a job and return a one-line summary."""
    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    cancel = _cancel_check(pdir)

    if step == "download_sample":
        sample = SAMPLES[project.sample or ""]
        emit("progress", step="download", fraction=0.0, message="Downloading sample county")
        total = download(
            sample,
            pdir / "in",
            lambda done, size, name: emit(
                "progress",
                step="download",
                fraction=done / size if size else None,
                message=f"Downloading {name} ({done // 2**20} of {size // 2**20} MB)",
            ),
        )
        return f"Downloaded {total / 2**20:.0f} MB"

    if step == "check_files":
        return _check_files(project, pdir, cancel)

    if step == "check_stitch":
        report = stitcher.run(pdir, project.setup, write=False, on_progress=_reporter("stitch"))
        projects.save_check(
            project_id,
            "stitch",
            {"hash": projects.decisions_hash(project.setup, "stitch"), "report": report.model_dump(mode="json")},
        )
        return f"{report.parcels:,} parcels, {report.sales:,} sales"

    from openavmkit import progress
    from openavmkit.headless import run_stage

    if step == "bring_in_data":
        report = stitcher.run(pdir, project.setup, write=True, on_progress=_reporter("stitch"))
        _fill_center(project, pdir)
        projects.write_settings(project)
        run_stage(pdir, "assemble", _on_progress, cancel)
        engine = _counts(pdir, "1-assemble")
        projects.save_check(
            project_id,
            "receipt-bring_in_data",
            {"report": report.model_dump(mode="json"), "engine": engine},
        )
        return f"{engine['parcels']:,} parcels, {engine['sales']:,} sales"

    if step == "model_groups":
        # M1: model groups come from setup and are tagged in step 1.
        counts = _group_counts(pdir)
        return ", ".join(f"{name}: {n:,} parcels" for name, n in counts.items())

    if step == "check_sales":
        run_stage(pdir, "clean", _on_progress, cancel)
        engine = _counts(pdir, "2-clean")
        return f"{engine['parcels']:,} parcels, {engine['sales']:,} sales"

    if step == "check_values":
        with progress.reporting(_on_progress, cancel, "check_values"):
            return _check_values(project, pdir)

    raise ValueError(f"Unknown step: {step}")


def _check_files(project: projects.Project, pdir: Path, cancel) -> str:
    """Import every file that isn't imported yet, and measure it."""
    todo = [f for f in project.setup.files if not f.imported]
    for i, f in enumerate(todo):
        if cancel():
            raise InterruptedError("Stopped.")

        def prog(fraction: float, message: str, i: int = i, name: str = f.name) -> None:
            emit("progress", step="files", fraction=(i + fraction) / len(todo), message=f"{name}: {message}")

        f.profile = sources.import_file(pdir, f, prog, cancel)
        f.imported = True
        projects.save(project)
    projects.save_check(project.id, "files", {"hash": projects.decisions_hash(project.setup, "files")})
    rows = sum(f.profile.rows for f in project.setup.files if f.profile)
    return f"{len(project.setup.files)} files ready, {rows:,} rows"


def _fill_center(project: projects.Project, pdir: Path) -> None:
    b = project.setup.basics
    if b.center_lat is not None and b.center_lon is not None:
        return
    import geopandas as gpd

    geo = gpd.read_parquet(pdir / "in" / "stitched" / "geo_parcels.geoparquet", columns=["geometry"])
    c = geo.to_crs(4326).union_all().centroid if hasattr(geo, "union_all") else geo.to_crs(4326).unary_union.centroid
    b.center_lat, b.center_lon = float(c.y), float(c.x)
    projects.save(project)


def _check_values(project: projects.Project, pdir: Path) -> str:
    from openavmkit import progress
    from openavmkit.pipeline import load_settings, read_pickle
    from openavmkit.value_studies import run_value_field_studies

    previous = os.getcwd()
    os.chdir(pdir)
    try:
        progress.report("load", 0.05, "Loading cleaned data")
        sup = read_pickle("out/2-clean-sup")
        progress.report("studies", 0.2, "Running ratio and equity studies")
        results = run_value_field_studies(
            sup,
            load_settings(),
            project.setup.columns.value_fields,
            location=project.setup.columns.location_field,
            outpath="out/studies",
        )
    finally:
        os.chdir(previous)
    first = results[project.setup.columns.value_fields[0]]["overall"]["ratio"]
    med, cod = first["median_ratio"]["value"], first["cod"]["value"]
    if med is None or cod is None:
        return "Not enough sales in the study window to compute a ratio study."
    return f"Median ratio {med:.2f}, COD {cod:.1f}, {first['count']:,} sales"


def _counts(pdir: Path, prefix: str) -> dict[str, int]:
    import pandas as pd

    look = pdir / "out" / "look"
    univ = pd.read_parquet(look / f"{prefix}-universe.parquet", columns=["key"])
    sales = pd.read_parquet(look / f"{prefix}-sales.parquet", columns=["key_sale"])
    return {"parcels": len(univ), "sales": len(sales)}


def _group_counts(pdir: Path) -> dict[str, int]:
    import pandas as pd

    univ = pd.read_parquet(pdir / "out" / "look" / "1-assemble-universe.parquet", columns=["model_group"])
    return {str(k): int(v) for k, v in univ["model_group"].value_counts().items()}


def main() -> None:
    warnings.filterwarnings("ignore")
    project_id, step = sys.argv[1], sys.argv[2]
    _route_engine_output_to_stderr()
    try:
        message = run(project_id, step)
        emit("done", message=message)
    except Exception as e:  # noqa: BLE001 - every failure is reported as an event
        if isinstance(e, InterruptedError) or type(e).__name__ == "Cancelled":
            emit("cancelled", message="Stopped.")
            sys.exit(2)
        emit("error", message=str(e) or type(e).__name__, detail=traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

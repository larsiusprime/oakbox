"""Every step that runs OpenAVMKit gets the same routes from `_step_routes` (steps.py): its state, run, stop
and Looks right."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from oakbox import assemble, bring_in, clean, final, model, prepare, projects, ratio, steps, vartest
from oakbox.routes.common import assemble_view, bring_in_view, clean_view, editing, load_project

router = APIRouter()


# ---------- The steps: each one's state, run, stop and Looks right, the same way (steps.py) ----------


def _write(project: projects.Project, _pdir: Path) -> None:
    projects.write_settings(project)


def _decide(project: projects.Project, pdir: Path) -> None:
    """Check sales' proposals written down, so the settings say them all, then the settings."""
    try:
        clean.decide(project, pdir)
    except FileNotFoundError as e:
        raise ValueError("Write step 2 first (Model groups): this starts from its hand-off.") from e
    projects.save(project)
    projects.write_settings(project)


def _step_routes(
    path: str,
    view_type: type,
    view: Callable[[projects.Project], Any],
    step: steps.Step,
    start: Callable[[projects.Project, Path], None] | None,
    before: Callable[[projects.Project, Path], None] | None = None,
    accept: Callable[[projects.Project, Path], None] | None = None,
    run_doc: str = "",
) -> None:
    """GET <path>: ready, running, or the last run's receipt and whether it's out of date. POST run (in a
    process of its own; `before` gets the project ready), stop, and accept (Looks right) when it has one."""
    base = f"/api/projects/{{project_id}}/{path}"
    name = step.module

    @router.get(base, response_model=view_type, name=f"{name}_state")
    def state(project_id: str) -> Any:
        return view(load_project(project_id))

    if start is not None:

        @router.post(f"{base}/run", response_model=view_type, name=f"{name}_run", description=run_doc)
        def run(project_id: str) -> Any:
            with projects.lock(project_id):  # `before` may save the project; the run starts from it as saved
                project = load_project(project_id)
                pdir = projects.project_dir(project_id)
                try:
                    if before is not None:
                        before(project, pdir)
                    start(project, pdir)
                except (ValueError, FileNotFoundError) as e:
                    raise HTTPException(409, str(e)) from e
            return view(project)

    @router.post(f"{base}/stop", response_model=view_type, name=f"{name}_stop")
    def stop(project_id: str) -> Any:
        step.stop(project_id)
        return view(load_project(project_id))

    if accept is not None:

        @router.post(f"{base}/accept", response_model=view_type, name=f"{name}_accept")
        def accept_route(project_id: str) -> Any:
            with editing(project_id) as project:
                try:
                    accept(project, projects.project_dir(project_id))
                except ValueError as e:
                    raise HTTPException(409, str(e)) from e
            return view(project)


_step_routes("bring-in", bring_in.View, bring_in_view, bring_in.STEP, None, accept=bring_in.STEP.accept)
_step_routes(
    "assemble",
    assemble.AssembleView,
    assemble_view,
    assemble.STEP,
    assemble.start,
    before=_write,
    accept=assemble.STEP.accept,
    run_doc="Tag each parcel with its model group and write notebook 1's output.",
)
_step_routes(
    "clean",
    clean.CleanView,
    clean_view,
    clean.STEP,
    clean.start,
    before=_decide,
    accept=clean.STEP.accept,
    run_doc="Check sales: notebook 2's clean stage.",
)
_step_routes(
    "prepare",
    prepare.PrepareView,
    lambda p: prepare.view(p, projects.project_dir(p.id)),
    prepare.STEP,
    prepare.start,
    before=_decide,
    accept=prepare.STEP.accept,
    run_doc="Fill blanks and fold rare categories on Check sales' hand-off; write notebook 2's output again.",
)
_step_routes(
    "ratio",
    ratio.RatioView,
    lambda p: ratio.view(p, projects.project_dir(p.id)),
    ratio.STEP,
    ratio.start,
    accept=ratio.accept,
    run_doc="Check the values: OpenAVMKit's value-field studies on the sales Check sales kept.",
)
_step_routes(
    "vartest",
    vartest.VarTestView,
    lambda p: vartest.view(p, projects.project_dir(p.id)),
    vartest.STEP,
    vartest.start,
    before=_write,
    run_doc="Test the variables ticked: OpenAVMKit's variable tests, per model group.",
)
_step_routes(
    "model",
    model.ModelView,
    lambda p: model.view(p, projects.project_dir(p.id)),
    model.STEP,
    model.start,
    before=_write,
    accept=model.STEP.accept,
    run_doc="Try the models: OpenAVMKit's try_models on the prepared fields, every model group.",
)
_step_routes(
    "final",
    final.FinalView,
    lambda p: final.view(p, projects.project_dir(p.id)),
    final.STEP,
    final.start,
    before=_write,
    accept=final.accept,
    run_doc="Finalize: OpenAVMKit's finalize_models, the groups Small groups leaves unvalued skipped, then the values"
    " checked against the sales (out of fold, held out, as valued) beside the roll's.",
)

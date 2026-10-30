"""Step 5, the models (F9): the variables there are, the models offered, and the calls on them. Preparing the
fields and the variable tests have only a step's routes (routes/steps.py)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from oakbox import model, projects
from oakbox.routes.common import load_project

router = APIRouter()


# ---------- Step 5 begins: prepare the fields for the models ----------

# ---------- Step 5, the models (F9) ----------


@router.get("/api/projects/{project_id}/model/setup")
def model_setup(project_id: str) -> model.ModelSetup:
    """The variables there are, the models offered, and each model group's sales."""
    project = load_project(project_id)
    try:
        return model.setup(project, projects.project_dir(project_id))
    except LookupError as e:
        raise HTTPException(409, str(e)) from e


@router.patch("/api/projects/{project_id}/model/setup")
def model_change(project_id: str, body: model.ModelPatch) -> model.ModelSetup:
    project = load_project(project_id)
    try:
        model.change(project, body)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    projects.save(project)
    try:
        return model.setup(project, projects.project_dir(project_id))
    except LookupError as e:
        raise HTTPException(409, str(e)) from e

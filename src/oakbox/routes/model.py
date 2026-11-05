"""Step 5, Variables, and step 6, Model values (F9): the variable lists, each model group's models, their location
stacks, and the calls on them. Preparing the fields and the variable tests have only a step's routes
(routes/steps.py)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from oakbox import locstack, model, projects, smallgroups, varlists
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound, NotReady
from oakbox.routes.common import editing, load_project

router = APIRouter()


# ---------- Step 5 begins: prepare the fields for the models ----------

# ---------- Step 5, the models (F9) ----------


@router.get("/api/projects/{project_id}/model/setup")
def model_setup(project_id: str) -> model.ModelSetup:
    """The variables there are, the models offered, and each model group's sales."""
    project = load_project(project_id)
    try:
        return model.setup(project, projects.project_dir(project_id))
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


@router.patch("/api/projects/{project_id}/model/setup")
def model_change(project_id: str, body: model.ModelPatch) -> model.ModelSetup:
    with editing(project_id) as project:
        try:
            model.change(project, body)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    try:
        return model.setup(project, projects.project_dir(project_id))
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


class GroupModelsBody(BaseModel):
    models: list[model.ModelEntry] | None = Field(description="The group's models, in order; null: the default ones.")


@router.put("/api/projects/{project_id}/model/groups/{group}")
def model_group(project_id: str, group: str, body: GroupModelsBody) -> model.ModelSetup:
    """A model group's models: each an engine, a name, a variable list and (Multi-MRA, Local area) a location stack."""
    with editing(project_id) as project:
        pdir = projects.project_dir(project_id)
        try:
            model.set_group(project, pdir, group, body.models)
        except NotFound as e:
            raise HTTPException(404, f"No model group {group}.") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    try:
        return model.setup(project, pdir)
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{project_id}/model/stack/{group}")
def model_stack(
    project_id: str, group: str, fields: Annotated[list[str] | None, Query()] = None
) -> locstack.StackPreview:
    """A location stack in a model group, broadest first: per level its areas, their sales, and whether it nests."""
    load_project(project_id)
    try:
        return locstack.preview(projects.project_dir(project_id), group, fields or [])
    except NotReady as e:
        raise HTTPException(409, str(e)) from e


# ---------- Variable lists ----------


class VarListsBody(BaseModel):
    lists: list[model.VarList] | None = Field(description="Every list, in order; null: back to the proposed ones.")


@router.get("/api/projects/{project_id}/varlists")
def varlists_view(project_id: str) -> varlists.VarListsView:
    """The variable lists, the variables, the tests' recommendations per model group and type."""
    project = load_project(project_id)
    return varlists.view(project, projects.project_dir(project_id))


@router.put("/api/projects/{project_id}/varlists")
def varlists_change(project_id: str, body: VarListsBody) -> varlists.VarListsView:
    """Every variable list at once. A new list (no id) gets one from its name; an id is kept through renames."""
    with editing(project_id) as project:
        pdir = projects.project_dir(project_id)
        if body.lists is None:
            project.model.lists = None
        else:
            taken = {x.id for x in body.lists if x.id}
            given = []
            for x in body.lists:
                if not x.id:
                    x = x.model_copy(update={"id": varlists.new_id(taken, x.name)})
                    taken.add(x.id)
                given.append(x)
            try:
                project.model.lists = varlists.check(project, given)
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
    return varlists.view(project, pdir)


# ---------- Small groups ----------


class SmallChoice(BaseModel):
    choice: smallgroups.Choice


@router.get("/api/projects/{project_id}/model/small")
def model_small(project_id: str) -> smallgroups.SmallGroupsView:
    """The groups the try can't be trusted on, why, and whether each is left unvalued or modeled anyway."""
    project = load_project(project_id)
    return smallgroups.view(project, projects.project_dir(project_id))


@router.put("/api/projects/{project_id}/model/small/{group}")
def model_small_choice(project_id: str, group: str, body: SmallChoice) -> smallgroups.SmallGroupsView:
    with editing(project_id) as project:
        pdir = projects.project_dir(project_id)
        try:
            smallgroups.choose(project, pdir, group, body.choice)
        except NotFound as e:
            raise HTTPException(404, f"No model group {group}.") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return smallgroups.view(project, pdir)

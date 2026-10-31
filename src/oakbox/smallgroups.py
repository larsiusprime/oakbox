"""Model values › Small groups (SPEC F9, slice 2): the model groups the try can't be trusted on, and what to do with
each. A group is flagged when it has too few sales to model (15, OpenAVMKit's own floor), none held out to judge it
by, a holdout median ratio that makes no sense (outside 0.5 to 2), or values below zero. A flagged group is left
unvalued unless the user models it anyway; a group no model produced values for can only be left. Values below zero
never ship: those parcels stay blank and are counted.

Read from the try's receipt; the choices apply when the values are made (Finalize), not to the try, which has to
model a group to judge it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import model
from oakbox.datafiles import BaseModel

MIN_SALES = 15
SANE = (0.5, 2.0)

Flag = Literal["too_few", "no_values", "no_holdout", "implausible", "below_zero"]
Choice = Literal["leave", "model"]


class SmallGroup(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    sales: int
    modeled: bool = Field(description="Ticked on Model groups › Check them.")
    median: float | None = Field(description="The ensemble's holdout median ratio.")
    cod: float | None = Field(description="The ensemble's holdout COD.")
    below_zero: int
    flags: list[Flag]
    can_model: bool = Field(description="Some model produced values for it: it can be modeled anyway.")
    choice: Choice | None = Field(description="Flagged: left unvalued or modeled anyway; null: not flagged.")


class SmallGroupsView(BaseModel):
    tried: bool = Field(description="The models have been tried: the flags are the try's.")
    groups: list[SmallGroup]
    unvalued_parcels: int = Field(description="Parcels in the groups left unvalued.")
    unvalued: list[str] = Field(description="The groups left unvalued, by name.")
    blanked: int = Field(description="Parcels in modeled groups valued below zero: left blank.")


def _ensemble(group: model.ModelGroupResult) -> tuple[float | None, float | None]:
    holdout = next((s for s in group.sets if s.key == "holdout"), None)
    row = next((x for x in holdout.rows if x.model == "ensemble"), None) if holdout else None
    if row is None and holdout and holdout.rows:
        row = holdout.rows[0]
    return (row.values.get("median_ratio"), row.values.get("cod")) if row else (None, None)


def flags(group: model.ModelGroupResult) -> list[Flag]:
    out: list[Flag] = []
    if group.sales < MIN_SALES:
        out.append("too_few")
    if not group.valued:
        out.append("no_values")
    elif not group.sets:
        out.append("no_holdout")
    median, _ = _ensemble(group)
    if median is not None and not SANE[0] <= median <= SANE[1]:
        out.append("implausible")
    if group.below_zero:
        out.append("below_zero")
    return out


def view(project, project_dir: Path) -> SmallGroupsView:
    from oakbox import assemble

    receipt = model.STEP.state(project, project_dir, check=False).receipt
    modeled = assemble.modeled(project, project_dir)
    tried = {g.id: g for g in receipt.groups} if receipt else {}
    chosen: dict[str, Choice] = project.model.small
    out: list[SmallGroup] = []
    for g in project.groups:
        r = tried.get(g.id)
        f = flags(r) if r and g.id in modeled else []
        can = bool(r and r.valued)
        median, cod = _ensemble(r) if r else (None, None)
        out.append(
            SmallGroup(
                id=g.id,
                name=g.name,
                color=g.color,
                parcels=r.parcels if r else 0,
                sales=r.sales if r else 0,
                modeled=g.id in modeled,
                median=median,
                cod=cod,
                below_zero=r.below_zero if r else 0,
                flags=f,
                can_model=can,
                choice=(chosen.get(g.id, "leave") if can else "leave") if f else None,
            )
        )
    left = [x for x in out if x.choice == "leave"]
    return SmallGroupsView(
        tried=receipt is not None,
        groups=out,
        unvalued_parcels=sum(x.parcels for x in left),
        unvalued=[x.name for x in left],
        blanked=sum(x.below_zero for x in out if x.modeled and x.choice != "leave"),
    )


def choose(project, project_dir: Path, group: str, choice: Choice) -> None:
    """Leave a flagged group unvalued, or model it anyway (only if some model produced values for it)."""
    v = next((x for x in view(project, project_dir).groups if x.id == group), None)
    if v is None:
        raise LookupError(group)
    if choice == "model" and not v.can_model:
        raise ValueError(f"{v.name} can't be modeled: no model produced values for it.")
    if choice == "leave":
        project.model.small.pop(group, None)
    else:
        project.model.small[group] = choice

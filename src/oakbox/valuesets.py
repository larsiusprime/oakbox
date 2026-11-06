"""Existing values to compare the models with (the roll, a vendor's AVM, last year's values): each set named, its
fields the roll's assr_* (OpenAVMKit's assessor) or a slot of their own (vset1_market_value…). Kept apart from
projects so the steps can read them without importing it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    from oakbox.projects import Project


class ValueSet(BaseModel):
    """A set of existing values to compare the models with: the roll, a vendor's AVM, last year's values."""

    id: str = Field(
        description="Its fields' prefix: \"assr\" for the roll (OpenAVMKit's assessor), else a slot (vset1…)."
    )
    name: str


ROLL = "assr"


def value_sets(project: Project) -> list[ValueSet]:
    """The project's existing values: the roll (OpenAVMKit's assr_* fields) and any others, each with a name."""
    if project.wizard.value_sets is not None:
        return project.wizard.value_sets
    return [ValueSet(id=ROLL, name=f"{project.jurisdiction} roll".strip() if project.jurisdiction else "The roll")]


def value_field(set_id: str, part: str = "market") -> str:
    return f"{set_id}_{part}_value"


def loaded_value_sets(project: Project) -> list[ValueSet]:
    """The value sets with a market value loaded: the ones that can be compared."""
    loaded = {k for f in project.files if f.holds == "parcels" for k in f.load}
    return [v for v in value_sets(project) if value_field(v.id) in loaded]

"""Existing values (F3d, Data › Existing values): sets of values to compare the models with (the roll, a vendor's
AVM, last year's values), each named, each a market value with optional land and improvement values. The roll's
fields are OpenAVMKit's assr_* (its assessor model); the others' take a slot of their own (vset1_market_value…),
compared as pass_through models.
"""

from __future__ import annotations

from oakbox.errors import NotFound
from oakbox.fields import VALUE_PARTS, VALUE_SLOTS
from oakbox.projects import Project
from oakbox.valuesets import ROLL, ValueSet, value_field, value_sets

# A DataFile's dicts keyed by field: what moves with a field when its set moves to another slot.
PER_FIELD = ("load", "numbers", "scales", "area_units", "rules")


def _move(project: Project, src: str, dst: str) -> None:
    """Move a set's fields from one prefix to another (the roll's assr_* and a slot), in every file."""
    for part in VALUE_PARTS:
        a, b = value_field(src, part), value_field(dst, part)
        for f in project.files:
            for attr in PER_FIELD:
                d = getattr(f, attr)
                if a in d:
                    d[b] = d.pop(a)
        for names in (project.wizard.decided, project.wizard.absent):
            if a in names:
                names[names.index(a)] = b


def _free_slot(sets: list[ValueSet]) -> str:
    used = {v.id for v in sets}
    slot = next((s for s in VALUE_SLOTS if s not in used), None)
    if slot is None:
        raise ValueError(f"At most {len(VALUE_SLOTS) + 1} sets of values.")
    return slot


def add_value_set(project: Project, name: str) -> None:
    sets = list(value_sets(project))
    name = name.strip() or f"Values {len(sets) + 1}"
    if any(v.name == name for v in sets):
        raise ValueError(f"There's already a set called {name}.")
    # The first set is the roll; the others take slots (any can be made the roll after).
    sid = ROLL if not sets else _free_slot(sets)
    project.wizard.value_sets = [*sets, ValueSet(id=sid, name=name)]


def change_value_set(project: Project, set_id: str, name: str | None, roll: bool | None) -> None:
    """Rename a set, or make it the roll (the roll there was moves to a slot of its own) or not the roll."""
    sets = list(value_sets(project))
    v = next((x for x in sets if x.id == set_id), None)
    if v is None:
        raise NotFound(set_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise ValueError("A set of values needs a name.")
        if any(x.name == name and x is not v for x in sets):
            raise ValueError(f"There's already a set called {name}.")
        v = v.model_copy(update={"name": name})
        sets = [v if x.id == set_id else x for x in sets]
    if roll is True and v.id != ROLL:
        mine = v.id
        old = any(x.id == ROLL for x in sets)
        if old:  # the roll there was takes this set's slot
            _move(project, ROLL, "swap")
            _move(project, mine, ROLL)
            _move(project, "swap", mine)
        else:
            _move(project, mine, ROLL)
        sets = [
            x.model_copy(update={"id": ROLL if x.id == mine else mine}) if x.id in (mine, ROLL) else x for x in sets
        ]
    elif roll is False and v.id == ROLL:
        slot = _free_slot(sets)
        _move(project, ROLL, slot)
        sets = [x.model_copy(update={"id": slot}) if x.id == ROLL else x for x in sets]
    project.wizard.value_sets = sets


def remove_value_set(project: Project, set_id: str) -> None:
    """Take a set away, and its fields from every file."""
    sets = list(value_sets(project))
    if not any(v.id == set_id for v in sets):
        raise NotFound(set_id)
    for part in VALUE_PARTS:
        key = value_field(set_id, part)
        for f in project.files:
            for attr in PER_FIELD:
                getattr(f, attr).pop(key, None)
        for names in (project.wizard.decided, project.wizard.absent):
            if key in names:
                names.remove(key)
    project.wizard.value_sets = [v for v in sets if v.id != set_id]

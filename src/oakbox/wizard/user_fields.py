"""Fields the user names (F3d): location fields (a neighbourhood, a district: an area each parcel is in) and
custom fields the user classifies as land, building or other (Land use & building type), each with a check of its
column, and the names OpenAVMKit keeps for itself, which neither may take.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from oakbox.projects import Project
from oakbox.wizard.base import RENAMED
from oakbox.wizard.files import Files, _by_key, _field_files
from oakbox.wizard.models import Check, CustomFieldView, LocationField, Source
from oakbox.wizard.rules import _distinct

# ---------- Location fields the user names, and where the parcels are (F3d) ----------


# Names OpenAVMKit gives a meaning of its own, besides its dictionary's derived fields.
TAKEN = {"key", "key2", "key3", "key_sale", "geometry", "latitude", "longitude", "polar_radius", "polar_angle"}


def locations(project: Project, in_dir: Path) -> list[LocationField]:
    files = Files(project, in_dir)
    out = []
    for name in project.wizard.locations:
        entry = next((f for f in _field_files(project, False) if name in f.load), None)
        if entry is None:
            continue
        column = entry.load[name][0]
        values = [v for v in files.values(entry.name, column) if v] if entry.name in files.preview else []
        distinct = len(set(values))
        if not values:
            check = Check(ok=False, text="empty")
        elif distinct == 1:
            check = Check(ok=True, warn=True, text="one value for every parcel")
        elif distinct > 0.5 * len(values):
            check = Check(ok=True, warn=True, text=f"{distinct:,} values: nearly one per parcel. An ID, not an area?")
        else:
            check = Check(ok=True, text="✓")
        out.append(
            LocationField(
                name=name,
                file=entry.name,
                column=column,
                check=check,
                distinct=_distinct(files, Source(file=entry.name, column=column)),
            )
        )
    return out


def set_location(project: Project, in_dir: Path, name: str, file: str | None, column: str | None) -> None:
    """Load a column of a parcel file as a location field the user names (or, with no column, remove it)."""
    by_key = _by_key()
    if column is None:
        for f in _field_files(project, False):
            if name in project.wizard.locations:
                f.load.pop(name, None)
        if name in project.wizard.locations:
            project.wizard.locations.remove(name)
        return
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("Names use lowercase letters, digits and underscores, and start with a letter.")
    d = by_key.get(name)
    if name in TAKEN or name.startswith("polar_") or (d is not None and d.source in ("derived", "reserved")):
        raise ValueError(f"OpenAVMKit works out {name} itself: choose another name.")
    entry = next((f for f in _field_files(project, False) if f.name == file), None)
    if entry is None:
        raise ValueError("Locations come from a parcel file: the universe, or one joined to it.")
    if Files(project, in_dir).column(entry.name, column) is None:
        raise ValueError(f"{entry.name} has no column {column}.")
    loaded_as = {spec[0]: field for field, spec in entry.load.items()}
    if column in loaded_as and loaded_as[column] != name:
        raise ValueError(f"{column} is already loaded as {_field_name(loaded_as[column])}.")
    for f in project.files:
        if name in f.load and name not in project.wizard.locations:
            raise ValueError(f"{name} is already used for another field.")
        if name in f.load and f is not entry:
            f.load.pop(name)
    entry.load[name] = [column, "string"]
    if name not in project.wizard.locations:
        project.wizard.locations.append(name)


# ---------- Fields the user names and classifies: land, building or other (F3d Land use & building type) ----------


def custom_fields(project: Project, in_dir: Path) -> list[CustomFieldView]:
    files = Files(project, in_dir)
    out = []
    for c in project.wizard.custom:
        entry = next((f for f in _field_files(project, False) if c.name in f.load), None)
        if entry is None:
            continue
        column = entry.load[c.name][0]
        values = (
            [v.strip() for v in files.values(entry.name, column) if v.strip()] if entry.name in files.preview else []
        )
        distinct = len(set(values))
        if not values:
            check = Check(ok=False, text="empty")
        elif c.type == "number":
            bad = sum(1 for v in values if not _is_number(v))
            check = (
                Check(ok=True, text="✓ numbers")
                if bad == 0
                else Check(ok=True, warn=True, text=f"{bad:,} values aren't numbers: they'll be blank")
            )
        elif distinct == 1:
            check = Check(ok=True, warn=True, text="one value for every parcel")
        else:
            check = Check(ok=True, text="✓")
        out.append(
            CustomFieldView(
                name=c.name,
                group=c.group,
                type=c.type,
                file=entry.name,
                column=column,
                check=check,
                distinct=_distinct(files, Source(file=entry.name, column=column)),
            )
        )
    return out


def _field_name(key: str) -> str:
    """A field as the wizard names it ("Building units"); the user's own fields by their own name."""
    d = _by_key().get(key)
    return RENAMED.get(key, (d.name, ""))[0] if d else key


def _is_number(v: str) -> bool:
    try:
        float(v.replace(",", ""))
    except ValueError:
        return False
    return True


def set_custom(
    project: Project,
    in_dir: Path,
    name: str,
    file: str | None,
    column: str | None,
    group: Literal["land", "building", "other"] = "other",
    type_: Literal["category", "number"] = "category",
) -> None:
    """Load a parcel file's column as a field the user names and classifies (or, with no column, remove it)."""
    from oakbox.projects import CustomField

    mine = [c.name for c in project.wizard.custom]
    if column is None:
        if name in mine:
            for f in _field_files(project, False):
                f.load.pop(name, None)
            project.wizard.custom = [c for c in project.wizard.custom if c.name != name]
        return
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("Names use lowercase letters, digits and underscores, and start with a letter.")
    if name in TAKEN or name.startswith("polar_") or name in _by_key():
        raise ValueError(f"{name} is one of OpenAVMKit's own fields: choose another name.")
    if name in project.wizard.locations:
        raise ValueError(f"{name} is already a location field.")
    entry = next((f for f in _field_files(project, False) if f.name == file), None)
    if entry is None:
        raise ValueError("Your own fields come from a parcel file: the parcel universe, or one joined to it.")
    if Files(project, in_dir).column(entry.name, column) is None:
        raise ValueError(f"{entry.name} has no column {column}.")
    loaded_as = {spec[0]: field for field, spec in entry.load.items()}
    if column in loaded_as and loaded_as[column] != name:
        raise ValueError(f"{column} is already loaded as {_field_name(loaded_as[column])}.")
    for f in project.files:
        if name in f.load and name not in mine:
            raise ValueError(f"{name} is already used for another field.")
        if name in f.load and f is not entry:
            f.load.pop(name)
    entry.load[name] = [column, "float" if type_ == "number" else "string"]
    field = CustomField(name=name, group=group, type=type_)
    if name in mine:
        project.wizard.custom = [field if c.name == name else c for c in project.wizard.custom]
    else:
        project.wizard.custom.append(field)

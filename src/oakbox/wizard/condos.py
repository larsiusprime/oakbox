"""Units of a shared parcel: condos (F3d). Rows with a parcel ID but no shape of their own, set up as units of a
building (their IDs, their links, their land), and the question "Do you have condos?".
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from oakbox import enrichments, projects
from oakbox.datafiles import (
    EXTRA_IDS,
    SQFT_PER,
    DataFile,
    Units,
    clean_value,
    guess_area_unit,
    small_unit,
)
from oakbox.projects import Project
from oakbox.wizard.base import RENAMED
from oakbox.wizard.checks import counted, parcel_ids
from oakbox.wizard.files import Files, cleaned_ids, dictionary_by_key, file_stamp, is_more_sales, steps_key, values_of
from oakbox.wizard.maps import read_geo
from oakbox.wizard.models import (
    Check,
    CondoFile,
    CondosView,
    Left,
    Status,
    UnitExample,
    UnitField,
    UnitsView,
    WizardFile,
)
from oakbox.wizard.quality import field_by_id
from oakbox.wizard.rules import rule_result

# ---------- Units of a shared parcel: condos (F3d) ----------

# A parcel's location fields a unit never takes: its own address, and what its shape brings (census, by enrichment).
INHERIT_NEVER = {"address", "census_tract", "census_block", "census_block_group", projects.CONDO_GROUP}


def from_shape(project: Project, units: Units) -> list[str]:
    """What each unit gets from the shape of the parcel it's on, as every parcel does from its own."""
    out = [
        f"{f.name} (map layer)"
        for f in project.files
        if f.holds == "overlay" and f.overlay and f.overlay.use in ("stamp", "distance")
    ]
    e = project.enrich
    if e is not None:
        names = enrichments.osm_names(e)
        on = [s.label.lower() for s, *_ in enrichments.FEATURES if s.key in names]
        if on:
            out.append("Distance to " + ", ".join(on))
        if e.census:
            out.append("Census tract and block group")
        if e.elevation:
            out.append("Elevation and slope")
    if units.location:
        out.append("The parcel itself, as a location")
    return out


def unshaped_rows(files: Files, f: DataFile, base: str | None) -> int:
    """A parcel file's rows whose ID finds no parcel shape (its own blank IDs aside)."""
    if f.holds != "parcels" or f.name == base or base is None or f.name not in files.preview or "key" not in f.load:
        return 0
    shaped = parcel_ids(files, base) | (unit_ids(files) if f.units is None else set())
    return sum(1 for v in files.ids(f.name, "key") if v and v not in shaped)


def unit_ids(files: Files) -> set[str]:
    """The IDs of units that find their building: parcels of the parcel universe once condos are resolved."""
    f = next((x for x in files.project.files if x.units is not None and x.holds == "parcels"), None)
    if f is None or f.name not in files.preview:
        return set()
    rows = _unit_rows(files, f, f.units or Units())
    ids = files.ids(f.name, "key")
    return {ids[i] for i, b in zip(rows, _links(files, f, f.units or Units(), rows), strict=True) if b}


def _unit_rows(files: Files, f: DataFile, units: Units) -> list[int]:
    """Rows of the file without a shape that the rule says are units."""
    shaped = parcel_ids(files, files.project.wizard.base)
    ids = files.ids(f.name, "key")
    rows = [i for i, v in enumerate(ids) if v and v not in shaped]
    if units.rule and units.rule.conditions:
        try:
            _, _, yes = rule_result(files, f, units.rule)
        except Exception:  # noqa: BLE001 - an unfinished rule selects nothing yet
            return []
        flags = yes.tolist()
        rows = [i for i in rows if i < len(flags) and flags[i]]
    return rows


def _links(files: Files, f: DataFile, units: Units, rows: list[int]) -> list[str | None]:
    """Per unit row, the building it finds (the parcel universe's ID), as OpenAVMKit links them."""
    base = files.project.wizard.base
    if base is None or units.column is None or files.column(f.name, units.column) is None:
        return [None] * len(rows)
    mine = files.values(f.name, units.column)
    if units.link == "prefix":
        if not units.base_column or files.column(base, units.base_column) is None:
            return [None] * len(rows)
        n = units.prefix_len
        theirs = files.values(base, units.base_column)
        keys = files.ids(base, "key")
        # OpenAVMKit takes the largest shape with the prefix: any of them names the building here.
        building = {}
        for v, k in zip(theirs, keys, strict=False):
            if v and k:
                building.setdefault(v[:n], k)
        return [building.get(mine[i][:n]) if mine[i] else None for i in rows]
    entry = files.entry(base)
    shaped = parcel_ids(files, base)
    steps = entry.clean.get("key", [])
    return [
        (c if (c := clean_value(mine[i], steps) if mine[i] else "") in shaped else None) if mine[i] else None
        for i in rows
    ]


def units_view(project: Project, files: Files, f: DataFile) -> UnitsView:
    units = f.units or Units()
    if f.name not in files.preview:
        return UnitsView(
            settings=units,
            units=0,
            linked=0,
            buildings=0,
            examples=[],
            fields=[],
            land=Check(ok=False, text="the file can't be read"),
            check=Check(ok=False, text="the file can't be read"),
        )
    rows = _unit_rows(files, f, units)
    links = _links(files, f, units, rows)
    linked = [b for b in links if b]
    ids = files.ids(f.name, "key")
    base = project.wizard.base
    base_entry = files.entry(base) if base else None
    addr_col = f.load.get("address", [None])[0]
    addrs = files.values(f.name, addr_col) if addr_col and files.column(f.name, addr_col) else None
    land, shares = _unit_land(project, files, f, units, rows, links)
    # What each building was matched by, in the parcel universe file: shown beside the unit's own value.
    matched: dict[str, str] = {}
    if base and units.link == "prefix" and units.base_column and files.column(base, units.base_column):
        for v, k in zip(files.values(base, units.base_column), files.ids(base, "key"), strict=False):
            if v and k:
                matched.setdefault(k, v)
    show = [i for i, b in enumerate(links) if b][:4] + [i for i, b in enumerate(links) if not b][:2]
    examples = [
        UnitExample(
            unit=(
                files.values(f.name, units.column)[rows[i]]
                if units.column and files.column(f.name, units.column)
                else ids[rows[i]]
            ),
            building=links[i],
            building_value=matched.get(links[i] or ""),
            share=shares.get(rows[i]),
            address=addrs[rows[i]] if addrs else "",
        )
        for i in show
    ]
    by_key = dictionary_by_key()

    def named(k: str) -> str:
        return RENAMED.get(k, (by_key[k].name, ""))[0] if k in by_key else k

    base_load = base_entry.load if base_entry is not None else {}
    given = [
        UnitField(field=k, name=named(k), column=spec[0])
        for k, spec in f.load.items()
        if k not in ("key", *EXTRA_IDS) and k in base_load
    ]
    # Offered, never copied unasked: the parcel universe's fields this file has a same-named column for.
    columns = {c.name for c in files.columns(f.name)}
    # The land size only when it's what the units' land is (otherwise their share replaces it).
    land_key = "land_area_sqft" if project.units == "imperial" else "land_area_sqm"
    skip = {"key", *EXTRA_IDS, projects.CONDO_LINK, *([land_key] if units.land != "field" else [])}
    offers = [
        UnitField(field=k, name=named(k), column=spec[0])
        for k, spec in base_load.items()
        if k not in skip and k not in f.load and spec[0] in columns
    ]
    # From the parcel each unit is on: its land and location fields (never the unit's own: address, size, values).
    own = set(f.load)
    inheritable = []
    seen: set[str] = set()
    for g in project.files:
        if g is f or g.holds != "parcels":
            continue
        for k, spec in g.load.items():
            d = by_key.get(k)
            land_or_place = k in project.wizard.locations or (
                d is not None and bool({"location", "land use"} & set(d.groups)) or k == "land_class"
            )
            if land_or_place and k not in INHERIT_NEVER and k not in own and k not in seen:
                seen.add(k)
                inheritable.append(UnitField(field=k, name=named(k), column=spec[0]))
    if not rows:
        check = Check(ok=False, text="no row without a shape is a unit: check which rows are units")
    elif units.column is None:
        check = Check(ok=False, text="say how each unit finds the parcel it's on")
    else:
        missing = len(rows) - len(linked)
        text = (
            f"{len(linked):,} of {len(rows):,} units find the parcel they're on ({counted(len(set(linked)), 'parcel')})"
        )
        if missing:
            text += f" · {missing:,} {'finds' if missing == 1 else 'find'} none: left out"
        check = Check(ok=bool(linked), warn=missing > 0, text=("✓ " if not missing else "") + text)
    basis = None
    if units.guessed and units.column:
        if units.link == "prefix":
            cut = next(
                (v[units.prefix_len] for v in files.values(f.name, units.column) if len(v) > units.prefix_len), ""
            )
            sep = f" (up to the \u201c{cut}\u201d)" if cut and not cut.isalnum() else ""
            basis = (
                f"Guessed: {units.column} is in both files, and its first {units.prefix_len} characters{sep} match "
                f"a parcel's for more units than any other column or length. Check the examples; change it if your "
                f"files link units otherwise."
            )
        else:
            basis = (
                f"Guessed: {units.column} holds a parcel ID of the parcel universe for most units. Check the "
                f"examples; change it if your files link units otherwise."
            )
    return UnitsView(
        settings=units,
        units=len(rows),
        linked=len(linked),
        buildings=len(set(linked)),
        examples=examples,
        fields=given,
        offers=offers,
        inheritable=inheritable,
        from_shape=from_shape(project, units),
        basis=basis,
        land=land,
        check=check,
    )


@lru_cache(maxsize=8)
def _shape_areas(stamp: tuple[str, float, int], layer: str | None, column: str, steps: str) -> dict[str, float]:
    """Each parcel shape's area in square feet, by its parcel ID (cleaned as it joins): a building's land when its
    units share it, as OpenAVMKit measures it."""
    gdf = read_geo(stamp, layer)
    if gdf.crs is None or column not in gdf.columns:
        return {}
    area = gdf.to_crs(gdf.estimate_utm_crs()).geometry.area * 10.7639
    cleaned = cleaned_ids(stamp, layer, column, steps)
    raw = values_of(stamp, layer, column)
    by_raw = {r: c for r, c in zip(raw, cleaned, strict=False)}
    out: dict[str, float] = {}
    for v, a in zip(gdf[column].astype(str), area, strict=False):
        k = by_raw.get(v.strip(), by_raw.get(v, v))
        if k:
            out[k] = max(out.get(k, 0.0), float(a))
    return out


def _unit_land(
    project: Project, files: Files, f: DataFile, units: Units, rows: list[int], links: list[str | None]
) -> tuple[Check, dict[int, str]]:
    """Whether the land setting can be worked out (else Bring in data stops), and the shares it gives, by row."""
    base = files.entry(project.wizard.base) if project.wizard.base else None
    land_key = "land_area_sqft" if project.units == "imperial" else "land_area_sqm"
    ids = files.ids(f.name, "key")
    area_of: dict[str, float] = {}
    if base is not None and "key" in base.load:
        area_of = _shape_areas(
            file_stamp(files.in_dir / base.filename),
            base.layer,
            base.load["key"][0],
            steps_key(base.clean.get("key", [])),
        )

    def acres(sqft: float) -> str:
        if project.units != "imperial":
            return f"{sqft / 10.7639:,.0f} m²"
        return f"{sqft / 43_560:,.2f} acres" if sqft >= 0.5 * 43_560 else f"{sqft:,.0f} sq ft"

    shares: dict[int, str] = {}
    by_building: dict[str, list[int]] = {}
    for r, b in zip(rows, links, strict=True):
        if b:
            by_building.setdefault(b, []).append(r)
    if units.land == "equal":
        for b, rs in by_building.items():
            if b in area_of:
                for r in rs:
                    shares[r] = f"1/{len(rs)} of {acres(area_of[b])} = {acres(area_of[b] / len(rs))}"
        return Check(ok=True, text="✓ the parcel's land in equal shares, one per unit"), shares
    if units.land == "none":
        for r in rows:
            shares[r] = "0 (the land is the parcel's)"
        return Check(ok=True, text="✓ no land of their own: it's the parcel's"), shares
    if units.land == "floor_area":
        holder = next(
            (x for x in [f, *project.files] if "bldg_area_finished_sqft" in x.load and x.holds == "parcels"), None
        )
        if holder is None:
            text = "pick the building size (finished area) on More details › Big five first, or share the land equally"
            return Check(ok=False, text=text), shares
        floors: dict[str, float] = {}
        for x in [f, *(y for y in project.files if y is not f and y.holds == "parcels")]:
            for k, v in field_by_id(project, files, "bldg_area_finished_sqft", "key", only=x).items():
                floors.setdefault(k, v)
        for b, rs in by_building.items():
            total = sum(floors.get(ids[r], 0.0) for r in rs)
            if b in area_of and total:
                for r in rs:
                    part = floors.get(ids[r], 0.0) / total
                    shares[r] = f"{part:.1%} of {acres(area_of[b])} = {acres(area_of[b] * part)}"
        column = holder.load["bldg_area_finished_sqft"][0]
        return Check(ok=True, text=f"✓ shared by finished area ({column} in {holder.name})"), shares
    if land_key not in f.load:
        text = f"pick the column of {f.name} with each unit's land size, or share the parcel's land"
        return Check(ok=False, text=text), shares
    own = field_by_id(project, files, land_key, "key", only=f)
    filled = sum(1 for r in rows if ids[r] in own)
    for r in rows:
        if ids[r] in own:
            shares[r] = acres(own[ids[r]] * SQFT_PER[small_unit(project.units)] / SQFT_PER["sqft"])
    if not filled:
        return Check(ok=False, text=f"{f.load[land_key][0]} is blank for every unit: share the parcel's land"), shares
    text = f"✓ each unit's own land size, from {f.load[land_key][0]}" + (
        f" · {len(rows) - filled:,} blank" if filled < len(rows) else ""
    )
    return Check(ok=True, warn=filled < len(rows), text=text), shares


def _guess_units(project: Project, files: Files, f: DataFile) -> Units:
    """How the units find their building: a column both files have whose start matches (the longest start that
    links the most units, ending before a separator), or a column holding the building's parcel ID."""
    base = project.wizard.base
    units = Units()
    if base is None or base not in files.preview:
        return units
    rows = _unit_rows(files, f, units)
    if not rows:
        return units
    mine_cols = {c.name for c in files.columns(f.name)}
    best: tuple[int, int, int, str, int] | None = None  # (linked, separator, n, column, ...)
    for col in [c.name for c in files.columns(base) if c.name in mine_cols and c.type != "geometry"]:
        if col == f.load.get("key", [None])[0]:
            continue
        sample = [v for v in (files.values(f.name, col)[i] for i in rows[:2000]) if v]
        if not sample:
            continue
        top = max(len(v) for v in sample)
        for n in range(3, min(top, 24) + 1):
            trial = Units(link="prefix", column=col, base_column=col, prefix_len=n)
            linked = sum(1 for b in _links(files, f, trial, rows[:2000]) if b)
            sep = sum(1 for v in sample if len(v) > n and not v[n].isalnum())
            score = (linked, sep, n)
            if linked and (best is None or score > best[:3]):
                best = (linked, sep, n, col, 0)
    if best is not None and best[0] >= 0.5 * min(len(rows), 2000):
        return Units(link="prefix", column=best[3], base_column=best[3], prefix_len=best[2])
    for col in mine_cols:
        trial = Units(link="parent", column=col)
        if sum(1 for b in _links(files, f, trial, rows[:2000]) if b) >= 0.5 * min(len(rows), 2000):
            return trial
    return units


def set_units(project: Project, in_dir: Path, name: str, units: Units | None, guess: bool = False) -> None:
    """Treat a parcel file's rows without a shape as units of a shared parcel (or stop). The first time, guess how
    they find their building (said as a guess on the panel). The parcel universe's fields are offered for the
    units, never copied unasked."""
    files = Files(project, in_dir)
    f = next((x for x in project.files if x.name == name), None)
    if f is None or f.holds != "parcels" or f.name == project.wizard.base:
        raise ValueError("Units come from a parcel file joined to the parcel universe.")
    if units is None:
        for k in [k for k in f.load if k not in ("key", *EXTRA_IDS)]:
            if any(k in g.load for g in project.files if g is not f):
                f.load.pop(k)  # the units' copies of the parcel universe's fields
        f.units = None
        return
    other = next((x for x in project.files if x.units is not None and x is not f), None)
    if other is not None:
        set_units(project, in_dir, other.name, None)  # OpenAVMKit takes one units file: they move to this one
    if project.wizard.condos is None:
        project.wizard.condos = True
    first = f.units is None
    if guess or (first and units.column is None):
        f.units = _guess_units(project, files, f).model_copy(
            update={"land": units.land, "location": units.location, "rule": units.rule, "guessed": True}
        )
        return
    old = f.units
    # Changing how units find their building makes it the user's choice, no longer a guess.
    link = ("link", "column", "base_column", "prefix_len")
    same = old is not None and all(getattr(old, k) == getattr(units, k) for k in link)
    f.units = units.model_copy(update={"guessed": bool(old and old.guessed and same)})


def set_unit_field(project: Project, in_dir: Path, name: str, field: str, column: str | None) -> None:
    """Give the units a parcel universe field from a column of their file (or take it away)."""
    f = next((x for x in project.files if x.name == name and x.units is not None), None)
    base = project.base_file()
    if f is None or base is None:
        raise ValueError("Set up the units first.")
    land_key = "land_area_sqft" if project.units == "imperial" else "land_area_sqm"
    # The units' own land size (Condo units › Land) even when the parcel universe's comes from its shapes.
    if (field not in base.load and field != land_key) or field in ("key", *EXTRA_IDS):
        raise ValueError(f"{field} isn't one of the parcel universe's fields.")
    if column is None:
        f.load.pop(field, None)
        return
    if Files(project, in_dir).column(f.name, column) is None:
        raise ValueError(f"{f.name} has no column {column}.")
    if field not in base.load:
        f.load[field] = [column, "float"]
        f.area_units[field] = guess_area_unit(column) or small_unit(project.units)
        return
    f.load[field] = [column, *base.load[field][1:]]
    for attr in ("area_units", "numbers", "scales"):
        src = getattr(base, attr)
        if field in src:
            getattr(f, attr)[field] = src[field]


def has_condos(project: Project) -> bool | None:
    """The answer on Condo units; a project that set up units before the question was asked has them."""
    if project.wizard.condos is not None:
        return project.wizard.condos
    return True if projects.units_file(project) is not None else None


def condo_ask_status(project: Project, files: list[WizardFile]) -> tuple[Status, list[Left]]:
    """Do you have condos? Done once answered; until then worth deciding when the files suggest units, even before
    the step is reached."""
    if has_condos(project) is not None:
        return "done", []
    if _condo_evidence(files):
        return "attention", [Left(text="Say whether some parcels are condos or other units", blocking=False)]
    return "blank", []


def _condo_evidence(files: list[WizardFile]) -> list[str]:
    """What the files suggest about units without a shape of their own, a sentence each."""
    from oakbox.wizard.missing import MISSING_FEW  # missing reads the condos: imported here, not above

    out = []
    for f in files:
        many = f.unshaped >= MISSING_FEW or f.unshaped >= 0.5 * (f.rows or 1)
        if f.holds == "parcels" and not f.base and f.unshaped and many:
            of = f" of {f.rows:,}" if f.rows else ""
            out.append(f"{f.filename}: {f.unshaped:,}{of} rows have a parcel ID but no shape in the parcel universe.")
        elif f.holds == "sales" and not is_more_sales(f) and f.not_in_universe and f.not_in_universe.kind == "missing":
            n = f.not_in_universe.rows
            out.append(
                f"{counted(n, 'sale')} {'is' if n == 1 else 'are'} for parcels the parcel universe doesn't have."
            )
    return out


def condo_left(key: str, files: list[WizardFile]) -> list[Left]:
    """What's left on a part of Condo units."""
    u = next((f for f in files if f.units is not None), None)
    if key == "condo_file":
        return [Left(text="Pick the file with the units")] if u is None else []
    if u is None or u.units is None:
        return []
    v = u.units
    if key == "condo_rows" and v.units == 0:
        return [Left(text=v.check.text)]
    if key == "condo_link" and v.units:
        if not v.check.ok:
            return [Left(text=v.check.text)]
        if v.check.warn:
            return [Left(text=v.check.text, blocking=False)]
    if key == "condo_land":
        if not v.land.ok:
            return [Left(text=v.land.text)]
        if v.land.warn:
            return [Left(text=v.land.text.removeprefix("✓ "), blocking=False)]
    if key == "condo_fields" and v.offers:
        n = len(v.offers)
        return [Left(text=f"{counted(n, 'field')} of {u.name} could be given to the units", blocking=False)]
    return []


def condos_view(project: Project, files: list[WizardFile]) -> CondosView:
    parcels = sorted(
        (f for f in files if f.holds == "parcels" and not f.base), key=lambda f: -f.unshaped / (f.rows or 1)
    )
    return CondosView(
        answer=has_condos(project),
        evidence=_condo_evidence(files),
        files=[CondoFile(name=f.name, filename=f.filename, rows=f.rows, unshaped=f.unshaped) for f in parcels],
        file=next((f.name for f in files if f.units is not None), None),
    )


def set_condos(project: Project, in_dir: Path, has: bool | None) -> None:
    """Answer "Do you have condos?". No stops any units set up (their settings and the fields given them)."""
    project.wizard.condos = has
    if has is False:
        for f in [f for f in project.files if f.units is not None]:
            set_units(project, in_dir, f.name, None)

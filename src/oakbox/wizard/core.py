"""Reading and changing the Fields wizard: ``view``, the whole wizard as it stands (each step's status and
what's left), the guesses made when a step is first shown, and the setters for its base file, the files, the sale
ID and the fields. It brings the sections (checks, rules, money, quality, condos, layers…) together.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from oakbox import enrichments, fields
from oakbox.datafiles import (
    AREA_FIELDS,
    EXTRA_IDS,
    QC_FIELDS,
    AreaUnit,
    Condition,
    DataFile,
    Dupes,
    Holds,
    Match,
    NumberFormat,
    Rule,
    Scale,
    guess_area_unit,
    small_unit,
)
from oakbox.errors import NotFound
from oakbox.fields import VALUE_PARTS
from oakbox.projects import Project
from oakbox.valuesets import ROLL, value_field, value_sets
from oakbox.wizard.base import (
    ABSENT_OK,
    ASSUMABLE,
    ONLY_WITHOUT,
    PAIRS,
    PARENTS,
    RECOMMENDED,
    RENAMED,
    REQUIRED,
    SCALED,
    STEP_KEYS,
    STEPS,
    Step,
)
from oakbox.wizard.checks import (
    MATCH_MIN,
    MATCH_OK,
    _guess_field,
    _guess_id,
    _guess_sale_id,
    _id_check,
    _n,
    _pct,
    field_check,
)
from oakbox.wizard.condos import _condo_ask_status, _condo_left, _condos_view, _unshaped, has_condos, units_view
from oakbox.wizard.deeds_permits import _deeds_check, _guess_permits, _permits_left, _permits_view
from oakbox.wizard.files import (
    Files,
    _by_key,
    _field_files,
    _more_sales,
    _rows,
    base_file,
    file_stamp,
    sales_file,
    values_of,
)
from oakbox.wizard.maps import layers
from oakbox.wizard.missing import _diagnose_missing
from oakbox.wizard.models import (
    AGE,
    ORDER,
    Check,
    ExtraId,
    LayerView,
    Left,
    NotLoaded,
    RepeatRows,
    SaleId,
    Source,
    Status,
    StepView,
    ValueSetView,
    Wizard,
    WizardField,
    WizardFile,
)
from oakbox.wizard.money import _area_check, _money_check, _plain, detect_number_format, is_money
from oakbox.wizard.quality import _new_scale, _scale_check
from oakbox.wizard.rows import ROWS, copy_rule
from oakbox.wizard.rows import assume as rows_assume
from oakbox.wizard.rows import main_of as rows_main
from oakbox.wizard.rows import propose as propose_rows
from oakbox.wizard.rows import view as rows_view
from oakbox.wizard.rules import _date_check, _distinct, _rule_check
from oakbox.wizard.user_fields import custom_fields, locations

# ---------- Reading and changing the wizard ----------


def _used(project: Project) -> dict[str, dict[str, str]]:
    out = {f.name: {spec[0]: field for field, spec in f.load.items()} for f in project.files}
    for f in project.files:
        for key, rule in f.rules.items():
            for c in rule.conditions:
                out[f.name].setdefault(c.column, key)
    return out


# OpenAVMKit's name for the parcel file with shapes: it requires an entry of this name (load_dataframes).
BASE_NAME = "geo_parcels"


def update_base(project: Project, in_dir: Path, rename: bool = False) -> None:
    """The base: the parcel file with shapes the others join to (F3d).

    It's the one already named geo_parcels if that's a parcel file with shapes, else the first
    parcel file with shapes. With ``rename`` (wizard changes only), the base's entry is renamed
    geo_parcels, as OpenAVMKit requires, and a non-base entry of that name gets another name.
    """
    files = Files(project, in_dir)
    shaped = [f for f in project.files if f.holds == "parcels" and files.geometry(f.name)]
    base = next((f for f in shaped if f.name == BASE_NAME), shaped[0] if shaped else None)
    if base is not None and rename and base.name != BASE_NAME:
        from oakbox.datafiles import suggest_name

        holder = next((f for f in project.files if f.name == BASE_NAME), None)
        if holder is not None:
            holder.name = suggest_name(holder.filename, {f.name for f in project.files} | {BASE_NAME})
        base.name = BASE_NAME
    project.wizard.base = base.name if base else None


def view(project: Project, in_dir: Path) -> Wizard:
    files = Files(project, in_dir)
    by_key = {d.key: d for d in fields.dictionary(project.jurisdiction)}
    base = project.wizard.base
    used = _used(project)
    loaded = {field: f for f in project.files if f.holds in ("parcels", "sales") for field in f.load}

    out_files = []
    for f in project.files:
        match: Match = "key" if f.name == base else f.match
        # More sales details joined on a made sale ID: their own made from their parcel ID and date.
        key = f.load.get("key") if _more_sales(f) and "key_sale" in f.calc else f.load.get(match)
        id_check, repeats = _id_check(files, f.name, f.holds, base)
        extra_ids = []
        if f.name == base and f.name in files.preview:
            for field in EXTRA_IDS:
                spec = f.load.get(field)
                if spec:
                    extra_ids.append(ExtraId(field=field, column=spec[0]))
        out_files.append(
            WizardFile(
                name=f.name,
                filename=f.filename,
                missing=not (in_dir / f.filename).is_file(),
                problem=files.problem.get(f.name),
                rows=len(files.values(f.name, key[0])) if key and f.name in files.preview else _rows(files, f.name),
                geometry=files.geometry(f.name),
                holds=f.holds,
                match=match,
                id_column=key[0] if key else None,
                id_check=id_check,
                repeats=repeats,
                extra_ids=extra_ids,
                columns=files.columns(f.name),
                base=f.name == base,
                clean=f.clean,
                unshaped=_unshaped(files, f, base),
                units=units_view(project, files, f) if f.units is not None else None,
                appended=rows_view(project, files, f) if f.holds in ROWS else None,
                date_column=f.load.get("sale_date", [None])[0] if _more_sales(f) else None,
            )
        )

    sales = sales_file(project)
    sale_id = SaleId(file=None, column=None, made=False, check=None)
    if sales is not None:
        spec = sales.load.get("key_sale")
        made = "key_sale" in sales.calc
        check = None
        if spec and sales.name in files.preview:
            present = [v for v in files.values(sales.name, spec[0]) if v]
            dupes = len(present) - len(set(present))
            check = Check(ok=not dupes, text="✓ all different" if not dupes else f"{dupes:,} repeated")
        elif made:
            has_date = "sale_date" in sales.load
            check = Check(ok=has_date, text="from parcel ID + sale date" if has_date else "needs a sale date")
        sale_id = SaleId(file=sales.name, column=spec[0] if spec else None, made=made, check=check)

    set_fields = {
        value_field(v.id, part): f"{v.name} {words}" for v in value_sets(project) for part, words in VALUE_PARTS.items()
    }
    out_fields = []
    for step in STEPS:
        for more, keys in ((False, step.fields), (True, step.more)):
            for key in keys:
                d = by_key.get(key)
                if d is None:
                    continue
                # A units file gives its units the parcel universe's own fields: not a second source of them.
                given = [f for f in _field_files(project, step.sales) if key in f.load]
                sources = [
                    Source(file=f.name, column=f.load[key][0])
                    for f in given
                    if f.units is None or all(g.units is not None for g in given)
                ]
                ruled = next((f for f in _field_files(project, step.sales) if key in f.rules), None)
                rule = ruled.rules[key] if ruled else None
                if ruled and rule and rule.conditions:
                    sources.append(Source(file=ruled.name, column=rule.conditions[0].column))
                check = None
                date_format = None
                area_unit = None
                number_format = None
                scale = None
                if ruled and rule is not None and len(sources) == 1:
                    check = _rule_check(files, ruled, key, rule)
                elif len(sources) == 1:
                    col = files.column(sources[0].file, sources[0].column)
                    spec = files.entry(sources[0].file).load.get(key, [])
                    if col and d.type == "date" and len(spec) == 3:
                        date_format = spec[2]
                        check = _date_check(files, sources[0].file, col.name, spec[2])
                    elif col and key in AREA_FIELDS:
                        entry = files.entry(sources[0].file)
                        area_unit = entry.area_units.get(key, small_unit(project.units))
                        check = field_check(d, col)[0]
                        if check.ok:
                            check = _area_check(files, entry, key, col.name, area_unit, project.units)
                    elif col and key in SCALED:
                        entry = files.entry(sources[0].file)
                        scale = entry.scales.get(key) or Scale()
                        check = _scale_check(files, entry, key, col.name, scale)
                    elif col and is_money(key):
                        entry = files.entry(sources[0].file)
                        number_format = entry.numbers.get(key)
                        check = _money_check(project, files, entry, key, col.name, number_format)
                    else:
                        check = field_check(d, col)[0] if col else Check(ok=False, text="not in the file")
                elif len(sources) > 1:
                    check = Check(ok=False, text="loaded from more than one file")
                assumed = bool(sales and key in ASSUMABLE and key in sales.calc)
                name, description = RENAMED.get(key, (d.name, d.description))
                if key in set_fields:  # a value set's field: named by the set ("Acme AVM market value")
                    name = set_fields[key]
                if project.units == "metric":  # written as land_area_sqm etc. (datafiles.area_key)
                    name, description = (x.replace("square feet", "square metres") for x in (name, description))
                out_fields.append(
                    WizardField(
                        key=key,
                        name=name,
                        description=description,
                        type=d.type,
                        step=step.key,
                        more=more,
                        sources=sources,
                        assumed=assumed,
                        check=check,
                        hidden=key in ONLY_WITHOUT and ONLY_WITHOUT[key] in loaded,
                        rule=rule,
                        date_format=date_format,
                        area_unit=area_unit,
                        number_format=number_format,
                        scale=scale,
                        absent=key in project.wizard.absent and not sources,
                        distinct=_distinct(files, sources[0]) if len(sources) == 1 else None,
                    )
                )

    _diagnose_missing(project, files, out_files)
    problems = _problems(out_files, sale_id, out_fields)
    warnings = _warnings(out_files, out_fields)
    layer_list = layers(project, in_dir)
    steps = []
    has = has_condos(project)
    for step in STEPS:
        if step.parent == "condos" and step.key != "condo_ask" and not has:
            continue  # the rest of Condo units, only once some parcels are units
        status, left = _status(project, step, out_files, sale_id, out_fields, problems, warnings, layer_list)
        steps.append(
            StepView(
                key=step.key,
                parent=step.parent,
                status=status,
                left=left,
                fields=step.fields,
                more=step.more,
                sales=step.sales,
            )
        )
    for parent in (s for s in steps if s.key in PARENTS):
        # A step with parts (More details, Condo units) shows the worst of them.
        subs = [s.status for s in steps if s.parent == parent.key]
        worst = min(subs, key=lambda x: ORDER[x])
        if worst in ("blocked", "attention"):
            parent.status = worst
        else:
            parent.status = "done" if all(x == "done" for x in subs) else "blank"

    not_loaded = []
    for f in project.files:
        if f.holds in ("parcels", "sales"):
            rest = [c.name for c in files.columns(f.name) if c.name not in used.get(f.name, {})]
            if rest:
                not_loaded.append(NotLoaded(file=f.name, columns=rest))

    return Wizard(
        steps=steps,
        files=out_files,
        sale_id=sale_id,
        fields=out_fields,
        used=used,
        problems=problems,
        warnings=warnings,
        not_loaded=not_loaded,
        locations=locations(project, in_dir),
        custom=custom_fields(project, in_dir),
        layers=layer_list,
        deeds=_deeds_check(project, files),
        permits=_permits_view(project, files),
        condos=_condos_view(project, out_files),
        value_sets=[ValueSetView(id=v.id, name=v.name, roll=v.id == ROLL) for v in value_sets(project)],
    )


def _status(
    project: Project,
    step: Step,
    files: list[WizardFile],
    sale_id: SaleId,
    flds: list[WizardField],
    problems: list[str],
    warnings: list[str],
    layer_views: list[LayerView] | None = None,
) -> tuple[Status, list[Left]]:
    """A step's mark, worked out from what's on it, and what's left to do there (SPEC F3d). Blank until visited."""
    w = project.wizard
    layer_views = layer_views or []
    if step.key in PARENTS:
        return "blank", []  # the worst of its parts, filled in by the caller
    if step.key == "condo_ask":
        return _condo_ask_status(project, files)
    if step.key not in w.visited:
        return "blank", []
    if step.key == "review":
        return ("blocked" if problems else "attention" if warnings else "done"), []
    mine = [f for f in flds if f.step == step.key and not f.hidden]
    left = [Left(text=f"{f.name}: {f.check.text}") for f in mine if f.check is not None and not f.check.ok]
    # Quality and condition still to rank or say the meaning of: to do, but optional fields don't block.
    left += [
        Left(text=f"{f.name}: {f.check.text}", blocking=False)
        for f in mine
        if f.key in SCALED and f.check is not None and f.check.ok and f.check.warn
    ]

    def ids(f: WizardFile | None, what: str) -> None:
        if f is None:
            left.append(Left(text=f"Add the {what} file"))
        elif f.id_check is None:
            left.append(Left(text="Pick the parcel ID"))
        else:
            todo = [i for i in f.id_check.issues if not i.resolved]
            left.extend(Left(text=i.todo or i.text, blocking=i.blocking) for i in todo)
            share = f.id_check.share
            low = share is not None and share < MATCH_OK
            if low and _shapeless(f):
                # Rows without a shape of their own are the Condo units step's: a pointer there, never a stop here.
                n = _n(f.unshaped, "row")
                text = (
                    f"{n} without a shape of their own are left out: no units, you said on Condo units"
                    if project.wizard.condos is False
                    else f"{n} without a shape of their own: condos or other units? Set them up on Condo units"
                )
                left.append(Left(text=text, blocking=False))
            elif low and f.not_in_universe is not None:
                # Parcels missing from the parcel universe, not IDs to clean: a note on the step (and on Review),
                # not a to-do here, unless so few match that it's likely the wrong file or ID.
                if (share or 0) < MATCH_MIN:
                    left.append(Left(text=f.not_in_universe.lines[0]))
            elif low:
                text = f.id_check.text
                matched = text if "match" in text else f"only {_pct(round((share or 0) * 1000), 1000)} match"
                left.append(Left(text=f"Reconcile the IDs: {matched}", blocking=(share or 0) < MATCH_MIN))
            if (
                not f.id_check.ok
                and not any(i.blocking for i in todo)
                and not (low and (share or 0) < MATCH_MIN)
                and not _shapeless(f)
            ):
                left.append(Left(text=f"Parcel ID: {f.id_check.text}"))

    if step.key == "universe":
        base = next((f for f in files if f.base), None)
        if base is not None and base.name != BASE_NAME:
            left.append(Left(text="Use this file as the parcel universe"))
        ids(base, "parcel")
    elif step.key == "more_files":
        for f in files:
            # Map layers are the Shapefiles step's; they join by where parcels are, not on an ID.
            if f.base or f.holds in ("unused", "overlay", "permits") or (f.holds == "sales" and not _more_sales(f)):
                continue
            if f.holds is None:
                left.append(Left(text=f"{f.name}: say what it joins to", blocking=False))
            elif f.id_column is None:
                left.append(Left(text=f"{f.name}: pick the ID it joins on"))
            else:
                before = len(left)
                ids(f, f.name)
                for i in left[before:]:
                    i.text = f"{f.name}: {i.text}"
            if f.appended is not None:
                a = f.appended
                if a.few:
                    text = f"{f.name}: has {a.have} of the {a.of} fields: the right file?"
                    left.append(Left(text=text, blocking=False))
                if not a.key_ok and f.id_column is not None:
                    left.append(Left(text=f"{f.name}: {a.key_text}", blocking=False))
    elif step.key.startswith("condo_"):
        left.extend(_condo_left(step.key, files))
    elif step.key == "permits":
        f = next((f for f in files if f.holds == "permits"), None)
        if f is not None:
            ids(f, "permits")
            pv = _permits_left(project)
            left.extend(Left(text=t) for t in pv)
    elif step.key == "enrich":
        left.extend(Left(text=t, blocking=False) for t in enrichments.left(project))
    elif step.key == "shapefiles":
        for lv in layer_views:
            left.extend(Left(text=f"{lv.name}: {p.text}", blocking=p.blocking) for p in lv.left)
    elif step.key == "sales":
        sales = next((f for f in files if f.holds == "sales" and not _more_sales(f)), None)
        ids(sales, "sales")
        if sales is not None:
            if sale_id.column is None and not sale_id.made:
                left.append(Left(text="Pick a sale ID, or make one"))
            elif sale_id.check is not None and not sale_id.check.ok:
                left.append(Left(text=f"Sale ID: {sale_id.check.text}"))
            for f in mine:
                if f.key in ("sale_price", "sale_date", *ASSUMABLE) and not f.sources and not f.assumed:
                    left.append(Left(text=f"Pick the {f.name.lower()}"))
    elif step.key == "big_five":
        by_key = {f.key: f for f in flds}
        left.extend(
            Left(text=f"Pick the {by_key[k].name.lower()}") for k in REQUIRED if k in by_key and not by_key[k].sources
        )
        # Age is the one to flag; quality and condition are nice to have, and many places lack them.
        if not any(by_key[k].sources for k in AGE if k in by_key):
            left.append(Left(text="Pick the year built (or an age)", blocking=False))
    left.sort(key=lambda i: not i.blocking)
    if any(i.blocking for i in left):
        return "blocked", left
    if left:
        return "attention", left
    if step.key in ("universe", "sales", "big_five"):
        return "done", left
    return ("done" if step.key in w.confirmed or step.key in w.skipped else "blank"), left


def confirm(project: Project, step: str) -> None:
    """Next (or Start) on a step: an optional step counts as complete once it's been moved on from."""
    if step not in STEP_KEYS:
        raise NotFound(step)
    if step not in project.wizard.confirmed:
        project.wizard.confirmed.append(step)


def _shapeless(f: WizardFile) -> bool:
    """A parcel file whose rows mostly have no shape of their own, not set up as units: the Condo units step's."""
    return f.holds == "parcels" and not f.base and f.units is None and f.unshaped >= 0.5 * (f.rows or 1) > 0


def _label(f: WizardFile) -> str:
    """What a file is called in messages: the parcel universe and the sales record by those names (our terms)."""
    if f.base:
        return "Parcel universe"
    if f.holds == "sales" and not _more_sales(f):
        return "Sales record"
    return f.name


def _problems(files: list[WizardFile], sale_id: SaleId, flds: list[WizardField]) -> list[str]:
    out = []
    base = next((f for f in files if f.base), None)
    if base is None:
        out.append("No parcel universe yet: add a file of parcels with shapes.")
    elif base.name != BASE_NAME:
        out.append(f"The parcel universe file must be named {BASE_NAME}. Open Parcel universe to fix it.")
    for f in files:
        if f.holds in ("parcels", "sales") and f.id_column is None:
            out.append(f"{_label(f)}: no ID column to join on.")
        blocking = [i for i in f.id_check.issues if i.blocking] if f.id_check else []
        for issue in blocking:
            out.append(f"{_label(f)}: {issue.text.split(',')[0]}. Resolve them on its step to drop those rows.")
        if f.id_check is not None and not f.id_check.ok and not blocking and f.holds in ("parcels", "sales"):
            if not _shapeless(f):  # rows without a shape: Condo units' to set up (or leave out), not a stop
                out.append(f"{_label(f)}: {f.id_check.text.removeprefix('✓ ')}.")
        if f.units is not None and not f.units.land.ok:
            # OpenAVMKit stops when it can't work out the units' land.
            out.append(f"Condo units › Land: {f.units.land.text}.")
        if f.units is not None and not f.units.check.ok:
            out.append(f"Condo units: {f.units.check.text}.")
    if not any(f.holds == "sales" for f in files):
        out.append("No sales record yet.")
    else:
        if sale_id.column is None and not sale_id.made:
            out.append("The sales record has no sale ID.")
        elif sale_id.check is not None and not sale_id.check.ok:
            out.append(f"Sale ID: {sale_id.check.text}.")
        for f in flds:
            if f.key in ("sale_price", "sale_date", "valid_sale", "vacant_sale") and not f.sources and not f.assumed:
                out.append(f"No {f.name.lower()}.")
    by_key = {f.key: f for f in flds}
    for key in REQUIRED:
        if key in by_key and not by_key[key].sources:
            out.append(f"No {by_key[key].name.lower()}: a model needs it.")
    for f in flds:
        if f.check is not None and not f.check.ok:
            out.append(f"{f.name}: {f.check.text}.")
    return out


def _warnings(files: list[WizardFile], flds: list[WizardField]) -> list[str]:
    by_key = {f.key: f for f in flds}
    out = []
    for f in files:
        r = f.repeats
        if r is None or f.holds not in ("parcels", "sales"):
            continue
        if r.blank and not r.blank_ok and f.holds == "sales":
            what = _n(r.blank, "sale")
            out.append(
                f"{_label(f)}: {what} {'has' if r.blank == 1 else 'have'} no ID and will be dropped. "
                f"That can mean {f.id_column} isn't the right ID."
            )
        if f.holds == "parcels" and r.extra and r.few and r.policy is None:
            out.append(
                f"{_label(f)}: {_n(r.repeated, 'ID')} repeat{'s' if r.repeated == 1 else ''}. "
                "Resolve it on its step; until then OpenAVMKit keeps the first row of each."
            )
    for f in files:
        if f.units is not None and f.units.offers:
            names = ", ".join(x.name.lower() for x in f.units.offers[:4]) + ("…" if len(f.units.offers) > 4 else "")
            out.append(
                f"{_label(f)}: its units don't have {names} yet; the file has columns of the same name. Give them "
                f"on Condo units › Their fields, or the units go without."
            )
        if f.not_in_universe is not None:
            out.append(f"{_label(f)}: {' '.join(f.not_in_universe.lines)}")
    for group in RECOMMENDED:
        if not any(by_key[k].sources for k in group if k in by_key):
            first = by_key.get(group[0])
            if first is not None:
                out.append(f"No {first.name.lower()}: recommended for a good model.")
    return out


def visit(project: Project, in_dir: Path, step: str) -> None:
    """Show a step: fill in guesses for whatever on it hasn't been decided (F3d)."""
    if step not in STEP_KEYS:
        raise NotFound(step)
    _guess(project, in_dir, step)
    if step == "enrich":
        enrichments.start(project, in_dir)
    if step not in project.wizard.visited:
        project.wizard.visited.append(step)


def _guess(project: Project, in_dir: Path, step: str) -> None:
    """Guesses for a step: once a file is there to guess from, and never over a choice."""
    files = Files(project, in_dir)
    if step == "universe":
        _guess_universe(project, files)
    if step == "sales":
        _guess_sales(project, files)
    spec = next(s for s in STEPS if s.key == step)
    candidates = [f.name for f in _field_files(project, spec.sales)]
    if not candidates:
        return
    by_key = _by_key()
    loaded = {field for f in project.files for field in f.load}
    # A field is decided once chosen (even as none) or guessed; a guess that found nothing can
    # still find something in a file added later.
    for key in [*spec.fields, *spec.more]:
        if key in project.wizard.decided or key not in by_key:
            continue
        if key in loaded or (key in ONLY_WITHOUT and ONLY_WITHOUT[key] in loaded):
            continue
        if key in PAIRS and key not in SCALED and PAIRS[key] in loaded:
            continue  # the number's there: the category is loaded only if asked for (F3d)
        if key in SCALED and key in project.wizard.absent:
            continue
        found = _guess_field(files, by_key[key], candidates, _used(project))
        if found:
            files.entry(found[0]).load[key] = found[1]
            if key in SCALED:
                files.entry(found[0]).scales[key] = _new_scale(files, files.entry(found[0]), key, found[1][0])
            if key in AREA_FIELDS:
                unit = guess_area_unit(found[1][0]) or small_unit(project.units)
                files.entry(found[0]).area_units[key] = unit
            loaded.add(key)
            project.wizard.decided.append(key)


def _guess_universe(project: Project, files: Files) -> None:
    base = base_file(project)
    if base is not None and "key" not in base.load and base.name in files.preview:
        column = _guess_id(files, base.name, "parcels", None)
        if column:
            base.load["key"] = [column, "string"]


def _guess_sales(project: Project, files: Files) -> None:
    sales = sales_file(project)
    if sales is None or sales.name not in files.preview:
        return
    base = base_file(project)
    names = {c.name for c in files.columns(sales.name)}
    if not any(k in sales.load for k in ("key", *EXTRA_IDS)):
        # The universe's ID column names in the sales file decide: its parcel ID first, then its extra IDs.
        found = next((k for k in ("key", *EXTRA_IDS) if base and base.load.get(k) and base.load[k][0] in names), None)
        if found and base:
            sales.load[found] = [base.load[found][0], "string"]
            sales.match = cast(Match, found)
        else:
            # The column whose values are the universe's parcel IDs, even written differently; else by name.
            column = _best_match(files, sales.name, base, "key") if base and "key" in base.load else None
            column = column or _guess_id(files, sales.name, "sales", None)
            if column:
                sales.load["key"] = [column, "string"]
    if "key_sale" not in sales.load and "key_sale" not in sales.calc:
        column = _guess_sale_id(files, sales.name)
        if column:
            sales.load["key_sale"] = [column, "string"]
        else:
            sales.calc["key_sale"] = made_sale_id(sales.match)


def _loose(v: str) -> str:
    """An ID compared loosely, for guessing only: letters and digits, no leading zeros, one case."""
    return re.sub(r"[^0-9A-Za-z]", "", v).lstrip("0").upper()


def _best_match(files: Files, name: str, target: DataFile, field: str) -> str | None:
    """The column of a file whose values best match a target's IDs, compared loosely; None under 30%."""
    want = {_loose(v) for v in files.ids(target.name, field) if v}
    want.discard("")
    if not want:
        return None
    best: tuple[float, str] | None = None
    for c in files.columns(name)[:60]:
        if c.type not in ("text", "number"):
            continue
        values = {_loose(v) for v in files.values(name, c.name) if v}
        values.discard("")
        if not values:
            continue
        share = len(values & want) / len(values)
        if share >= 0.3 and (best is None or share > best[0]):
            best = (share, c.name)
    return best[1] if best else None


def _guess_join(project: Project, files: Files, entry: DataFile) -> None:
    """A file just said to join the parcels or the sales: the ID column with the same name as its target's,
    or one that looks like an ID."""
    names = {c.name for c in files.columns(entry.name)}
    if entry.match == "key_sale":
        main = sales_file(project)
        column = main.load["key_sale"][0] if main and "key_sale" in main.load else None
        found = column if column in names else None
        found = found or (_best_match(files, entry.name, main, "key_sale") if main and column else None)
        found = found or _guess_sale_id(files, entry.name)
    else:
        base = base_file(project)
        column = base.load[entry.match][0] if base and entry.match in base.load else None
        found = column if column in names else None
        found = found or (_best_match(files, entry.name, base, entry.match) if base and column else None)
        # Several rows per parcel are fine here (building cards): don't insist on one each.
        found = found or _guess_id(files, entry.name, "sales", column)
    if found:
        entry.load[entry.match] = [found, "string"]


def repeat_rows(project: Project, in_dir: Path, name: str, limit: int = 5) -> RepeatRows:
    """Every row of a few repeated IDs, for the duplicates dialog: are they copies, or different records?"""
    files = Files(project, in_dir)
    entry = files.entry(name)
    field = "key" if name == project.wizard.base else entry.match
    spec = entry.load.get(field)
    if spec is None or name not in files.preview:
        raise ValueError(f"{name} has no ID column yet.")
    values = files.ids(name, field)
    counts: dict[str, int] = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    # A few of the most repeated, then shown sorted by the ID, each ID's rows together.
    from oakbox.bring_in import bands, natural

    ids = [v for v, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n > 1][:limit]
    ids.sort(key=natural)
    loaded = [s[0] for s in entry.load.values()]
    shown = [spec[0], *[c for c in loaded if c != spec[0]]][:8]
    rest = [c.name for c in files.columns(name) if c.name not in shown]
    shown = (shown + rest)[:8]
    picked = [i for i, v in enumerate(values) if v in set(ids)]
    columns = {c: files.values(name, c) for c in shown}
    rows = [[columns[c][i] for c in shown] for i in sorted(picked, key=lambda i: ids.index(values[i]))]
    rows = rows[:40]
    return RepeatRows(columns=shown, rows=rows, bands=bands(r[0] for r in rows))


def _main_made(project: Project) -> bool:
    """The sales record's sale ID is made from parcel ID + date (not a column)."""
    main = sales_file(project)
    return main is not None and "key_sale" in main.calc


def made_sale_id(match: Match) -> list:
    """The sale ID made from the parcel ID + sale date, e.g. "0012-001-2023-01-09" (an OpenAVMKit calc)."""
    return ["join", ["values", match, "sale_date"], "str:-"]


def set_file(
    project: Project,
    in_dir: Path,
    name: str,
    holds: Holds | None,
    id_column: str | None,
    extra_field: str | None = None,
    extra_column: str | None = None,
    match: Match | None = None,
    universe: bool = False,
    dupes: Dupes | None = None,
    dupes_sort: str | None = None,
    dupes_desc: bool = False,
    blank_ok: bool | None = None,
) -> None:
    """A file's part (the parcel universe, sales, or more parcel details) and the ID it joins on.

    ``extra_field`` (key2, key3) with ``extra_column`` sets one of the universe's extra IDs; with
    no column it removes it (key3 then becomes key2).
    """
    files = Files(project, in_dir)
    entry = files.entry(name)
    columns = {c.name for c in files.columns(name)}
    for column in (id_column, extra_column):
        if column is not None and column not in columns:
            raise ValueError(f"{name} has no column {column}.")
    if universe:
        if not files.geometry(name):
            raise ValueError(f"{name} has no shapes. The parcel universe needs parcel geometry.")
        for f in project.files:
            if f is not entry and f.holds == "parcels" and f.name == project.wizard.base:
                f.holds = "unused"
                project.wizard.base = None
        entry.holds, entry.match, holds = "parcels", "key", None
    is_base = universe or entry.name == project.wizard.base
    if holds == "parcel_rows" and not files.geometry(name):
        raise ValueError(f"{name} has no shapes: parcels added to the universe need their shape, as the others have.")
    if holds is not None and holds != entry.holds and (holds in ROWS or entry.holds in ROWS):
        # Into or out of appended rows: its fields were for the other role; the ID stays, as the parcel ID.
        kept = entry.load.get(entry.match) or entry.load.get("key")
        entry.load, entry.rules, entry.calc = ({"key": kept} if kept else {}), {}, {}
        entry.match = "key"
    if holds == "parcels" and entry.match == "key_sale":  # was more sales details: back to a parcel ID
        match = match if match not in (None, "key_sale") else "key"
    if match == "key_sale" and (holds or entry.holds) != "sales":
        raise ValueError("Only sales details join the sales record on the sale ID.")
    if match is not None and not is_base and match != entry.match:
        old = entry.load.pop(entry.match, None)
        entry.match = match
        if old and id_column is None:
            id_column = old[0]
    joined_made = (holds or entry.holds) == "sales" and entry.match == "key_sale" and _main_made(project)
    if id_column is not None:
        # Appended rows, and details joined on a made sale ID, carry the parcel ID.
        field = "key" if is_base or (holds or entry.holds) in ROWS or joined_made else entry.match
        if not is_base:
            for other in ("key", *EXTRA_IDS):
                if other != field:
                    entry.load.pop(other, None)
        _put(entry, field, [id_column, "string"])
    if extra_field is not None:
        if extra_field not in EXTRA_IDS or not is_base:
            raise ValueError("Extra IDs belong to the parcel universe: key2, then key3.")
        if extra_column is not None:
            if extra_field == "key3" and "key2" not in entry.load:
                raise ValueError("Add the 2nd ID first.")
            entry.load.pop(extra_field, None)
            _put(entry, extra_field, [extra_column, "string"])
        else:  # removed: the 3rd ID moves up to 2nd
            entry.load.pop(extra_field, None)
            if extra_field == "key2" and "key3" in entry.load:
                entry.load["key2"] = entry.load.pop("key3")
                for f in project.files:  # files joined on the 3rd ID follow it
                    if f is not entry and f.match == "key3":
                        f.match = "key2"
                        if "key3" in f.load:
                            f.load["key2"] = f.load.pop("key3")
    if holds is not None and holds != entry.holds:
        if holds == "sales" and entry.match != "key_sale":  # one main sales file: a new one replaces it
            for f in project.files:
                if f is not entry and f.holds == "sales" and f.match != "key_sale":
                    f.holds = "unused"
                    f.calc = {}
        if entry.holds == "sales":  # what only a sales file has
            for key in ("key_sale", *ASSUMABLE):
                entry.calc.pop(key, None)
        entry.holds = holds
    if entry.holds == "sales" and entry.match == "key_sale" and joined_made:
        entry.calc["key_sale"] = made_sale_id("key")  # made as the sales record's, from its own columns
    elif entry.holds == "sales" and entry.match == "key_sale":
        entry.calc.pop("key_sale", None)  # more sales details carry the sale ID itself
    elif entry.holds == "sales" and "key_sale" in entry.calc:
        entry.calc["key_sale"] = made_sale_id(entry.match)
    if holds is not None and id_column is None and entry.match not in entry.load and not is_base:
        _guess_join(project, files, entry)
    if entry.holds in ROWS and "key" in entry.load:
        propose_rows(project, in_dir, entry)
    if dupes is not None:  # the duplicates dialog: what to do with repeated IDs
        if dupes_sort is not None and dupes_sort not in entry.load:
            raise ValueError(f"Sort by a field {name} loads; {dupes_sort} isn't one.")
        entry.dupes, entry.dupes_sort, entry.dupes_desc = dupes, dupes_sort, dupes_desc
    if blank_ok is not None:
        entry.blank_ok = blank_ok
    if id_column is not None and dupes is None:  # a new ID: its repeats and blanks are looked at afresh
        entry.dupes, entry.dupes_sort, entry.dupes_desc, entry.blank_ok = None, None, False, False
    update_base(project, in_dir, rename=True)
    # A file just given its part: guess its IDs and fields now, as showing the step would have.
    if universe:
        _guess(project, in_dir, "universe")
    elif holds == "sales":
        _guess(project, in_dir, "sales")
    elif holds == "permits":
        for f in project.files:  # one permits file: a new one replaces it
            if f is not entry and f.holds == "permits":
                f.holds, f.permits = "unused", None
        if entry.permits is None:
            entry.permits = _guess_permits(Files(project, in_dir), entry)
    elif holds == "parcels":  # more parcel details: the steps already seen may find more in it
        for step in STEPS:
            if step.fields and not step.sales and step.key in project.wizard.visited:
                _guess(project, in_dir, step.key)


def _put(entry: DataFile, field: str, spec: list[str]) -> None:
    """Load a column as a field, taking it from whatever field had it."""
    for other, s in list(entry.load.items()):
        if s[0] == spec[0] and other != field:
            raise ValueError(f"{spec[0]} is already loaded as {other}.")
    entry.load[field] = spec


def set_sale_id(project: Project, column: str | None, make: bool) -> None:
    sales = sales_file(project)
    if sales is None:
        raise ValueError("No file holds sales.")
    sales.load.pop("key_sale", None)
    sales.calc.pop("key_sale", None)
    if make:
        sales.calc["key_sale"] = made_sale_id(sales.match)
    elif column:
        _put(sales, "key_sale", [column, "string"])


def set_field(
    project: Project,
    in_dir: Path,
    key: str,
    file: str | None,
    column: str | None,
    assume: bool,
    date_format: str | None = None,
    area_unit: AreaUnit | None = None,
    number_format: NumberFormat | None = None,
    scale: Scale | None = None,
    absent: bool = False,
    only: str | None = None,
) -> None:
    """Load a field from one file's column, from nowhere, or (valid/vacant sale) as an assumption.

    A yes/no field from a column that isn't yes/no gets a rule to fill in: which values mean yes. ``only``: in
    that one file, which carries its own (a file appended as rows, or the date of more sales details joined on a
    made sale ID), the other files untouched."""
    by_key = _by_key()
    step = next((s for s in STEPS if key in s.fields or key in s.more), None)
    if step is None or key not in by_key:
        raise NotFound(key)
    allowed = _field_files(project, step.sales)
    if only is not None:
        allowed = [f for f in project.files if f.name == only and (f.holds in ROWS or _more_sales(f))]
        if not allowed:
            raise NotFound(only)
        step = step.model_copy(update={"sales": allowed[0].holds in ("sales", "sale_rows")})
    sales = sales_file(project)
    target: DataFile | None = None
    spec: list[str] | None = None
    reading: NumberFormat | None = None
    if file is not None and column is not None:
        target = next((f for f in allowed if f.name == file), None)
        if target is None:
            where = "the sales record" if step.sales else "the parcel universe or a file joined to it"
            raise ValueError(f"{key} comes from {where}.")
        col = Files(project, in_dir).column(file, column)
        if col is None:
            raise ValueError(f"{file} has no column {column}.")
        d = by_key[key]
        check, spec = field_check(d, col)
        if key in SCALED:
            # Numbers, or a category to rank into tiers: either way it becomes a number (F3d).
            entry = next(f for f in allowed if f.name == file)
            plain = _plain(values_of(file_stamp(in_dir / entry.filename), entry.layer, column))
            spec = [column, "float"] if plain else [column, "string"]
            if not plain and scale is not None and scale.kind not in (None, "tiers"):
                raise ValueError(f"{column} isn't numbers: rank its tiers instead.")
        if is_money(key):
            # Money written as text ($250,000.00, N/A): read with a format, worked out from the whole column.
            entry = next(f for f in allowed if f.name == file)
            values = values_of(file_stamp(in_dir / entry.filename), entry.layer, column)
            reading = number_format or (None if _plain(values) else detect_number_format(values, project.numbers)[0])
            if reading is not None:
                spec = [column, "float"]
        if d.type == "date" and date_format:
            spec = [column, "datetime", date_format]
        elif spec is None and d.type == "boolean" and step.sales:
            spec = None  # becomes a rule, below
        elif spec is None:
            raise ValueError(f"{column}: {check.text}.")
        for other, s in target.load.items():
            # A category can be both the text and, ranked, the number (F3d).
            if s[0] == column and other != key and not (key in QC_FIELDS and other in QC_FIELDS):
                raise ValueError(f"{column} is already loaded as {other}.")
    elif assume and (key not in ASSUMABLE or sales is None):
        raise ValueError(f"{key} can't be assumed.")
    elif absent and key not in ABSENT_OK:
        raise ValueError(f"{key} can't be said not to exist.")
    for f in allowed:
        f.load.pop(key, None)
        f.rules.pop(key, None)
        f.area_units.pop(key, None)
        f.numbers.pop(key, None)
        f.scales.pop(key, None)
    if only is None and key in project.wizard.absent:
        project.wizard.absent.remove(key)
    if absent and only is None:
        project.wizard.absent.append(key)
    if only is None and sales is not None and key in ASSUMABLE:  # (one file's own: the sales record untouched)
        sales.calc.pop(key, None)
    if target is not None and spec is None:
        target.rules[key] = Rule(conditions=[Condition(column=cast(str, column))])
    if target is not None and spec is not None:
        target.load[key] = spec
        if key in AREA_FIELDS:
            target.area_units[key] = area_unit or guess_area_unit(cast(str, column)) or small_unit(project.units)
        if reading is not None:
            target.numbers[key] = reading
        if key in SCALED:
            target.scales[key] = _new_scale(Files(project, in_dir), target, key, spec[0], scale)
    elif assume and sales is not None:
        sales.calc[key] = ["set", ASSUMABLE[key]]
    if only is not None:
        return
    if key not in project.wizard.decided:
        project.wizard.decided.append(key)
    if step.key in project.wizard.skipped and (file or assume):
        project.wizard.skipped.remove(step.key)


def set_row_field(
    project: Project, in_dir: Path, name: str, key: str, column: str | None, date_format: str | None = None
) -> None:
    """One field of a file appended as rows (or the date of more sales details on a made sale ID): its own column,
    or none (blank for its rows). A yes/no field takes the main file's rule, on this column."""
    entry = next((f for f in project.files if f.name == name), None)
    if entry is None or not (entry.holds in ROWS or _more_sales(entry)):
        raise NotFound(name)
    main = rows_main(project, entry.holds or "")
    if column is None:
        for part in (entry.load, entry.rules, entry.area_units, entry.numbers, entry.scales):
            part.pop(key, None)
        if main is not None and entry.holds == "sale_rows":
            rows_assume(main, entry)  # no column: assumed as the sales record assumes it, if it does
        return
    set_field(project, in_dir, key, name, column, False, date_format=date_format, only=name)
    entry.calc.pop(key, None)  # a column of its own, not an assumption
    if main is not None:
        copy_rule(main, entry, key)


def skip(project: Project, step: str) -> None:
    """'I don't have these': nothing loaded for the step's fields."""
    spec = next((s for s in STEPS if s.key == step), None)
    if spec is None or not spec.fields:
        raise NotFound(step)
    for key in [*spec.fields, *spec.more]:
        if key in ASSUMABLE:
            raise ValueError("Sales need a valid sale and a vacant sale field.")
    for f in _field_files(project, spec.sales):
        for key in [*spec.fields, *spec.more]:
            f.load.pop(key, None)
    for key in [*spec.fields, *spec.more]:
        if key not in project.wizard.decided:
            project.wizard.decided.append(key)
    if step not in project.wizard.skipped:
        project.wizard.skipped.append(step)
    if step not in project.wizard.visited:
        project.wizard.visited.append(step)

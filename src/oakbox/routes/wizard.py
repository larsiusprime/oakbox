"""The Fields wizard (SPEC §3.0 F3d-F3g): its steps, each file's part and ID, the fields, units, map layers,
enrichments, the centre, deed names, and the previews behind them."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import datafiles, enrichments, mapdata, names, projects, wizard
from oakbox.datafiles import BaseModel, CleanStep
from oakbox.errors import NotFound
from oakbox.routes.common import editing, file_entry, load_project, wizard_view
from oakbox.wizard import as_sold, combine, sales_only

router = APIRouter()


class WizardFileChoice(BaseModel):
    """Step 1 of the Fields wizard, for one file (F3d). Leave a value out to keep it."""

    holds: datafiles.Holds | None = None
    universe: bool = Field(default=False, description="Make this the parcel universe file (it needs shapes).")
    match: datafiles.Match | None = Field(default=None, description="Join on the parcel ID (key) or second ID (key2).")
    id_column: str | None = Field(default=None, description="The column loaded as the ID it joins on.")
    extra_field: Literal["key2", "key3"] | None = Field(
        default=None, description="One of the universe's extra IDs: set to extra_column, or removed if it's null."
    )
    extra_column: str | None = None
    dupes: datafiles.Dupes | None = Field(
        default=None, description="Repeated IDs: keep the first of each, or drop all."
    )
    dupes_sort: str | None = Field(default=None, description="With first: the field to sort by before keeping.")
    dupes_desc: bool = False
    dupes_by: list[datafiles.SortKey] | None = Field(
        default=None, description="With first: the file's columns to sort by, in order (the ID breaks ties)."
    )
    blank_ok: bool | None = Field(default=None, description="Acknowledge the rows with no ID (they're dropped).")
    added: bool = Field(
        default=False, description="Added on More files: one of its files, not said yet what it holds (nothing else)."
    )


class WizardReconcile(BaseModel):
    file_steps: list[CleanStep] = Field(default_factory=list, description="Clean-up steps for the sales file's ID.")
    base_steps: list[CleanStep] = Field(default_factory=list, description="And for the parcel universe's.")


class WizardReconcilePreview(WizardReconcile):
    view: wizard.SampleView = "unmatched"
    seed: int = Field(default=0, description="Change it for new samples.")
    suggest: bool = Field(default=False, description="Also try a few common clean-ups (slower).")


class CombineAsk(BaseModel):
    """What to preview; leave a value out for what's set (or suggested)."""

    about: str | None = None
    groups: list[datafiles.CombineGroup] | None = None
    main: list[str] | None = None
    main_on: bool | None = None
    measures: dict[str, datafiles.CombineHow] | None = None


class CombineSet(BaseModel):
    about: str
    groups: list[datafiles.CombineGroup]
    measures: dict[str, datafiles.CombineHow] = Field(default_factory=dict, description="Number columns kept, how.")
    main: list[str] | None = Field(default=None, description="The order for the main value; None: not made.")


class WizardSaleId(BaseModel):
    column: str | None = None
    make: bool = Field(default=False, description="Make one from parcel ID + sale date.")


class WizardLocation(BaseModel):
    file: str | None = None
    column: str | None = Field(default=None, description="None removes the location field.")


class WizardDates(BaseModel):
    column: str
    format: str


class UnitsBody(BaseModel):
    units: datafiles.Units | None = None
    guess: bool = False


class CondosBody(BaseModel):
    has: bool | None = None


class UnitFieldBody(BaseModel):
    column: str | None = None


class WizardCustom(BaseModel):
    file: str | None = None
    column: str | None = Field(default=None, description="None removes the field.")
    group: Literal["land", "building", "other"] = "other"
    type: Literal["category", "number"] = "category"


class NamesBody(BaseModel):
    format: names.FormatId
    pattern: str | None = Field(default=None, description="For custom: a regular expression with a surname group.")


class WizardFieldChoice(BaseModel):
    file: str | None = None
    column: str | None = None
    assume: bool = Field(default=False, description="Valid/vacant sale only: all valid, none vacant.")
    date_format: str | None = Field(default=None, description="Dates: the format to read it with.")
    area_unit: datafiles.AreaUnit | None = Field(default=None, description="Areas: the unit the column is in.")
    number_format: datafiles.NumberFormat | None = Field(
        default=None, description="Money written as text: how to read it. None: worked out from the column."
    )
    scale: datafiles.Scale | None = Field(
        default=None, description="Quality/condition number: how the column becomes higher-is-better."
    )
    absent: bool = Field(default=False, description="Condition: there isn't one (effective age carries it).")


class WizardColumnRef(BaseModel):
    file: str
    column: str
    scale: datafiles.Scale | None = Field(default=None, description="None: the saved one, or a first one.")


class WizardNumbers(BaseModel):
    key: str
    column: str
    format: datafiles.NumberFormat | None = Field(default=None, description="None: the saved one, or as detected.")


class UnitFieldsBody(BaseModel):
    fields: dict[str, str]


class PermitsBody(BaseModel):
    permits: datafiles.Permits | None = None
    guess: bool = False


# ---------- F3d: the Fields wizard ----------


@router.get("/api/projects/{project_id}/names")
def get_names(project_id: str, format: names.FormatId | None = None, pattern: str | None = None) -> names.NamesView:
    """The deed names read with the saved format, or with one being tried (a live preview: nothing is saved)."""
    project = load_project(project_id)
    return names.view(project, projects.inputs_dir(project_id), format, pattern)


@router.put("/api/projects/{project_id}/names")
def set_names(project_id: str, body: NamesBody) -> names.NamesView:
    """How the deed names are written: one of the formats, or a regular expression with a surname group."""
    with editing(project_id, settings=True) as project:
        try:
            names.save(project, body.format, body.pattern)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return names.view(project, projects.inputs_dir(project_id))


def _apply(project_id: str, change) -> projects.Project:
    """A change to the project made by the wizard: saved with its settings.json; 404 for an unknown step or
    field, 422 for a change that can't be made."""
    with editing(project_id, settings=True) as project:
        try:
            change(project, projects.inputs_dir(project_id))
        except NotFound as e:
            raise HTTPException(404, f"No such step or field: {e}") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return project


def _change(project_id: str, change) -> wizard.Wizard:
    return wizard_view(_apply(project_id, change))


@router.get("/api/projects/{project_id}/wizard")
def get_wizard(project_id: str) -> wizard.Wizard:
    """Every step, file and field of the Fields wizard as it stands (SPEC §3.0 F3d)."""
    return wizard_view(load_project(project_id))


@router.post("/api/projects/{project_id}/wizard/steps/{step}/visit")
def visit_step(project_id: str, step: str) -> wizard.Wizard:
    """A step is shown: fill in guesses for what on it hasn't been decided yet (F3d)."""
    return _change(project_id, lambda p, d: wizard.visit(p, d, step))


@router.post("/api/projects/{project_id}/wizard/steps/{step}/confirm")
def confirm_step(project_id: str, step: str) -> wizard.Wizard:
    """Next (or Start) on a step: an optional step is complete once moved on from (F3d)."""
    return _change(project_id, lambda p, _d: wizard.confirm(p, step))


@router.post("/api/projects/{project_id}/wizard/steps/{step}/skip")
def skip_step(project_id: str, step: str) -> wizard.Wizard:
    """'I don't have these': nothing loaded for the step's fields (F3d)."""
    return _change(project_id, lambda p, _d: wizard.skip(p, step))


# Choices of a file whose reading was stopped (project:request): when its reading ends, it's undone.
_stopped: set[str] = set()


@router.post("/api/projects/{project_id}/wizard/files/{name}/stop")
def stop_wizard_file(project_id: str, name: str, request: str) -> None:
    """Stop on a file being read for a step (a big one takes a while): the reading can't be cut short, but when it
    ends its choice is undone, unless the project has changed again since (a later choice stands)."""
    load_project(project_id)
    _stopped.add(f"{project_id}:{request}")


def _undo_if_stopped(project_id: str, request: str, before: str, after: str) -> None:
    key = f"{project_id}:{request}"
    if not request or key not in _stopped:
        return
    _stopped.discard(key)
    with projects.lock(project_id):
        now = load_project(project_id)
        if now.model_dump_json() == after:  # nothing else changed it since: put it back as it was
            back = projects.Project.model_validate_json(before)
            projects.save(back)
            projects.write_settings(back)
    raise HTTPException(409, "Stopped: the file wasn't set for the step.")


@router.put("/api/projects/{project_id}/wizard/files/{name}")
def wizard_file(project_id: str, name: str, body: WizardFileChoice, request: str = "") -> wizard.Wizard:
    """A file's part (parcel universe, sales, more parcel details) and the ID it joins on (F3d). `request`: an ID for
    this choice, so Stop (.../stop) can undo it once its reading ends."""
    project = load_project(project_id)
    file_entry(project, name)
    before = project.model_dump_json()
    changed = _apply(
        project_id,
        lambda p, d: wizard.set_file(
            p,
            d,
            name,
            holds=body.holds,
            id_column=body.id_column,
            extra_field=body.extra_field,
            extra_column=body.extra_column,
            match=body.match,
            universe=body.universe,
            dupes=body.dupes,
            dupes_sort=body.dupes_sort,
            dupes_desc=body.dupes_desc,
            dupes_by=body.dupes_by,
            blank_ok=body.blank_ok,
            added=body.added,
        ),
    )
    after = changed.model_dump_json()
    _undo_if_stopped(project_id, request, before, after)
    out = wizard_view(changed)
    _undo_if_stopped(project_id, request, before, after)
    if body.universe:  # the map window's shapes, made in the background (SPEC §3.15)
        mapdata.start(load_project(project_id), projects.project_dir(project_id), projects.inputs_dir(project_id))
    return out


@router.get("/api/projects/{project_id}/wizard/files/{name}/repeats")
def wizard_repeats(project_id: str, name: str) -> wizard.RepeatRows:
    """Every row of a few repeated IDs, for the duplicates dialog (F3d)."""
    project = load_project(project_id)
    file_entry(project, name)
    try:
        return wizard.repeat_rows(project, projects.inputs_dir(project_id), name)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{project_id}/wizard/files/{name}/combine/preview")
def wizard_combine_preview(project_id: str, name: str, body: CombineAsk) -> combine.CombinePreview:
    """What combining a parcel file's rows into one per parcel would make: its groups, numbers and main value, with
    how many parcels each (F3d duplicates dialog); nothing is saved."""
    project = load_project(project_id)
    file_entry(project, name)
    try:
        return combine.preview(
            project,
            projects.inputs_dir(project_id),
            name,
            about=body.about,
            groups=body.groups,
            main=body.main,
            main_on=body.main_on,
            measures=body.measures,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.put("/api/projects/{project_id}/wizard/files/{name}/combine")
def wizard_combine(project_id: str, name: str, body: CombineSet) -> wizard.Wizard:
    """Combine a parcel file's rows into one per parcel (or change how): its fields become the user's own."""
    return _change(
        project_id,
        lambda p, d: combine.set_combine(p, d, name, body.about, body.groups, body.measures, body.main),
    )


@router.post("/api/projects/{project_id}/wizard/files/{name}/reconcile")
def wizard_reconcile_preview(project_id: str, name: str, body: WizardReconcilePreview) -> wizard.Reconcile:
    """How the sales would match the parcels with these clean-up steps, with samples; nothing is saved (F3d)."""
    project = load_project(project_id)
    file_entry(project, name)
    try:
        return wizard.reconcile(
            project,
            projects.inputs_dir(project_id),
            name,
            body.file_steps,
            body.base_steps,
            body.view,
            body.seed,
            body.suggest,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.put("/api/projects/{project_id}/wizard/files/{name}/reconcile")
def wizard_reconcile(project_id: str, name: str, body: WizardReconcile) -> wizard.Wizard:
    """Save the clean-up steps for the sales file's ID and the parcel universe's (F3d)."""
    return _change(project_id, lambda p, d: wizard.set_reconcile(p, d, name, body.file_steps, body.base_steps))


class RowFieldChoice(BaseModel):
    column: str | None = Field(description="Its column in this file; null: not in it (blank for its rows).")
    date_format: str | None = None


@router.put("/api/projects/{project_id}/wizard/files/{name}/rows/{key}")
def wizard_row_field(project_id: str, name: str, key: str, body: RowFieldChoice) -> wizard.Wizard:
    """A field of a file appended as rows (more sales, more parcels), or the date of more sales details joined on
    a made sale ID: from this file's own column (F3d)."""
    return _change(project_id, lambda p, d: wizard.set_row_field(p, d, name, key, body.column, body.date_format))


@router.put("/api/projects/{project_id}/wizard/sale-id")
def wizard_sale_id(project_id: str, body: WizardSaleId) -> wizard.Wizard:
    """The sales file's sale ID: a column, or made from parcel ID + sale date (F3d)."""
    return _change(project_id, lambda p, _d: wizard.set_sale_id(p, body.column, body.make))


@router.put("/api/projects/{project_id}/wizard/fields/{key}")
def wizard_field(project_id: str, key: str, body: WizardFieldChoice) -> wizard.Wizard:
    """Load a field from a file's column, from nowhere, or as an assumption (F3d)."""
    return _change(
        project_id,
        lambda p, d: wizard.set_field(
            p,
            d,
            key,
            body.file,
            body.column,
            body.assume,
            body.date_format,
            body.area_unit,
            body.number_format,
            body.scale,
            body.absent,
        ),
    )


@router.post("/api/projects/{project_id}/wizard/fields/{key}/rule")
def wizard_rule_preview(project_id: str, key: str, body: datafiles.Rule) -> wizard.RulePreview:
    """What a yes/no rule makes of the sales file, without saving it (F3d)."""
    project = load_project(project_id)
    try:
        return wizard.rule_preview(project, projects.inputs_dir(project_id), key, body)
    except NotFound as e:
        raise HTTPException(404, f"No such field: {e}") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.put("/api/projects/{project_id}/wizard/fields/{key}/rule")
def wizard_rule(project_id: str, key: str, body: datafiles.Rule) -> wizard.Wizard:
    """Work a yes/no field (valid sale, vacant sale) out from the sales file's columns (F3d)."""
    return _change(project_id, lambda p, d: wizard.set_rule(p, d, key, body))


class AsSoldChoice(BaseModel):
    column: str | None = Field(description="The sales file's column the sales use; null: today's (the parcel's).")
    area_unit: datafiles.AreaUnit | None = Field(default=None, description="An area: the unit the column is in.")


@router.get("/api/projects/{project_id}/wizard/sales-only")
def wizard_sales_only(project_id: str) -> sales_only.SalesOnlyView:
    """The main sales file's columns no parcel file has: for valid-sale rules and Outliers, not models (F3d)."""
    return sales_only.view(load_project(project_id), projects.inputs_dir(project_id))


@router.get("/api/projects/{project_id}/wizard/as-sold")
def wizard_as_sold(project_id: str) -> as_sold.AsSoldView:
    """Sales record fields: the sales file's columns that mirror a characteristic, each against today's values."""
    project = load_project(project_id)
    return as_sold.view(project, projects.inputs_dir(project_id))


@router.put("/api/projects/{project_id}/wizard/as-sold/{key}")
def wizard_as_sold_choose(project_id: str, key: str, body: AsSoldChoice) -> as_sold.AsSoldView:
    """For a characteristic, the sale's value (its column, read as the parcel's) or today's."""
    with editing(project_id, settings=True) as project:
        try:
            as_sold.choose(project, projects.inputs_dir(project_id), key, body.column, body.area_unit)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return as_sold.view(project, projects.inputs_dir(project_id))


@router.get("/api/projects/{project_id}/wizard/locations")
def wizard_locations(project_id: str) -> list[wizard.LocationField]:
    """The location fields the user named (F3d)."""
    return wizard.locations(load_project(project_id), projects.inputs_dir(project_id))


@router.put("/api/projects/{project_id}/wizard/locations/{name}")
def wizard_location(project_id: str, name: str, body: WizardLocation) -> wizard.Wizard:
    """Load a parcel file's column as a location field the user names; no column removes it (F3d)."""
    return _change(project_id, lambda p, d: wizard.set_location(p, d, name, body.file, body.column))


@router.get("/api/projects/{project_id}/wizard/files/{name}/values")
def wizard_column_values(
    project_id: str,
    name: str,
    column: str,
    search: str = "",
    sort: wizard.ValueSort | None = None,
    desc: bool = True,
) -> wizard.ColumnValues:
    """A column's values with their row counts, most common first, or sorted by count or value (the values list
    beside a field)."""
    try:
        return wizard.column_values(
            load_project(project_id),
            projects.inputs_dir(project_id),
            name,
            column,
            search,
            sort=sort,
            desc=desc,
        )
    except NotFound as e:
        raise HTTPException(404, f"No column {column} in {name}.") from e


@router.put("/api/projects/{project_id}/wizard/condos")
def wizard_condos(project_id: str, body: CondosBody) -> wizard.Wizard:
    """Condo units: do some parcels have no shape of their own, on a parcel they share? No stops any units."""
    return _change(project_id, lambda p, d: wizard.set_condos(p, d, body.has))


@router.put("/api/projects/{project_id}/wizard/files/{name}/units")
def wizard_units(project_id: str, name: str, body: UnitsBody) -> wizard.Wizard:
    """A parcel file's rows without a shape are units on a parcel they share (condos and the like), each
    borrowing that parcel's shape; no settings stops it. guess: work out how units find their parcel again."""
    return _change(project_id, lambda p, d: wizard.set_units(p, d, name, body.units, body.guess))


@router.put("/api/projects/{project_id}/wizard/files/{name}/units/fields")
def wizard_unit_fields(project_id: str, name: str, body: UnitFieldsBody) -> wizard.Wizard:
    """Give the units several of the parcel universe's fields at once: field -> column of their file."""

    def give(p, d):
        for field, column in body.fields.items():
            wizard.set_unit_field(p, d, name, field, column)

    return _change(project_id, give)


@router.put("/api/projects/{project_id}/wizard/files/{name}/units/fields/{field}")
def wizard_unit_field(project_id: str, name: str, field: str, body: UnitFieldBody) -> wizard.Wizard:
    """Give the units one of the parcel universe's fields from a column of their file; no column takes it away."""
    return _change(project_id, lambda p, d: wizard.set_unit_field(p, d, name, field, body.column))


class ValueSetNew(BaseModel):
    name: str


class ValueSetChange(BaseModel):
    name: str | None = None
    roll: bool | None = Field(default=None, description="Make it the assessor's roll (true), or not (false).")


@router.post("/api/projects/{project_id}/wizard/value-sets")
def wizard_add_value_set(project_id: str, body: ValueSetNew) -> wizard.Wizard:
    """Add a set of existing values to compare the models with (a vendor's AVM, last year's values)."""
    return _change(project_id, lambda p, _d: wizard.add_value_set(p, body.name))


@router.patch("/api/projects/{project_id}/wizard/value-sets/{set_id}")
def wizard_change_value_set(project_id: str, set_id: str, body: ValueSetChange) -> wizard.Wizard:
    """Rename a set of values, or make it the roll (or not)."""
    return _change(project_id, lambda p, _d: wizard.change_value_set(p, set_id, body.name, body.roll))


@router.delete("/api/projects/{project_id}/wizard/value-sets/{set_id}")
def wizard_remove_value_set(project_id: str, set_id: str) -> wizard.Wizard:
    """Take a set of values away, with its fields."""
    return _change(project_id, lambda p, _d: wizard.remove_value_set(p, set_id))


@router.put("/api/projects/{project_id}/wizard/custom/{name}")
def wizard_custom(project_id: str, name: str, body: WizardCustom) -> wizard.Wizard:
    """Load a parcel file's column as a field the user names and classifies (land, building or other); no column
    removes it (F3d)."""
    return _change(
        project_id, lambda p, d: wizard.set_custom(p, d, name, body.file, body.column, body.group, body.type)
    )


@router.put("/api/projects/{project_id}/wizard/layers/{name}")
def wizard_layer(project_id: str, name: str, body: datafiles.Overlay | None = None) -> wizard.Wizard:
    """Use a file as a map layer (stamped onto parcels, or measured to); no body sets it aside (F3d)."""
    return _change(project_id, lambda p, d: wizard.set_overlay(p, d, name, body))


@router.put("/api/projects/{project_id}/wizard/files/{name}/permits")
def wizard_permits(project_id: str, name: str, body: PermitsBody) -> wizard.Wizard:
    """The permits file's date and type columns and what each kind of permit means (F3g); no settings stops using
    it as permits. guess: work them out from the file."""
    return _change(project_id, lambda p, d: wizard.set_permits(p, d, name, body.permits, body.guess))


@router.get("/api/projects/{project_id}/wizard/enrich")
def wizard_enrich(project_id: str) -> enrichments.EnrichView:
    """The Enrichments step (F3e): what's chosen, the counties, the area the downloads cover."""
    return wizard.enrich_view(load_project(project_id), projects.inputs_dir(project_id))


@router.put("/api/projects/{project_id}/wizard/enrich")
def set_wizard_enrich(project_id: str, body: enrichments.Enrichments) -> enrichments.EnrichView:
    """Choose the enrichments and their options (F3e)."""
    project = _apply(project_id, lambda p, _d: enrichments.set_enrichments(p, body))
    return wizard.enrich_view(project, projects.inputs_dir(project_id))


@router.get("/api/projects/{project_id}/wizard/layers/{name}/map")
def wizard_layer_map(project_id: str, name: str) -> wizard.LayerMap:
    """A map layer's shapes in degrees, and the parcel centres, for its map (F3d)."""
    project = load_project(project_id)
    try:
        return wizard.layer_map(project, projects.inputs_dir(project_id), name)
    except NotFound as e:
        raise HTTPException(404, f"No such layer: {e}") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/projects/{project_id}/wizard/locations/{name}/map")
def wizard_location_map(project_id: str, name: str) -> wizard.LocationMap:
    """A location field on the map: each parcel's centre, coloured by its area (F3d: Location fields)."""
    try:
        return wizard.location_map(load_project(project_id), projects.inputs_dir(project_id), name)
    except NotFound as e:
        raise HTTPException(404, f"No such location field: {e}") from e


@router.get("/api/projects/{project_id}/wizard/map")
def wizard_map(project_id: str) -> wizard.MapView:
    """Where the parcels are, and the centre polar coordinates are measured from (F3d)."""
    return wizard.map_view(load_project(project_id), projects.inputs_dir(project_id))


@router.put("/api/projects/{project_id}/center")
def set_center(project_id: str, body: projects.Center | None = None) -> wizard.MapView:
    """Set the centre polar coordinates are measured from; none: the middle of the parcels (F3d)."""
    with editing(project_id, settings=True) as project:
        project.center = body
    return wizard.map_view(project, projects.inputs_dir(project_id))


@router.post("/api/projects/{project_id}/wizard/files/{name}/dates")
def wizard_dates(project_id: str, name: str, body: WizardDates) -> wizard.DatePreview:
    """A column read with a date format, as OpenAVMKit reads it (F3d)."""
    project = load_project(project_id)
    file_entry(project, name)
    try:
        return wizard.date_preview(project, projects.inputs_dir(project_id), name, body.column, body.format)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{project_id}/wizard/files/{name}/numbers")
def wizard_numbers(project_id: str, name: str, body: WizardNumbers) -> wizard.NumberPreview:
    """A money column read with a format, as OpenAVMKit reads it, with checks on the amounts (F3d)."""
    project = load_project(project_id)
    file_entry(project, name)
    try:
        return wizard.number_preview(project, projects.inputs_dir(project_id), name, body.key, body.column, body.format)
    except NotFound as e:
        raise HTTPException(404, f"{body.key} isn't an amount of money.") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/projects/{project_id}/wizard/fields/{key}/candidates")
def wizard_candidates(project_id: str, key: str) -> list[wizard.Candidate]:
    """Columns that look like quality or condition, checked over every row, side by side (F3d)."""
    try:
        return wizard.candidates(load_project(project_id), projects.inputs_dir(project_id), key)
    except NotFound as e:
        raise HTTPException(404, f"{key} isn't quality or condition.") from e


@router.get("/api/projects/{project_id}/wizard/fields/{key}/histogram")
def wizard_field_histogram(project_id: str, key: str, sales: bool = False) -> wizard.FieldSpread:
    """How a number field's values spread, as loaded: sizes in the project's unit, years (F3d: Big five). `sales`:
    as the sales file has it (At the sale)."""
    try:
        return wizard.field_histogram(load_project(project_id), projects.inputs_dir(project_id), key, sales=sales)
    except NotFound as e:
        raise HTTPException(404, f"{key} isn't loaded.") from e


@router.post("/api/projects/{project_id}/wizard/fields/{key}/scale")
def wizard_scale(project_id: str, key: str, body: WizardColumnRef) -> wizard.ScalePreview:
    """A quality/condition numbers column read with a meaning, against age and price (F3d)."""
    try:
        return wizard.scale_preview(
            load_project(project_id),
            projects.inputs_dir(project_id),
            key,
            body.file,
            body.column,
            body.scale,
        )
    except NotFound as e:
        raise HTTPException(404, f"{key} isn't quality or condition.") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{project_id}/wizard/fields/{key}/tiers")
def wizard_tiers(project_id: str, key: str, body: WizardColumnRef) -> wizard.TiersPreview:
    """A category's tiers, worst to best, each with a number and what it sells for (F3d)."""
    try:
        return wizard.tiers_preview(
            load_project(project_id), projects.inputs_dir(project_id), key, body.file, body.column
        )
    except NotFound as e:
        raise HTTPException(404, f"{key} isn't quality or condition.") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

"""What the Fields wizard sends: the models of its view (the steps, the files, the fields and what's left to do)
that the app's routes return, so the screens read them. Rows a section of the wizard works out itself (a location
field, a custom field, a map layer) are here too, as the whole view carries them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from oakbox.datafiles import (
    AreaUnit,
    BaseModel,
    CleanStep,
    Dupes,
    Holds,
    Match,
    NumberFormat,
    Overlay,
    PermitMeaning,
    Permits,
    Rule,
    Scale,
    Units,
)
from oakbox.fields import Column

# ---------- What the wizard sends ----------


class Issue(BaseModel):
    text: str = Field(description="'1 repeated ID'; once resolved, with the choice: '1 repeated ID, first kept'.")
    resolved: bool = Field(description="A choice was made for it (the duplicates dialog).")
    blocking: bool = Field(default=False, description="OpenAVMKit can't run well until it's dealt with (blank IDs).")
    todo: str = Field(default="", description="While unresolved, as a to-do: '442 blank IDs to confirm'.")


class Check(BaseModel):
    ok: bool
    text: str = Field(description="Short: '✓ 1890–2025', 'several rows per parcel'.")
    warn: bool = Field(default=False, description="Usable, but worth a look (repeats handled, blank IDs dropped).")
    issues: list[Issue] = Field(default_factory=list, description="What's worth a look, each short.")
    share: float | None = Field(default=None, description="Sales: the share that find a parcel (0-1), for Reconcile.")


class Repeats(BaseModel):
    """What a file's ID column holds, for the duplicates notice and dialog (F3d)."""

    rows: int
    blank: int = Field(description="Rows with no ID. OpenAVMKit drops them when it joins the parcel files.")
    distinct: int = Field(description="Different IDs: the rows kept when keeping the first of each.")
    repeated: int = Field(description="IDs on more than one row.")
    extra: int = Field(description="Rows beyond the first for a repeated ID.")
    singles: int = Field(description="IDs on exactly one row: the rows kept when dropping every repeat.")
    few: bool = Field(description="Under 1% of the rows and under 10 rows: stray repeats, kept-first by default.")
    policy: Dupes | None
    sort: str | None
    descending: bool
    blank_ok: bool = Field(description="The rows with no ID have been acknowledged.")


class RepeatRows(BaseModel):
    """Examples of repeated IDs, every row of each, for the duplicates dialog."""

    columns: list[str]
    rows: list[list[str]]
    bands: list[int] = Field(default_factory=list, description="0 or 1 per row, alternating per ID.")


class UnitExample(BaseModel):
    unit: str = Field(description="The unit's ID (or the column the link is read from).")
    building: str | None = Field(description="The building parcel it finds, None: none.")
    building_value: str | None = Field(
        default=None, description="What it matched in the parcel universe file (the building's own value)."
    )
    share: str | None = Field(default=None, description="Its land share, worked out as the land setting says.")
    address: str = ""


class UnitField(BaseModel):
    field: str
    name: str
    column: str


class UnitsView(BaseModel):
    """What the units settings do on the file's rows, worked out as OpenAVMKit's condo handling will."""

    settings: Units
    units: int = Field(description="Rows without a shape that the rule says are units.")
    linked: int = Field(description="Of them, units that find their building's shape.")
    buildings: int
    examples: list[UnitExample]
    fields: list[UnitField] = Field(description="The parcel universe's fields this file gives its units.")
    offers: list[UnitField] = Field(
        default_factory=list,
        description="The parcel universe's fields not given yet that this file has a column of the same name for.",
    )
    inheritable: list[UnitField] = Field(
        default_factory=list,
        description="The parcel's land and location fields a unit can take from the parcel it's on (column: the "
        "parcel's), the units file's own left out.",
    )
    from_shape: list[str] = Field(
        default_factory=list, description="What each unit gets from its parcel's shape: map layers, enrichments."
    )
    basis: str | None = Field(default=None, description="How the link was guessed, when it was.")
    land: Check
    check: Check


class MissingParcels(BaseModel):
    kind: Literal["missing", "other_id"] = Field(
        default="missing",
        description="missing: parcels the parcel universe lacks; other_id: under half match, likely another ID.",
    )
    rows: int = Field(description="Its rows that find no parcel.")
    ids: int = Field(description="The different parcel IDs they're for.")
    lines: list[str] = Field(description="What it means and what to do, a sentence each.")
    title: str = Field(default="", description="A few words for the row it's on: '777 sales off the map'.")
    units: bool = Field(
        default=False, description="They look like units without a shape of their own: the Condo units step's."
    )


class RowField(BaseModel):
    key: str
    name: str
    column: str | None = Field(description="This file's column for it; None: not in it (blank for its rows).")
    assumed: bool = Field(default=False, description="No column: assumed, as the sales record assumes it.")


class RowsView(BaseModel):
    """An appended file against the main file it adds to."""

    adds_to: str = Field(description="sales or parcels.")
    fields: list[RowField]
    have: int = Field(description="Of the main file's fields, how many this file has.")
    of: int
    few: bool = Field(description="Half of them or fewer: likely the wrong file, or a different layout.")
    key_text: str = Field(description="Whether its IDs look like the main file's, in a line.")
    key_ok: bool
    found: int = Field(description="Rows whose ID finds a parcel in the universe (more sales) or is already in it.")
    rows: int
    overlap: int = Field(description="Rows already in the main file (same sale ID, or parcel ID): kept once.")


class WizardFile(BaseModel):
    name: str
    filename: str
    missing: bool
    problem: str | None = Field(default=None, description="Why it can't be read.")
    rows: int | None
    geometry: bool
    holds: Holds | None
    match: Match = Field(description="Which ID it joins to the parcel universe on: key, or an extra ID (key2, key3).")
    id_column: str | None = Field(description="Loaded as the ID it joins on (match).")
    id_check: Check | None
    repeats: Repeats | None = Field(description="Set when the ID repeats or is blank on some rows.")
    extra_ids: list[ExtraId] = Field(description="The universe's extra IDs (key2, key3).")
    columns: list[Column]
    base: bool
    clean: dict[str, list[CleanStep]] = Field(description="ID field -> its clean-up steps (Reconcile).")
    unshaped: int = Field(default=0, description="Parcel file: rows whose ID finds no parcel shape.")
    units: UnitsView | None = Field(default=None, description="Its rows without a shape, as units (condos).")
    not_in_universe: MissingParcels | None = Field(
        default=None,
        description="Its rows that don't find a parcel are for parcels missing from the parcel universe, not IDs "
        "written differently: cleaning won't help (Reconcile is for that).",
    )
    appended: RowsView | None = Field(default=None, description="Appended as rows: against the file it adds to.")
    date_column: str | None = Field(
        default=None, description="More sales details on a made sale ID: the date its own sale ID is made with."
    )


class ExtraId(BaseModel):
    """An extra ID of the parcel universe, for files that join on a different key (F3d).

    Not checked: rows are kept or dropped by the parcel ID alone.
    """

    field: Literal["key2", "key3"]
    column: str


class SaleId(BaseModel):
    file: str | None = Field(description="The sales file.")
    column: str | None = Field(description="Its sale ID column (loaded as key_sale).")
    made: bool = Field(description="Made from parcel ID + sale date (an entry calc).")
    check: Check | None


class Source(BaseModel):
    file: str
    column: str


class WizardField(BaseModel):
    key: str
    name: str
    description: str
    type: str
    step: str
    more: bool
    sources: list[Source] = Field(description="Where it's loaded from; more than one is a conflict.")
    assumed: bool = Field(description="Valid/vacant sale with no column: all valid, none vacant (F3d).")
    check: Check | None
    hidden: bool = Field(description="Computed from a field that's loaded, so not asked (e.g. age from year built).")
    rule: Rule | None = Field(default=None, description="Yes/no worked out from columns (valid/vacant sale).")
    date_format: str | None = Field(default=None, description="Dates: the format it's read with.")
    area_unit: AreaUnit | None = Field(default=None, description="Areas: the unit its column is in.")
    number_format: NumberFormat | None = Field(
        default=None, description="Money written as text: how it's read. None: read as plain numbers."
    )
    scale: Scale | None = Field(default=None, description="Quality/condition number: how it becomes higher-is-better.")
    absent: bool = Field(default=False, description="Said not to exist (no condition: effective age carries it).")
    distinct: int | None = Field(default=None, description="How many different values its column has (not blank).")
    numbers: bool | None = Field(
        default=None, description="Quality/condition: its column is all numbers, so it can be read as numbers."
    )


Status = Literal["blank", "blocked", "attention", "done"]
# Worst first: More details shows the worst of its parts.
ORDER: dict[str, int] = {"blocked": 0, "attention": 1, "blank": 2, "done": 3}
AGE = ("bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years")


class Left(BaseModel):
    text: str = Field(description="Short, as a to-do: '442 blank IDs to confirm'.")
    blocking: bool = Field(default=True, description="❌ stops a run; otherwise ⚠ worth deciding.")


class StepView(BaseModel):
    key: str
    parent: str | None
    title: str | None = Field(default=None, description="A part made from a file (More files): its file's name.")
    status: Status = Field(
        description="blank: not visited (or an optional step not confirmed yet); blocked: something here stops a "
        "run; attention: something to decide, or recommended and missing; done: complete."
    )
    left: list[Left] = Field(description="What's still to do here, worst first; Next is greyed while any remain.")
    fields: list[str]
    more: list[str]
    sales: bool


class NotLoaded(BaseModel):
    file: str
    columns: list[str]


class DeedsCheck(BaseModel):
    ok: bool
    text: str
    deeds: int = Field(description="Deeds (on one day) that more than one sale was recorded under.")
    sales: int = Field(description="The sales on them.")
    blank: int = Field(description="Sales without a deed ID: never counted as one deed.")


class PermitKind(BaseModel):
    value: str
    count: int
    means: PermitMeaning
    guessed: bool = Field(description="Not said yet: what the words suggest.")


class PermitsView(BaseModel):
    file: str
    settings: Permits
    rows: int
    date: Check | None
    span: str | None = Field(description="The first and last permit dates.")
    kinds: list[PermitKind]
    more: int = Field(description="Kinds of permit not listed (the rarest).")
    year_built: bool = Field(description="The year built is loaded: renovations can reset the effective year.")
    ready: bool


class CondoFile(BaseModel):
    name: str
    filename: str
    rows: int | None
    unshaped: int = Field(description="Rows whose parcel ID finds no shape in the parcel universe.")


class CondosView(BaseModel):
    """The Condo units step: the answer to "do you have condos?", what the files suggest, and the files that could
    hold the units."""

    answer: bool | None = Field(description="None: not answered yet.")
    evidence: list[str] = Field(description="What the files suggest, a sentence each.")
    files: list[CondoFile] = Field(
        description="Parcel files joined to the parcel universe, those with rows without a shape first."
    )
    file: str | None = Field(description="The file holding the units.")


class LocationField(BaseModel):
    name: str
    file: str
    column: str
    check: Check
    distinct: int | None


class CustomFieldView(BaseModel):
    name: str
    group: Literal["land", "building", "other"]
    type: Literal["category", "number"]
    file: str
    column: str
    check: Check
    distinct: int | None


class LayerView(BaseModel):
    name: str
    filename: str
    columns: list[Column]
    overlay: Overlay
    features: int
    polygons: int
    points: int
    lines: int
    projected: bool = Field(description="It has a coordinate system, so it can be placed against the parcels.")
    check: Check | None = Field(description="Stamp: how many parcels fall in a shape. Distance: the features.")
    left: list[Left] = Field(default_factory=list, description="What's still to do or wrong with it.")


class ValueSetView(BaseModel):
    id: str = Field(description='Its fields\' prefix: "assr" (the roll), or a slot.')
    name: str
    roll: bool = Field(description="The assessor's roll: OpenAVMKit's assessor model; Check my values' first.")


class Wizard(BaseModel):
    steps: list[StepView]
    files: list[WizardFile]
    sale_id: SaleId
    fields: list[WizardField]
    used: dict[str, dict[str, str]] = Field(description="file -> column -> the field it's loaded as.")
    problems: list[str] = Field(description="What stops OpenAVMKit from running.")
    warnings: list[str] = Field(description="Recommended fields that are missing.")
    not_loaded: list[NotLoaded]
    locations: list[LocationField] = Field(default_factory=list, description="The location fields the user named.")
    custom: list[CustomFieldView] = Field(default_factory=list, description="Fields the user named and classified.")
    layers: list[LayerView] = Field(default_factory=list, description="Map layers (Shapefiles).")
    deeds: DeedsCheck | None = Field(default=None, description="Sales sharing a deed (the Deeds step).")
    permits: PermitsView | None = Field(default=None, description="The permits file, set up (the Permits step).")
    condos: CondosView | None = Field(default=None, description="The Condo units step.")
    value_sets: list[ValueSetView] = Field(default_factory=list, description="Existing values (Assessed values).")

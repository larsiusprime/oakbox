"""The wizard's answers: everything Oakbox needs to know to write settings.json.

The new-project wizard (SPEC §3.2) fills one of these in, one screen at a time.
Sample counties ship a pre-filled copy. ``settings_gen.generate`` turns it into
an OpenAVMKit ``settings.json``; users never edit that file directly.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Place(BaseModel):
    name: str
    state: str
    tax_year: int
    units: Literal["imperial", "metric"] = "imperial"
    center_lat: float
    center_lon: float


class ParcelLayer(BaseModel):
    """The GIS parcel file and its parcel-ID column."""

    file: str
    id_column: str


class Transform(BaseModel):
    """A typed column transform (SPEC §3.13). M1a supports a numeric multiplier."""

    kind: Literal["multiply"]
    column: str
    factor: float


class FieldSource(BaseModel):
    """Where one OpenAVMKit field comes from: a source column, or a transform of one."""

    column: str | None = None
    transform: Transform | None = None
    dtype: Literal["string", "float", "int"] | None = None


class ParcelDetails(BaseModel):
    """A table of parcel characteristics joined to the parcel layer by ID."""

    file: str
    id_column: str
    fields: dict[str, FieldSource] = Field(
        description="OpenAVMKit field name -> source. E.g. 'bldg_area_finished_sqft'."
    )


class Sales(BaseModel):
    file: str
    parcel_id_column: str
    date_column: str
    date_format: str = Field(description="strftime format, e.g. '%m/%d/%Y'")
    price_column: str
    sale_id_columns: list[str] = Field(
        default_factory=list,
        description="Columns combined with parcel ID and date to make a unique sale ID.",
    )
    validity_column: str | None = None
    valid_codes: list[str] = Field(default_factory=list)
    vacant_codes: list[str] = Field(
        default_factory=list,
        description="Codes meaning 'vacant when sold'. Empty means: follow the parcel's current vacancy.",
    )


class ModelGroup(BaseModel):
    id: str
    name: str


class Dates(BaseModel):
    valuation_date: dt.date
    use_sales_from: int = Field(description="First sale year used for modeling.")
    ratio_study_years: int = 1


class WizardAnswers(BaseModel):
    place: Place
    parcels: ParcelLayer
    details: ParcelDetails | None = None
    sales: Sales
    value_fields: list[str] = Field(
        description="OpenAVMKit field names of the total values to check, e.g. ['assr_market_value']."
    )
    location_field: str | None = Field(
        default=None, description="Field used as the main location, e.g. 'neighborhood'."
    )
    model_groups: list[ModelGroup] = Field(default_factory=lambda: [ModelGroup(id="all", name="All properties")])
    dates: Dates

    def slug(self) -> str:
        """OpenAVMKit locality slug: country-state-name, no dashes inside the name."""
        name = "".join(ch for ch in self.place.name.lower() if ch.isalnum())
        return f"us-{self.place.state.lower()}-{name}"

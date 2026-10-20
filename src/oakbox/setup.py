"""The guided build's decisions (SPEC §3.2): everything Oakbox needs to write settings.json.

The user fills these in stage by stage. Sample counties ship a pre-filled copy.
``stitcher`` turns ``files`` + ``stitch`` into the stitched tables in ``in/``, and
``settings_gen.generate`` turns the rest into an OpenAVMKit ``settings.json``.
Users never edit either file directly.
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


StageId = Literal["basics", "files", "stitch", "columns", "sales_basics"]
STAGE_ORDER: tuple[StageId, ...] = ("basics", "files", "stitch", "columns", "sales_basics")


# ---------- Stage 1: Basics ----------


class Basics(BaseModel):
    name: str = ""
    state: str = Field(default="", description="Two-letter state or province code, e.g. 'VA'.")
    tax_year: int | None = None
    units: Literal["imperial", "metric"] = "imperial"
    valuation_date: dt.date | None = None
    center_lat: float | None = None
    center_lon: float | None = None

    def complete(self) -> bool:
        return bool(self.name and self.state and self.tax_year and self.valuation_date)


# ---------- Stage 2: Your files ----------

FileUse = Literal["parcel_map", "parcels", "sales", "points", "map_layer"]
FileFormat = Literal[
    "parquet", "geoparquet", "csv", "excel", "shapefile", "geopackage", "geojson", "filegdb", "fixed_width"
]
ColumnType = Literal["text", "number", "date", "yes_no", "geometry"]


class ColumnInfo(BaseModel):
    name: str
    type: ColumnType
    blank: int = 0
    distinct: int | None = None
    examples: list[str] = Field(default_factory=list)
    description: str = Field(default="", description="From the file's layout, when it has one.")


class FileProfile(BaseModel):
    """Measured on the imported copy, over every row."""

    rows: int
    columns: list[ColumnInfo]
    distinct_ids: int | None = None
    blank_ids: int | None = None
    crs: str | None = None


class RowFilter(BaseModel):
    """Keep only rows whose ``column`` is one of ``values`` (e.g. property type 'R')."""

    column: str
    values: list[str]


class SourceFile(BaseModel):
    id: str = Field(description="Short slug, unique in the project; names the imported copy.")
    name: str = Field(description="What the user sees, e.g. 'PROP.TXT (property)'.")
    path: str = Field(description="Absolute path of the file the user picked (a zip for exports).")
    member: str | None = Field(default=None, description="File inside a zip, or layer inside a GeoPackage/FileGDB.")
    format: FileFormat
    layout: str | None = Field(default=None, description="Fixed-width layout id, e.g. 'pacs-legacy-8.0.33'.")
    description: str = ""
    uses: list[FileUse] = Field(default_factory=list)
    id_columns: list[str] = Field(default_factory=list, description="The parcel ID column (text).")
    keep_columns: list[str] | None = Field(default=None, description="None keeps every column.")
    keep_rows: RowFilter | None = None
    size_bytes: int | None = None
    imported: bool = False
    profile: FileProfile | None = None


# ---------- Stage 3: Stitch ----------

IdFixOp = Literal["trim", "strip_leading_zeros", "remove_non_alnum", "upper", "pad_zeros"]
Agg = Literal["first", "sum", "max", "min", "count"]


class IdFix(BaseModel):
    op: IdFixOp
    width: int | None = Field(default=None, description="For pad_zeros: total width.")


class SortKey(BaseModel):
    column: str
    descending: bool = False


class Collapse(BaseModel):
    """How several rows per parcel become one: sort, then per-column aggregation (default 'first')."""

    sort_by: list[SortKey] = Field(default_factory=list)
    fields: dict[str, Agg] = Field(default_factory=dict)


class Stitch(BaseModel):
    spine: str | None = Field(default=None, description="File id of the parcel map everything attaches to.")
    id_fixes: dict[str, list[IdFix]] = Field(default_factory=dict, description="File id -> fixes to its IDs.")
    collapse: dict[str, Collapse] = Field(default_factory=dict, description="File id -> several-rows rule.")
    dissolve: bool = Field(default=True, description="Merge several map polygons with one ID into one shape.")
    context: Literal["none", "recommended", "custom"] = "none"


# ---------- Stage 4: Columns (screen in M1c; the sample pre-fills it) ----------


class Transform(BaseModel):
    """A typed column transform (SPEC §3.13). So far: a numeric multiplier."""

    kind: Literal["multiply"]
    column: str
    factor: float


class FieldSource(BaseModel):
    """Where one OpenAVMKit field comes from: a stitched column, or a transform of one."""

    column: str | None = None
    transform: Transform | None = None
    dtype: Literal["string", "float", "int"] | None = None


class Columns(BaseModel):
    fields: dict[str, FieldSource] = Field(
        default_factory=dict, description="OpenAVMKit field name -> stitched parcel column."
    )
    value_fields: list[str] = Field(
        default_factory=list, description="OpenAVMKit names of the total values to check, e.g. 'assr_market_value'."
    )
    location_field: str | None = Field(default=None, description="Main location field, e.g. 'neighborhood'.")


# ---------- Stage 5: Sales basics (screen in M1c; the sample pre-fills it) ----------


class SalesBasics(BaseModel):
    """Columns refer to the stitched sales table, whose parcel ID column is 'key'."""

    date_column: str
    date_format: str = Field(description="strftime format, e.g. '%m/%d/%Y'")
    price_column: str
    sale_id_columns: list[str] = Field(
        default_factory=list, description="Columns combined with parcel ID and date to make a unique sale ID."
    )
    validity_column: str | None = None
    valid_codes: list[str] = Field(default_factory=list)
    vacant_codes: list[str] = Field(
        default_factory=list, description="Codes meaning 'vacant when sold'. Empty: follow the parcel's vacancy."
    )
    use_sales_from: int = Field(description="First sale year used for modeling.")
    ratio_study_years: int = 1


class ModelGroup(BaseModel):
    id: str
    name: str


class Setup(BaseModel):
    basics: Basics = Field(default_factory=Basics)
    files: list[SourceFile] = Field(default_factory=list)
    stitch: Stitch = Field(default_factory=Stitch)
    columns: Columns = Field(default_factory=Columns)
    sales_basics: SalesBasics | None = None
    model_groups: list[ModelGroup] = Field(default_factory=lambda: [ModelGroup(id="all", name="All properties")])

    def slug(self) -> str:
        """OpenAVMKit locality slug: country-state-name, no dashes inside the name."""
        name = "".join(ch for ch in self.basics.name.lower() if ch.isalnum()) or "project"
        return f"us-{(self.basics.state or 'xx').lower()}-{name}"

    def file(self, file_id: str) -> SourceFile:
        for f in self.files:
            if f.id == file_id:
                return f
        raise KeyError(file_id)

    def files_for(self, use: FileUse) -> list[SourceFile]:
        return [f for f in self.files if use in f.uses]

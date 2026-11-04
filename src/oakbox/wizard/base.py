"""The Fields wizard's steps (SPEC §3.0 F3d): what each asks for, in order, and the names a field's column is
guessed by (its aliases, the ID names, the words for yes, no and dates). Plain tables every other part of the
wizard reads; nothing here reads a file.
"""

from __future__ import annotations

import re

from pydantic import Field

from oakbox.datafiles import (
    BaseModel,
)
from oakbox.fields import VALUE_SLOTS

# ---------- The steps ----------


class Step(BaseModel):
    key: str
    parent: str | None = Field(default=None, description="The step this is part of (More details).")
    fields: list[str] = Field(default_factory=list, description="Asked on the step.")
    more: list[str] = Field(default_factory=list, description="Asked under More on the step.")
    sales: bool = Field(default=False, description="Its fields come from the sales file.")


STEPS: list[Step] = [
    Step(key="universe"),
    Step(key="sales", fields=["sale_price", "sale_date", "valid_sale", "vacant_sale"], sales=True),
    # More files, one by one, each joined to the universe (a parcel ID) or to the sales (the sale ID).
    Step(key="more_files"),
    # What a model leans on most, a part each (revised 2026-11-04: its own step, not part of More details).
    Step(key="big_five"),
    Step(key="building_size", parent="big_five", fields=["bldg_area_finished_sqft"]),
    Step(key="land_size", parent="big_five", fields=["land_area_sqft"]),
    Step(
        key="age",
        parent="big_five",
        fields=["bldg_year_built", "bldg_effective_year_built"],
        more=["bldg_age_years", "bldg_effective_age_years"],
    ),
    # A number for modelling, and the category as text: both asked, the number preferred (F3d).
    Step(key="quality", parent="big_five", fields=["bldg_quality_num", "bldg_quality_txt"]),
    Step(key="condition", parent="big_five", fields=["bldg_condition_num", "bldg_condition_txt"]),
    Step(key="details"),
    # Where each parcel is, in three parts (revised 2026-11-04): the situs address; the coordinates OpenAVMKit works
    # out (and the centre they're measured from); the areas parcels belong to, the user's own location fields
    # (set_location). Land, Building and Rooms & features steps are left out for now: their fields are in the
    # advanced view.
    Step(key="address", parent="details", fields=["address"]),
    Step(key="coordinates", parent="details"),
    Step(key="location", parent="details"),
    # What kind of property each parcel is: model groups are made from these (F5).
    Step(
        key="property_type",
        parent="details",
        fields=["land_class", "bldg_type"],
        more=["bldg_desc", "bldg_class", "bldg_units", "bldg_stories"],
    ),
    # The user's own fields: any other column, under a name they choose, with its class and kind (revised
    # 2026-11-04: a part of its own, not under Land use & building type).
    Step(key="custom", parent="details"),
    Step(
        key="assessed",
        parent="details",
        # Not OpenAVMKit's true_* values: they're the answer key of synthetic data, never a real roll.
        fields=["assr_land_value", "assr_impr_value", "assr_market_value"],
        # Other existing values (a vendor's AVM…), each set in a slot of its own: shown only for the sets there are.
        more=[f"{slot}_{part}_value" for slot in VALUE_SLOTS for part in ("market", "land", "impr")],
    ),
    # Map layers joined onto the parcels by where they are, or measured to (F3d Shapefiles).
    Step(key="shapefiles", parent="details"),
    # Condos and the like: units on the roll without a shape of their own, on a parcel they share (F3d condos).
    # Asked first; the rest, one decision each, only when the answer is yes.
    Step(key="condos"),
    Step(key="condo_ask", parent="condos"),
    Step(key="condo_file", parent="condos"),
    Step(key="condo_rows", parent="condos"),
    Step(key="condo_link", parent="condos"),
    Step(key="condo_land", parent="condos"),
    Step(key="condo_fields", parent="condos"),
    Step(key="condo_location", parent="condos"),
    Step(key="condo_summary", parent="condos"),
    # The deed each sale was recorded under: several sales on one deed are one sale of several parcels (F3f).
    Step(
        key="deeds",
        fields=["deed_id", "deed_book", "deed_page"],
        more=["deed_grantor", "deed_grantee", "deed_grantor_surname", "deed_grantee_surname"],
        sales=True,
    ),
    # Public data about each parcel, downloaded as Bring in data runs (F3e).
    Step(key="enrich"),
    # Building permits: teardowns make a sale a land sale; major renovations reset the effective year (F3g).
    Step(key="permits"),
    Step(key="review"),
]
STEP_KEYS = [s.key for s in STEPS]
PARENTS = {s.parent for s in STEPS if s.parent}
# The "big five" a model needs: building size is required; land size comes from the shapes when
# missing; age is flagged when missing; quality and condition are nice to have.
REQUIRED = ["bldg_area_finished_sqft"]
RECOMMENDED = [("bldg_year_built", "bldg_effective_year_built", "bldg_age_years", "bldg_effective_age_years")]
# Required by OpenAVMKit's sales merge; without a column, an assumption confirmed in a warning (F3d).
ASSUMABLE = {"valid_sale": True, "vacant_sale": False}
# Computed fields asked only when what they're computed from isn't loaded.
ONLY_WITHOUT = {"bldg_age_years": "bldg_year_built", "bldg_effective_age_years": "bldg_effective_year_built"}

# Quality and condition: the number (used for modelling) and the category (kept as text), each the other's pair.
PAIRS = {
    "bldg_quality_num": "bldg_quality_txt",
    "bldg_condition_num": "bldg_condition_txt",
    "bldg_quality_txt": "bldg_quality_num",
    "bldg_condition_txt": "bldg_condition_num",
}
SCALED = ("bldg_quality_num", "bldg_condition_num")
# Said not to exist, rather than left blank (condition: effective age carries it).
ABSENT_OK = ("bldg_condition_num",)

# Fields the wizard words its own way.
RENAMED = {
    "address": (
        "Situs address",
        "The physical address of the property itself: where it is, not where the owner gets mail.",
    ),
    "land_class": (
        "Land use",
        "What the land is used for: residential, commercial, condo, government… Often called land class or use code.",
    ),
}

# Common column names, beside the field's own key and name (normalised: lowercase letters and digits).
ALIASES: dict[str, list[str]] = {
    "address": [
        *("situs", "situsaddr", "situsaddress", "siteaddr", "siteaddress", "propaddr", "addr", "locaddr"),
        *("phyaddr", "physaddr", "physicaladdress", "propertyaddress", "locationaddress", "locationaddr"),
    ],
    "neighborhood": ["nbhd", "nbhdcd", "nbhdcode", "neighborhoodcode", "neighcode", "hood"],
    "city": ["situscity", "sitecity"],
    "school_district": ["school", "schooldist", "isd", "schooldistrict"],
    "census_tract": ["tract", "censustract"],
    "zoning": ["zone", "zonecode", "zoningcode"],
    "zoning_desc": ["zonedesc", "zoningdescription"],
    "land_area_sqft": [
        *("landsqft", "lotsqft", "landsf", "lotsf", "lotsize", "landarea", "lotarea"),
        *("acres", "acreage", "calcacres", "deededacres", "gisacres", "landacres", "totalacres", "hectares", "landha"),
        *("landsqm", "lotsqm", "landm2"),
    ],
    "land_class": [
        *("landuse", "landusecode", "luc", "usecode", "landclass", "landclasscode", "propertyclass", "propclass"),
        *("propertyuse", "propuse", "puc", "stateclass", "propertytype", "proptype", "classcode"),
    ],
    "bldg_desc": ["bldgdesc", "buildingdesc", "buildingdescription", "imprvdesc", "improvementdescription"],
    "bldg_type": ["imprvtype", "imprtype", "buildingtype", "improvementtype", "bldgtype"],
    "bldg_class": ["buildingclass", "bldgclass", "imprvclass"],
    "bldg_stories": ["stories", "numstories", "story"],
    "bldg_units": ["units", "numunits"],
    "bldg_count": ["numbldgs", "bldgs", "buildingcount"],
    "bldg_area_finished_sqft": ["livingarea", "livarea", "heatedarea", "finishedsqft", "gla", "bldgsqft", "sqft"],
    "bldg_area_footprint_sqft": ["footprint", "footprintsqft"],
    "bldg_year_built": ["yrblt", "yearbuilt", "yrbuilt", "actualyearbuilt", "ayb"],
    "bldg_effective_year_built": ["effyrblt", "effectiveyearbuilt", "eyb", "effyear", "effyearbuilt"],
    "bldg_quality_txt": ["quality", "qual", "grade"],
    "bldg_quality_num": [
        *("quality", "qual", "grade", "qualitynum", "qualnum", "qualityscore", "gradescore", "gradenum"),
        *("gradefactor", "qualityfactor"),
    ],
    "bldg_condition_txt": ["condition", "cond"],
    "bldg_condition_num": [
        *("condition", "cond", "conditionnum", "condnum", "conditionscore", "condscore", "pctgood", "percentgood"),
        *("depr", "deprpct", "depreciation", "physdepr", "physicaldepreciation"),
    ],
    "bldg_rooms_bed": ["beds", "bedrooms", "bed", "bdrms"],
    "bldg_rooms_bath": ["baths", "bathrooms", "bath"],
    "bldg_rooms_bath_full": ["fullbaths", "fullbath"],
    "bldg_rooms_bath_half": ["halfbaths", "halfbath"],
    "bldg_heating": ["heat", "heating", "heattype"],
    "bldg_ac": ["ac", "aircond", "cooling", "airconditioning"],
    "bldg_exterior": ["extwall", "exterior", "exteriorwall"],
    "bldg_foundation": ["foundation"],
    "bldg_style": ["style"],
    "sale_price": ["price", "saleprice", "saleamt", "saleamount", "consideration"],
    "sale_date": ["saledate", "saledt", "deeddate"],
    "valid_sale": ["valid", "validsale", "salevalid", "qualified", "qualifiedsale", "salequalified", "armslength"],
    "vacant_sale": ["vacant", "vac", "vacantsale", "salevacant", "vacantatsale"],
    "assr_land_value": [
        "landval",
        "landvalue",
        "apprland",
        "appraisedland",
        "totallandvalue",
        "totallandvalueassessed",
    ],
    "assr_impr_value": [
        *("imprval", "imprvval", "improvementvalue", "bldgval", "bldgvalue", "totalbldgvalue"),
        "totalbldgvalueassessed",
    ],
    "assr_market_value": [
        *("marketval", "mktval", "totalval", "apprval", "appraisedvalue", "marketvalue", "totalvalue"),
        *("totalpropvalue", "totalpropertyvalue"),
    ],
    "deed_id": [
        *("deedid", "deedno", "deednum", "deednumber", "instrument", "instrumentno", "instrumentnum"),
        *("instrumentnumber", "instno", "docno", "docnum", "documentno", "documentnumber", "recordingno"),
        *("recordingnumber", "receptionno", "receptionnumber", "bookpage", "deedbookpage"),
    ],
    "deed_book": ["book", "deedbook"],
    "deed_page": ["page", "deedpage"],
    "deed_grantor": ["grantor", "seller"],
    "deed_grantee": ["grantee", "buyer"],
    "deed_grantor_surname": ["grantorsurname", "grantorlast", "grantorlastname", "sellersurname", "sellerlastname"],
    "deed_grantee_surname": ["granteesurname", "granteelast", "granteelastname", "buyersurname", "buyerlastname"],
    "mail_address": ["mailaddr", "mailaddress", "mailingaddress"],
    "mail_city": ["mailcity"],
    "mail_state": ["mailstate"],
    "mail_zip": ["mailzip", "mailzipcode"],
}
# A parcel ID's name: most specific first.
ID_NAMES = re.compile(
    r"^(pin|pinnum|pinno|apn|parcel(id|no|num|number|pin)?|parid|pid|prop(erty)?(id|no|num)|account(no|num)?|"
    r"acct(no|num)?|key|geoid|folio|id|(gdv)?reid|realestateid)$"
)
SALE_ID_NAMES = re.compile(r"^(sale(id|key|no|num|number)|instrument(no|num)?|doc(ument)?(no|num|number)|deedid)$")
YES = {"true", "t", "1", "y", "yes", "1.0"}  # OpenAVMKit's reading (_boolify_column_in_df), plus 1.0 from a CSV
NO = {"false", "f", "0", "n", "no", "0.0"}
DATE_WORDS = {
    "%Y-%m-%d": "year-month-day",
    "%m/%d/%Y": "month/day/year",
    "%m/%d/%y": "month/day/2-digit year",
    "%d/%m/%Y": "day/month/year",
    "%Y%m%d": "yearmonthday",
    "%Y-%m-%d %H:%M:%S": "year-month-day and time",
    "%m/%d/%Y %H:%M": "month/day/year and time",
    "%m/%d/%Y %H:%M:%S": "month/day/year and time",
    "%d/%m/%Y %H:%M": "day/month/year and time",
    "%Y/%m/%d": "year/month/day",
    "%m-%d-%Y": "month-day-year",
    "%d-%b-%Y": "day-Mon-year (09-Jan-2024)",
    "%b %d %Y": "Mon day year (Jan 09 2024)",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())

"""Turn wizard answers into an OpenAVMKit settings.json.

Everything OpenAVMKit needs but a user would never think to set is written
explicitly here (SPEC §6.3): ``dupes`` on every file, ``valid_sale`` /
``vacant_sale`` / ``key_sale``, the merge block, spatial-lag entries per model
group, and main-only LightGBM with the default variables.
"""

from __future__ import annotations

from typing import Any

from oakbox.answers import FieldSource, WizardAnswers

DEFAULT_IND_VARS = [
    "bldg_area_finished_sqft",
    "land_area_sqft",
    "bldg_effective_age_years",
    "bldg_age_years",
    "bldg_quality_num",
    "bldg_condition_num",
    "latitude",
    "longitude",
    "spatial_lag_sale_price_time_adj",
    "spatial_lag_sale_price_time_adj_impr_sqft",
    "spatial_lag_sale_price_time_adj_land_sqft",
]

_YEAR_FIELDS = {"bldg_year_built": "bldg_age_years", "bldg_effective_year_built": "bldg_effective_age_years"}


def _by_key(field: str) -> dict:
    return {"subset": [field], "sort_by": [field, "asc"], "drop": True}


def _source(field: str, src: FieldSource, load: dict, calc: dict) -> None:
    if src.transform is not None:
        t = src.transform
        if t.kind == "multiply":
            calc[field] = ["*", t.column, t.factor]
        return
    if src.column is None:
        return
    load[field] = [src.column, src.dtype] if src.dtype else src.column


def generate(a: WizardAnswers) -> dict[str, Any]:
    """Build a complete settings dict from wizard answers."""
    s = a.sales
    data_load: dict[str, Any] = {
        "geo_parcels": {
            "filename": a.parcels.file,
            "load": {"key": [a.parcels.id_column, "string"]},
            "dupes": _by_key("key"),
        }
    }
    universe_sources = ["geo_parcels"]
    provided: set[str] = set()

    if a.details is not None:
        load: dict[str, Any] = {"key": [a.details.id_column, "string"]}
        calc: dict[str, Any] = {}
        for field, src in a.details.fields.items():
            _source(field, src, load, calc)
        provided |= set(a.details.fields)
        entry: dict[str, Any] = {"filename": a.details.file, "load": load, "dupes": _by_key("key")}
        if calc:
            entry["calc"] = calc
        data_load["parcels"] = entry
        universe_sources = ["parcels"]

    sales_load: dict[str, Any] = {
        "key": [s.parcel_id_column, "string"],
        "sale_date": [s.date_column, "datetime", s.date_format],
        "sale_price": [s.price_column, "float"],
    }
    if s.validity_column:
        sales_load["sale_type"] = [s.validity_column, "string"]
    valid_rule: list = [">", "sale_price", 0]
    if s.validity_column and s.valid_codes:
        valid_rule = ["and", valid_rule, ["isin", "sale_type", list(s.valid_codes)]]
    if s.validity_column and s.vacant_codes:
        vacant_rule: list = ["isin", "sale_type", list(s.vacant_codes)]
    else:
        vacant_rule = ["set", False]
    key_parts = [
        s.parcel_id_column,
        *s.sale_id_columns,
        ["asstr", ["datetimestr", s.date_column, f"str:{s.date_format}"]],
    ]
    sales_calc = {
        "valid_sale": ["?", valid_rule],
        "vacant_sale": ["?", vacant_rule] if vacant_rule[0] != "set" else vacant_rule,
        "key_sale": ["join", ["values", *key_parts], "str:---"],
    }
    data_load["sales"] = {
        "filename": s.file,
        "load": sales_load,
        "calc": sales_calc,
        "dupes": _by_key("key_sale"),
    }

    groups = {g.id: {"name": g.name, "filter": ["not", ["isempty", "key"]]} for g in a.model_groups}
    locations = [a.location_field] if a.location_field else []
    ind_vars = [v for v in DEFAULT_IND_VARS if _available(v, provided)]
    if a.location_field:
        ind_vars.append(a.location_field)
        ind_vars.append(f"area_stat_{a.location_field}_sale_price_time_adj_median")

    enrich: dict[str, Any] = {
        "spatial_lag": {"model_groups": {g.id: {"sample_from": [g.id]} for g in a.model_groups}},
    }
    if a.location_field:
        enrich["area_stats"] = {
            "locations": [a.location_field],
            "fields": ["bldg_area_finished_sqft", "sale_price"],
            "stats": ["median"],
        }

    return {
        "__generated_by": "Oakbox. Edit the project in Oakbox rather than this file.",
        "locality": {
            "name": a.place.name,
            "state": a.place.state,
            "slug": a.slug(),
            "units": a.place.units,
            "center": {"latitude": a.place.center_lat, "longitude": a.place.center_lon},
        },
        "data": {
            "load": data_load,
            "process": {
                "merge": {"universe": universe_sources, "sales": ["sales"]},
                "enrich": enrich,
            },
        },
        "modeling": {
            "metadata": {
                "modeler": "OAK box",
                "valuation_date": a.dates.valuation_date.isoformat(),
                "use_sales_from": a.dates.use_sales_from,
            },
            "model_groups": groups,
            "instructions": {"main": {"run": ["lightgbm"]}},
            "models": {"main": {"default": {"ind_vars": ind_vars}}},
        },
        "analysis": {"ratio_study": {"look_back_years": a.dates.ratio_study_years}},
        "field_classification": {
            "important": {
                "fields": {"loc_neighborhood": a.location_field} if a.location_field else {},
                "locations": locations,
            }
        },
    }


def _available(var: str, provided: set[str]) -> bool:
    """Whether a default model variable can exist given the mapped fields."""
    always = {"latitude", "longitude", "land_area_sqft"}
    if var in always or var.startswith("spatial_lag_"):
        return True
    derived = {age: year for year, age in _YEAR_FIELDS.items()}
    if var in derived:
        return derived[var] in provided
    return var in provided

"""Turn the guided build's decisions into an OpenAVMKit settings.json.

OpenAVMKit loads the stitched tables in ``in/stitched/`` (see ``stitcher``), all
keyed on ``key``. Everything OpenAVMKit needs but a user would never think to set
is written explicitly here (SPEC §6.3): ``dupes`` on every file, ``valid_sale`` /
``vacant_sale`` / ``key_sale``, the merge block, spatial-lag entries per model
group, and main-only LightGBM with the default variables.
"""

from __future__ import annotations

from typing import Any

from oakbox.setup import FieldSource, Setup

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


STITCHED = {
    "geo_parcels": "stitched/geo_parcels.geoparquet",
    "parcels": "stitched/parcels.parquet",
    "sales": "stitched/sales.parquet",
}


def generate(setup: Setup) -> dict[str, Any]:
    """Build a complete settings dict. Needs Basics, a stitch plan, Columns and Sales basics."""
    b, cols, s = setup.basics, setup.columns, setup.sales_basics
    if s is None or b.valuation_date is None:
        raise ValueError("Sales basics and the valuation date are needed before settings can be written.")
    data_load: dict[str, Any] = {
        "geo_parcels": {
            "filename": STITCHED["geo_parcels"],
            "load": {"key": ["key", "string"]},
            "dupes": _by_key("key"),
        }
    }
    universe_sources = ["geo_parcels"]
    provided: set[str] = set()

    if setup.files_for("parcels"):
        load: dict[str, Any] = {"key": ["key", "string"]}
        calc: dict[str, Any] = {}
        for field, src in cols.fields.items():
            _source(field, src, load, calc)
        provided |= set(cols.fields)
        entry: dict[str, Any] = {"filename": STITCHED["parcels"], "load": load, "dupes": _by_key("key")}
        if calc:
            entry["calc"] = calc
        data_load["parcels"] = entry
        universe_sources = ["parcels"]

    sales_load: dict[str, Any] = {
        "key": ["key", "string"],
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
        "key",
        *s.sale_id_columns,
        ["asstr", ["datetimestr", s.date_column, f"str:{s.date_format}"]],
    ]
    sales_calc = {
        "valid_sale": ["?", valid_rule],
        "vacant_sale": ["?", vacant_rule] if vacant_rule[0] != "set" else vacant_rule,
        "key_sale": ["join", ["values", *key_parts], "str:---"],
    }
    data_load["sales"] = {
        "filename": STITCHED["sales"],
        "load": sales_load,
        "calc": sales_calc,
        "dupes": _by_key("key_sale"),
    }

    groups = {g.id: {"name": g.name, "filter": ["not", ["isempty", "key"]]} for g in setup.model_groups}
    loc = cols.location_field
    locations = [loc] if loc else []
    ind_vars = [v for v in DEFAULT_IND_VARS if _available(v, provided)]
    if loc:
        ind_vars.append(loc)
        ind_vars.append(f"area_stat_{loc}_sale_price_time_adj_median")

    enrich: dict[str, Any] = {
        "spatial_lag": {"model_groups": {g.id: {"sample_from": [g.id]} for g in setup.model_groups}},
    }
    if loc:
        enrich["area_stats"] = {
            "locations": [loc],
            "fields": ["bldg_area_finished_sqft", "sale_price"],
            "stats": ["median"],
        }

    locality: dict[str, Any] = {"name": b.name, "state": b.state, "slug": setup.slug(), "units": b.units}
    if b.center_lat is not None and b.center_lon is not None:
        locality["center"] = {"latitude": b.center_lat, "longitude": b.center_lon}
    return {
        "__generated_by": "OAK box. Edit the project in OAK box rather than this file.",
        "locality": locality,
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
                "valuation_date": b.valuation_date.isoformat(),
                "use_sales_from": s.use_sales_from,
            },
            "model_groups": groups,
            "instructions": {"main": {"run": ["lightgbm"]}},
            "models": {"main": {"default": {"ind_vars": ind_vars}}},
        },
        "analysis": {"ratio_study": {"look_back_years": s.ratio_study_years}},
        "field_classification": {
            "important": {
                "fields": {"loc_neighborhood": loc} if loc else {},
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

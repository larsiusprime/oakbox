"""Write a synthetic OpenAVMKit locality of roughly N parcels for benchmarking.

Usage: python make_synthetic.py <n_parcels> <base_dir>

Creates <base_dir>/data/us-zz-synth<N>/in/{parcels.parquet,sales.parquet,settings.json}.
Uses openavmkit.synthetic.basic.generate_basic, but rebuilds parcel geometry:
upstream gives every parcel a rectangle the size of the whole study area.
"""

import json
import math
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from openavmkit.synthetic.basic import generate_basic

VALUATION_DATE = "2025-01-01"


def build(n_parcels: int, base_dir: Path) -> Path:
    size = int(round(math.sqrt(n_parcels)))
    slug = f"us-zz-synth{n_parcels // 1000}k"
    in_dir = base_dir / "data" / slug / "in"
    in_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    sd = generate_basic(size, percent_sales=0.1, percent_vacant=0.1)
    print(f"generate_basic({size}) -> {len(sd.df_universe):,} parcels, {len(sd.df_sales):,} sales in {time.time() - t0:.0f}s")

    univ = sd.df_universe.copy()
    # Upstream extent: 0.4 deg of latitude by 0.5 deg of longitude, one grid cell per parcel.
    cell_lat = 0.4 / size
    cell_lon = 0.5 / size
    univ["geometry"] = [
        box(lon - cell_lon / 2, lat - cell_lat / 2, lon + cell_lon / 2, lat + cell_lat / 2)
        for lat, lon in zip(univ["latitude"], univ["longitude"])
    ]
    val_year = int(VALUATION_DATE[:4])
    univ["bldg_year_built"] = np.where(
        univ["is_vacant"], 0, (val_year - univ["bldg_age_years"]).round()
    )
    # Stand-in for the office's current roll: true value with +/-15% assessment noise.
    rng = np.random.default_rng(7)
    univ["assr_market_value"] = (univ["total_value"] * rng.uniform(0.85, 1.15, len(univ))).round()
    keep = [
        "key", "geometry", "neighborhood", "bldg_area_finished_sqft", "land_area_sqft",
        "bldg_type", "bldg_quality_num", "bldg_condition_num", "bldg_year_built",
        "assr_market_value",
    ]
    gpd.GeoDataFrame(univ[keep], geometry="geometry", crs="EPSG:4326").to_parquet(in_dir / "parcels.parquet")

    sales = sd.df_sales[["key", "key_sale", "valid_sale", "vacant_sale", "sale_price", "sale_date"]]
    sales.to_parquet(in_dir / "sales.parquet")

    lat_c, lon_c = univ["latitude"].mean(), univ["longitude"].mean()
    parcel_fields = [c for c in keep if c != "geometry"]
    settings = {
        "locality": {
            "name": f"Synth {n_parcels // 1000}k",
            "slug": slug,
            "units": "imperial",
            "center": {"latitude": lat_c, "longitude": lon_c},
        },
        "data": {
            "load": {
                "geo_parcels": {
                    "filename": "parcels.parquet",
                    "load": {f: ([f, "string"] if f == "key" else f) for f in parcel_fields},
                    # Must be explicit: without it OpenAVMKit de-dupes geometry files on an
                    # arbitrary column (set-ordered), silently dropping parcels.
                    "dupes": {"subset": ["key"], "sort_by": ["key", "asc"], "drop": True},
                },
                "sales": {
                    "filename": "sales.parquet",
                    "load": {
                        "key": ["key", "string"],
                        "key_sale": ["key_sale", "string"],
                        "valid_sale": ["valid_sale", "bool"],
                        "vacant_sale": ["vacant_sale", "bool"],
                        "sale_price": ["sale_price", "float"],
                        "sale_date": ["sale_date", "datetime"],
                    },
                    "dupes": {"subset": ["key_sale"], "sort_by": ["key_sale", "asc"], "drop": True},
                },
            },
            "process": {
                "merge": {"universe": ["geo_parcels"], "sales": ["sales"]},
                "enrich": {
                    "spatial_lag": {"model_groups": {"all": {"sample_from": ["all"]}}},
                    "area_stats": {
                        "locations": ["neighborhood"],
                        "fields": ["bldg_area_finished_sqft", "sale_price"],
                        "stats": ["median"],
                    },
                },
            },
        },
        "modeling": {
            "metadata": {
                "modeler": "Oakbox M0",
                "valuation_date": VALUATION_DATE,
                "use_sales_from": 2020,
            },
            "model_groups": {
                "all": {"name": "All properties", "filter": [">=", "land_area_sqft", 0]},
            },
            "instructions": {"main": {"run": ["lightgbm"]}},
            "models": {
                "main": {
                    "default": {
                        "ind_vars": [
                            "bldg_area_finished_sqft", "land_area_sqft", "bldg_age_years",
                            "bldg_quality_num", "bldg_condition_num", "latitude", "longitude",
                            "neighborhood", "spatial_lag_sale_price_time_adj",
                            "spatial_lag_sale_price_time_adj_impr_sqft",
                            "spatial_lag_sale_price_time_adj_land_sqft",
                            "area_stat_neighborhood_sale_price_time_adj_median",
                        ]
                    }
                }
            },
        },
        "field_classification": {
            "important": {
                "fields": {"loc_neighborhood": "neighborhood"},
                "locations": ["neighborhood"],
            },
            "impr": {"categorical": ["bldg_type"]},
        },
        "analysis": {"ratio_study": {"look_back_years": 1}},
    }
    (in_dir / "settings.json").write_text(json.dumps(settings, indent=2))
    print(f"wrote {in_dir}")
    return in_dir.parent


if __name__ == "__main__":
    build(int(sys.argv[1]), Path(sys.argv[2]).resolve())

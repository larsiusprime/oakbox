"""Run one Oakbox step headlessly against an OpenAVMKit locality (M0 spike).

Usage: python stage.py <base_dir> <slug> <assemble|clean|check_values|model> [quick|thorough]

Mirrors the notebook cells (01-assemble, 02-clean, assessment_quality, 03-model)
without Jupyter. Emits one "@@OAKBOX {json}" line per sub-step so the driver
can time them.
"""

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

T0 = time.time()


def mark(step: str, **extra) -> None:
    print("@@OAKBOX " + json.dumps({"step": step, "t": round(time.time() - T0, 2), **extra}), flush=True)


def assemble(p) -> None:
    p.delete_checkpoints("1-assemble")
    settings = p.load_settings()
    dataframes = p.load_dataframes(settings=settings, verbose=False)
    mark("load_dataframes")
    sup = p.process_dataframes(dataframes=dataframes, settings=p.load_settings(), verbose=False)
    mark("process_dataframes")
    sup = p.tag_model_groups_sup(sup=sup, settings=p.load_settings(), verbose=False)
    mark("tag_model_groups")
    p.write_notebook_output_sup(sup, "1-assemble", parquet=True, gpkg=False, shp=False)
    mark("write_output", parcels=len(sup.universe), sales=len(sup.sales))


def clean(p) -> None:
    p.delete_checkpoints("2-clean")
    sup = p.read_pickle("out/1-assemble-sup")
    sup = p.fill_unknown_values_sup(sup, p.load_settings())
    mark("fill")
    sup = p.mark_horizontal_equity_clusters_per_model_group_sup(
        sup=sup, settings=p.load_settings(), verbose=False, do_land_clusters=True, do_impr_clusters=True
    )
    mark("horizontal_equity_clusters")
    sup = p.process_sales(sup=sup, settings=p.load_settings(), verbose=False)
    mark("process_sales")
    sup = p.run_sales_scrutiny(
        sup=sup, settings=p.load_settings(), drop_cluster_outliers=True, drop_heuristic_outliers=True, verbose=False
    )
    mark("sales_scrutiny")
    sup = p.collapse_sparse_categories_sup(sup, p.load_settings())
    p.write_notebook_output_sup(sup, "2-clean")
    mark("write_output", sales=len(sup.sales))


def check_values(p) -> None:
    sup = p.read_sales_univ("out/look/2-clean-")
    s = p.load_settings()
    val = s["modeling"]["metadata"]["valuation_date"]
    start = f"{int(val[:4]) - 1}{val[4:]}"
    for mg in s["modeling"]["model_groups"]:
        rs = p.run_ratio_study(sup, mg, "assr_market_value", "sale_price", start, val, land_only=False, max_trim=0.05)
        mark("ratio_study", model_group=mg, summary=str(rs.summary())[:400] if rs is not None else None)
        p.run_horizontal_equity_study(sup, mg, "assr_market_value")
        mark("horizontal_equity", model_group=mg)
        p.run_vertical_equity_study(sup, mg, "assr_market_value", "sale_price", "neighborhood", start, val)
        mark("vertical_equity", model_group=mg)


def model(p, tier: str) -> None:
    p.delete_checkpoints("3-model")
    settings = p.load_settings()
    if tier == "quick":
        settings["modeling"]["instructions"]["cv_folds"] = 1
    sup = p.load_cleaned_data_for_modeling(settings)
    mark("load_cleaned")
    p.write_canonical_splits(sup, settings, verbose=False)
    mark("splits")
    sup = p.enrich_sup_spatial_lag(sup=sup, settings=settings, verbose=False)
    mark("spatial_lag")
    sup = p.enrich_sup_area_stats(sup=sup, settings=settings, verbose=False)
    mark("area_stats", columns=[c for c in sup.universe.columns if c.startswith(("spatial_lag", "area_stat"))])
    p.try_models(sup=sup, settings=settings, save_params=True, verbose=False, run_main=True,
                 run_vacant=False, run_ensemble=True, do_shaps=False, do_plots=False)
    mark("try_models")
    p.finalize_models(sup=sup, settings=settings, save_params=True, use_saved_params=True, verbose=False,
                      run_main=True, run_vacant=False)
    mark("finalize_models")
    p.run_and_write_ratio_study_breakdowns(settings)
    mark("ratio_study_report")


def main() -> None:
    base, slug, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    tier = sys.argv[4] if len(sys.argv) > 4 else "thorough"
    os.chdir(base)
    import openavmkit.pipeline as p  # heavy import; timed as its own step

    mark("import")
    p.init_notebook(slug)
    {"assemble": assemble, "clean": clean, "check_values": check_values}.get(stage, lambda p: model(p, tier))(p)
    mark("done")


if __name__ == "__main__":
    main()

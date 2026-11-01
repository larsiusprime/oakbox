"""Step 5, the models (SPEC F9): the variables found, and the settings written for them."""

import json

import pandas as pd
import pytest

from oakbox import model, projects, ratio


def _project(units="imperial"):
    return projects.Project.model_validate(
        {
            "id": "x",
            "name": "x",
            "created_at": "2026-01-01T00:00:00",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "units": units,
            "groups": [{"id": "sf", "name": "Single-family", "color": "#000"}],
        }
    )


@pytest.fixture
def prepared(tmp_path):
    (tmp_path / "in").mkdir()
    # The user's own field, as OAK box writes it: a number, in OpenAVMKit's improvement fields.
    own = {"field_classification": {"impr": {"numeric": ["bath_half"]}}}
    (tmp_path / "in" / "settings.json").write_text(json.dumps(own), encoding="utf-8")
    look = tmp_path / "out" / "look"
    look.mkdir(parents=True)
    pd.DataFrame(
        {
            "key": ["1", "2", "3"],
            "model_group": ["sf", "sf", "sf"],
            "bldg_area_finished_sqft": [1200.0, 1500.0, 900.0],
            "land_area_sqft": [5000.0, 6000.0, 4000.0],
            "bldg_age_years": [30.0, 20.0, 50.0],
            "latitude_norm": [0.1, 0.5, 0.9],
            "slope_mean_deg": [1.0, None, 2.0],  # a blank left: trees only
            "dist_to_park": [100.0, 200.0, 300.0],  # a distance: its proximity is offered instead
            "proximity_to_park": [0.9, 0.5, 0.0],
            "bath_half": [0, 1, 1],
            "assr_market_value": [100.0, 200.0, 300.0],  # the roll's: never a variable
            "land_class": ["A", "B", "A"],  # a category
            "deed_book": ["1", "2", "3"],  # a deed: never a variable
        }
    ).to_parquet(look / "2-clean-universe.parquet")
    return tmp_path


def test_the_variables_found(prepared):
    vs = {v.field: v for v in model.variables(_project(), prepared)}
    assert list(vs)[:8] == [
        "bldg_area_finished_sqft",
        "land_area_sqft",
        "bldg_age_years",
        "bath_half",
        "proximity_to_park",
        "slope_mean_deg",
        "latitude_norm",
        "land_class",
    ]
    # Then the nearby averages (spatial lag, on to start): the sales' prices, and the parcels' fields that are there.
    assert list(vs)[8:] == [
        "spatial_lag_sale_price",
        "spatial_lag_sale_price_impr_sqft",
        "spatial_lag_bldg_area_finished_sqft",
        "spatial_lag_land_area_sqft",
        "spatial_lag_floor_area_ratio",
        "spatial_lag_bldg_age_years",
    ]
    assert vs["spatial_lag_sale_price"].kind == "location" and vs["spatial_lag_sale_price"].name == "Nearby sale price"
    assert vs["land_class"].kind == "category" and not vs["land_class"].numeric
    assert vs["bldg_area_finished_sqft"].kind == "big_five" and not vs["bldg_area_finished_sqft"].trees_only
    assert vs["slope_mean_deg"].blanks == 1 and vs["slope_mean_deg"].trees_only
    assert model.big_five_missing(list(vs), "imperial") == ["quality", "condition"]


def test_default_settings(prepared):
    s = model.settings(_project(), prepared)
    main = s["modeling"]
    # Every modeled group starts with LightGBM, MRA and Multi-MRA; the roll runs too, as OpenAVMKit's assessor
    # model: it's audited on the study set, beside the models.
    assert main["instructions"]["main"]["run"] == ["lightgbm", "mra", "multi_mra", "assessor"]
    assert main["instructions"]["main"]["ensemble"]["models"] == ["lightgbm", "mra", "multi_mra"]
    block = main["models"]["main"]["sf"]
    # No variable lists to start (the user makes them): no model has variables, and a try is stopped.
    assert s["variable_lists"] == {}
    assert block["lightgbm"] == {"model": "lightgbm", "ind_vars": [], "n_trials": 50}
    assert block["mra"]["log"] and block["multi_mra"]["locations"] == []
    assert model.problems(_project(), prepared)[0] == (
        "Single-family › LightGBM: no variable list. Make one on Variables › Variable lists."
    )
    # A list for the group: its models take it, by reference.
    from oakbox import varlists

    p = _project()
    p.model.lists = varlists.check(
        p, [model.VarList(id="trees", name="Trees", kind="ml", groups=["sf"], variables=["land_area_sqft"])]
    )
    block = model.settings(p, prepared)["modeling"]["models"]["main"]["sf"]
    assert block["lightgbm"] == {"model": "lightgbm", "ind_vars": "$$variable_lists.trees", "n_trials": 50}
    # Local area and the roll take the areas from the group's default entry.
    assert block["default"] == {"ind_vars": ["land_area_sqft", "bldg_area_finished_sqft"]}
    # The study set judges the models by their holdout predictions, like for like with the roll.
    assert s["analysis"] == {"ratio_study": {"study_set_predictions": "holdout"}}


def test_a_groups_own_models(prepared):
    from oakbox import varlists

    p = _project()
    p.model.lists = varlists.check(
        p,
        [
            model.VarList(id="short", name="Short", kind="regression", groups=["sf"], variables=["land_area_sqft"]),
            model.VarList(
                id="blanks",
                name="Blanks",
                kind="regression",
                groups=["sf"],
                variables=["land_area_sqft", "slope_mean_deg"],
            ),
        ],
    )
    model.set_group(
        p,
        prepared,
        "sf",
        [
            model.ModelEntry(engine="xgboost", name="Trees", list_id="short"),
            model.ModelEntry(engine="mra", list_id="blanks"),
            model.ModelEntry(engine="local_area", locations=[]),
        ],
    )
    entries = p.model.groups["sf"]
    # A key from its name; the engine's name unless given one.
    assert [(e.key, e.name) for e in entries] == [("trees", "Trees"), ("mra", "MRA"), ("local_area", "Local area")]
    main = model.settings(p, prepared)["modeling"]
    block = main["models"]["main"]["sf"]
    assert main["instructions"]["main"]["run"] == ["trees", "mra", "local_area", "assessor"]
    assert block["trees"] == {"model": "xgboost", "ind_vars": "$$variable_lists.short", "n_trials": 50}
    # A linear model can't take a blank: its list without the variables with blanks, written out.
    assert block["mra"]["ind_vars"] == ["land_area_sqft"]
    assert block["local_area"] == {"model": "local_area", "locations": []}
    # Local area needs a location; a mismatched list is said, not refused.
    assert model.problems(p, prepared) == ["Single-family › Local area: Local area needs at least one location."]
    views = {e.key: e for e in model.setup(p, prepared).groups[0].models}
    assert [w.code for w in views["trees"].warnings] == ["kind_mismatch"]
    assert [(w.code, w.n) for w in views["mra"].warnings] == [("blanks_left_out", 1)]
    with pytest.raises(ValueError):
        model.set_group(p, prepared, "sf", [model.ModelEntry(engine="nope")])
    with pytest.raises(ValueError):
        model.set_group(p, prepared, "sf", [model.ModelEntry(engine="mra", list_id="gone")])
    with pytest.raises(ValueError):
        model.set_group(p, prepared, "sf", [model.ModelEntry(engine="mra"), model.ModelEntry(engine="mra")])
    # Back to the default models.
    model.set_group(p, prepared, "sf", None)
    assert "sf" not in p.model.groups


def test_nothing_before_the_fields_are_prepared(tmp_path):
    assert model.settings(_project(), tmp_path) == {}


def test_how_they_did_tables():
    from types import SimpleNamespace

    def stats(models, sales):
        rows = {
            m: {
                "utility_score": 20.0,
                "count_sales": sales,
                "count_univ": 5408,
                "median_ratio": 1.0 if m != "mra" else 0.8,
                "cod": 12.345678,
                "prd": 1.01,
                "prb": 0.07,
                "vei": -3.0,
                "vei_sig": 0.4,
                "chd": None,
                "count_trim": sales - 2,
                "cod_trim": 30.0,
                "prd_trim": 1.0,
                "prb_trim": 0.01,
                "median_ratio_trim": 1.0 if m != "mra" else 0.85,
                "vei_trim": -2.0,
                "vei_sig_trim": 0.5,
            }
            for m in models
        }
        return pd.DataFrame.from_dict(rows, orient="index")

    dates = pd.DataFrame({"sale_date": pd.to_datetime(["2024-03-01", "2024-11-30"])})
    bench = SimpleNamespace(
        df_stats_test=stats(["lightgbm", "mra", "ensemble"], 1234),
        df_stats_test_post_val=stats(["mra"], 0),
        test_post_val_empty=True,
        df_stats_full=stats(["lightgbm", "mra", "ensemble", "assessor"], 300),
    )
    first = SimpleNamespace(df_test=dates, df_sales_lookback=dates)
    r = SimpleNamespace(benchmark=bench, model_results={"lightgbm": first})
    holdout, study = model._sets(r, ratio.iaao_standards()[0], {}, ())
    assert holdout.key == "holdout" and study.key == "study"  # no sales after the valuation date: no such set
    # The roll is on the study set only, first; the ensemble before the models.
    assert [f.model for f in holdout.rows] == ["ensemble", "lightgbm", "mra"]
    assert [f.model for f in study.rows] == ["assessor", "ensemble", "lightgbm", "mra"]
    assert study.rows[0].name == "The roll"
    # The engine's numbers as they are: not rounded, and counts in the thousands kept.
    assert holdout.sales == 1234 and holdout.rows[1].values["cod"] == 12.345678
    assert (holdout.first, holdout.last) == ("2024-03-01", "2024-11-30")
    # Judged: the level, the COD and the PRB, untrimmed and trimmed; the PRD only reported.
    mra = holdout.rows[2]
    assert mra.judged == {"median_ratio": "bad", "cod": "ok", "prb": "slight"}
    assert holdout.trimmed[2].judged == {"median_ratio_trim": "bad", "cod_trim": "bad", "prb_trim": "ok"}
    assert set(holdout.trimmed[0].values) == {
        "count_trim",
        "median_ratio_trim",
        "cod_trim",
        "prd_trim",
        "prb_trim",
        "vei_trim",
        "vei_sig_trim",
    }


def test_each_models_own_settings(prepared):
    from oakbox import varlists

    p = _project()
    p.model.lists = varlists.check(
        p, [model.VarList(id="r", name="R", kind="regression", groups=["sf"], variables=["land_area_sqft"])]
    )
    model.set_group(
        p,
        prepared,
        "sf",
        [
            model.ModelEntry(engine="mra", intercept=False, interactions="default", n_trials=9),
            model.ModelEntry(engine="catboost", list_id="r", n_trials=20, use_gpu=False, log=False),
            model.ModelEntry(engine="gwr"),
        ],
    )
    # Only the options an engine reads are kept.
    mra, cat, gwr = p.model.groups["sf"]
    assert mra.n_trials is None and cat.log is None
    block = model.settings(p, prepared)["modeling"]["models"]["main"]["sf"]
    # Every option written, defaults too: what's shown is what runs.
    assert block["mra"] == {
        "model": "mra",
        "ind_vars": "$$variable_lists.r",
        "log": True,
        "intercept": False,
        "interactions": {"default": True},
    }
    assert block["catboost"] == {
        "model": "catboost",
        "ind_vars": "$$variable_lists.r",
        "n_trials": 20,
        "use_gpu": False,
    }
    assert block["gwr"]["interactions"] == {"default": False}
    with pytest.raises(ValueError):
        model.ModelEntry(engine="lightgbm", n_trials=0)


def test_infinite_variables_are_named_before_the_models_run():
    """OpenAVMKit's "Input contains infinity" names no variable: OAK box says which, where, and which models use it."""
    import numpy as np
    import pandas as pd

    from oakbox.model import not_finite

    sales = pd.DataFrame(
        {"model_group": ["sf", "sf", "condo"], "ratio": [1.0, np.inf, np.inf], "area": [1.0, 2.0, 3.0]}
    )
    universe = pd.DataFrame(
        {"model_group": ["sf"] * 3, "ratio": [np.inf, -np.inf, 1.0], "area": [1.0, 2.0, 1e308 * 10]}
    )
    settings = {
        "variable_lists": {"main": ["ratio", "area"]},
        "modeling": {
            "models": {
                "main": {
                    "sf": {
                        "default": {"ind_vars": ["area"]},
                        "lightgbm": {"model": "lightgbm", "ind_vars": "$$variable_lists.main"},
                        "mra": {"model": "mra", "ind_vars": ["ratio"]},
                    }
                }
            }
        },
    }
    found = not_finite(sales, universe, settings, {"sf": "Single family"}, {"sf": {"lightgbm": "Trees"}})
    assert found == [
        "ratio in Single family: 1 sales and 2 parcels (used by Trees, MRA)",
        "area in Single family: 0 sales and 1 parcels (used by Trees)",
    ]


def test_far_out_variables_and_where_it_stopped():
    """What a crash can say: variables whose parcels go far past the sales (a log model's prediction overflows there),
    and the frames it stopped in."""
    import pandas as pd

    from oakbox.model import _stack, far_out

    sales = pd.DataFrame({"model_group": ["sf"] * 3, "area": [1000.0, 1500.0, 2000.0], "age": [10.0, 20.0, 30.0]})
    universe = pd.DataFrame(
        {"model_group": ["sf"] * 4, "area": [1200.0, 900.0, 80_000.0, 1100.0], "age": [5.0, 15.0, 25.0, 40.0]}
    )
    assert far_out(sales, universe, "sf", ["area", "age", "missing"]) == [
        "area: sales 1,000 to 2,000, parcels 900 to 8e+04 (1 parcels far outside)"
    ]

    def inner():
        raise ValueError("Input contains infinity")

    try:
        inner()
    except ValueError as e:
        assert _stack(e).endswith("test_model.py:" + str(inner.__code__.co_firstlineno + 1) + " inner")


def test_layered_comps(prepared):
    """Layered comps (OpenAVMKit's lcomp): a machine-learning engine like the trees: it takes a machine-learning list,
    blanks and all, and has no settings of its own (it isn't tuned)."""
    from oakbox import varlists

    assert model.kind_of("lcomp") == "ml" and "lcomp" in model.TAKES_LIST and "lcomp" not in model.OPTIONS
    p = _project()
    p.model.lists = varlists.check(
        p,
        [
            model.VarList(
                id="comps", name="Comps", kind="ml", groups=["sf"], variables=["land_area_sqft", "slope_mean_deg"]
            )
        ],
    )
    model.set_group(p, prepared, "sf", [model.ModelEntry(engine="lcomp", list_id="comps", n_trials=9)])
    (e,) = p.model.groups["sf"]
    assert (e.key, e.name, e.n_trials) == ("layered_comps", "Layered comps", None)
    s = model.settings(p, prepared)["modeling"]
    # The list as it is: blanks don't take a variable out, as they do for a linear model.
    assert s["models"]["main"]["sf"]["layered_comps"] == {"model": "lcomp", "ind_vars": "$$variable_lists.comps"}
    assert "layered_comps" in s["instructions"]["main"]["run"]


def test_nearby_sales_and_buildings(prepared):
    """Spatial lag: on to start, each modeled group averaging its own sales; borrowing and more fields as asked. The
    price averages are offered under a plain name and written as OpenAVMKit names them (after the price averaged)."""
    from oakbox import bring_in, varlists

    p = _project()
    p.groups.append(projects.ModelGroup(id="th", name="Townhomes", color="#111"))
    s = model.settings(p, prepared)
    assert s["data"]["process"]["enrich"]["spatial_lag"] == {
        "model_groups": {"sf": {"sample_from": ["sf"]}, "th": {"sample_from": ["th"]}}
    }
    model.change(
        p, model.ModelPatch(lag_borrow=model.LagBorrow(group="th", sources=["sf", "th"]), lag_fields=["bath_half"])
    )
    lag = model.settings(p, prepared)["data"]["process"]["enrich"]["spatial_lag"]
    assert lag["model_groups"]["th"] == {"sample_from": ["th", "sf"]} and lag["fields"] == {"bath_half": 5}
    assert "spatial_lag_bath_half" in {v.field for v in model.variables(p, prepared)}
    with pytest.raises(ValueError):
        model.change(p, model.ModelPatch(lag_borrow=model.LagBorrow(group="th", sources=["nowhere"])))

    # A list's price average, as OpenAVMKit names it: time adjusted when Check sales adjusts prices.
    p.model.lists = varlists.check(
        p,
        [
            model.VarList(
                id="m", name="M", kind="ml", groups=["sf"], variables=["land_area_sqft", "spatial_lag_sale_price"]
            )
        ],
    )
    assert model.settings(p, prepared)["variable_lists"]["m"] == ["land_area_sqft", "spatial_lag_sale_price_time_adj"]
    p.clean.time_adjust = False
    assert model.settings(p, prepared)["variable_lists"]["m"] == ["land_area_sqft", "spatial_lag_sale_price"]

    # Worked out as the models run: Bring in data's settings don't change with it.
    on = {"data": {"load": {}, "process": {"enrich": {"census": {"enabled": True}}}}}
    with_lag = {"data": {"load": {}, "process": {"enrich": {"census": {"enabled": True}, "spatial_lag": lag}}}}
    assert bring_in.settings_key(on) == bring_in.settings_key(with_lag) and bring_in.changes(on, with_lag) == []
    # Nor when it's the only enrichment (no enrich section before it).
    bare = {"data": {"load": {}, "process": {}}}
    only_lag = {"data": {"load": {}, "process": {"enrich": {"spatial_lag": lag}}}}
    assert bring_in.settings_key(bare) == bring_in.settings_key(only_lag)

    # Off: nothing written, nothing offered.
    model.change(p, model.ModelPatch(lag_on=False))
    assert "data" not in model.settings(p, prepared)
    assert not [v for v in model.variables(p, prepared) if v.field.startswith(model.LAG)]


def test_a_nearby_average_with_too_few_sales_is_named():
    """OpenAVMKit writes 0 where there are too few sales to average: a model would read it as worth nothing."""
    universe = pd.DataFrame({"model_group": ["sf", "sf", "th"], "spatial_lag_sale_price": [0.0, 0.0, 250_000.0]})
    settings = {
        "variable_lists": {"l": ["spatial_lag_sale_price", "land_area_sqft"]},
        "modeling": {
            "models": {
                "main": {
                    "sf": {"m": {"ind_vars": "$$variable_lists.l"}},
                    "th": {"m": {"ind_vars": "$$variable_lists.l"}},
                }
            }
        },
    }
    names = {"sf": "Single family", "th": "Townhomes"}
    zeros = model.lag_zeros(None, universe, settings, names)
    assert zeros == {"sf": ["spatial_lag_sale_price"]}
    # Not worked out at all (every group too small to average): the same.
    assert model.lag_zeros(None, universe[["model_group"]], settings, names) == {
        "sf": ["spatial_lag_sale_price"],
        "th": ["spatial_lag_sale_price"],
    }
    # Left out of that group's models only, for the run, and said; the other group keeps it.
    lines = model.drop_lag_zeros(settings, zeros, names)
    assert settings["modeling"]["models"]["main"]["sf"]["m"]["ind_vars"] == ["land_area_sqft"]
    assert settings["modeling"]["models"]["main"]["th"]["m"]["ind_vars"] == "$$variable_lists.l"
    assert lines[0].startswith("Single family: spatial_lag_sale_price left out of its models")
    # A model left with nothing stops the run.
    bare = {"modeling": {"models": {"main": {"sf": {"m": {"ind_vars": ["spatial_lag_sale_price"]}}}}}}
    with pytest.raises(ValueError):
        model.drop_lag_zeros(bare, zeros, names)


def test_groups_too_small_to_average_are_left_out():
    """OpenAVMKit looks up each parcel's 5 nearest in its group, and stops on a smaller one: such groups aren't
    averaged (their models do without), nor borrowed from."""
    universe = pd.DataFrame({"model_group": ["sf"] * 12 + ["tiny"] * 4})
    settings = {
        "data": {
            "process": {
                "enrich": {
                    "spatial_lag": {
                        "model_groups": {"sf": {"sample_from": ["sf", "tiny"]}, "tiny": {"sample_from": ["tiny"]}}
                    }
                }
            }
        }
    }
    assert model.lag_prune(settings, universe) == ["tiny"]
    assert settings["data"]["process"]["enrich"]["spatial_lag"]["model_groups"] == {"sf": {"sample_from": ["sf"]}}

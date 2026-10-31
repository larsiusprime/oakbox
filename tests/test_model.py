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
    assert list(vs) == [
        "bldg_area_finished_sqft",
        "land_area_sqft",
        "bldg_age_years",
        "bath_half",
        "proximity_to_park",
        "slope_mean_deg",
        "latitude_norm",
        "land_class",
    ]
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

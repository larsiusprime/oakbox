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


def test_choose_for_me_settings(prepared):
    main = model.settings(_project(), prepared)["modeling"]
    # The roll runs too, as OpenAVMKit's assessor model: it's audited on the study set, beside the models.
    assert main["instructions"]["main"]["run"] == ["lightgbm", "mra", "local_area", "assessor"]
    entries = main["models"]["main"]
    # The default list is the linear-safe one; trees get every variable; MRA fits log price.
    assert "slope_mean_deg" not in entries["default"]["ind_vars"]
    assert "slope_mean_deg" in entries["lightgbm"]["ind_vars"]
    assert entries["mra"] == {"log": True} and entries["local_area"] == {}
    # The study set judges the models by their holdout predictions, like for like with the roll.
    assert model.settings(_project(), prepared)["analysis"] == {"ratio_study": {"study_set_predictions": "holdout"}}


def test_choices(prepared):
    p = _project()
    model.change(p, model.ModelPatch(variables=["land_area_sqft"], models=["mra", "xgboost"]))
    main = model.settings(p, prepared)["modeling"]
    assert main["instructions"]["main"]["run"] == ["xgboost", "mra", "assessor"]  # in the order offered
    assert main["models"]["main"]["xgboost"]["ind_vars"] == ["land_area_sqft"]
    with pytest.raises(ValueError):
        model.change(p, model.ModelPatch(models=[]))
    with pytest.raises(ValueError):
        model.change(p, model.ModelPatch(models=["nope"]))
    model.change(p, model.ModelPatch(every_variable=True, choose_for_me=True))
    assert p.model.variables is None and p.model.models is None


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

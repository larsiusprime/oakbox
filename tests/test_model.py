"""Step 5, the models (SPEC F9): the variables found, and the settings written for them."""

import json

import pandas as pd
import pytest

from oakbox import model, projects


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
    assert main["instructions"]["main"]["run"] == ["lightgbm", "mra", "local_area"]
    entries = main["models"]["main"]
    # The default list is the linear-safe one; trees get every variable; MRA fits log price.
    assert "slope_mean_deg" not in entries["default"]["ind_vars"]
    assert "slope_mean_deg" in entries["lightgbm"]["ind_vars"]
    assert entries["mra"] == {"log": True} and entries["local_area"] == {}


def test_choices(prepared):
    p = _project()
    model.change(p, model.ModelPatch(variables=["land_area_sqft"], models=["mra", "xgboost"]))
    main = model.settings(p, prepared)["modeling"]
    assert main["instructions"]["main"]["run"] == ["xgboost", "mra"]  # in the order offered
    assert main["models"]["main"]["xgboost"]["ind_vars"] == ["land_area_sqft"]
    with pytest.raises(ValueError):
        model.change(p, model.ModelPatch(models=[]))
    with pytest.raises(ValueError):
        model.change(p, model.ModelPatch(models=["nope"]))
    model.change(p, model.ModelPatch(every_variable=True, choose_for_me=True))
    assert p.model.variables is None and p.model.models is None


def test_nothing_before_the_fields_are_prepared(tmp_path):
    assert model.settings(_project(), tmp_path) == {}

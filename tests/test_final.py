"""Model values › Finalize (SPEC F9, slice 2): the groups left unvalued skipped, the values compared with the roll's."""

import math

import pandas as pd

from oakbox import final, model


def test_the_groups_left_unvalued_skip_every_model():
    settings = {
        "modeling": {
            "instructions": {
                "main": {"run": ["lightgbm", "mra", "ensemble"], "skip": {"apartments": ["mra"], "condos": ["mra"]}}
            }
        }
    }
    final._skip(settings, ["apartments", "public"])
    skip = settings["modeling"]["instructions"]["main"]["skip"]
    # Every model, the ensemble combining them aside; a group's own skips kept; the others untouched.
    assert skip == {"apartments": ["lightgbm", "mra"], "public": ["lightgbm", "mra"], "condos": ["mra"]}


def test_a_value_looked_up_by_key_is_blank_where_there_is_none():
    keys = pd.Series(["1", 2, "3"], index=[10, 11, 12])
    out = final._look(keys, {"1": 100.0, "2": 200.0})
    assert list(out.index) == [10, 11, 12]
    assert out[10] == 100.0 and out[11] == 200.0 and math.isnan(out[12])


def test_how_far_the_values_moved_from_the_roll():
    values = pd.DataFrame(
        {
            "model_group": ["sf"] * 5 + ["condo"],
            final.VALUE: [130.0, 100.0, 70.0, 110.0, float("nan"), 50.0],
            "assr_market_value": [100.0, 100.0, 100.0, 100.0, 100.0, 50.0],
        }
    )
    median, up, down, total, roll_total = final._changes(values, "assr_market_value", "sf")
    # 1.3, 1.0, 0.7, 1.1 (the blank one left out): median 1.05, one up and one down over 20%.
    assert round(median or 0, 3) == 0.05
    assert (up, down) == (1, 1)
    assert total == 410.0 and roll_total == 400.0
    # No roll: the total alone.
    assert final._changes(values, None, "sf") == (None, 0, 0, 410.0, None)


def test_finalize_follows_the_try():
    assert final.STEP.after is model.STEP
    assert set(final.FIELDS) == set(final.SETS) == set(final.ROLLS)


def test_the_parcels_for_the_map(tmp_path):
    d = final.out_dir(tmp_path)
    d.mkdir(parents=True)
    pd.DataFrame(
        {
            "key": ["1", "2", "3"],
            "model_group": ["sf", "condo", "sf"],
            final.VALUE: [200.0, float("nan"), 300.0],
            "below_zero": [False, False, False],
            "assr_market_value": [180.0, 90.0, None],
            "latitude": [36.1, 36.2, None],  # no place: not on the map
            "longitude": [-79.8, -79.9, -79.7],
            "area": [1000.0, None, 1500.0],
        }
    ).to_parquet(d / "values.parquet")
    p = final.parcel_points(tmp_path)
    assert p is not None
    assert p.key == ["1", "2"] and p.groups == ["condo", "sf"] and p.group == [1, 0]
    assert p.value == [200.0, None] and p.roll == [180.0, 90.0] and p.area == [1000.0, None]
    assert final.parcel_points(tmp_path / "nothing") is None

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

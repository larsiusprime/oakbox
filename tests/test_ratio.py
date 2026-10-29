"""Step 4, Check my values (SPEC F8): its calls, the window proposed, and the values checked on a small project."""

import datetime as dt

import pytest

from oakbox import projects, ratio


@pytest.mark.parametrize(
    "gid, name, cls",
    [
        ("single_family", "Single-family", "residential"),
        ("condos_townhomes", "Condos & townhomes", "residential"),
        ("small_multi_family", "Small multi-family", "residential"),
        ("apartments", "Apartments", "income"),
        ("commercial_industrial", "Commercial & industrial", "income"),
        ("public_exempt", "Public & exempt", "none"),
        ("vacant_land", "Vacant land", "vacant"),
    ],
)
def test_classes_proposed_from_the_name(gid, name, cls):
    assert ratio.proposed_class(gid, name) == cls


def _project():
    return projects.Project.model_validate(
        {
            "id": "x",
            "name": "x",
            "created_at": "2026-01-01T00:00:00",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "groups": [{"id": "sf", "name": "Single-family", "color": "#000"}],
        }
    )


def test_the_window_reaches_back_until_there_are_enough_sales():
    import pandas as pd

    p = _project()
    # 40 sales in 2023, none since: the year before (2025) and two years (2024-) are empty; three years hold them.
    sales = pd.DataFrame(
        {
            "sale_date": pd.to_datetime(["2023-06-01"] * 40),
            "sale_price": [100_000.0] * 40,
            "assr_market_value": [90_000.0] * 40,
            "valid_for_ratio_study": [True] * 40,
        }
    )
    start, end, proposed = ratio.window(p, sales)
    assert (start, end) == (dt.date(2023, 1, 1), dt.date(2025, 12, 31)) and proposed == start
    p.ratio.start = dt.date(2024, 6, 1)
    assert ratio.window(p, sales)[0] == dt.date(2024, 6, 1)


def test_changes_are_checked():
    p = _project()
    with pytest.raises(ValueError):
        ratio.change(p, ratio.RatioPatch(fields=["nope"]))
    with pytest.raises(ValueError):
        ratio.change(p, ratio.RatioPatch(start=dt.date(2025, 1, 1), end=dt.date(2024, 1, 1)))
    ratio.change(p, ratio.RatioPatch(reset_window=True, classes={"sf": "income"}))
    assert p.ratio.start is None and ratio.classes(p) == {"sf": "income"}
    t = ratio.Targets().standards()
    assert t["level"] == [0.9, 1.1] and t["cod"]["residential"] == 15.0

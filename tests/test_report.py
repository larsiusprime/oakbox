"""Step 7, Report (SPEC §4): every parcel's model value as a file, and the report to print."""

import datetime as dt
import json

import pandas as pd
import pytest

from oakbox import final, projects, ratio, report


def _project():
    return projects.Project.model_validate(
        {
            "id": "x",
            "name": "Town",
            "created_at": "2026-01-01T00:00:00",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "jurisdiction": "Town",
            "region": "NC",
            "groups": [
                {"id": "sf", "name": "Single-family", "color": "#000"},
                {"id": "apt", "name": "Apartments", "color": "#111"},
            ],
        }
    )


def study_view(gid, name, median=0.97, sales=40, judged=True):
    return ratio.Study(
        id=gid,
        name=name,
        color="#000",
        cls="residential" if gid else None,
        sales=sales,
        trimmed=0,
        parcels=100,
        median=median,
        low=median - 0.02,
        high=median + 0.02,
        cod=9.5,
        prd=1.01,
        prb=-0.01,
        vei=-2.0,
        vei_significance=0.4,
        vei_verdict="not_significant",
        median_chd=12.0,
        verdict=ratio.Verdict(judged=judged, level=True, cod=True, cod_target=[5, 15], prb=True, vei=True),
    )


@pytest.fixture
def finalized(tmp_path):
    out = final.out_dir(tmp_path)
    (out / "studies").mkdir(parents=True)
    model = ratio.FieldResult(
        field="oak_oof",
        name="Model values",
        groups=[study_view("sf", "Single-family")],
        overall=study_view("", "All"),
        trimmed=[],
    )
    roll = ratio.FieldResult(
        field="oak_roll_oof",
        name="Roll",
        groups=[study_view("sf", "Single-family", 0.84)],
        overall=study_view("", "All", 0.84),
        trimmed=[],
    )
    receipt = final.FinalReceipt(
        ran_at="2026-11-01T10:00:00",
        seconds=1.0,
        engine="0.0",
        start=dt.date(2025, 1, 1),
        end=dt.date(2025, 12, 31),
        price="sold",
        trim=True,
        roll="Roll",
        sets=[
            final.SetResult(key="oof", sales=40, model=model, roll=roll),
            final.SetResult(key="held", sales=0, model=None, roll=None),
        ],
        groups=[
            final.GroupValues(
                id="sf",
                name="Single-family",
                color="#000",
                parcels=2,
                valued=2,
                unvalued=None,
                blanked=0,
                median_change=0.1,
                up=1,
                down=0,
                total=300.0,
                roll_total=250.0,
            ),
            final.GroupValues(
                id="apt",
                name="Apartments",
                color="#111",
                parcels=1,
                valued=0,
                unvalued="Left unvalued (Small groups)",
                blanked=0,
                median_change=None,
                up=0,
                down=0,
                total=None,
                roll_total=None,
            ),
        ],
    )
    (out / "receipt.json").write_text(receipt.model_dump_json(), encoding="utf-8")
    (out / "settings.json").write_text(json.dumps({"hash": "x"}), encoding="utf-8")
    pd.DataFrame(
        {
            "key": ["1", "2", "3"],
            "model_group": ["sf", "sf", "apt"],
            final.VALUE: [100.0, 200.0, float("nan")],
            "below_zero": [False, False, False],
            "assr_market_value": [80.0, 170.0, 500.0],
            "latitude": [36.1, 36.2, 36.3],
            "longitude": [-79.8, -79.7, -79.6],
            "area": [1000.0, 0.0, 800.0],
        }
    ).to_parquet(out / "values.parquet")
    pd.DataFrame(
        {
            "key_sale": ["1-a", "1-b"],
            "key": ["1", "1"],
            "model_group": ["sf", "sf"],
            "sale_date": pd.to_datetime(["2025-02-01", "2025-06-01"]),
            "latitude": [36.1, 36.1],
            "longitude": [-79.8, -79.8],
            "sale_price": [90.0, 110.0],
            "value": [100.0, 100.0],
            "ratio": [1.111, 0.909],
            "trimmed": [False, False],
        }
    ).to_parquet(out / "studies" / f"{final.VALUE}.sales.parquet")
    return tmp_path


def test_every_parcel_with_its_value_the_rolls_and_its_latest_sale(finalized):
    t = report.table(_project(), finalized)
    assert list(t["model_group"]) == ["Single-family", "Single-family", "Apartments"]
    assert list(t["change_pct"][:2]) == [25.0, 17.6]
    # Per finished area only where there is one.
    per = t["value_per_sqft"].tolist()
    assert per[0] == 0.1 and pd.isna(per[1])
    assert t["no_value_why"][2] == "Left unvalued (Small groups)"
    # The latest sale in the window, and its ratio.
    assert t["sale_price"].tolist()[0] == 110.0 and t["sale_date"].tolist()[0] == "2025-06-01"
    assert t["ratio"].tolist()[0] == 0.909
    assert pd.isna(t["sale_price"].tolist()[1])


@pytest.mark.parametrize("fmt", ["csv", "xlsx", "gpkg", "shp", "parquet"])
def test_export_writes_every_format(finalized, fmt):
    r = report.export(_project(), finalized, fmt)
    assert r.rows == 3 and (finalized / r.path).is_file()
    if fmt in report.GEO:
        # No parcel shapes here: points from latitude and longitude, said.
        assert any("point" in n for n in r.notes)
    if fmt == "shp":
        assert (finalized / r.path).with_name("town_2026_model_values_fields.csv").is_file()


def test_the_report(finalized, monkeypatch):
    monkeypatch.setattr(report, "_method", lambda *a: "<section>method</section>")
    p = _project()
    page = report.build(p, finalized)
    assert "<title>Town: model values, tax year 2026</title>" in page
    assert "values sit at 0.970 of sale prices" in page and "The roll on the same sales: 0.840" in page
    assert "Judged on out-of-fold sales" in page
    # A set chosen with no sales is said, not left out silently.
    assert "No held-out sales in the window" in page
    assert "Apartments (1 parcel: Left unvalued (Small groups))" in page
    # The sets picked, and a title of the user's.
    report.change(p, report.ReportPatch(sets=["held"], title="  Board summary "))
    page = report.build(p, finalized)
    assert "<title>Board summary</title>" in page and "Judged on out-of-fold" not in page
    with pytest.raises(ValueError):
        report.change(p, report.ReportPatch(sets=[]))

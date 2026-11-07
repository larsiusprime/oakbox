"""6. Models › Outliers (SPEC F9, slice 3): the outlying sales, what the misses have in common, and the calls."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from openavmkit.filters import resolve_filter

from oakbox import final, model, outliers, projects
from oakbox.datafiles import Condition, Rule
from oakbox.projects import ModelGroup, Project


def _project(**kw) -> Project:
    groups = [
        ModelGroup(
            id="sf",
            name="Single-family",
            color="#111111",
            rule=Rule(join="any", conditions=[Condition(column="land_use", op="isin", values=["SFR"])]),
        ),
        ModelGroup(
            id="condo",
            name="Condos",
            color="#222222",
            rule=Rule(join="any", conditions=[Condition(column="land_use", op="isin", values=["CONDO"])]),
        ),
    ]
    p = Project(id="p1", name="Test", created_at=dt.datetime(2026, 1, 1), tax_year=2026, groups=groups, **kw)
    p.clean.location = ""  # Check sales decided: its marks are written
    return p


def test_a_parcel_moved_by_hand_is_in_its_new_group_and_no_other():
    p = _project()
    u = pd.DataFrame({"key": ["1", "2", "3"], "land_use": ["SFR", "SFR", "CONDO"]})
    p.groups[1].keys = ["2"]
    sf = resolve_filter(u, projects.group_filter(p.groups[0], p.groups)).fillna(False).astype(bool).tolist()
    condo = resolve_filter(u, projects.group_filter(p.groups[1], p.groups)).fillna(False).astype(bool).tolist()
    assert sf == [True, False, False]
    assert condo == [False, True, True]
    # A group with no rule yet: only the parcels put in it.
    lone = ModelGroup(id="x", name="X", color="#333333", keys=["3"])
    assert resolve_filter(u, projects.group_filter(lone)).fillna(False).astype(bool).tolist() == [False, False, True]


def test_patches_are_written_as_openavmkits_tweak_the_last_one_winning():
    p = _project()
    at = dt.datetime(2026, 1, 2)
    p.patches = [
        projects.Patch(key="7", field="bldg_quality_num", was=3.0, now=4.0, at=at),
        projects.Patch(key="7", field="bldg_quality_num", was=4.0, now=5.0, at=at),
        projects.Patch(key="9", field="pool", was="no", now="yes", at=at),
    ]
    out: dict = {}
    projects._patches(p, out)
    assert out["process"]["enrich"]["tweak"]["universe"] == [
        {"field": "bldg_quality_num", "key": "key", "values": {"7": 5.0}},
        {"field": "pool", "key": "key", "values": {"9": "yes"}},
    ]


def _sales(tmp_path, n=200, seed=1):
    """A group's sales whose error lines up with `pool` (pools valued 30% low), not with `noise`; `pool_too` the same
    sales as `pool`; the places random."""
    rng = np.random.default_rng(seed)
    pool = rng.random(n) < 0.25
    err = np.where(pool, np.log(0.7), 0.0) + rng.normal(0, 0.08, n)
    price = rng.uniform(200_000, 400_000, n)
    t = pd.DataFrame(
        {
            "key": [str(i) for i in range(n)],
            "key_sale": [f"{i}-2025-01-01" for i in range(n)],
            "model_group": "sf",
            "sale_date": "2025-01-01",
            "sale_price": price,
            "oak_price": price,
            "oak_oof": price * np.exp(err),
            "pool": np.where(pool, "yes", "no"),
            "pool_too": np.where(pool, "Y", "N"),
            "noise": rng.normal(0, 1, n),
            "bldg_quality_num": rng.integers(1, 6, n).astype(float),
            "latitude": 38 + rng.random(n) / 10,
            "longitude": -77 + rng.random(n) / 10,
        }
    )
    t["oak_ratio"] = t["oak_oof"] / t["oak_price"]
    d = final.out_dir(tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    t.to_parquet(d / final.SALES, index=False)
    return t


@pytest.fixture
def looked(monkeypatch):
    names = {"pool": "Pool", "pool_too": "Has a pool", "noise": "Noise", "bldg_quality_num": "Quality"}

    def cands(project, project_dir, t):
        return [
            model.Variable(
                field=f,
                name=n,
                kind="other",
                numeric=f in ("noise", "bldg_quality_num"),
                parcels=1,
                blanks=0,
                ml_only=False,
            )
            for f, n in names.items()
        ]

    monkeypatch.setattr(outliers, "_candidates", cands)
    monkeypatch.setattr(outliers, "in_model", lambda *a: {"noise", "bldg_quality_num"})
    monkeypatch.setattr(outliers, "patch_fields", lambda *a: {"bldg_quality_num", "pool"})


def test_what_the_misses_have_in_common_finds_the_field_and_not_the_noise(tmp_path, looked):
    _sales(tmp_path)
    c = outliers.common(_project(), tmp_path, "sf")
    fields = [x.field for x in c.patterns]
    assert fields[0] in ("pool", "pool_too") and "noise" not in fields
    top = c.patterns[0]
    assert top.off == pytest.approx(-0.3, abs=0.05) and abs(top.rest_off) < 0.05
    assert not top.in_model and top.chance < 0.05
    # The same sales under another name: said to go with the first, not as a second finding.
    second = next(x for x in c.patterns if x.field in ("pool", "pool_too") and x is not top)
    assert second.goes_with == top.name
    assert c.clustered is False  # random places: the errors aren't alike between neighbours


def test_the_outliers_worst_first_and_one_sales_context(tmp_path, looked):
    t = _sales(tmp_path)
    p = _project()
    v = outliers.view(p, tmp_path, None)
    out = t[(t["oak_ratio"] < 0.75) | (t["oak_ratio"] > 1.25)]
    assert v.ready and v.group == "sf" and len(v.outliers) == len(out) > 0
    lows = [s.ratio for s in v.outliers if s.ratio < 0.75]
    highs = [s.ratio for s in v.outliers if s.ratio > 1.25]
    assert [s.ratio for s in v.outliers] == sorted(lows) + sorted(highs, reverse=True)
    assert len(v.points) == len(t)
    d = outliers.detail(p, tmp_path, v.outliers[0].key_sale)
    assert len(d.comps) == outliers.COMPS and all(c.key_sale != d.sale.key_sale for c in d.comps)
    pool = next(u for u in d.unlike if u.field == "pool")
    assert pool.share is not None and not pool.in_model
    assert {x.field for x in d.patchable} == {"bldg_quality_num", "pool"}


def test_each_call_goes_where_it_belongs_and_comes_back(tmp_path, looked):
    t = _sales(tmp_path)
    p = _project()
    k = t["key_sale"].tolist()
    with pytest.raises(ValueError):
        outliers.decide(p, tmp_path, k[0], outliers.OutlierCallBody(why="invalid"))
    with pytest.raises(ValueError):
        outliers.decide(p, tmp_path, k[3], outliers.OutlierCallBody(why="data", field="noise", now="1"))
    outliers.decide(p, tmp_path, k[0], outliers.OutlierCallBody(why="invalid", reason="related", note="to a son"))
    outliers.decide(p, tmp_path, k[1], outliers.OutlierCallBody(why="group", group="condo"))
    outliers.decide(
        p, tmp_path, k[2], outliers.OutlierCallBody(why="data", field="bldg_quality_num", now="5", source="visit")
    )
    outliers.decide(p, tmp_path, k[4], outliers.OutlierCallBody(why="model", note="near the rail line"))
    # On the list only, changing nothing, until applied: the steps after stay as they are meanwhile.
    assert not p.clean.marks and not p.patches and p.groups[1].keys == []
    assert outliers.pending(p) == ["data", "group", "invalid"]
    assert outliers.apply(p, tmp_path) == ["data", "group", "invalid", "model"]
    assert outliers.pending(p) == []
    # The sale isn't a market sale: Check sales' Exclude, with the reason.
    assert p.clean.marks[k[0]].action == "exclude" and "related parties: to a son" in p.clean.marks[k[0]].note
    # The wrong group: the parcel put in the other by hand.
    assert p.groups[1].keys == ["1"]
    # The data: a patch, a number for a number field.
    assert p.patches[0].now == 5.0 and p.patches[0].key == "2" and p.patches[0].sale == k[2]
    assert "key,field,was,now" in outliers.patches_csv(p)
    assert {c.why for c in p.outliers.calls.values()} == {"invalid", "group", "data", "model"}
    # Each taken back, with what it did.
    for key in k[:5]:
        outliers.undo(p, key)
    assert not p.outliers.calls and not p.patches and k[0] not in p.clean.marks and p.groups[1].keys == []

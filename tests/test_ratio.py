"""Step 4, Check my values (SPEC F8): its calls, the window proposed, and the values checked on a small project."""

import datetime as dt

import pytest

from oakbox import projects, ratio


@pytest.mark.parametrize(
    "gid, name, cls",
    [
        ("single_family", "Single-family", "residential"),
        ("condos_townhomes", "Condos & townhomes", "residential_homogeneous"),
        ("small_multi_family", "Small multi-family", "residential"),
        ("apartments", "Apartments", "apartments"),
        ("commercial_industrial", "Commercial & industrial", "commercial"),
        ("farms", "Agricultural land", "agricultural"),
        ("mh", "Manufactured homes", "residential_rural"),
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
        ratio.change(p, ratio.RatioPatch(start=dt.date(2025, 1, 1), end=dt.date(2024, 1, 1)))
    ratio.change(p, ratio.RatioPatch(reset_window=True))
    assert p.ratio.start is None
    # The exposure draft's targets: COD ranges per category (Table 7), the PRB's good and unacceptable ranges.
    t = ratio.Targets().standards()
    assert t["level"] == [0.9, 1.1] and t["cod"]["residential"] == [5.0, 15.0] and t["cod"]["apartments"] == [7.0, 20.0]
    assert t["prb"] == [-0.05, 0.05] and t["prb_unacceptable"] == [-0.10, 0.10] and "prd" not in t


def test_standards_the_iaaos_or_custom_and_the_groups_each_judges():
    p = _project()
    p.groups.append(projects.ModelGroup(id="condo", name="Condos", color="#111"))
    # The IAAO's, one standard per category; each group's proposed from its name.
    iaao = ratio.standards(p)
    assert [x.id for x in iaao] == list(ratio.CATEGORIES) and iaao[1].cod_low == 4.0
    assert ratio.classes(p) == {"sf": "residential", "condo": "residential_homogeneous"}
    # Custom, starting from the IAAO's figures (each changeable), or with none.
    ratio.change(p, ratio.RatioPatch(source="custom", start_from="empty"))
    assert (
        p.ratio.source == "custom" and ratio.standards(p) == [] and ratio.classes(p) == {"sf": "none", "condo": "none"}
    )
    ratio.change(p, ratio.RatioPatch(source="custom", start_from="iaao"))
    assert len(ratio.standards(p)) == 7
    # A state's own: its own targets and the groups it judges; a group in one standard at most (the last naming it).
    state = ratio.Standard(id="s1", name="State residential", level_low=0.95, level_high=1.05, vei=15.0, groups=["sf"])
    other = ratio.Standard(id="s2", name="State condos", groups=["condo", "sf"])
    ratio.change(p, ratio.RatioPatch(standards=[state, other]))
    assert ratio.classes(p) == {"sf": "s2", "condo": "s2"}
    with pytest.raises(ValueError):
        ratio.change(p, ratio.RatioPatch(standards=[state, state]))  # a name once
    with pytest.raises(ValueError):
        ratio.change(p, ratio.RatioPatch(standards=[state.model_copy(update={"level_low": 1.2})]))  # upside down
    ratio.change(p, ratio.RatioPatch(standards=[state, other.model_copy(update={"groups": ["condo"]})]))
    e = ratio.engine_standards(p)
    assert e["cod"]["s1"] == [5.0, 15.0] and e["by_class"]["s1"]["level"] == [0.95, 1.05]
    assert e["by_class"]["s1"]["vei"] == 15.0 and ratio.classes(p) == {"sf": "s1", "condo": "s2"}
    # Back to the IAAO's.
    ratio.change(p, ratio.RatioPatch(reset_standards=True))
    assert p.ratio.source == "iaao" and p.ratio.standards is None


def test_sales_by_their_neighbourhood_on_the_map(tmp_path):
    """Neighbourhood price levels' map: each sale studied with a place, by its region; each region's median ratio
    without the outlying (trimmed) ones, and the median of them all; a model group picked keeps only its sales."""
    import pandas as pd

    studies = ratio.out_dir(tmp_path) / "studies"
    studies.mkdir(parents=True)
    pd.DataFrame(
        {
            "latitude": [1.0, 1.0, 2.0, 2.0, None],
            "longitude": [3.0, 3.0, 4.0, 4.0, 5.0],
            "model_group": ["sf", "sf", "sf", "condo", "sf"],
            "neighborhood": ["B", "B", "A", "A", "A"],
            "ratio": [0.8, 5.0, 1.2, 1.0, 1.0],
            "trimmed": [False, True, False, False, False],
        }
    ).to_parquet(studies / "v.sales.parquet")
    got = ratio.region_points(tmp_path, "v", "neighborhood", None)
    assert got.regions == ["A", "B"] and got.region == [1, 1, 0, 0]  # the one with no place left out
    assert got.median == [1.1, 0.8] and got.sales == [2, 1] and got.overall == 1.0
    sf = ratio.region_points(tmp_path, "v", "neighborhood", "sf")
    assert sf.median == [1.2, 0.8] and len(sf.lon) == 3
    assert ratio.region_points(tmp_path, "v", "zone", None).lon == []  # not a column of the study


def test_a_group_of_similar_parcels(tmp_path):
    """Similar parcels' map: each parcel's group (its model group and cluster) and that group's spread (CHD); a
    group clicked, its parcels with their places and values, dearest first."""
    import pandas as pd

    from oakbox import clean

    where = clean.out_dir(tmp_path)
    where.mkdir(parents=True)
    pd.DataFrame(
        {
            "key": ["a", "b", "c", "d"],
            "latitude": [1.0, 1.1, 1.2, 2.0],
            "longitude": [3.0, 3.1, 3.2, 4.0],
            "model_group": ["sf", "sf", "sf", "condo"],
            "he_id": ["0", "0", "0", "0"],  # numbered per model group: sf:0 and condo:0 are different groups
            "v": [100.0, 200.0, 300.0, 50.0],
        }
    ).to_parquet(where / clean.UNIVERSE_KEPT)
    pts = ratio.similar_points(tmp_path, "v", None)
    assert pts.size == [3, 3, 3, 1] and pts.chd[3] is None
    assert [pts.clusters[i] for i in pts.cluster] == ["sf:0", "sf:0", "sf:0", "condo:0"]
    g = ratio.similar_group(tmp_path, "v", "sf:0")
    assert [m.key for m in g.members] == ["c", "b", "a"] and g.median == 200.0
    assert g.chd == round(100 * (100 + 0 + 100) / 3 / 200, 1)
    assert ratio.similar_group(tmp_path, "v", "condo:0").members[0].key == "d"

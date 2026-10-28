"""Repeated IDs, wherever they're shown: sorted by the ID, each ID's rows sharing a background, IDs alternating."""

import pandas as pd

from oakbox import bring_in


def test_rows_are_sorted_by_the_id_and_lead_with_it():
    df = pd.DataFrame({"CARD": ["2", "3", "2", "2"], "REID": ["120", "99", "120", "100"]})
    ids = pd.Series(["120", "99", "120", "100"], name="REID")
    out = bring_in.by_id(df, ids)
    assert list(out.columns) == ["REID", "CARD"]
    assert list(out["REID"]) == ["99", "100", "120", "120"]  # numbers as numbers: 99 before 100


def test_each_ids_rows_share_a_band_and_ids_alternate():
    assert bring_in.bands(["99", "100", "100", "120", "120", "120", "7"]) == [0, 1, 1, 0, 0, 0, 1]


def test_a_page_of_repeats_carries_its_bands_from_the_whole_set(tmp_path):
    rows = pd.DataFrame({"REID": ["1", "1", "2", "3", "3", "3"], "CARD": list("abcdef")})
    bring_in._write(rows, bring_in.out_dir(tmp_path) / "rows" / "building_repeats.parquet")
    page = bring_in.page(tmp_path, "building_repeats", offset=3, limit=3)
    assert page.rows[0][0] == "3" and page.bands == [0, 0, 0]  # the whole set: 1 1 | 2 | 3 3 3 is 0 0 1 0 0 0
    bring_in._write(rows, bring_in.out_dir(tmp_path) / "rows" / "building_orphans.parquet")
    assert bring_in.page(tmp_path, "building_orphans", offset=0).bands is None  # not repeats: no bands


def test_every_row_of_a_repeated_id_is_shown_the_kept_one_marked(tmp_path):
    from types import SimpleNamespace

    raw = pd.DataFrame({"REID": ["5", "12", "5", "7", "12", "12"], "CARD": ["1", "1", "2", "1", "2", "3"]})
    ids = pd.Series(raw["REID"])
    dropped = ids.duplicated(keep="first")
    f = SimpleNamespace(load={"key": ["REID", "string"]})
    rows = bring_in._repeats(raw, ids, dropped, ids == "", f, "key")
    assert list(rows.columns) == ["REID", "kept?", "CARD"]
    assert rows.values.tolist() == [
        ["5", "✓ kept", "1"],
        ["5", "left out", "2"],
        ["12", "✓ kept", "1"],
        ["12", "left out", "2"],
        ["12", "left out", "3"],
    ]  # 7 isn't repeated: not shown
    bring_in._write(rows, bring_in.out_dir(tmp_path) / "rows" / "x_repeats.parquet")
    page = bring_in.page(tmp_path, "x_repeats", offset=0)
    assert page.kept == [True, False, True, False, False] and page.kept_total == 2
    assert page.bands == [0, 0, 1, 1, 1]

    # Every row dropped: none kept.
    all_out = bring_in._repeats(raw, ids, ids.duplicated(keep=False), ids == "", f, "key")
    assert set(all_out["kept?"]) == {"left out"}

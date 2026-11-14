"""The clean-up a suggestion finds (wizard/ids.py): worked out on distinct IDs with numpy, it counts the same as
cleaning every ID and counting them one by one."""

import random
from collections import Counter

import pandas as pd

from oakbox.datafiles import clean_value
from oakbox.wizard import ids


def _slow(base: list[str], file: list[str]) -> list[list[int]]:
    """The table as it used to be worked out: every ID cleaned, the sales counted one by one."""
    out = []
    for tb in ids._TRIES:
        bset = {v for v in (clean_value(x, tb) for x in base) if v}
        row = []
        for tf in ids._TRIES:
            counts = Counter(v for v in (clean_value(x, tf) for x in file) if v)
            row.append(sum(n for v, n in counts.items() if v in bset))
        out.append(row)
    return out


def test_the_table_counts_as_one_by_one_would(tmp_path, monkeypatch):
    rnd = random.Random(7)

    def messy(i: int) -> str:
        v = f"{i:08d}"
        return rnd.choice(
            [v, f" {v}", v.lstrip("0"), f"{v[:3]}-{v[3:]}", f"{v[:3]}- {v[3:]}", f"a{v}", f"A{v} ", "", "  ", "000"]
        )

    base = [messy(i) for i in range(3000)]
    file = [messy(rnd.randrange(3500)) for _ in range(5000)]
    sides = {"b": tuple(base), "f": tuple(file)}
    monkeypatch.setattr(ids, "values_of", lambda stamp, layer, column, raw=False: sides[column])
    ids._match_table.cache_clear()
    table = ids._match_table((("x", 0.0, 0), None, "b"), (("y", 0.0, 0), None, "f"))
    assert pd.DataFrame(table).values.tolist() == _slow(base, file)

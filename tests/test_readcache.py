"""A CSV's quick-read copy (readcache): the same values as the CSV, made once, remade when the file changes."""

from __future__ import annotations

import time
from pathlib import Path

from oakbox import readcache
from oakbox.wizard.files import file_stamp, values_of


def _wait(path: Path) -> readcache.Status:
    for _ in range(200):
        s = readcache.status(path)
        if s.state not in ("reading", "waiting"):
            return s
        time.sleep(0.05)
    return readcache.status(path)


def test_copy_reads_as_the_csv(tmp_path: Path) -> None:
    src = tmp_path / "in" / "parcels.csv"
    src.parent.mkdir()
    src.write_text("id,size,note\n001, 1200 ,\n002,,x y\n003,900,NA\n", encoding="utf-8")
    before = [values_of(file_stamp(src), None, c, raw) for c in ("id", "size", "note") for raw in (False, True)]
    assert readcache.status(src).state in ("reading", "ready")  # the first read started it
    assert _wait(src).state == "ready"
    target = readcache.cache_path(src)
    assert target is not None and target.is_file() and target.parent == tmp_path / "out" / "oakbox" / "cache"
    values_of.cache_clear()
    after = [values_of(file_stamp(src), None, c, raw) for c in ("id", "size", "note") for raw in (False, True)]
    assert after == before
    assert values_of(file_stamp(src), None, "id", True) == ("001", "002", "003")  # text, not numbers
    assert values_of(file_stamp(src), None, "note") == ("", "x y", "NA")  # NA is a value, not a blank

    time.sleep(0.01)
    src.write_text("id,size,note\n004,1,a\n", encoding="utf-8")  # changed: a new copy, the old one gone
    readcache.start(src)
    assert _wait(src).state == "ready"
    copies = list(target.parent.glob("parcels-*.parquet"))
    assert copies == [readcache.cache_path(src)]


def test_not_a_csv_has_no_copy(tmp_path: Path) -> None:
    p = tmp_path / "x.parquet"
    p.write_bytes(b"")
    assert readcache.cache_path(p) is None
    assert readcache.status(p).state == "none"


def test_header_only_csv(tmp_path: Path) -> None:
    src = tmp_path / "in" / "empty.csv"
    src.parent.mkdir()
    src.write_text("a,b\n", encoding="utf-8")
    assert readcache.ensure(src) is not None
    values_of.cache_clear()
    assert values_of(file_stamp(src), None, "a") == ()

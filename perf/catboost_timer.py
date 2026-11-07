"""Whether Windows' timer tick is what makes CatBoost's category rounds slow: catboost_cats.py found any category
handling (CTRs) costs a flat ~20 ms a round on Windows, whatever the categories, about one 15.6 ms tick. Times the
same model, 300 rounds, at Windows' default tick and then at 1 ms (timeBeginPeriod(1), this process only).

    uv run python perf/catboost_timer.py
"""

from __future__ import annotations

import sys
import time

from catboost_cats import BASE, ROUNDS, data  # type: ignore[import-not-found]


def sleep_ms() -> float:
    """What time.sleep(0.001) really takes: the timer tick."""
    t0 = time.perf_counter()
    for _ in range(20):
        time.sleep(0.001)
    return (time.perf_counter() - t0) / 20 * 1000


def one(label: str) -> None:
    from catboost import CatBoostRegressor, Pool

    X, y, cf = data(60)
    m = CatBoostRegressor(**{**BASE, "iterations": ROUNDS})
    t0 = time.perf_counter()
    m.fit(Pool(X.iloc[:400], y.iloc[:400], cat_features=cf), eval_set=Pool(X.iloc[400:], y.iloc[400:], cat_features=cf))
    s = time.perf_counter() - t0
    print(
        f"{label:<28} sleep(1 ms) takes {sleep_ms():5.1f} ms; CatBoost {1000 * s / ROUNDS:6.1f} ms a round", flush=True
    )


def main() -> None:
    one("Windows' default tick")
    if sys.platform != "win32":
        print("(not Windows: nothing to change)")
        return
    import ctypes

    winmm = ctypes.WinDLL("winmm")
    winmm.timeBeginPeriod(1)
    try:
        one("1 ms tick")
    finally:
        winmm.timeEndPeriod(1)


if __name__ == "__main__":
    main()

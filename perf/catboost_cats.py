"""Which way of handling category variables keeps CatBoost's rounds fast on this computer: catboost_bisect.py found
the categories cost ~20 ms a round on Windows (1.4 ms without them). The same model, 300 rounds, with the categories
handled one way at a time; 12 values each, then 60 (a neighbourhood field). Prints milliseconds a round and the
validation MAPE (lower is better), so speed and accuracy can be weighed together.

    uv run python perf/catboost_cats.py
"""

from __future__ import annotations

import os
import sys
import time

ROUNDS = 300
BASE = {
    "loss_function": "RMSE",
    "eval_metric": "MAPE",
    "bootstrap_type": "Bayesian",
    "bagging_temperature": 2.12,
    "boosting_type": "Plain",
    "grow_policy": "SymmetricTree",
    "max_ctr_complexity": 1,
    "learning_rate": 0.077,
    "depth": 7,
    "border_count": 32,
    "random_strength": 9.7,
    "reg_lambda": 1.45,
    "random_seed": 42,
    "verbose": False,
    "allow_writing_files": False,
    "thread_count": 4,
}


def data(levels: int, n_cats: int = 4):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    n = 603
    X = pd.DataFrame(rng.normal(size=(n, 43)), columns=[f"x{i}" for i in range(43)])
    effect = rng.normal(scale=20_000, size=levels)
    y = 300_000 + 40_000 * X["x0"] + 15_000 * X["x1"] + rng.normal(scale=8_000, size=n)
    for j in range(n_cats):
        codes = rng.integers(0, levels, size=n)
        X[f"c{j}"] = [f"v{i}" for i in codes]
        if j == 0:
            y = y + effect[codes]  # one category matters, as a neighbourhood would
    return X, y, [f"c{j}" for j in range(n_cats)]


def run(label: str, change: dict, levels: int, *, n_cats: int = 4, as_codes: bool = False) -> None:
    import numpy as np
    from catboost import CatBoostRegressor, Pool

    X, y, cf = data(levels, n_cats)
    if as_codes:  # the categories as plain numbers: no category handling at all
        for c in cf:
            X[c] = X[c].str[1:].astype(int)
        cf = []
    cut = 400
    params = {**BASE, **change, "iterations": ROUNDS}
    m = CatBoostRegressor(**params)
    t0 = time.perf_counter()
    m.fit(Pool(X.iloc[:cut], y.iloc[:cut], cat_features=cf), eval_set=Pool(X.iloc[cut:], y.iloc[cut:], cat_features=cf))
    s = time.perf_counter() - t0
    p = m.predict(X.iloc[cut:])
    mape = float(np.mean(np.abs(p - y.iloc[cut:]) / y.iloc[cut:]))
    print(f"{label:<46} {1000 * s / ROUNDS:7.1f} ms a round  MAPE {mape:.4f}", flush=True)


def main() -> None:
    import catboost

    print(f"Python {sys.version.split()[0]} on {sys.platform}, {os.cpu_count()} logical CPUs", end=", ")
    print(f"CatBoost {catboost.__version__}")
    for levels in (12, 60):
        print(f"-- 4 categories of {levels} values each")
        run("as tuning runs it", {}, levels)
        run("one category only", {}, levels, n_cats=1)
        run("one-hot up to 255 values (no CTR)", {"one_hot_max_size": 255}, levels)
        run("one-hot up to 16 values", {"one_hot_max_size": 16}, levels)
        run("CTR: Borders only", {"simple_ctr": ["Borders"], "combinations_ctr": ["Borders"]}, levels)
        run("CTR: Counter only", {"simple_ctr": ["Counter"], "combinations_ctr": ["Counter"]}, levels)
        run("CTR: one prior", {"simple_ctr": ["Borders:Prior=0.5"], "combinations_ctr": ["Borders:Prior=0.5"]}, levels)
        run("CTR: counter_calc_method SkipTest", {"counter_calc_method": "SkipTest"}, levels)
        run("categories as numbers (no CatBoost handling)", {}, levels, as_codes=True)


if __name__ == "__main__":
    main()

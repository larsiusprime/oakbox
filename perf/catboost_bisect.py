"""Which CatBoost setting makes each boosting round slow on this computer: one tuning trial's model (catboost_bench.py),
300 rounds on one split, with one thing changed at a time. Prints the milliseconds a round for each.

    uv run python perf/catboost_bisect.py
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


def data(cats: bool):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    n = 603
    X = pd.DataFrame(rng.normal(size=(n, 43)), columns=[f"x{i}" for i in range(43)])
    if cats:
        for j in range(4):
            X[f"c{j}"] = rng.choice([f"v{i}" for i in range(12)], size=n)
    y = 300_000 + 40_000 * X["x0"] + 15_000 * X["x1"] + rng.normal(scale=8_000, size=n)
    cut = 400
    return X.iloc[:cut], y.iloc[:cut], X.iloc[cut:], y.iloc[cut:], [f"c{j}" for j in range(4)] if cats else []


def run(label: str, change: dict, *, cats: bool = True, evals: bool = True) -> None:
    from catboost import CatBoostRegressor, Pool

    Xa, ya, Xb, yb, cf = data(cats)
    params = {**BASE, **change, "iterations": ROUNDS}
    params = {k: v for k, v in params.items() if v is not None}
    if params.get("bootstrap_type") != "Bayesian":
        params.pop("bagging_temperature", None)
    m = CatBoostRegressor(**params)
    t0 = time.perf_counter()
    m.fit(Pool(Xa, ya, cat_features=cf), eval_set=Pool(Xb, yb, cat_features=cf) if evals else None)
    s = time.perf_counter() - t0
    print(f"{label:<44} {1000 * s / ROUNDS:7.1f} ms a round  ({s:5.1f} s)", flush=True)


def main() -> None:
    import catboost

    print(f"Python {sys.version.split()[0]} on {sys.platform}, {os.cpu_count()} logical CPUs", end=", ")
    print(f"CatBoost {catboost.__version__}")
    run("as tuning runs it", {})
    run("1 thread", {"thread_count": 1})
    run("no eval set (no metric each round)", {}, evals=False)
    run("metric only every 50 rounds", {"metric_period": 50})
    run("eval metric RMSE (not MAPE)", {"eval_metric": "RMSE"})
    run("no categories", {}, cats=False)
    run("bootstrap Bernoulli", {"bootstrap_type": "Bernoulli", "subsample": 0.8})
    run("bootstrap No", {"bootstrap_type": "No"})
    run("random_strength 1", {"random_strength": 1})
    run("depth 4", {"depth": 4})
    run("logging Silent", {"verbose": None, "logging_level": "Silent"})
    run("used_ram_limit 8gb", {"used_ram_limit": "8gb"})


if __name__ == "__main__":
    main()

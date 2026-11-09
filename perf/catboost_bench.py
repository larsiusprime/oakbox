"""How fast CatBoost runs one of OpenAVMKit's tuning trials on this computer, alone and as OAK box's folds run it.

One trial from an assessor's trial log (603 sales, 47 variables, 4 categories; depth 7, 907 trees, a 3-fold CV), on
synthetic data of that shape:
  1. alone, on 1 thread and on 4;
  2. as 5 processes at once (OAK box's 5 folds at once), each on 4 threads, as the run does it (OpenMP pinned to 1).
It took 4.2 s and 2.9 s alone on a 4-core Linux machine; an assessor's run took 28-36 s a trial on 4 threads.

    uv run python perf/catboost_bench.py
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

TRIAL = {
    "iterations": 907,
    "learning_rate": 0.07725378389307355,
    "depth": 7,
    "border_count": 32,
    "random_strength": 9.699098521619943,
    "reg_lambda": 1.452824663751602,
    "bagging_temperature": 2.1233911067827616,
}
FIXED = {  # OpenAVMKit's _CATBOOST_FIXED_PARAMS
    "loss_function": "RMSE",
    "eval_metric": "MAPE",
    "bootstrap_type": "Bayesian",
    "boosting_type": "Plain",
    "grow_policy": "SymmetricTree",
    "max_ctr_complexity": 1,
}


def one_trial(threads: int) -> float:
    import tempfile

    import numpy as np
    import pandas as pd
    from catboost import Pool, cv

    rng = np.random.default_rng(0)
    n = 603
    X = pd.DataFrame(rng.normal(size=(n, 43)), columns=[f"x{i}" for i in range(43)])
    for j in range(4):
        X[f"c{j}"] = rng.choice([f"v{i}" for i in range(12)], size=n)
    y = 300_000 + 40_000 * X["x0"] + 15_000 * X["x1"] + rng.normal(scale=8_000, size=n)
    pool = Pool(X, y, cat_features=[f"c{j}" for j in range(4)])
    params = {
        **FIXED,
        **TRIAL,
        "random_seed": 42,
        "verbose": False,
        "allow_writing_files": False,
        "thread_count": threads,
        "train_dir": tempfile.mkdtemp(prefix="catboost_bench_"),
    }
    t0 = time.perf_counter()
    cv(pool, params, fold_count=3, partition_random_seed=42, early_stopping_rounds=100, verbose=False)
    return time.perf_counter() - t0


def _pinned_trial(threads: int) -> float:
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[k] = "1"  # as OpenAVMKit pins its fold workers
    return one_trial(threads)


def main() -> None:
    print(f"Python {sys.version.split()[0]} on {sys.platform}, {os.cpu_count()} logical CPUs", flush=True)
    import catboost

    print(f"CatBoost {catboost.__version__}", flush=True)
    for threads in (1, 4):
        print(f"alone, {threads} thread{'s' if threads > 1 else ''}: {one_trial(threads):5.1f} s", flush=True)
    with ProcessPoolExecutor(max_workers=5) as ex:
        t0 = time.perf_counter()
        each = list(ex.map(_pinned_trial, [4] * 5))
    print(
        f"5 at once, 4 threads each: {time.perf_counter() - t0:5.1f} s in all; each "
        + ", ".join(f"{x:.1f}" for x in each)
        + " s",
        flush=True,
    )


if __name__ == "__main__":
    main()

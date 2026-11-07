"""The last settings that might make CatBoost's category rounds fast on Windows (catboost_cats.py: any CTR costs a
flat ~20 ms a round there; catboost_timer.py: not Windows' timer tick). The same model, 4 categories of 60 values,
300 rounds, one setting changed at a time. Run it with this project's CatBoost and with the newest:

    uv run python perf/catboost_ctr.py
    uv run --with catboost==1.2.10 python perf/catboost_ctr.py
"""

from __future__ import annotations

import os
import sys

from catboost_cats import run  # type: ignore[import-not-found]


def main() -> None:
    import catboost

    print(f"Python {sys.version.split()[0]} on {sys.platform}, {os.cpu_count()} logical CPUs", end=", ")
    print(f"CatBoost {catboost.__version__}")
    run("as tuning runs it", {}, 60)
    run("model_size_reg 0", {"model_size_reg": 0}, 60)
    run("fold_permutation_block 64", {"fold_permutation_block": 64}, 60)
    run("fold_len_multiplier 4", {"fold_len_multiplier": 4}, 60)
    run("ctr_leaf_count_limit 64", {"ctr_leaf_count_limit": 64}, 60)
    run("store_all_simple_ctr", {"store_all_simple_ctr": True}, 60)
    run("boosting_type Ordered", {"boosting_type": "Ordered"}, 60)
    run(
        "all of the first four",
        {
            "model_size_reg": 0,
            "fold_permutation_block": 64,
            "fold_len_multiplier": 4,
            "ctr_leaf_count_limit": 64,
        },
        60,
    )
    run("one-hot up to 255 values (no CTR)", {"one_hot_max_size": 255}, 60)


if __name__ == "__main__":
    main()

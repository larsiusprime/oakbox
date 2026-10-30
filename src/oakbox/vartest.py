"""Step 5: test the variables before the models (SPEC F9). OpenAVMKit's own variable tests, per model group, on the
variables ticked: are they represented, how they correlate with price and with each other, elastic net, R², p- and
t-values, VIF, and whether their signs agree. The receipt keeps every test's result for every variable, so the step
can show the tests one at a time and the user can untick what's a waste of time.

It runs in a process of its own (`python -m oakbox.vartest <project id>`): the prepared hand-off, the canonical
splits, then `get_variable_recommendations(..., return_tests=True)` per model group, main models only.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from oakbox import bring_in, model, prepare
from oakbox.datafiles import BaseModel

MODULE = "vartest"
TESTS = ["represented", "corr", "enr", "r2", "p_value", "t_value", "vif", "signs"]


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "vartest"


class TestRow(BaseModel):
    column: str = Field(description="The column tested: the variable, or one of a category's values.")
    variable: str = Field(description="The variable it belongs to.")
    level: str | None = Field(default=None, description="A category's value, for its column.")
    value: float | None
    passed: bool | None = Field(description="Passed the test (None: not tested).")
    more: dict[str, float | None] = Field(default_factory=dict, description="The test's other figures.")


class VarGroup(BaseModel):
    id: str
    name: str
    color: str
    sales: int
    skipped: str | None = None
    empty: list[str] = Field(
        default_factory=list, description="Ticked but not tested here: no sale in the group has a value for them."
    )
    recommended: list[str] = Field(default_factory=list, description="The variables OpenAVMKit would use.")
    scores: dict[str, float] = Field(default_factory=dict, description="Each variable's weighted score.")
    tests: dict[str, list[TestRow]] = Field(default_factory=dict)


class VarTestReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    variables: list[str] = Field(description="The variables tested.")
    thresholds: dict[str, float]
    groups: list[VarGroup]
    notes: list[str] = Field(default_factory=list)


def _f(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else x


def _sources(variables: list[str], one_hot: dict) -> dict[str, tuple[str, str | None]]:
    """Each column tested -> (the variable, the category value it stands for)."""
    out: dict[str, tuple[str, str | None]] = {v: (v, None) for v in variables}
    for var, columns in one_hot.items():
        for c in columns or []:
            level = c[len(var) + 1 :] if c.startswith(f"{var}_") else c
            out[c] = (var, level)
    return out


def _rows(frame, column: str, src: dict, passed, more: tuple[str, ...] = ()) -> list[TestRow]:
    if frame is None or len(frame) == 0 or "variable" not in frame:
        return []
    out = []
    for _, r in frame.iterrows():
        c = str(r["variable"])
        if c == "const" or c not in src:
            continue
        var, level = src[c]
        value = _f(r.get(column))
        out.append(
            TestRow(
                column=c,
                variable=var,
                level=level,
                value=value,
                passed=passed(c, value),
                more={m: _f(r.get(m)) for m in more},
            )
        )
    return out


def _group_tests(tests: dict, df_results, variables: list[str]) -> dict[str, list[TestRow]]:
    th = tests.get("thresholds") or {}
    src = _sources(variables, tests.get("one_hot") or {})

    def final(name: str) -> set[str]:
        t = tests.get(name)
        f = t.get("final") if isinstance(t, dict) else None
        return set(f["variable"].astype(str)) if f is not None and "variable" in f else set()

    out: dict[str, list[TestRow]] = {}
    rep = tests.get("representation")
    bad = set(tests.get("representation_bad") or [])
    if rep is not None:
        rep = rep.rename(columns={"name": "variable"})
        out["represented"] = _rows(rep, "sales_pct_gt0", src, lambda c, _v: c not in bad, ("univ_pct_gt0",))
    # Correlation drops low scores and overlaps in turn: what's left at the end passed.
    corr = tests.get("corr") or {}
    kept = final("corr") - set(corr.get("bad_vars") or [])
    out["corr"] = _rows(
        corr.get("initial"), "corr_score", src, lambda c, _v: c in kept, ("corr_strength", "corr_clarity")
    )
    for name, column in (("enr", "enr_coef"), ("p_value", "p_value"), ("t_value", "t_value"), ("vif", "vif")):
        t = tests.get(name) or {}
        keep = final(name)
        out[name] = _rows(t.get("initial"), column, src, lambda c, _v, keep=keep: c in keep)
    r2 = tests.get("r2")
    floor = th.get("adj_r2", 0.0)
    out["r2"] = _rows(r2, "adj_r2", src, lambda _c, v: None if v is None else v > floor, ("r2", "coef_sign"))
    if df_results is not None and "signs_match" in df_results:
        out["signs"] = _rows(
            df_results,
            "signs_match",
            src,
            lambda _c, v: None if v is None else v == 1,
            ("coef_sign", "enr_coef_sign", "t_value_sign"),
        )
    return out


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    if not (pdir / "out" / "2-clean-sup.pickle").is_file():
        raise RuntimeError("Prepare the fields first: the tests start from what it writes.")
    variables = [v.field for v in model.variables(project, pdir) if v.chosen]
    if not variables:
        raise RuntimeError("Tick at least one variable.")
    tmp = out_dir(pdir).with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import get_hydrated_sales_from_sup
    from openavmkit.model_runner import get_variable_recommendations

    t0 = time.time()
    beating = threading.Event()
    threading.Thread(target=bring_in._heartbeat, args=(beating,), daemon=True).start()
    groups: list[VarGroup] = []
    thresholds: dict[str, float] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        bring_in._emit(step="load", fraction=0.0, message="Reading the prepared fields")
        settings = pl.load_settings()
        sup = pl.load_cleaned_data_for_modeling(settings)
        pl.write_canonical_splits(sup, settings, verbose=False)
        sales = get_hydrated_sales_from_sup(sup)
        universe = sup.universe
        for k, g in enumerate(project.groups):
            bring_in._emit(step="test", fraction=0.05 + 0.9 * k / max(len(project.groups), 1), message=g.name)
            df_s = cast(pd.DataFrame, sales[sales["model_group"].astype(str).eq(g.id) & sales["valid_sale"].eq(True)])
            df_u = cast(pd.DataFrame, universe[universe["model_group"].astype(str).eq(g.id)])
            vg = VarGroup(id=g.id, name=g.name, color=g.color, sales=len(df_s))
            if len(df_s) < 15:
                vg.skipped = f"{len(df_s):,} {'sale' if len(df_s) == 1 else 'sales'}: too few to test"
                groups.append(vg)
                continue
            # The tests fill a variable's blanks with its median; one with no value among the group's sales has none
            # (days to renovation where none of them had a permit, say), and would stop them: it's left out, named.
            vg.empty = [v for v in variables if v in df_s.columns and bool(df_s[v].isna().all())]
            here = [v for v in variables if v not in vg.empty]
            if not here:
                vg.skipped = "none of the variables has a value among its sales"
                groups.append(vg)
                continue
            try:
                rec = get_variable_recommendations(
                    df_s,
                    df_u,
                    False,
                    settings,
                    g.id,
                    variables_to_use=here,
                    do_cross=True,
                    return_tests=True,
                )
            except Exception as e:  # noqa: BLE001 - one group's failure is said on its row
                first = str(e).split(". ")[0].strip()
                vg.skipped = f"couldn't be tested ({type(e).__name__}: {first})"[:200]
                groups.append(vg)
                continue
            tests = rec["tests"]
            thresholds = {k: float(v) for k, v in (tests.get("thresholds") or {}).items() if _f(v) is not None}
            src = _sources(variables, tests.get("one_hot") or {})
            vg.recommended = list(dict.fromkeys(src.get(c, (c, None))[0] for c in rec["variables"]))
            df = rec["df_results"]
            for _, r in df.iterrows():
                var = src.get(str(r["variable"]), (str(r["variable"]), None))[0]
                score = _f(r.get("weighted_score"))
                if score is not None:
                    vg.scores[var] = max(vg.scores.get(var, score), score)
            vg.tests = _group_tests(tests, df, here)
            groups.append(vg)
    beating.set()
    mine = [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]
    receipt = VarTestReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        variables=variables,
        thresholds=thresholds,
        groups=groups,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    r, _ = prepare._ran(pdir)
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"prepare": r.ran_at if r else None}), encoding="utf-8")
    final = out_dir(pdir)
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    tested = sum(1 for g in groups if g.tests)
    bring_in._emit(step="done", fraction=1.0, message=f"{tested} of {len(groups)} model groups tested")


# ---------- The step's state ----------


class VarTestView(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: bring_in.Job | None
    receipt: VarTestReceipt | None
    stale: bool = Field(description="The fields were prepared again, or a variable was ticked that wasn't tested.")
    blocked: list[str]


def _ran(project_dir: Path) -> tuple[VarTestReceipt | None, dict | None]:
    base = out_dir(project_dir)
    if not (base / "receipt.json").is_file():
        return None, None
    ran = (
        json.loads((base / "settings.json").read_text(encoding="utf-8")) if (base / "settings.json").is_file() else None
    )
    try:
        return VarTestReceipt.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran
    except ValueError:
        return None, None  # an older receipt: test again


def view(project, project_dir: Path) -> VarTestView:
    r, ran = _ran(project_dir)
    j = bring_in.job(project.id, MODULE)
    p, _ = prepare._ran(project_dir)
    chosen = {v.field for v in model.variables(project, project_dir) if v.chosen}
    # Unticking a tested variable doesn't need a new test; ticking one that wasn't tested does.
    stale = bool(r and ((ran or {}).get("prepare") != (p.ran_at if p else None) or chosen - set(r.variables)))
    blocked = []
    if not prepare.view(project, project_dir).accepted:
        blocked.append("Press Looks right on What changed first: the tests start from the prepared fields.")
    elif not chosen:
        blocked.append("Tick at least one variable.")
    return VarTestView(
        status=j.status if j else ("done" if r else "never"),
        job=j,
        receipt=r,
        stale=stale,
        blocked=blocked,
    )


def start(project, project_dir: Path) -> None:
    v = view(project, project_dir)
    if v.blocked:
        raise ValueError(v.blocked[0])
    bring_in.start(project.id, project_dir, MODULE)


if __name__ == "__main__":
    from oakbox.net import use_system_certificates

    use_system_certificates()
    try:
        run(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - the app shows the last line of the log
        import traceback

        traceback.print_exc()
        print(f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

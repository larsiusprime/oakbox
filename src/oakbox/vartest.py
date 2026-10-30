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
# The correlation test's first pass: a correlation with price weaker than this (in absolute value) is none at all,
# and the variable is dropped before the combined scores are worked out.
CORR_FLOOR = 0.05
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
    reason: Literal["no_correlation", "low_score", "overlaps"] | None = Field(
        default=None, description="Why it failed the correlation test."
    )


class Overlap(BaseModel):
    column: str
    variable: str
    level: str | None = None
    r: float = Field(description="Their correlation, -1 to 1.")


class CorrDetail(BaseModel):
    """How a column's correlation score came about, for the step to show on a click."""

    to_price: float | None = Field(description="Its correlation with price, -1 to 1.")
    clarity: float | None = Field(description="1 less its average overlap with the others, 0 to 1.")
    score: float | None = Field(description="Strength (|correlation with price|) times clarity squared.")
    overlaps: list[Overlap] = Field(description="The variables it overlaps most, strongest first.")
    dropped_by: Overlap | None = Field(
        default=None, description="The stronger variable it overlaps more than it relates to price, if dropped so."
    )


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
    corr: dict[str, CorrDetail] = Field(default_factory=dict, description="Each column's correlation, in detail.")


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
    # Correlation: the first pass drops what has no correlation with price; then low scores and overlaps in turn.
    # What's left at the end passed.
    corr = tests.get("corr") or {}
    kept = final("corr") - set(corr.get("bad_vars") or [])
    rows = _rows(corr.get("initial"), "corr_score", src, lambda c, _v: c in kept, ("corr_strength", "corr_clarity"))
    floor_score = th.get("correlation", 0.1)
    for x in rows:
        if not x.passed:
            x.reason = "low_score" if x.value is not None and x.value < floor_score else "overlaps"
    matrix = corr.get("matrix")
    for c in corr.get("weak") or []:
        if c in src:
            var, level = src[c]
            r = _f(matrix.iloc[:, 0].get(c)) if matrix is not None else None
            rows.append(
                TestRow(
                    column=c,
                    variable=var,
                    level=level,
                    value=None,
                    passed=False,
                    more={"corr_strength": None if r is None else abs(r)},
                    reason="no_correlation",
                )
            )
    out["corr"] = rows
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


def _corr_detail(corr: dict, variables: list[str], one_hot: dict, threshold: float) -> dict[str, CorrDetail]:
    """Each column's correlation with price, clarity and score, its strongest overlaps, and for one dropped for
    overlapping, the stronger variable it overlaps more than it relates to price."""
    m = corr.get("matrix")
    if m is None or len(m.columns) < 2:
        return {}
    src = _sources(variables, one_hot)
    target = m.columns[0]
    first = corr.get("initial")
    scores = {} if first is None else {str(r["variable"]): r for _, r in first.iterrows()}
    last = corr.get("final")
    kept = set(last["variable"].astype(str)) if last is not None and "variable" in last else set()

    def ov(c: str, r) -> Overlap:
        var, level = src.get(c, (c, None))
        return Overlap(column=c, variable=var, level=level, r=round(float(r), 3))

    out: dict[str, CorrDetail] = {}
    others = [c for c in m.columns[1:] if c in src]
    for c in others:
        to_price = _f(m.loc[c, target])
        row = scores.get(c)
        near = sorted(
            ((o, m.loc[c, o]) for o in others if o != c and _f(m.loc[c, o]) is not None), key=lambda x: -abs(x[1])
        )[:5]
        dropped_by = None
        if row is not None and c not in kept and (_f(row.get("corr_score")) or 0) >= threshold:
            # As the test drops it: a variable more related to price that it's more related to than to price.
            mine = abs(to_price or 0)
            stronger = [(o, r) for o, r in near if abs(_f(m.loc[o, target]) or 0) > mine and abs(r) > mine]
            if stronger:
                dropped_by = ov(*stronger[0])
        out[c] = CorrDetail(
            to_price=to_price,
            clarity=_f(row.get("corr_clarity")) if row is not None else None,
            score=_f(row.get("corr_score")) if row is not None else None,
            overlaps=[ov(o, r) for o, r in near],
            dropped_by=dropped_by,
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
        thresholds_set = (
            settings.setdefault("modeling", {})
            .setdefault("instructions", {})
            .setdefault("feature_selection", {})
            .setdefault("thresholds", {})
        )
        thresholds_set.setdefault("correlation_strength", CORR_FLOOR)
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
            vg.corr = _corr_detail(
                tests.get("corr") or {},
                here,
                tests.get("one_hot") or {},
                float((tests.get("thresholds") or {}).get("correlation", 0.1)),
            )
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

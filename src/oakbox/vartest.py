"""Step 5: test the variables before the models (SPEC F9). OpenAVMKit's own variable tests, per model group, on the
variables ticked: are they represented, and those the user picked of how they correlate with price and with each
other, their p-values together, and VIF. The receipt keeps every test's result for every variable, so the step can
show the tests one at a time and the user can untick what's a waste of time.

It runs in a process of its own (`python -m oakbox.vartest <project id>`): the prepared hand-off, the canonical
splits, then `get_variable_recommendations(..., return_tests=True)` per model group, main models only.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from oakbox import cells, model, prepare, steps
from oakbox.datafiles import BaseModel

MODULE = "vartest"


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "vartest"


class TestRow(BaseModel):
    column: str = Field(description="The column tested: the variable, or one of a category's values.")
    variable: str = Field(description="The variable it belongs to.")
    level: str | None = Field(default=None, description="A category's value, for its column.")
    value: float | None
    passed: bool | None = Field(description="Passed the test (None: not tested).")
    more: dict[str, float | None] = Field(default_factory=dict, description="The test's other figures.")
    reason: Literal["no_correlation"] | None = Field(default=None, description="Why it failed the correlation test.")


class Overlap(BaseModel):
    column: str
    variable: str
    level: str | None = None
    r: float = Field(description="Their correlation, -1 to 1.")


class CorrDetail(BaseModel):
    """A column's correlation with price (what the test judges), and the variables it moves with most (what VIF
    judges), for the step to show on a click."""

    to_price: float | None = Field(description="Its correlation with price, -1 to 1.")
    overlaps: list[Overlap] = Field(description="The variables it moves with most, strongest first.")


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
    tests: list[str] = Field(default_factory=list, description="The tests run, besides Represented.")
    thresholds: dict[str, float]
    groups: list[VarGroup]
    notes: list[str] = Field(default_factory=list)


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
        value = cells.number(r.get(column))
        out.append(
            TestRow(
                column=c,
                variable=var,
                level=level,
                value=value,
                passed=passed(c, value),
                more={m: cells.number(r.get(m)) for m in more},
            )
        )
    return out


def _group_tests(tests: dict, variables: list[str]) -> dict[str, list[TestRow]]:
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
    # Correlation: judged on the correlation with price alone (overlap is VIF's to judge); what's left passed.
    corr = tests.get("corr") or {}
    kept = final("corr") - set(corr.get("bad_vars") or [])
    rows = _rows(corr.get("initial"), "corr_strength", src, lambda c, _v: c in kept)
    for x in rows:
        if not x.passed:
            x.reason = "no_correlation"
    out["corr"] = rows
    if not tests.get("corr"):
        del out["corr"]
    for name in ("vif",):
        t = tests.get(name)
        if t:
            keep = final(name)
            out[name] = _rows(t.get("initial"), name, src, lambda c, _v, keep=keep: c in keep)
    return out


def _corr_detail(corr: dict, variables: list[str], one_hot: dict) -> dict[str, CorrDetail]:
    """Each column's correlation with price, and the variables it moves with most."""
    m = corr.get("matrix")
    if m is None or len(m.columns) < 2:
        return {}
    src = _sources(variables, one_hot)
    target = m.columns[0]

    def ov(c: str, r) -> Overlap:
        var, level = src.get(c, (c, None))
        return Overlap(column=c, variable=var, level=level, r=round(float(r), 3))

    others = [c for c in m.columns[1:] if c in src]
    out: dict[str, CorrDetail] = {}
    for c in others:
        near = sorted(
            ((o, m.loc[c, o]) for o in others if o != c and cells.number(m.loc[c, o]) is not None),
            key=lambda x: -abs(x[1]),
        )[:5]
        out[c] = CorrDetail(to_price=cells.number(m.loc[c, target]), overlaps=[ov(o, r) for o, r in near])
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
    variables = [v.field for v in model.variables(project, pdir)]  # every variable: lists are built from the results
    to_run = model.tests(project)
    if not variables:
        raise RuntimeError("Tick at least one variable.")
    tmp = steps.workdir(out_dir(pdir))
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import get_hydrated_sales_from_sup
    from openavmkit.model_runner import get_variable_recommendations

    t0 = time.time()
    groups: list[VarGroup] = []
    thresholds: dict[str, float] = {}
    with warnings.catch_warnings(record=True) as caught, steps.heartbeat():
        warnings.simplefilter("always")
        steps.emit(step="load", fraction=0.0, message="Reading the prepared fields")
        settings = pl.load_settings()
        # The correlation test judges the relation to price alone: overlap is the VIF test's (OpenAVMKit's opt-in).
        settings.setdefault("modeling", {}).setdefault("instructions", {}).setdefault("feature_selection", {})[
            "correlation_overlap"
        ] = False
        sup = pl.load_cleaned_data_for_modeling(settings)
        pl.write_canonical_splits(sup, settings, verbose=False)
        sales = get_hydrated_sales_from_sup(sup)
        universe = sup.universe
        from oakbox import assemble

        modeled = assemble.modeled(project, pdir)
        for k, g in enumerate(project.groups):
            steps.emit(step="test", fraction=0.05 + 0.9 * k / max(len(project.groups), 1), message=g.name)
            df_s = cast(pd.DataFrame, sales[sales["model_group"].astype(str).eq(g.id) & sales["valid_sale"].eq(True)])
            df_u = cast(pd.DataFrame, universe[universe["model_group"].astype(str).eq(g.id)])
            vg = VarGroup(id=g.id, name=g.name, color=g.color, sales=len(df_s))
            if g.id not in modeled:
                vg.skipped = "Not modeled: unticked on Model groups › Check them"
                groups.append(vg)
                continue
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
                    tests_to_run=to_run,
                    do_cross=True,
                    return_tests=True,
                )
            except Exception as e:  # noqa: BLE001 - one group's failure is said on its row
                first = str(e).split(". ")[0].strip()
                vg.skipped = f"couldn't be tested ({type(e).__name__}: {first})"[:200]
                groups.append(vg)
                continue
            tests = rec["tests"]
            thresholds = {
                k: float(v) for k, v in (tests.get("thresholds") or {}).items() if cells.number(v) is not None
            }
            src = _sources(variables, tests.get("one_hot") or {})
            vg.recommended = list(dict.fromkeys(src.get(c, (c, None))[0] for c in rec["variables"]))
            df = rec["df_results"]
            for _, r in df.iterrows():
                var = src.get(str(r["variable"]), (str(r["variable"]), None))[0]
                score = cells.number(r.get("weighted_score"))
                if score is not None:
                    vg.scores[var] = max(vg.scores.get(var, score), score)
            vg.tests = _group_tests(tests, here)
            vg.corr = _corr_detail(tests.get("corr") or {}, here, tests.get("one_hot") or {})
            groups.append(vg)
    mine = steps.engine_notes(caught)
    receipt = VarTestReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        variables=variables,
        tests=to_run,
        thresholds=thresholds,
        groups=groups,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(
        json.dumps({"prepare": prepare.STEP.ran_at(pdir), "modeled": sorted(modeled)}), encoding="utf-8"
    )
    steps.publish(tmp, out_dir(pdir))
    tested = sum(1 for g in groups if g.tests)
    steps.emit(step="done", fraction=1.0, message=f"{tested} of {len(groups)} model groups tested")


# ---------- The step's state ----------


class VarTestView(steps.RunView):
    receipt: VarTestReceipt | None


def _key(project, project_dir: Path) -> dict:
    from oakbox import assemble

    return {"prepare": prepare.STEP.ran_at(project_dir), "modeled": sorted(assemble.modeled(project, project_dir))}


# The run keeps the Prepare run it tested, and the groups it tested (settings.json).
STEP = steps.Step(
    MODULE,
    "Test the variables",
    VarTestReceipt,
    key=_key,
    after=prepare.STEP,
    ran_hash=lambda ran: steps.key_hash({"prepare": ran.get("prepare"), "modeled": ran.get("modeled", [])}),
    again="Test the variables again first: something changed since.",
)


def view(project, project_dir: Path) -> VarTestView:
    s = STEP.state(project, project_dir)
    r = s.receipt
    every = {v.field for v in model.variables(project, project_dir)}
    # The fields were prepared again (a variable not tested is new), or the tests changed.
    stale = bool(r and (s.stale or every - set(r.variables) or r.tests != model.tests(project)))
    return VarTestView(
        status=s.status, job=s.job, receipt=r, stale=stale, blocked=_blocked(project, project_dir, every)
    )


def _blocked(project, project_dir: Path, every: set[str]) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    if not every:
        return ["Prepare the fields first: there are no variables to test."]
    return []


def start(project, project_dir: Path) -> None:
    every = {v.field for v in model.variables(project, project_dir)}
    STEP.start(project.id, project_dir, _blocked(project, project_dir, every))


if __name__ == "__main__":
    steps.main(run)

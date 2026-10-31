"""Variable lists (SPEC F9): each model takes its variables from a named list. A list has a type (regression or
machine learning) and the model groups it's for; one list can serve several groups. Beside each variable, the
variable tests' figures and what's recommended for the list's type, per model group.

Written to OpenAVMKit's settings as `variable_lists` (each a list of fields), a model pointing at its list by
`"ind_vars": "$$variable_lists.<id>"` (OpenAVMKit resolves `$$` paths when it loads the settings).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import model, steps, vartest
from oakbox.datafiles import BaseModel
from oakbox.model import ListKind as Kind
from oakbox.model import VarList

# Why a variable isn't recommended for a list's type, in one group.
Reason = Literal["blanks", "not_represented", "weak", "overlaps", "many_values"]

# A category becomes a column per value: a regression with more than this many is fragile; CatBoost slows with each.
MAX_REGRESSION_VALUES = 8
MAX_ML_VALUES = 20
# A regression wants about this many sales for each variable it estimates.
SALES_PER_VARIABLE = 10
ID = re.compile(r"[a-z][a-z0-9_]*")


# ---------- What's recommended ----------


def judge(kind: Kind, var: model.Variable, rows: dict[str, list[vartest.TestRow]] | None) -> Reason | None:
    """Why a variable isn't recommended for a list of this type in a model group (None: recommended). Without the
    group's test results, only what's known without them: blanks and a category's values."""
    if kind == "ml":
        if var.values and var.values > MAX_ML_VALUES:
            return "many_values"
        rep = (rows or {}).get("represented")
        if rep is not None and not any(r.passed for r in rep):
            return "not_represented"
        return None
    if var.trees_only:
        return "blanks"
    if var.values and var.values > MAX_REGRESSION_VALUES:
        return "many_values"
    if rows is None:
        return None
    rep = rows.get("represented")
    if rep is not None and not any(r.passed for r in rep):
        return "not_represented"
    corr = rows.get("corr")
    if corr is not None and not any(r.passed for r in corr):
        return "weak"
    vif = rows.get("vif")
    if vif and not any(r.passed for r in vif):
        return "overlaps"
    return None


def _by_variable(group: vartest.VarGroup, tests: list[str]) -> dict[str, dict[str, list[vartest.TestRow]]]:
    """A tested group's rows by variable and test; a test run but with no row for a variable counts as failed by it."""
    out: dict[str, dict[str, list[vartest.TestRow]]] = {}
    for test, rows in group.tests.items():
        for r in rows:
            out.setdefault(r.variable, {}).setdefault(test, []).append(r)
    for v in out.values():
        # Correlation leaves out what it never scored (a variable with no values among the sales): not related.
        if "corr" in tests and "corr" in group.tests:
            v.setdefault("corr", [])
    return out


@lru_cache(maxsize=4)
def _receipt(path: str, mtime: float) -> vartest.VarTestReceipt | None:
    return steps.read(Path(path), vartest.VarTestReceipt)[0]


def tested(project_dir: Path) -> vartest.VarTestReceipt | None:
    base = vartest.out_dir(project_dir)
    receipt = base / "receipt.json"
    return _receipt(str(base), receipt.stat().st_mtime) if receipt.is_file() else None


def recommendations(project, project_dir: Path) -> dict[str, dict[str, dict[str, Reason | None]]]:
    """Group -> type -> variable -> why it isn't recommended (None: it is)."""
    variables = model.variables(project, project_dir)
    r = tested(project_dir)
    by_group = {g.id: g for g in r.groups} if r else {}
    out: dict[str, dict[str, dict[str, Reason | None]]] = {}
    for g in project.groups:
        vg = by_group.get(g.id)
        rows = _by_variable(vg, r.tests) if vg and r and vg.tests else None
        # Tested, but not in its results (no sale in the group has a value): not represented there.
        out[g.id] = {
            kind: {
                v.field: judge(kind, v, None if rows is None else rows.get(v.field, {"represented": []}))
                for v in variables
            }
            for kind in ("regression", "ml")
        }
    return out


# ---------- The lists ----------


def _sales(project, project_dir: Path) -> dict[str, int]:
    r = tested(project_dir)
    return {g.id: g.sales for g in r.groups} if r else {}


def lists(project, project_dir: Path) -> list[VarList]:
    """The lists the user made (none to start: settled 2026-10-31, so it's plain that a list's ticks are shared by
    every group it's for). Variables no longer offered are left out."""
    chosen: list[VarList] = project.model.lists or []
    offered = {v.field for v in model.variables(project, project_dir)}
    return [x.model_copy(update={"variables": [v for v in x.variables if v in offered]}) for x in chosen]


def check(project, new: list[VarList]) -> list[VarList]:
    """The lists as they'd be saved: names and ids unique, types and groups known."""
    groups = {g.id for g in project.groups}
    ids: set[str] = set()
    names: set[str] = set()
    out = []
    for x in new:
        name = x.name.strip()
        if not name:
            raise ValueError("Every variable list needs a name.")
        if name.lower() in names:
            raise ValueError(f"Two variable lists are called {name}.")
        if not ID.fullmatch(x.id) or x.id in ids:
            raise ValueError(f"Not a list id OAK box can use: {x.id}.")
        unknown = [g for g in x.groups if g not in groups]
        if unknown:
            raise ValueError(f"No model group {', '.join(unknown)}.")
        names.add(name.lower())
        ids.add(x.id)
        out.append(x.model_copy(update={"name": name, "variables": list(dict.fromkeys(x.variables))}))
    return out


def new_id(taken: set[str], name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "list"
    if not base[0].isalpha():
        base = f"list_{base}"
    out, n = base, 2
    while out in taken:
        out, n = f"{base}_{n}", n + 1
    return out


def for_group(all_lists: list[VarList], group: str, kind: Kind) -> VarList | None:
    """The list a model of this type in this group takes unless told otherwise: the first of its type that's for the
    group; none if there isn't one (a list for other groups, or of the other type, only when the user picks it)."""
    return next((x for x in all_lists if x.kind == kind and group in x.groups), None)


# ---------- The step's view ----------


class ListWarning(BaseModel):
    code: Literal["few_sales", "many_values", "blanks"]
    group: str | None = None
    n: int = 0
    variables: list[str] = Field(default_factory=list)


class ListView(VarList):
    used_by: list[str] = Field(description="Models that take it: '<model> · <group>' or '<model> · <n> groups'.")
    warnings: list[ListWarning]


class GroupSales(BaseModel):
    id: str
    name: str
    color: str
    sales: int | None = Field(description="Sales the variables were tested on; None: not tested.")
    modeled: bool


class VarListsView(BaseModel):
    lists: list[ListView]
    variables: list[model.Variable]
    groups: list[GroupSales]
    tested: bool = Field(description="The variable tests have run: the figures and recommendations use them.")
    recommend: dict[str, dict[str, dict[str, Reason | None]]] = Field(
        description="Model group -> type -> variable -> why it isn't recommended (null: it is)."
    )
    missing: list[str] = Field(description="Big five fields not loaded, in words.")


def _warnings(x: VarList, variables: dict[str, model.Variable], sales: dict[str, int]) -> list[ListWarning]:
    out = []
    if x.kind == "regression":
        for g in x.groups:
            n = sales.get(g)
            if n is not None and x.variables and n < SALES_PER_VARIABLE * len(x.variables):
                out.append(ListWarning(code="few_sales", group=g, n=n))
        blanks = [v for v in x.variables if v in variables and variables[v].trees_only]
        if blanks:
            out.append(ListWarning(code="blanks", variables=blanks))
    limit = MAX_REGRESSION_VALUES if x.kind == "regression" else MAX_ML_VALUES
    many = [v for v in x.variables if v in variables and (variables[v].values or 0) > limit]
    if many:
        out.append(ListWarning(code="many_values", variables=many))
    return out


def view(project, project_dir: Path) -> VarListsView:
    from oakbox import assemble

    variables = model.variables(project, project_dir)
    by_field = {v.field: v for v in variables}
    sales = _sales(project, project_dir)
    modeled = assemble.modeled(project, project_dir)
    all_lists = lists(project, project_dir)
    # Who takes each list: a model by its name, with its group, or how many groups it's in.
    takers: dict[str, dict[str, list[str]]] = {}
    for g in project.groups:
        if g.id not in modeled:
            continue
        for e in model.group_models(project, project_dir, g.id, all_lists):
            if e.list_id:
                takers.setdefault(e.list_id, {}).setdefault(e.name, []).append(g.name)
    used = {
        lid: [f"{name} · {gs[0] if len(gs) == 1 else f'{len(gs)} groups'}" for name, gs in by_name.items()]
        for lid, by_name in takers.items()
    }
    return VarListsView(
        lists=[
            ListView(**x.model_dump(), used_by=used.get(x.id, []), warnings=_warnings(x, by_field, sales))
            for x in all_lists
        ],
        variables=variables,
        groups=[
            GroupSales(id=g.id, name=g.name, color=g.color, sales=sales.get(g.id), modeled=g.id in modeled)
            for g in project.groups
        ],
        tested=tested(project_dir) is not None,
        recommend=recommendations(project, project_dir),
        missing=model.missing(project, project_dir),
    )

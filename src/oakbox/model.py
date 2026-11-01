"""Step 5 continues: the models (SPEC F9, slice 1). Which variables, which models, a try, and how they did.

A try is OpenAVMKit's notebook 3 up to `try_models`: the prepared hand-off (out/2-clean-sup.pickle, written by
Prepare the fields), the canonical splits, then every model on every model group, main models only (no vacant
models: OAK box values the whole parcel). It runs in a process of its own (`python -m oakbox.model <project id>`)
and keeps each group's benchmark as the receipt (out/oakbox/model/), as OpenAVMKit's benchmark has it: the IAAO
figures on the holdout (each sale predicted by a model that never saw it, by 5-fold nested cross-validation), on
sales after the valuation date if there are any, and on the study set (the look-back before the valuation date),
each untrimmed and trimmed; the academic figures on the holdout; and the timings. The roll runs as OpenAVMKit's
`assessor` model, and is shown on the study set only: the holdout is OpenAVMKit's own draw, and the roll's values
may have been made with those very sales.

The variables and models are written as OpenAVMKit's settings (`modeling.models.main`,
`modeling.instructions.main`): the default list is the linear-safe one (numbers with no blanks left), which
OpenAVMKit prunes per group by its own variable tests before a linear model uses it; trees get the whole list.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import cells, fields, locstack, prepare, ratio, steps, valuesets
from oakbox.datafiles import BaseModel
from oakbox.fields import VALUE_SLOTS
from oakbox.valuesets import ROLL, value_field

MODULE = "model"

# The engines offered, in the order shown: (name, one line).
ENGINES: dict[str, tuple[str, str]] = {
    "lightgbm": ("LightGBM", "Gradient-boosted trees: the most accurate, harder to explain. Takes blanks."),
    "xgboost": ("XGBoost", "Gradient-boosted trees, like LightGBM; slower. Takes blanks."),
    "catboost": ("CatBoost", "Gradient-boosted trees, good with categories; the slowest of the three. Takes blanks."),
    "mra": ("MRA", "A linear model on log price: explainable, never negative. Uses only variables with no blanks."),
    "multi_mra": ("Multi-MRA", "A linear model per neighbourhood, on log price. Uses only variables with no blanks."),
    "gwr": ("GWR", "A linear model that varies smoothly over the map: slow. Uses only variables with no blanks."),
    "local_area": ("Local area", "The neighbourhood's price per area: a baseline to beat."),
    "lcomp": (
        "Layered comps",
        "Comparable sales as a model: sales split into ever-closer groups by their variables, a parcel valued from"
        " the trimmed mean prices of the groups it falls in, the closest weighted most. Explainable. Takes blanks.",
    ),
}
# Machine-learning engines: they take a machine-learning list, blanks and all (the linear ones leave out
# variables with blanks).
ML = {"lightgbm", "xgboost", "catboost", "lcomp"}
# Each engine's own settings (Model values › Models › Configuration), as OpenAVMKit reads them from its entry, and
# their defaults. Locations are the stack (LOCATED); interactions only for the linear ones (trees find their own).
OPTIONS: dict[str, list[str]] = {
    "mra": ["log", "intercept", "interactions"],
    "multi_mra": ["locations", "log", "intercept", "interactions", "optimize_vars"],
    "gwr": ["interactions"],
    "local_area": ["locations"],
    "lightgbm": ["n_trials"],
    "xgboost": ["n_trials"],
    "catboost": ["n_trials", "use_gpu"],
}
DEFAULTS: dict[str, object] = {
    "log": True,
    "intercept": True,
    "interactions": "none",
    "optimize_vars": False,
    "n_trials": 50,
    "use_gpu": True,
}
Interactions = Literal["none", "default"]
# Models that read a location stack; Local area takes no variable list (its areas' price per area is the model).
LOCATED = {"multi_mra", "local_area"}
TAKES_LIST = set(ENGINES) - {"local_area"}
# Every modeled group starts with these.
DEFAULT_MODELS = ["lightgbm", "mra", "multi_mra"]
# Names OpenAVMKit gives a meaning of its own: a model can't be called these.
RESERVED = {"default", "assessor", "ensemble", "pass_through", "ground_truth", "main", "vacant"}

LOCATION = ["latitude_norm", "longitude_norm", "polar_radius", "polar_angle"]
# Never offered: identifiers and the roll's own values, sale fields, raw coordinates (the normalized ones are), land
# area as given or measured (land area is), years (ages are), Check sales' groups of similar parcels (he_id), and
# distances (each feature's proximity is: it rises near the feature and is 0 beyond the distance that matters).
NEVER = ("key", "assr_", "vset", "sale_", "model_group", "latitude", "longitude", "deed_", "within_", "dist_to_")
NEVER_ENDS = ("_in_acres", "_gis_sqft", "_gis_sqm", "_given_sqft", "_given_sqm", "_year_built", "_date", "he_id")
NEVER_HAS = ("_delta",)
KEEP = {"latitude_norm", "longitude_norm", "dist_to_cbd"}
# Names for fields the data dictionary doesn't name.
NAMES = {"polar_radius": "Distance from the centre", "polar_angle": "Direction from the centre"}

Kind = Literal["big_five", "building", "land", "location", "other", "category"]


ListKind = Literal["regression", "ml"]


def kind_of(engine: str) -> ListKind:
    """The type of variable list an engine is made for: machine-learning engines (trees, layered comps) take a
    machine-learning list, the rest a regression's."""
    return "ml" if engine in ML else "regression"


class VarList(BaseModel):
    """A variable list (varlists.py): its variables, its type and the model groups it's for."""

    id: str = Field(default="", description="Its name in the settings: variable_lists.<id>. Kept when it's renamed.")
    name: str
    kind: ListKind
    groups: list[str] = Field(description="The model groups it's for.")
    variables: list[str]


class ModelEntry(BaseModel):
    """One of a model group's models."""

    key: str = Field(default="", description="Its name in the settings, unique in its group: made from its name.")
    name: str = Field(default="", description="As shown; the engine's name unless given.")
    engine: str
    list_id: str | None = Field(
        default=None, description="The variable list it takes (its id); None: the group's first of its type."
    )
    locations: list[str] | None = Field(
        default=None, description="Its location stack, finest first (Multi-MRA, Local area); None: proposed."
    )
    # Its own settings (OPTIONS); None: the default (DEFAULTS).
    log: bool | None = Field(default=None, description="MRA, Multi-MRA: fit on log price.")
    intercept: bool | None = Field(default=None, description="MRA, Multi-MRA: a base value every parcel gets.")
    interactions: Interactions | None = Field(
        default=None, description="Linear models: default multiplies each land and building category by its area."
    )
    optimize_vars: bool | None = Field(default=None, description="Multi-MRA: drop unhelpful variables per area.")
    n_trials: int | None = Field(default=None, ge=1, le=500, description="Trees: tuning trials.")
    use_gpu: bool | None = Field(default=None, description="CatBoost: the graphics card if there is one.")

    def option(self, name: str):
        """An option's value, or its default."""
        v = getattr(self, name)
        return DEFAULTS[name] if v is None else v


class ModelState(BaseModel):
    tests: list[str] | None = Field(
        default=None, description="The variable tests to run (besides Represented); None: all of TESTS."
    )
    lists: list[VarList] | None = Field(default=None, description="The variable lists the user made; None: none yet.")
    groups: dict[str, list[ModelEntry]] = Field(
        default_factory=dict, description="Model group -> its models; a group not here has the default ones."
    )
    small: dict[str, Literal["leave", "model"]] = Field(
        default_factory=dict, description="Small groups: model group -> left unvalued or modeled anyway."
    )


# The variable tests offered (OpenAVMKit's names), each answering a question of its own; Represented always runs. The
# engine's other tests (elastic net, R², t-value, signs agree) mostly repeat one of these and aren't run.
TESTS = ("corr", "vif")


def tests(project) -> list[str]:
    chosen = project.model.tests
    return list(TESTS) if chosen is None else [x for x in TESTS if x in chosen]


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "model"


# ---------- The variables there are ----------


class Variable(BaseModel):
    field: str
    name: str
    kind: Kind
    numeric: bool
    parcels: int = Field(description="Parcels with a value.")
    blanks: int = Field(description="Parcels with none, after Prepare the fields.")
    trees_only: bool = Field(description="A number with blanks: linear models leave it out.")
    values: int | None = Field(
        default=None,
        description="A category's values: each becomes a column of its own to the models (one-hot), which slows them.",
    )


def _universe_path(project_dir: Path) -> Path:
    return project_dir / "out" / "look" / "2-clean-universe.parquet"


def _offered(field: str) -> bool:
    if field in KEEP:
        return True
    return not (field.startswith(NEVER) or field.endswith(NEVER_ENDS) or any(x in field for x in NEVER_HAS))


def _candidates(settings: dict, columns: list[str], units: str | None) -> list[tuple[str, Kind, bool]]:
    """(field, kind, numeric) for every field OpenAVMKit classifies as land, building or other (the data dictionary's,
    the user's own fields, map layers', public data's), the big five first, categories last."""
    import pandas as pd
    from openavmkit.utilities.settings import get_fields_impr, get_fields_land, get_fields_other

    df = pd.DataFrame(columns=pd.Index(columns))
    u = "sqft" if units == "imperial" else "sqm"
    age = "bldg_effective_age_years" if "bldg_effective_age_years" in columns else "bldg_age_years"
    big = [f"bldg_area_finished_{u}", f"land_area_{u}", age, "bldg_quality_num", "bldg_condition_num"]
    big_five: Kind = "big_five"
    out: list[tuple[str, Kind, bool]] = [(f, big_five, True) for f in big if f in columns]
    seen = {f for f, _, _ in out}
    cats: list[str] = []
    buckets: list[tuple[dict, Kind]] = [
        (get_fields_impr(settings, df), "building"),
        (get_fields_land(settings, df), "land"),
        (get_fields_other(settings, df), "other"),
    ]
    for found, kind in buckets:
        for f in sorted({*found.get("numeric", []), *found.get("boolean", [])}):
            if f in seen or not _offered(f):
                continue
            seen.add(f)
            k: Kind = "location" if f in LOCATION else kind
            out.append((f, k, True))
        cats += [f for f in sorted(found.get("categorical", [])) if f not in seen and _offered(f)]
    location: Kind = "location"
    for f in LOCATION:
        if f in columns and f not in seen:
            seen.add(f)
            out.append((f, location, True))
    category: Kind = "category"
    out.extend((f, category, False) for f in dict.fromkeys(cats) if f not in seen)
    order = ["big_five", "building", "land", "location", "other", "category"]
    return sorted(out, key=lambda x: order.index(x[1]))


def _counts(universe, sale_keys) -> tuple[dict[str, int], dict[str, int]]:
    """Parcels and sales per model group."""
    group = universe["model_group"].astype(str)
    of = dict(zip(universe["key"].astype(str), group, strict=False))
    parcels: dict[str, int] = {}
    for g in group:
        parcels[g] = parcels.get(g, 0) + 1
    sales: dict[str, int] = {}
    for k in sale_keys:
        g = of.get(str(k))
        if g is not None:
            sales[g] = sales.get(g, 0) + 1
    return parcels, sales


def big_five_missing(columns: list[str], units: str | None) -> list[str]:
    u = "sqft" if units == "imperial" else "sqm"
    words = {
        f"bldg_area_finished_{u}": "finished area",
        f"land_area_{u}": "land area",
        "bldg_age_years": "building age",
        "bldg_quality_num": "quality",
        "bldg_condition_num": "condition",
    }
    return [w for f, w in words.items() if f not in columns]


@lru_cache(maxsize=8)
def _scan(
    path: str, mtime: float, settings_mtime: float, units: str | None
) -> tuple[tuple[str, str, bool, int, int, int | None], ...]:
    """(field, kind, numeric, parcels with a value, blanks, a category's values) for each candidate in the prepared
    universe. A category with one value, or nearly one per parcel (an ID, an address), isn't offered; nor is a number
    the same everywhere, or infinite anywhere."""
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq

    columns = pq.ParquetFile(path).schema_arrow.names
    settings = steps.engine_settings(Path(path).parents[2])
    found = _candidates(settings, columns, units)
    df = pd.read_parquet(path, columns=[f for f, _, _ in found])
    out = []
    for f, kind, numeric in found:
        s = df[f]
        blanks = int(s.isna().sum())
        values = None
        if not numeric or not (pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)):
            distinct = s.nunique(dropna=True)
            if distinct <= 1 or (distinct > len(s) / 2 and distinct > 50):
                continue
            kind, numeric, values = "category", False, int(distinct)
        elif s.nunique(dropna=True) <= 1:
            continue  # the same everywhere: nothing to learn
        elif not pd.api.types.is_bool_dtype(s) and bool(np.isinf(s.to_numpy(dtype=float, na_value=np.nan)).any()):
            continue  # infinite somewhere (a ratio over a zero): no model can take it
        out.append((f, kind, numeric, len(s) - blanks, blanks, values))
    return tuple(out)


def _universe_fields(project_dir: Path) -> list[str]:
    import pyarrow.parquet as pq

    path = _universe_path(project_dir)
    return pq.ParquetFile(path).schema_arrow.names if path.is_file() else []


def _outside(project, project_dir: Path) -> list[str]:
    """The value sets besides the roll that Prepare's output carries a market value for."""
    have = set(_universe_fields(project_dir))
    return [v.id for v in valuesets.value_sets(project) if v.id != ROLL and value_field(v.id) in have]


def _has_roll(project_dir: Path) -> bool:
    import pyarrow.parquet as pq

    path = _universe_path(project_dir)
    return path.is_file() and ratio.FIELD in pq.ParquetFile(path).schema_arrow.names


def variables(project, project_dir: Path) -> list[Variable]:
    path = _universe_path(project_dir)
    if not path.is_file():
        return []
    names = fields.names() | NAMES
    out = []
    settings_path = project_dir / "in" / "settings.json"
    stamp = settings_path.stat().st_mtime if settings_path.is_file() else 0.0
    for f, kind, numeric, parcels, blanks, values in _scan(str(path), path.stat().st_mtime, stamp, project.units):
        out.append(
            Variable(
                field=f,
                name=names.get(f) or f,
                kind=kind,  # type: ignore[arg-type]
                numeric=numeric,
                parcels=parcels,
                blanks=blanks,
                trees_only=blanks > 0,
                values=values,
            )
        )
    return out


def missing(project, project_dir: Path) -> list[str]:
    """The big five fields Prepare's output doesn't have, in words."""
    return (
        big_five_missing(_universe_fields(project_dir), project.units) if _universe_path(project_dir).is_file() else []
    )


def entry_key(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "model"
    if not base[0].isalpha():
        base = f"m_{base}"
    out, n = base, 2
    while out in taken or out in RESERVED:
        out, n = f"{base}_{n}", n + 1
    return out


def default_models(project, project_dir: Path, group: str) -> list[ModelEntry]:
    taken: set[str] = set()
    out = []
    for engine in DEFAULT_MODELS:
        key = entry_key(engine, taken)
        taken.add(key)
        out.append(ModelEntry(key=key, name=ENGINES[engine][0], engine=engine))
    return out


def group_models(project, project_dir: Path, group: str, all_lists: list[VarList] | None = None) -> list[ModelEntry]:
    """A group's models as they'll run: each with its list (the group's first of its type unless told otherwise, or
    if its own was removed) and its location stack (proposed unless told otherwise)."""
    from oakbox import locstack, varlists

    lists = varlists.lists(project, project_dir) if all_lists is None else all_lists
    ids = {x.id for x in lists}
    out = []
    for e in project.model.groups.get(group) or default_models(project, project_dir, group):
        update: dict = {}
        if e.engine in TAKES_LIST and (e.list_id is None or e.list_id not in ids):
            first = varlists.for_group(lists, group, kind_of(e.engine))
            update["list_id"] = first.id if first else None
        elif e.engine not in TAKES_LIST:
            update["list_id"] = None
        if e.engine in LOCATED and e.locations is None:
            update["locations"] = locstack.proposed(project_dir, group)
        elif e.engine not in LOCATED:
            update["locations"] = None
        out.append(e.model_copy(update=update))
    return out


AREAS = ("land_area_sqft", "bldg_area_finished_sqft", "land_area_sqm", "bldg_area_finished_sqm")


def _areas(by_field: dict[str, Variable]) -> list[str]:
    """Land and finished area: what Local area divides a price by."""
    return [f for f in AREAS if f in by_field]


def settings(project, project_dir: Path) -> dict:
    """OpenAVMKit's modeling settings for the calls: nothing until Prepare the fields has written its output.

    The variable lists go in `variable_lists`; each modeled group has its own block of models under
    `modeling.models.main.<group>` (which OpenAVMKit takes in place of the shared one), each model pointing at its
    list by `$$variable_lists.<id>`. `run` names every group's models; each group skips the ones it hasn't."""
    from oakbox import assemble, varlists

    by_field = {v.field: v for v in variables(project, project_dir)}
    if not by_field:
        return {}
    all_lists = varlists.lists(project, project_dir)
    lists = {x.id: x for x in all_lists}
    # The roll, valued as a model: OpenAVMKit then audits it on the study set, beside the models. Other existing
    # values (a vendor's AVM…) as pass_through models, judged like the roll: off the holdout, out of the ensemble.
    roll = ["assessor"] if _has_roll(project_dir) else []
    outside = _outside(project, project_dir)
    modeled = assemble.modeled(project, project_dir)
    areas = _areas(by_field)
    blocks: dict[str, dict] = {}
    names: list[str] = []
    for g in project.groups:
        if g.id not in modeled:
            continue
        # Local area, the roll and existing values take no list: the default entry gives them the areas.
        block: dict = {"default": {"ind_vars": areas}}
        for e in group_models(project, project_dir, g.id, all_lists):
            entry: dict = {"model": e.engine}
            lst = lists.get(e.list_id or "")
            if e.engine in TAKES_LIST:
                blanks = [v for v in (lst.variables if lst else []) if v in by_field and by_field[v].trees_only]
                if lst is None:
                    entry["ind_vars"] = []
                elif blanks and e.engine not in ML:
                    # A linear model can't take a blank: the list without its variables with blanks.
                    entry["ind_vars"] = [v for v in lst.variables if v not in blanks]
                else:
                    entry["ind_vars"] = f"$$variable_lists.{lst.id}"
            # Every option the engine reads, defaults too: what's shown is what runs.
            for o in OPTIONS.get(e.engine, []):
                if o == "locations":
                    entry["locations"] = e.locations or []
                elif o == "interactions":
                    entry["interactions"] = {"default": e.option(o) == "default"}
                else:
                    entry[o] = e.option(o)
            block[e.key] = entry
            if e.key not in names:
                names.append(e.key)
        blocks[g.id] = block | {v: {"model": "pass_through", "field": value_field(v)} for v in outside}
    run = names + roll + outside
    skip = {g.id: [m for m in names if m not in blocks[g.id]] if g.id in blocks else run for g in project.groups}
    skip = {g: v for g, v in skip.items() if v}
    return {
        "variable_lists": {x.id: x.variables for x in all_lists},
        "modeling": {
            "instructions": {
                "main": {
                    "run": run,
                    "ensemble": {"type": "median", "models": names},
                    # Groups not modeled skip every model; the others, the models they haven't.
                    **({"skip": skip} if skip else {}),
                }
            },
            "models": {"main": blocks},
        },
        # On the study set, each model is judged by its holdout predictions, as the roll is beside it: on its
        # predictions on every sale, it would be judged on sales it trained on.
        "analysis": {
            "ratio_study": {"study_set_predictions": "holdout", **({"outside_models": outside} if outside else {})}
        },
    }


# ---------- Before running ----------


class Engine(BaseModel):
    key: str
    name: str
    note: str
    kind: ListKind = Field(description="The type of variable list it's made for.")
    takes_list: bool
    located: bool = Field(description="Reads a location stack.")
    options: list[str] = Field(description="Its own settings, as Configuration offers them (locations among them).")


class ModelGroupCount(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    sales: int = Field(description="Sales the models learn from and are tested on.")
    modeled: bool = Field(default=True, description="Modeled (Model groups › Check them).")


class EntryWarning(BaseModel):
    code: Literal["no_list", "kind_mismatch", "list_missing", "list_empty", "blanks_left_out", "no_locations"]
    n: int = 0


class EntryView(ModelEntry):
    warnings: list[EntryWarning]


class GroupModels(ModelGroupCount):
    models: list[EntryView] = Field(default_factory=list)
    custom: bool = Field(default=False, description="Its models were changed: not the default ones.")


class ListSummary(BaseModel):
    id: str
    name: str
    kind: ListKind
    groups: list[str]
    count: int


class ModelSetup(BaseModel):
    variables: list[Variable]
    engines: list[Engine]
    groups: list[GroupModels]
    lists: list[ListSummary]
    locations: list[locstack.LocationField] = Field(description="The location fields a stack can use.")
    defaults: dict[str, bool | int | str] = Field(description="Each model option's default.")
    tests: list[str] = Field(description="The variable tests to run, besides Represented.")


def _entry_view(e: ModelEntry, raw: ModelEntry | None, lists: dict[str, VarList], by_field: dict) -> EntryView:
    w: list[EntryWarning] = []
    lst = lists.get(e.list_id or "")
    if e.engine in TAKES_LIST:
        if raw is not None and raw.list_id and raw.list_id not in lists:
            w.append(EntryWarning(code="list_missing"))
        if lst is not None and lst.kind != kind_of(e.engine):
            w.append(EntryWarning(code="kind_mismatch"))
        if lst is None:
            w.append(EntryWarning(code="no_list"))
        elif not lst.variables:
            w.append(EntryWarning(code="list_empty"))
        elif e.engine not in ML:
            n = sum(1 for v in lst.variables if v in by_field and by_field[v].trees_only)
            if n:
                w.append(EntryWarning(code="blanks_left_out", n=n))
    if e.engine in LOCATED and not e.locations:
        w.append(EntryWarning(code="no_locations"))
    return EntryView(**e.model_dump(), warnings=w)


def setup(project, project_dir: Path) -> ModelSetup:
    import pandas as pd
    import pyarrow.parquet as pq

    from oakbox import assemble, varlists

    path = _universe_path(project_dir)
    if not path.is_file():
        raise LookupError("Prepare the fields first: the models start from what it writes.")
    columns = pq.ParquetFile(path).schema_arrow.names
    vs = variables(project, project_dir)
    by_field = {v.field: v for v in vs}
    all_lists = varlists.lists(project, project_dir)
    lists = {x.id: x for x in all_lists}
    universe = pd.read_parquet(path, columns=["key", "model_group"]) if "model_group" in columns else None
    sales_path = project_dir / "out" / "look" / "2-clean-sales.parquet"
    per: dict[str, int] = {}
    sold: dict[str, int] = {}
    if universe is not None:
        keys = pd.read_parquet(sales_path, columns=["key"])["key"].tolist() if sales_path.is_file() else []
        per, sold = _counts(universe, keys)
    modeled = assemble.modeled(project, project_dir)
    groups = []
    for x in project.groups:
        raw = {e.key: e for e in project.model.groups.get(x.id) or []}
        groups.append(
            GroupModels(
                id=x.id,
                name=x.name,
                color=x.color,
                parcels=per.get(x.id, 0),
                sales=sold.get(x.id, 0),
                modeled=x.id in modeled,
                models=[
                    _entry_view(e, raw.get(e.key), lists, by_field)
                    for e in group_models(project, project_dir, x.id, all_lists)
                ]
                if x.id in modeled
                else [],
                custom=x.id in project.model.groups,
            )
        )
    return ModelSetup(
        variables=vs,
        engines=[
            Engine(
                key=k,
                name=n,
                note=note,
                kind=kind_of(k),
                takes_list=k in TAKES_LIST,
                located=k in LOCATED,
                options=OPTIONS.get(k, []),
            )
            for k, (n, note) in ENGINES.items()
        ],
        groups=groups,
        lists=[
            ListSummary(id=x.id, name=x.name, kind=x.kind, groups=x.groups, count=len(x.variables)) for x in all_lists
        ],
        locations=locstack.offered(project_dir),
        defaults={k: v for k, v in DEFAULTS.items() if isinstance(v, bool | int | str)},
        tests=tests(project),
    )


class ModelPatch(BaseModel):
    tests: list[str] | None = Field(default=None, description="The variable tests to run, besides Represented.")


def change(project, body: ModelPatch) -> None:
    s: ModelState = project.model
    if body.tests is not None:
        unknown = [x for x in body.tests if x not in TESTS]
        if unknown:
            raise ValueError(f"Not a test OAK box offers: {', '.join(unknown)}.")
        if not body.tests:
            raise ValueError("Choose at least one test.")
        s.tests = [x for x in TESTS if x in body.tests]


def set_group(project, project_dir: Path, group: str, models: list[ModelEntry] | None) -> None:
    """A model group's models (None: back to the default ones). Each gets the engine's name unless given one, and a
    key from its name; a list must be one of the lists, a stack's fields location fields."""
    from oakbox import varlists

    if group not in {g.id for g in project.groups}:
        raise LookupError(group)
    if models is None:
        project.model.groups.pop(group, None)
        return
    lists = {x.id for x in varlists.lists(project, project_dir)}
    places = {x.field for x in locstack.offered(project_dir)}
    taken: set[str] = set()
    out = []
    for e in models:
        if e.engine not in ENGINES:
            raise ValueError(f"Not a model OAK box offers: {e.engine}.")
        name = e.name.strip() or ENGINES[e.engine][0]
        key = (
            e.key
            if e.key and e.key not in taken and e.key not in RESERVED and re.fullmatch(r"[a-z][a-z0-9_]*", e.key)
            else entry_key(name, taken)
        )
        taken.add(key)
        if e.list_id is not None and e.list_id not in lists:
            raise ValueError(f"No variable list {e.list_id}.")
        unknown = [f for f in e.locations or [] if f not in places]
        if unknown:
            raise ValueError(f"Not a location field: {', '.join(unknown)}.")
        out.append(
            ModelEntry(
                key=key,
                name=name,
                engine=e.engine,
                list_id=e.list_id if e.engine in TAKES_LIST else None,
                locations=list(dict.fromkeys(e.locations)) if e.engine in LOCATED and e.locations is not None else None,
                # Only the options the engine reads.
                **{o: getattr(e, o) for o in OPTIONS.get(e.engine, []) if o != "locations"},
            )
        )
    if len({e.name.lower() for e in out}) < len(out):
        raise ValueError("Two models in a group can't have the same name.")
    project.model.groups[group] = out


# ---------- The receipt ----------


Verdict = Literal["ok", "slight", "bad"]
SetKey = Literal["holdout", "post_val", "study"]


class ModelRow(BaseModel):
    """One row of a table: a model (or the roll) and its figures, by OpenAVMKit's names for them."""

    model: str
    name: str
    values: dict[str, float | None]
    judged: dict[str, Verdict] = Field(
        default_factory=dict, description="Against this project's IAAO targets: the figures that are judged."
    )


class SalesSet(BaseModel):
    """A set of sales the figures are on, as OpenAVMKit's benchmark has them."""

    key: SetKey
    sales: int
    first: str | None
    last: str | None
    rows: list[ModelRow] = Field(description="IAAO figures: a row per model; the roll's first on the study set.")
    trimmed: list[ModelRow] = Field(description="The same, without the outlying ratios.")


class ModelGroupResult(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    sales: int
    sets: list[SalesSet] = Field(default_factory=list)
    academic: list[ModelRow] = Field(default_factory=list, description="On the holdout: errors as a statistician's.")
    academic_trimmed: list[ModelRow] = Field(default_factory=list)
    timings: list[ModelRow] = Field(default_factory=list, description="Seconds each model took, by stage.")
    skipped: str | None = Field(default=None, description="Why it has no models, if it hasn't.")
    valued: int = Field(default=0, description="Parcels the try gave a value (the ensemble's, else a model's).")
    below_zero: int = Field(default=0, description="Of them, valued below zero.")


class ModelReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    models: list[str]
    variables: list[str]
    groups: list[ModelGroupResult]
    notes: list[str] = Field(default_factory=list)


NOT_MODELED = "Not modeled: unticked on Model groups › Check them"


def _name(model: str, names: dict[str, str]) -> str:
    """A model's name; the roll and other existing values by the names the user gave them."""
    if model == "ensemble":
        return "Ensemble"
    if model == "assessor":
        return names.get(ROLL, "The roll")
    return names.get(model) or ENGINES.get(model, (model,))[0]


# OpenAVMKit's benchmark columns, as each table shows them.
IAAO = ("utility_score", "count_univ", "count_sales", "median_ratio", "cod", "prd", "prb", "vei", "vei_sig", "chd")
IAAO_TRIMMED = ("count_trim", "median_ratio_trim", "cod_trim", "prd_trim", "prb_trim", "vei_trim", "vei_sig_trim")
ACADEMIC = {
    "count": "count",
    "MAPE": "mape",
    "MSE": "mse",
    "RMSE": "rmse",
    "m.ratio": "median_ratio",
    "avg.ratio": "mean_ratio",
    "Slope": "slope",
}


def _judge(values: dict[str, float | None], sales: float | None, std: ratio.Standard) -> dict:
    """The figures a standard judges, against the group's standard (Check my values): the level, the COD, the PRB."""
    if (sales or 0) < std.min_sales:
        return {}
    out: dict[str, Verdict] = {}
    for k in ("median_ratio", "median_ratio_trim"):
        m = values.get(k)
        if m is not None:
            out[k] = "ok" if std.level_low <= m <= std.level_high else "bad"
    for k in ("cod", "cod_trim"):
        c = values.get(k)
        if c is not None:
            out[k] = "ok" if std.cod_low <= c <= std.cod_high else "bad"
    for k in ("prb", "prb_trim"):
        b = values.get(k)
        if b is not None:
            out[k] = "ok" if abs(b) <= std.prb_good else "bad" if abs(b) > std.prb_bad else "slight"
    return out


def _rows(df, columns, rename=None, std=None, sales_key="count_sales", drop=(), names=None) -> list[ModelRow]:
    """A row per model from one of OpenAVMKit's tables, the ensemble first, then the models in OAK box's order."""
    if df is None or len(df) == 0:
        return []
    out = []
    for model, row in df.to_dict(orient="index").items():
        model = str(model)
        if model in drop:
            continue
        values = {(rename or {}).get(c, c): cells.number(row.get(c)) for c in columns}
        judged = _judge(values, values.get(sales_key), std) if std else {}
        out.append(ModelRow(model=model, name=_name(model, names or {}), values=values, judged=judged))
    order = ["assessor", *VALUE_SLOTS, "ensemble", *(names or {}), *ENGINES]
    return sorted(out, key=lambda f: order.index(f.model) if f.model in order else 99)


def _dates(df) -> tuple[str | None, str | None]:
    import pandas as pd

    if df is None or "sale_date" not in df or len(df) == 0:
        return None, None
    d = pd.to_datetime(df["sale_date"], errors="coerce").dropna()
    return (d.min().date().isoformat(), d.max().date().isoformat()) if len(d) else (None, None)


def _sets(r, std: ratio.Standard | None, names: dict[str, str], outside: tuple[str, ...]) -> list[SalesSet]:
    """OpenAVMKit's sets of sales: the holdout, the sales after the valuation date when there are any, and the
    study set (the look-back before the valuation date). The roll is only on the study set: the holdout is
    OpenAVMKit's own, and the roll's values may have been made with those very sales."""
    b = r.benchmark
    first = next(iter(r.model_results.values()))
    out = []
    frames: list[tuple[SetKey, object, object, tuple[str, ...]]] = [
        ("holdout", b.df_stats_test, first.df_test, ("assessor", *outside))
    ]
    if b.df_stats_test_post_val is not None and not b.test_post_val_empty:
        frames.append(("post_val", b.df_stats_test_post_val, None, ("assessor", *outside)))
    frames.append(("study", b.df_stats_full, first.df_sales_lookback, ()))
    for key, df, sales_df, drop in frames:
        rows = _rows(df, IAAO, std=std, drop=drop, names=names)
        n = int(rows[0].values.get("count_sales") or 0) if rows else 0
        f, last = _dates(sales_df) if sales_df is not None else (None, None)
        out.append(
            SalesSet(
                key=key,
                sales=n,
                first=f,
                last=last,
                rows=rows,
                trimmed=_rows(df, IAAO_TRIMMED, std=std, sales_key="count_trim", drop=drop, names=names),
            )
        )
    return out


def _valued(r, outside: tuple[str, ...]) -> tuple[int, int]:
    """Parcels a group's try valued, and how many below zero: the ensemble's values, else its one model's."""
    results = r.model_results
    m = results.get("ensemble") or next((v for k, v in results.items() if k not in ("assessor", *outside)), None)
    if m is None:
        return 0, 0
    values = m.df_universe[m.field_prediction]
    return int(values.notna().sum()), int((values < 0).sum())


def not_finite(sales, universe, settings: dict, groups: dict[str, str], own: dict[str, dict[str, str]]) -> list[str]:
    """Variables the models use with infinite (or float-overflowing) values, per model group, in words: what
    OpenAVMKit's "Input contains infinity or a value too large" doesn't say. groups: id -> name; own: each group's
    model keys -> the names the user gave them."""
    import numpy as np
    import pandas as pd

    lists = settings.get("variable_lists", {})
    main = settings.get("modeling", {}).get("models", {}).get("main", {})
    out: list[str] = []
    for g, gname in groups.items():
        uses: dict[str, list[str]] = {}
        for key, entry in (main.get(g) or {}).items():
            if not isinstance(entry, dict):
                continue
            ivs = entry.get("ind_vars") or []
            if isinstance(ivs, str) and ivs.startswith("$$variable_lists."):
                ivs = lists.get(ivs.split(".", 1)[1], [])
            for v in ivs if isinstance(ivs, list) else []:
                name = own.get(g, {}).get(key) or ENGINES.get(entry.get("model", key), (key,))[0]
                if key != "default" and name not in uses.setdefault(v, []):
                    uses[v].append(name)
        counts: dict[str, list[int]] = {}
        for i, df in enumerate((sales, universe)):
            rows = df[df["model_group"] == g] if "model_group" in df else df.iloc[0:0]
            for v in uses:
                if v not in rows or rows[v].dtype == bool:
                    continue
                col = np.asarray(pd.to_numeric(pd.Series(rows[v]), errors="coerce"), dtype=float)
                bad = int((np.isinf(col) | (np.abs(col) > 1e300)).sum())
                if bad:
                    counts.setdefault(v, [0, 0])[i] = bad
        for v, (n_sales, n_parcels) in counts.items():
            models = ", ".join(uses[v]) or "every model"
            out.append(f"{v} in {gname}: {n_sales:,} sales and {n_parcels:,} parcels (used by {models})")
    return out


def bad_prices(sales, groups: dict[str, str]) -> list[str]:
    """Prices a model can't learn from, per model group: 0 or below (their log is -infinity), or infinite."""
    import numpy as np
    import pandas as pd

    out = []
    for g, gname in groups.items():
        rows = sales[sales["model_group"] == g] if "model_group" in sales else sales.iloc[0:0]
        for f in ("sale_price", "sale_price_time_adj"):
            if f not in rows:
                continue
            col = np.asarray(pd.to_numeric(pd.Series(rows[f]), errors="coerce"), dtype=float)
            low, inf = int((col <= 0).sum()), int(np.isinf(col).sum())
            if low:
                out.append(f"{f} in {gname}: {low:,} sales at 0 or below (a log price makes them -infinity)")
            if inf:
                out.append(f"{f} in {gname}: {inf:,} sales infinite")
    return out


def far_out(sales, universe, group: str, variables: list[str], keep: int = 4) -> list[str]:
    """Variables whose parcels reach far beyond the group's sales (10 times the sales' spread past their edge): where a
    model predicting on log price overflows to infinity. Furthest first."""
    import numpy as np
    import pandas as pd

    def col(df, v):
        rows = df[df["model_group"] == group] if "model_group" in df else df
        x = np.asarray(pd.to_numeric(pd.Series(rows[v]), errors="coerce"), dtype=float)
        return x[np.isfinite(x)]

    found = []
    for v in variables:
        if v not in sales or v not in universe or sales[v].dtype == bool:
            continue
        s, u = col(sales, v), col(universe, v)
        if not len(s) or not len(u):
            continue
        spread = max(float(s.max() - s.min()), 1e-9)
        past = max(float(u.max() - s.max()), float(s.min() - u.min())) / spread
        if past > 10:
            n = int(((u > s.max() + 10 * spread) | (u < s.min() - 10 * spread)).sum())
            found.append(
                (
                    past,
                    f"{v}: sales {s.min():,.4g} to {s.max():,.4g}, parcels {u.min():,.4g} to {u.max():,.4g}"
                    f" ({n:,} parcels far outside)",
                )
            )
    return [text for _, text in sorted(found, reverse=True)[:keep]]


def _stack(e: BaseException, keep: int = 2) -> str:
    """Where it stopped: the last frame in OpenAVMKit (what it was doing) and the last few below it, in a library
    ("model_runner.py:1365 run_one_model › validation.py:133 _assert_all_finite")."""
    import traceback

    frames = traceback.extract_tb(e.__traceback__)

    def at(f: traceback.FrameSummary) -> str:
        return f"{Path(f.filename).name}:{f.lineno} {f.name}"

    engine = [i for i, f in enumerate(frames) if "openavmkit" in f.filename.replace("\\", "/")]
    if not engine:
        return " › ".join(at(f) for f in frames[-keep - 1 :])
    last = engine[-1]
    below = frames[last + 1 :][-keep:]
    skipped = len(frames) - last - 1 - len(below)
    return " › ".join([f"OpenAVMKit {at(frames[last])}", *(["…"] if skipped else []), *(at(f) for f in below)])


def _infinite_error(found: list[str]) -> str:
    return (
        "Some variables have infinite values, which no model can take: "
        + "; ".join(found)
        + ". Take them out of the variable lists (Variables), or see where they come from in Data."
    )


def _crashed(
    e: Exception, project, pdir: Path, at: dict[str, str], sup, settings: dict, gnames: dict[str, str], own: dict
) -> Exception:
    """OpenAVMKit's error, with what can be said about it: the model group and model it was training, its variable
    list, what in the data could have caused it (infinite variables, prices a log can't take), and where in the code
    it stopped."""
    from oakbox import varlists

    said = [str(e).rstrip(".") + "."]
    g, key = at.get("group"), at.get("model")
    if g:
        entry = next((x for x in group_models(project, pdir, g) if x.key == key), None)
        engine = own.get(g, {}).get(key or "") or ENGINES.get(key or "", (key,))[0]
        lst = next((x for x in varlists.lists(project, pdir) if entry and x.id == entry.list_id), None)
        listed = f', variable list "{lst.name}" ({len(lst.variables)} variables)' if lst else ""
        import traceback

        if any("ensemble" in f.name for f in traceback.extract_tb(e.__traceback__)):
            said.append(f"While combining {gnames.get(g, g)}'s models into the ensemble, after {engine}.")
        else:
            said.append(f"While training {engine} on {gnames.get(g, g)}{listed}.")
    scope = {g: gnames[g]} if g in gnames else gnames
    if "infinity" in str(e) or "too large" in str(e) or "NaN" in str(e):
        found = not_finite(sup.sales, sup.universe, settings, scope, own) + bad_prices(sup.sales, scope)
        if found:
            said.append("What could cause it: " + "; ".join(found) + ".")
        else:
            said.append("No variable or price is infinite as prepared, so the model made one while training.")
            # Most often a prediction that overflowed: a log-price model asked about parcels far outside its sales.
            ivs = (
                (settings.get("modeling", {}).get("models", {}).get("main", {}).get(g or "") or {}).get(key or "") or {}
            ).get("ind_vars") or []
            if isinstance(ivs, str) and ivs.startswith("$$variable_lists."):
                ivs = settings.get("variable_lists", {}).get(ivs.split(".", 1)[1], [])
            far = far_out(sup.sales, sup.universe, g, list(ivs)) if g and isinstance(ivs, list) else []
            if far:
                said.append(
                    "Likely a prediction that overflowed, for parcels far outside what its sales cover: "
                    + "; ".join(far)
                    + ". Take the variable out of the list, or leave those parcels out of the group."
                )
    said.append(f"Stopped in {_stack(e)}.")
    # The whole traceback, for anyone who needs more than the message.
    import traceback

    log = pdir / "out" / "oakbox" / "model_error.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(traceback.format_exception(e)), encoding="utf-8")
    said.append(f"The full traceback is in {log.relative_to(pdir)}.")
    # Shown as "<its own type>: <all of this>", as any error is.
    return type(type(e).__name__, (Exception,), {})(" ".join(said))


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    if not (pdir / "out" / "2-clean-sup.pickle").is_file():
        raise RuntimeError("Prepare the fields first: the models start from what it writes.")
    tmp = steps.workdir(out_dir(pdir))
    depends = STEP.now(project, pdir)  # what it starts from, before anything can change
    settings_text = (pdir / "in" / "settings.json").read_text(encoding="utf-8")
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit import progress

    groups = [g.id for g in project.groups]
    names = {v.id: v.name for v in valuesets.value_sets(project)}
    from oakbox import assemble

    modeled = assemble.modeled(project, pdir)
    # Each group's models by the names the user gave them.
    own = {g: {e.key: e.name for e in group_models(project, pdir, g)} for g in groups if g in modeled}
    outside = tuple(_outside(project, pdir))
    t0 = time.time()

    at: dict[str, str] = {}  # the group and model training now: said if it stops

    def inside(e) -> None:
        # "model:<group>:<model>": which group the models are on, as the step's fraction.
        parts = (e.step or "").split(":")
        if len(parts) == 3 and parts[0] == "model" and parts[1] in groups:
            at.update(group=parts[1], model=parts[2])
            done = groups.index(parts[1]) / max(len(groups), 1)
            name = next((g.name for g in project.groups if g.id == parts[1]), parts[1])
            engine = own.get(parts[1], {}).get(parts[2]) or ENGINES.get(parts[2], (parts[2],))[0]
            steps.emit(step="models", fraction=0.1 + 0.85 * done, message=f"{name}: training {engine}")
        else:
            steps.emit(detail=e.message)

    with warnings.catch_warnings(record=True) as caught, progress.reporting(inside), steps.heartbeat():
        warnings.simplefilter("always")
        steps.emit(step="load", fraction=0.0, message="Reading the prepared fields")
        settings = pl.load_settings()
        sup = pl.load_cleaned_data_for_modeling(settings)
        # A variable with infinite values stops every model with an error that names none: say which, before.
        gnames = {g.id: g.name for g in project.groups if g.id in modeled}
        found = not_finite(sup.sales, sup.universe, settings, gnames, own)
        if found:
            raise ValueError(_infinite_error(found))
        steps.emit(step="split", fraction=0.05, message="Splitting the sales into folds")
        pl.write_canonical_splits(sup, settings, verbose=False)
        steps.emit(step="models", fraction=0.1, message="Training the models")
        try:
            results = pl.try_models(
                sup,
                settings,
                save_params=True,
                use_saved_params=True,
                verbose=False,
                run_main=True,
                run_vacant=False,
                run_ensemble=True,
            )
        except Exception as e:
            raise _crashed(e, project, pdir, at, sup, settings, gnames, own) from e
    steps.emit(step="receipt", fraction=0.97, message="Counting")
    from openavmkit.model_runner import _get_max_ratio_study_trim, academic_metrics

    per, sold = _counts(sup.universe, sup.sales["key"].tolist())
    judged_by = ratio.standard_of(project)
    out: list[ModelGroupResult] = []
    for g in project.groups:
        r = results.get(g.id)
        n = sold.get(g.id, 0)
        if g.id not in modeled:
            out.append(
                ModelGroupResult(
                    id=g.id, name=g.name, color=g.color, parcels=per.get(g.id, 0), sales=n, skipped=NOT_MODELED
                )
            )
            continue
        if r is None:
            out.append(
                ModelGroupResult(
                    id=g.id,
                    name=g.name,
                    color=g.color,
                    parcels=per.get(g.id, 0),
                    sales=n,
                    skipped=f"{n:,} {'sale' if n == 1 else 'sales'}: too few to model"
                    if n < 15
                    else "No model produced values for it",
                )
            )
            continue
        nm = names | own.get(g.id, {})
        valued, below = _valued(r, outside)
        sets = _sets(r, judged_by.get(g.id), nm, outside)
        if not any(x.sales for x in sets):
            # Modeled, but no sale to judge it by: as good as unmodeled here.
            out.append(
                ModelGroupResult(
                    id=g.id,
                    name=g.name,
                    color=g.color,
                    parcels=per.get(g.id, 0),
                    sales=n,
                    skipped=f"{n:,} {'sale' if n == 1 else 'sales'}, none held out to judge the models by",
                    valued=valued,
                    below_zero=below,
                )
            )
            continue
        untrimmed, trimmed = academic_metrics(r, _get_max_ratio_study_trim(settings, g.id))
        out.append(
            ModelGroupResult(
                id=g.id,
                name=g.name,
                color=g.color,
                parcels=per.get(g.id, 0),
                sales=n,
                sets=sets,
                valued=valued,
                below_zero=below,
                academic=_rows(untrimmed, ACADEMIC, ACADEMIC, drop=("assessor", *outside), names=nm),
                academic_trimmed=_rows(trimmed, ACADEMIC, ACADEMIC, drop=("assessor", *outside), names=nm),
                timings=_rows(
                    r.benchmark.df_time,
                    ("total", "param", "train", "test", "univ", "chd"),
                    drop=("assessor", *outside),
                    names=nm,
                ),
            )
        )
    mine = steps.engine_notes(caught)
    s = json.loads(settings_text)
    run_names = s.get("modeling", {}).get("instructions", {}).get("main", {}).get("run", [])
    receipt = ModelReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        models=[m for m in run_names if m != "assessor" and m not in outside],
        variables=sorted({v for x in (s.get("variable_lists") or {}).values() for v in x}),
        groups=out,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": depends}), encoding="utf-8")
    steps.publish(tmp, out_dir(pdir))
    modeled = sum(1 for g in out if g.sets)
    steps.emit(step="done", fraction=1.0, message=f"{modeled} of {len(out)} model groups modeled")


# ---------- The step's state ----------


def settings_key(settings: dict, project_dir: Path) -> dict:
    """What a try depends on: the Prepare run it starts from, and the variables and models."""
    m = settings.get("modeling", {})
    return {
        "prepare": prepare.STEP.ran_at(project_dir),
        "models": m.get("models", {}).get("main"),
        "lists": settings.get("variable_lists"),
        "run": m.get("instructions", {}).get("main"),
        "study": settings.get("analysis", {}).get("ratio_study", {}).get("study_set_predictions"),
    }


class ModelView(steps.RunView):
    receipt: ModelReceipt | None


def _key(project, project_dir: Path) -> dict:
    from oakbox import projects

    return settings_key(projects.base_settings(project), project_dir)


STEP = steps.Step(
    MODULE,
    "Try the models",
    ModelReceipt,
    key=_key,
    after=prepare.STEP,
    again="Try the models again first: something changed since.",
)


def blocked(project, project_dir: Path) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    return problems(project, project_dir)


def problems(project, project_dir: Path) -> list[str]:
    """What stops a try in the models themselves: a group with none, a list with no variables, a Local area with no
    location."""
    from oakbox import assemble, varlists

    if not variables(project, project_dir):
        return ["Prepare the fields first: there are no variables."]
    all_lists = varlists.lists(project, project_dir)
    lists = {x.id: x for x in all_lists}
    out = []
    modeled = assemble.modeled(project, project_dir)
    for g in project.groups:
        if g.id not in modeled:
            continue
        entries = group_models(project, project_dir, g.id, all_lists)
        if not entries:
            out.append(f"{g.name} has no models: add one, or untick it on Model groups › Check them.")
        for e in entries:
            lst = lists.get(e.list_id or "")
            if e.engine in TAKES_LIST and lst is None:
                out.append(f"{g.name} › {e.name}: no variable list. Make one on Variables › Variable lists.")
            elif e.engine in TAKES_LIST and lst is not None and not lst.variables:
                out.append(f"{g.name} › {e.name}: its variable list has no variables.")
            if e.engine == "local_area" and not e.locations:
                out.append(f"{g.name} › {e.name}: Local area needs at least one location.")
    return out


def view(project, project_dir: Path) -> ModelView:
    s = STEP.state(project, project_dir)
    return ModelView(
        status=s.status, job=s.job, receipt=s.receipt, stale=s.stale, blocked=blocked(project, project_dir)
    )


def start(project, project_dir: Path) -> None:
    STEP.start(project.id, project_dir, blocked(project, project_dir))


if __name__ == "__main__":
    steps.main(run)

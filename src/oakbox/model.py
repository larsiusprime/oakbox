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
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import bring_in, clean, prepare, ratio
from oakbox.datafiles import BaseModel

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
}
CHOOSE_FOR_ME = ["lightgbm", "mra", "local_area"]
TREES = {"lightgbm", "xgboost", "catboost"}
LINEAR = {"mra", "multi_mra", "gwr"}
LOGGED = {"mra", "multi_mra"}

LOCATION = ["latitude_norm", "longitude_norm", "polar_radius", "polar_angle"]
# Never offered: identifiers and the roll's own values, sale fields, raw coordinates (the normalized ones are), land
# area as given or measured (land area is), years (ages are), Check sales' groups of similar parcels (he_id), and
# distances (each feature's proximity is: it rises near the feature and is 0 beyond the distance that matters).
NEVER = ("key", "assr_", "sale_", "model_group", "latitude", "longitude", "deed_", "within_", "dist_to_")
NEVER_ENDS = ("_in_acres", "_gis_sqft", "_gis_sqm", "_given_sqft", "_given_sqm", "_year_built", "_date", "he_id")
NEVER_HAS = ("_delta",)
KEEP = {"latitude_norm", "longitude_norm", "dist_to_cbd"}
# Names for fields the data dictionary doesn't name.
NAMES = {"polar_radius": "Distance from the centre", "polar_angle": "Direction from the centre"}

Kind = Literal["big_five", "building", "land", "location", "other", "category"]


class ModelState(BaseModel):
    variables: list[str] | None = Field(default=None, description="The variables chosen; None: every one found.")
    models: list[str] | None = Field(default=None, description="The engines chosen; None: Choose for me.")
    tests: list[str] | None = Field(
        default=None, description="The variable tests to run (besides Represented); None: all of TESTS."
    )


# The variable tests offered (OpenAVMKit's names), each answering a question of its own; Represented always runs. The
# engine's other tests (elastic net, R², t-value, signs agree) mostly repeat one of these and aren't run.
TESTS = ("corr", "p_value", "vif")


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
    chosen: bool
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
    for fields, kind in buckets:
        for f in sorted({*fields.get("numeric", []), *fields.get("boolean", [])}):
            if f in seen or not _offered(f):
                continue
            seen.add(f)
            k: Kind = "location" if f in LOCATION else kind
            out.append((f, k, True))
        cats += [f for f in sorted(fields.get("categorical", [])) if f not in seen and _offered(f)]
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
    universe. A category with one value, or nearly one per parcel (an ID, an address), isn't offered."""
    import pandas as pd
    import pyarrow.parquet as pq

    columns = pq.ParquetFile(path).schema_arrow.names
    settings = clean._engine_settings(Path(path).parents[2])
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
        out.append((f, kind, numeric, len(s) - blanks, blanks, values))
    return tuple(out)


def _has_roll(project_dir: Path) -> bool:
    import pyarrow.parquet as pq

    path = _universe_path(project_dir)
    return path.is_file() and ratio.FIELD in pq.ParquetFile(path).schema_arrow.names


def variables(project, project_dir: Path) -> list[Variable]:
    path = _universe_path(project_dir)
    if not path.is_file():
        return []
    names = clean._names() | NAMES
    chosen = project.model.variables
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
                chosen=chosen is None or f in chosen,
                trees_only=blanks > 0,
                values=values,
            )
        )
    return out


def models(project) -> list[str]:
    return [m for m in (project.model.models or CHOOSE_FOR_ME) if m in ENGINES]


def settings(project, project_dir: Path) -> dict:
    """OpenAVMKit's modeling settings for the calls: nothing until Prepare the fields has written its output."""
    vs = [v for v in variables(project, project_dir) if v.chosen]
    if not vs:
        return {}
    every = [v.field for v in vs]
    linear = [v.field for v in vs if not v.trees_only]
    chosen = models(project)
    # The roll, valued as a model: OpenAVMKit then audits it on the study set, beside the models.
    roll = ["assessor"] if _has_roll(project_dir) else []
    entries: dict = {"default": {"ind_vars": linear or every}}
    for m in chosen:
        entry: dict = {}
        if m in TREES:
            entry["ind_vars"] = every
        if m in LOGGED:
            entry["log"] = True
        entries[m] = entry
    return {
        "modeling": {
            "instructions": {"main": {"run": chosen + roll, "ensemble": {"type": "median"}}},
            "models": {"main": entries},
        },
        # On the study set, each model is judged by its holdout predictions, as the roll is beside it: on its
        # predictions on every sale, it would be judged on sales it trained on.
        "analysis": {"ratio_study": {"study_set_predictions": "holdout"}},
    }


# ---------- Before running ----------


class Engine(BaseModel):
    key: str
    name: str
    note: str
    chosen: bool


class ModelGroupCount(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    sales: int = Field(description="Sales the models learn from and are tested on.")


class ModelSetup(BaseModel):
    variables: list[Variable]
    missing: list[str] = Field(description="Big five fields not loaded, in words.")
    engines: list[Engine]
    choose_for_me: bool
    groups: list[ModelGroupCount]
    tests: list[str] = Field(description="The variable tests to run, besides Represented.")


def setup(project, project_dir: Path) -> ModelSetup:
    import pandas as pd
    import pyarrow.parquet as pq

    path = _universe_path(project_dir)
    if not path.is_file():
        raise LookupError("Prepare the fields first: the models start from what it writes.")
    columns = pq.ParquetFile(path).schema_arrow.names
    chosen = models(project)
    groups = []
    universe = pd.read_parquet(path, columns=["key", "model_group"]) if "model_group" in columns else None
    sales_path = project_dir / "out" / "look" / "2-clean-sales.parquet"
    if universe is not None:
        keys = pd.read_parquet(sales_path, columns=["key"])["key"].tolist() if sales_path.is_file() else []
        per, sold = _counts(universe, keys)
        groups = [
            ModelGroupCount(id=x.id, name=x.name, color=x.color, parcels=per.get(x.id, 0), sales=sold.get(x.id, 0))
            for x in project.groups
        ]
    return ModelSetup(
        variables=variables(project, project_dir),
        missing=big_five_missing(columns, project.units),
        engines=[Engine(key=k, name=n, note=note, chosen=k in chosen) for k, (n, note) in ENGINES.items()],
        choose_for_me=project.model.models is None,
        groups=groups,
        tests=tests(project),
    )


class ModelPatch(BaseModel):
    variables: list[str] | None = None
    every_variable: bool | None = Field(default=None, description="True: back to every variable found.")
    models: list[str] | None = None
    choose_for_me: bool | None = Field(default=None, description="True: back to Choose for me.")
    tests: list[str] | None = Field(default=None, description="The variable tests to run, besides Represented.")


def change(project, body: ModelPatch) -> None:
    s: ModelState = project.model
    if body.every_variable:
        s.variables = None
    elif body.variables is not None:
        s.variables = list(dict.fromkeys(body.variables))
    if body.choose_for_me:
        s.models = None
    elif body.models is not None:
        unknown = [m for m in body.models if m not in ENGINES]
        if unknown:
            raise ValueError(f"Not a model OAK box offers: {', '.join(unknown)}.")
        if not body.models:
            raise ValueError("Choose at least one model.")
        s.models = [m for m in ENGINES if m in body.models]
    if body.tests is not None:
        unknown = [x for x in body.tests if x not in TESTS]
        if unknown:
            raise ValueError(f"Not a test OAK box offers: {', '.join(unknown)}.")
        if not body.tests:
            raise ValueError("Choose at least one test.")
        s.tests = [x for x in TESTS if x in body.tests]


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


class ModelReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    models: list[str]
    variables: list[str]
    groups: list[ModelGroupResult]
    notes: list[str] = Field(default_factory=list)


def _num(v) -> float | None:
    import math

    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _name(model: str) -> str:
    if model == "ensemble":
        return "Ensemble"
    if model == "assessor":
        return "The roll"
    return ENGINES.get(model, (model,))[0]


# OpenAVMKit's benchmark columns, as each table shows them.
IAAO = ("utility_score", "count_sales", "count_univ", "median_ratio", "cod", "prd", "prb", "vei", "vei_sig", "chd")
IAAO_TRIMMED = ("count_trim", "cod_trim", "prd_trim", "prb_trim")
TIMINGS = ("total", "param", "train", "test", "univ", "chd")
ACADEMIC = {
    "count": "count",
    "MAPE": "mape",
    "MSE": "mse",
    "RMSE": "rmse",
    "m.ratio": "median_ratio",
    "avg.ratio": "mean_ratio",
    "VEI": "vei",
    "VEI_sig": "vei_sig",
    "Slope": "slope",
}


def _judge(values: dict[str, float | None], sales: float | None, cls: str, targets: ratio.Targets) -> dict:
    """The figures IAAO's standard judges, against this project's targets: the level, the COD, the PRB."""
    if (sales or 0) < targets.min_sales or cls == "none":
        return {}
    out: dict[str, Verdict] = {}
    m = values.get("median_ratio")
    if m is not None:
        out["median_ratio"] = "ok" if targets.level_low <= m <= targets.level_high else "bad"
    rng = targets.cod(cls)
    for k in ("cod", "cod_trim"):
        c = values.get(k)
        if c is not None and rng:
            out[k] = "ok" if rng.low <= c <= rng.high else "bad"
    for k in ("prb", "prb_trim"):
        b = values.get(k)
        if b is not None:
            out[k] = "ok" if abs(b) <= targets.prb_good else "bad" if abs(b) > targets.prb_bad else "slight"
    return out


def _rows(df, columns, rename=None, cls="none", targets=None, sales_key="count_sales", drop=()) -> list[ModelRow]:
    """A row per model from one of OpenAVMKit's tables, the ensemble first, then the models in OAK box's order."""
    if df is None or len(df) == 0:
        return []
    out = []
    for model, row in df.to_dict(orient="index").items():
        model = str(model)
        if model in drop:
            continue
        values = {(rename or {}).get(c, c): _num(row.get(c)) for c in columns}
        judged = _judge(values, values.get(sales_key), cls, targets) if targets else {}
        out.append(ModelRow(model=model, name=_name(model), values=values, judged=judged))
    order = ["assessor", "ensemble", *ENGINES]
    return sorted(out, key=lambda f: order.index(f.model) if f.model in order else 99)


def _dates(df) -> tuple[str | None, str | None]:
    import pandas as pd

    if df is None or "sale_date" not in df or len(df) == 0:
        return None, None
    d = pd.to_datetime(df["sale_date"], errors="coerce").dropna()
    return (d.min().date().isoformat(), d.max().date().isoformat()) if len(d) else (None, None)


def _sets(r, cls: str, targets: ratio.Targets) -> list[SalesSet]:
    """OpenAVMKit's sets of sales: the holdout, the sales after the valuation date when there are any, and the
    study set (the look-back before the valuation date). The roll is only on the study set: the holdout is
    OpenAVMKit's own, and the roll's values may have been made with those very sales."""
    b = r.benchmark
    first = next(iter(r.model_results.values()))
    out = []
    frames: list[tuple[SetKey, object, object, tuple[str, ...]]] = [
        ("holdout", b.df_stats_test, first.df_test, ("assessor",))
    ]
    if b.df_stats_test_post_val is not None and not b.test_post_val_empty:
        frames.append(("post_val", b.df_stats_test_post_val, None, ("assessor",)))
    frames.append(("study", b.df_stats_full, first.df_sales_lookback, ()))
    for key, df, sales_df, drop in frames:
        rows = _rows(df, IAAO, cls=cls, targets=targets, drop=drop)
        n = int(rows[0].values.get("count_sales") or 0) if rows else 0
        f, last = _dates(sales_df) if sales_df is not None else (None, None)
        out.append(
            SalesSet(
                key=key,
                sales=n,
                first=f,
                last=last,
                rows=rows,
                trimmed=_rows(df, IAAO_TRIMMED, cls=cls, targets=targets, sales_key="count_trim", drop=drop),
            )
        )
    return out


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    if not (pdir / "out" / "2-clean-sup.pickle").is_file():
        raise RuntimeError("Prepare the fields first: the models start from what it writes.")
    tmp = out_dir(pdir).with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    settings_text = (pdir / "in" / "settings.json").read_text(encoding="utf-8")
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit import progress

    groups = [g.id for g in project.groups]
    t0 = time.time()
    beating = threading.Event()
    threading.Thread(target=bring_in._heartbeat, args=(beating,), daemon=True).start()

    def inside(e) -> None:
        # "model:<group>:<model>": which group the models are on, as the step's fraction.
        parts = (e.step or "").split(":")
        if len(parts) == 3 and parts[0] == "model" and parts[1] in groups:
            done = groups.index(parts[1]) / max(len(groups), 1)
            name = next((g.name for g in project.groups if g.id == parts[1]), parts[1])
            engine = ENGINES.get(parts[2], (parts[2],))[0]
            bring_in._emit(step="models", fraction=0.1 + 0.85 * done, message=f"{name}: training {engine}")
        else:
            bring_in._emit(detail=e.message)

    with warnings.catch_warnings(record=True) as caught, progress.reporting(inside):
        warnings.simplefilter("always")
        bring_in._emit(step="load", fraction=0.0, message="Reading the prepared fields")
        settings = pl.load_settings()
        sup = pl.load_cleaned_data_for_modeling(settings)
        bring_in._emit(step="split", fraction=0.05, message="Splitting the sales into folds")
        pl.write_canonical_splits(sup, settings, verbose=False)
        bring_in._emit(step="models", fraction=0.1, message="Training the models")
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
    beating.set()
    bring_in._emit(step="receipt", fraction=0.97, message="Counting")
    from openavmkit.model_runner import _get_max_ratio_study_trim, academic_metrics

    per, sold = _counts(sup.universe, sup.sales["key"].tolist())
    cls = ratio.classes(project)
    targets = project.ratio.targets
    out: list[ModelGroupResult] = []
    for g in project.groups:
        r = results.get(g.id)
        n = sold.get(g.id, 0)
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
        sets = _sets(r, cls[g.id], targets)
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
                academic=_rows(untrimmed, ACADEMIC, ACADEMIC, drop=("assessor",)),
                academic_trimmed=_rows(trimmed, ACADEMIC, ACADEMIC, drop=("assessor",)),
                timings=_rows(
                    r.benchmark.df_time, ("total", "param", "train", "test", "univ", "chd"), drop=("assessor",)
                ),
            )
        )
    mine = [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]
    s = json.loads(settings_text)
    main = s.get("modeling", {}).get("models", {}).get("main", {})
    receipt = ModelReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        models=[
            m for m in s.get("modeling", {}).get("instructions", {}).get("main", {}).get("run", []) if m in ENGINES
        ],
        variables=list(main.get("lightgbm", {}).get("ind_vars") or main.get("default", {}).get("ind_vars") or []),
        groups=out,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": settings_hash(s, pdir)}), encoding="utf-8")
    final = out_dir(pdir)
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    modeled = sum(1 for g in out if g.sets)
    bring_in._emit(step="done", fraction=1.0, message=f"{modeled} of {len(out)} model groups modeled")


# ---------- The step's state ----------


def settings_key(settings: dict, project_dir: Path) -> dict:
    """What a try depends on: the Prepare run it starts from, and the variables and models."""
    r, _ = prepare._ran(project_dir)
    m = settings.get("modeling", {})
    return {
        "prepare": r.ran_at if r else None,
        "models": m.get("models", {}).get("main"),
        "run": m.get("instructions", {}).get("main"),
        "study": settings.get("analysis", {}).get("ratio_study", {}).get("study_set_predictions"),
    }


def settings_hash(settings: dict, project_dir: Path) -> str:
    text = json.dumps(settings_key(settings, project_dir), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class ModelView(BaseModel):
    status: Literal["never", "running", "failed", "stopped", "done"]
    job: bring_in.Job | None
    receipt: ModelReceipt | None
    stale: bool = Field(description="Prepare ran again, or a variable or model changed, since the try.")
    blocked: list[str]


def _ran(project_dir: Path) -> tuple[ModelReceipt | None, dict | None]:
    base = out_dir(project_dir)
    if not (base / "receipt.json").is_file():
        return None, None
    ran = (
        json.loads((base / "settings.json").read_text(encoding="utf-8")) if (base / "settings.json").is_file() else None
    )
    try:
        return ModelReceipt.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran
    except ValueError:
        return None, None  # an older receipt: try again


def view(project, project_dir: Path) -> ModelView:
    r, ran = _ran(project_dir)
    j = bring_in.job(project.id, MODULE)
    from oakbox import projects

    now = settings_hash(projects.base_settings(project), project_dir)
    blocked = []
    p = prepare.view(project, project_dir)
    if not p.accepted:
        blocked.append("Press Looks right on What changed first: the models start from the prepared fields.")
    elif not [v for v in variables(project, project_dir) if v.chosen]:
        blocked.append("Choose at least one variable.")
    return ModelView(
        status=j.status if j else ("done" if r else "never"),
        job=j,
        receipt=r,
        stale=bool(r and ran and ran.get("hash") != now),
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

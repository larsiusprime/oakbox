"""Step 5 continues: the models (SPEC F9, slice 1). Which variables, which models, a try, and how they did.

A try is OpenAVMKit's notebook 3 up to `try_models`: the prepared hand-off (out/2-clean-sup.pickle, written by
Prepare the fields), the canonical splits, then every model on every model group, main models only (no vacant
models: OAK box values the whole parcel). It runs in a process of its own (`python -m oakbox.model <project id>`)
and keeps each group's benchmark as the receipt (out/oakbox/model/): the holdout figures (each sale predicted by a
model that never saw it, by 5-fold nested cross-validation) for each model and the ensemble, and the roll's own
value on the same sales beside them.

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

BUILDING = [
    "bldg_units",
    "bldg_stories",
    "bldg_rooms_bed",
    "bldg_rooms_bath",
    "bldg_rooms_bath_full",
    "bldg_rooms_bath_half",
]
LOCATION = ["latitude_norm", "longitude_norm", "polar_radius", "polar_angle"]
CENSUS = ["median_income", "total_population", "median_g_rent", "median_c_rent"]
# Names for fields the data dictionary doesn't name.
NAMES = {"polar_radius": "Distance from the centre", "polar_angle": "Direction from the centre"}

Kind = Literal["big_five", "building", "location", "public", "category"]


class ModelState(BaseModel):
    variables: list[str] | None = Field(default=None, description="The variables chosen; None: every one found.")
    models: list[str] | None = Field(default=None, description="The engines chosen; None: Choose for me.")


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
    trees_only: bool = Field(description="A category, or a number with blanks: linear models leave it out.")


def _universe_path(project_dir: Path) -> Path:
    return project_dir / "out" / "look" / "2-clean-universe.parquet"


def _candidates(columns: list[str], units: str | None, locations: list[str]) -> list[tuple[str, Kind]]:
    u = "sqft" if units == "imperial" else "sqm"
    e = "ft" if units == "imperial" else "m"
    age = "bldg_effective_age_years" if "bldg_effective_age_years" in columns else "bldg_age_years"
    big = [f"bldg_area_finished_{u}", f"land_area_{u}", age, "bldg_quality_num", "bldg_condition_num"]
    public = [f"elevation_mean_{e}", "slope_mean_deg", *sorted(c for c in columns if c.startswith("dist_to_")), *CENSUS]
    kinds: list[tuple[list[str], Kind]] = [
        (big, "big_five"),
        (BUILDING, "building"),
        (LOCATION, "location"),
        (public, "public"),
        (locations, "category"),
    ]
    return [(f, kind) for fields, kind in kinds for f in fields if f in columns]


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
def _scan(path: str, mtime: float, units: str | None) -> tuple[tuple[str, str, bool, int, int], ...]:
    """(field, kind, numeric, parcels with a value, blanks) for each candidate in the prepared universe."""
    import pandas as pd
    import pyarrow.parquet as pq

    columns = pq.ParquetFile(path).schema_arrow.names
    project_dir = Path(path).parents[2]
    # Only the column names matter to which location fields there are.
    locations = clean._locations(project_dir, pd.DataFrame(columns=columns))
    found = _candidates(columns, units, locations)
    df = pd.read_parquet(path, columns=[f for f, _ in found])
    out = []
    for f, kind in found:
        s = df[f]
        numeric = kind != "category" and pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        blanks = int(s.isna().sum())
        out.append((f, kind if numeric or kind == "category" else "category", numeric, len(s) - blanks, blanks))
    return tuple(out)


def variables(project, project_dir: Path) -> list[Variable]:
    path = _universe_path(project_dir)
    if not path.is_file():
        return []
    names = clean._names() | NAMES
    chosen = project.model.variables
    out = []
    for f, kind, numeric, parcels, blanks in _scan(str(path), path.stat().st_mtime, project.units):
        out.append(
            Variable(
                field=f,
                name=names.get(f) or f,
                kind=kind,  # type: ignore[arg-type]
                numeric=numeric,
                parcels=parcels,
                blanks=blanks,
                chosen=chosen is None or f in chosen,
                trees_only=not numeric or blanks > 0,
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
            "instructions": {"main": {"run": chosen, "ensemble": {"type": "median"}}},
            "models": {"main": entries},
        }
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
    )


class ModelPatch(BaseModel):
    variables: list[str] | None = None
    every_variable: bool | None = Field(default=None, description="True: back to every variable found.")
    models: list[str] | None = None
    choose_for_me: bool | None = Field(default=None, description="True: back to Choose for me.")


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


# ---------- The receipt ----------


class ModelFigures(BaseModel):
    model: str
    name: str
    sales: int
    median: float | None
    cod: float | None
    prd: float | None
    prb: float | None
    vei: float | None
    vei_significance: float | None
    trimmed_sales: int | None
    cod_trimmed: float | None
    prb_trimmed: float | None
    level_ok: bool | None = Field(default=None, description="The median within the level range.")
    cod_ok: bool | None = Field(default=None, description="The COD within its category's range.")
    cod_low: bool = Field(default=False, description="Under its category's range: suspiciously even.")
    prb_ok: bool | None = Field(default=None, description="The PRB within its good range (None: in between).")
    prb_bad: bool = Field(default=False, description="The PRB outside its unacceptable range.")


class ModelGroupResult(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    sales: int
    models: list[ModelFigures] = Field(description="Each model and the ensemble, on the holdout.")
    roll: ModelFigures | None = Field(
        description="The roll's own value on the same holdout sales (it may have seen them: the models didn't)."
    )
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


def _figures(model: str, row, cls: str, targets: ratio.Targets) -> ModelFigures:
    median, cod, prb = _num(row.get("median_ratio")), _num(row.get("cod")), _num(row.get("prb"))
    sales = int(_num(row.get("count_sales")) or 0)
    judged = sales >= targets.min_sales and cls != "none"
    rng = targets.cod(cls)
    trimmed = _num(row.get("count_trim"))
    name = (
        "Ensemble"
        if model == "ensemble"
        else "The roll's value"
        if model == "assessor"
        else ENGINES.get(model, (model,))[0]
    )
    return ModelFigures(
        model=model,
        name=name,
        sales=sales,
        median=median,
        cod=cod,
        prd=_num(row.get("prd")),
        prb=prb,
        vei=_num(row.get("vei")),
        vei_significance=_num(row.get("vei_sig")),
        trimmed_sales=int(trimmed) if trimmed is not None else None,
        cod_trimmed=_num(row.get("cod_trim")),
        prb_trimmed=_num(row.get("prb_trim")),
        level_ok=(targets.level_low <= median <= targets.level_high) if judged and median is not None else None,
        cod_ok=(rng.low <= cod <= rng.high) if judged and rng and cod is not None else None,
        cod_low=bool(judged and rng and cod is not None and 0 <= cod < rng.low),
        prb_ok=(True if abs(prb) <= targets.prb_good else False if abs(prb) > targets.prb_bad else None)
        if judged and prb is not None
        else None,
        prb_bad=bool(judged and prb is not None and abs(prb) > targets.prb_bad),
    )


def _rows(df) -> dict[str, dict]:
    if df is None or len(df) == 0:
        return {}
    return {str(k): dict(r) for k, r in df.to_dict(orient="index").items()}


def _roll(r, group: str, settings: dict, values: dict[str, float]) -> dict | None:
    """The roll's value on the sales the models were judged on, as OpenAVMKit's ratio study figures them."""
    from openavmkit.model_runner import _get_max_ratio_study_trim
    from openavmkit.modeling import PredictionResults

    mr = r.model_results.get("ensemble") or next(iter(r.model_results.values()), None)
    pt = getattr(mr, "pred_test", None)
    if pt is None or getattr(pt, "df", None) is None or "key" not in pt.df:
        return None
    df = pt.df.copy()
    df["__roll"] = df["key"].astype(str).map(values)
    rs = PredictionResults(pt.dep_var, [], "__roll", df, _get_max_ratio_study_trim(settings, group)).ratio_study
    return {
        "count_sales": rs.count,
        "median_ratio": rs.median_ratio,
        "cod": rs.cod,
        "prd": rs.prd,
        "prb": rs.prb,
        "count_trim": rs.count_trim,
        "cod_trim": rs.cod_trim,
        "prb_trim": rs.prb_trim,
    }


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

    per, sold = _counts(sup.universe, sup.sales["key"].tolist())
    u = sup.universe
    values = dict(zip(u["key"].astype(str), u[ratio.FIELD], strict=False)) if ratio.FIELD in u else dict[str, float]()
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
                    models=[],
                    roll=None,
                    skipped=f"{n:,} {'sale' if n == 1 else 'sales'}: too few to model"
                    if n < 15
                    else "No model produced values for it",
                )
            )
            continue
        test = _rows(r.benchmark.df_stats_test)
        figs = [_figures(m, row, cls[g.id], targets) for m, row in test.items() if m != "assessor"]
        figs.sort(key=lambda f: (f.model != "ensemble", list(ENGINES).index(f.model) if f.model in ENGINES else 99))
        held = _roll(r, g.id, settings, values) if values else None
        roll = _figures("assessor", held, cls[g.id], targets) if held else None
        out.append(
            ModelGroupResult(
                id=g.id, name=g.name, color=g.color, parcels=per.get(g.id, 0), sales=n, models=figs, roll=roll
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
    modeled = sum(1 for g in out if g.models)
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

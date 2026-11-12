"""Model values › Finalize and Model values (SPEC F9, slice 2): the values that ship. OpenAVMKit's `finalize_models`
on the prepared fields, as Try them runs (the same folds, nearby averages and saved tuning), with the groups Small
groups leaves unvalued skipped; then the values checked as step 4 checks the roll's, on three sets of sales:

- **out of fold** (`oof`): each sale valued by a model that never saw it (the cross-validation's fold models): every
  sale, honestly; what How they did shows.
- **held out** (`held`): the sales the final models never trained on (under cross-validation, those after the
  valuation date; with a single split, its test sales), valued by the final models.
- **as valued** (`valued`): every sale, valued by the final models, most of which they trained on: the values as
  they ship, but flattering.

The roll's values beside each, on the same sales. Values below zero never ship: blank, and counted. Writes
out/oakbox/final/: the receipt, the studies, and values.parquet (each parcel's model value, beside the roll's).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import model, ratio, smallgroups, steps
from oakbox.datafiles import BaseModel
from oakbox.valuesets import ROLL, loaded_value_sets, value_field

if TYPE_CHECKING:
    from oakbox.projects import Project

MODULE = "final"
VALUE = "market_value"  # OpenAVMKit's name for the ensemble's value
SetKey = Literal["oof", "held", "valued"]
SETS: tuple[SetKey, ...] = ("oof", "held", "valued")
# The per-sale value of each set, as the studies take it (a sale's own column wins over its parcel's).
FIELDS: dict[SetKey, str] = {"oof": "oak_oof", "held": "oak_held", "valued": VALUE}
ROLLS: dict[SetKey, str] = {k: f"oak_roll_{k}" for k in SETS}  # the roll's, on the sales each set values
BIG_CHANGE = 0.20  # a value this far from the roll's, either way, is counted


def out_dir(project_dir: Path) -> Path:
    return steps.out_dir(project_dir, MODULE)


class SetResult(BaseModel):
    key: SetKey
    sales: int = Field(description="Sales in the window with a value in this set.")
    model: ratio.FieldResult | None = Field(description="The model values' study; None: no sales.")
    roll: ratio.FieldResult | None = Field(description="The roll's on the same sales; None: no roll loaded.")


class GroupValues(BaseModel):
    id: str
    name: str
    color: str
    parcels: int
    valued: int = Field(description="Parcels given a model value.")
    unvalued: str | None = Field(description="Why it has no values: not modeled, left unvalued, too few sales.")
    blanked: int = Field(description="Parcels valued below zero: left blank.")
    median_change: float | None = Field(description="The median of model value ÷ the roll's, less 1.")
    up: int = Field(description=f"Parcels valued over {BIG_CHANGE:.0%} above the roll.")
    down: int = Field(description=f"Parcels valued over {BIG_CHANGE:.0%} below the roll.")
    total: float | None = Field(description="The model values summed.")
    roll_total: float | None = Field(description="The roll's values summed, on the same parcels.")


class FinalReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    start: dt.date
    end: dt.date
    price: Literal["sold", "time_adjusted"]
    trim: bool
    roll: str | None = Field(description="The existing values beside the model's (their name); None: none loaded.")
    sets: list[SetResult]
    groups: list[GroupValues]
    notes: list[str] = Field(default_factory=list)


def _roll(project: Project) -> tuple[str, str] | None:
    """The existing values set beside the model's: the roll if loaded, else the first loaded. (field, name)"""
    loaded = loaded_value_sets(project)
    if not loaded:
        return None
    v = next((x for x in loaded if x.id == ROLL), loaded[0])
    return value_field(v.id), v.name


def _look(keys, table: dict[str, float]):
    """Each key's number in `table` (blank where it has none), as a column beside `keys`."""
    import pandas as pd

    return pd.Series([table.get(str(k), float("nan")) for k in keys], index=keys.index, dtype=float)


def unvalued_groups(project: Project, project_dir: Path) -> list[str]:
    """The model groups Small groups leaves unvalued (flagged, and not modeled anyway)."""
    return [g.id for g in smallgroups.view(project, project_dir).groups if g.choice == "leave"]


def settings_key(project: Project, project_dir: Path) -> dict:
    """What it depends on: the try it finalizes, the groups left unvalued, the roll it compares with, and the
    study's calls (Check my values')."""
    return {
        "try": model.STEP.ran_at(project_dir),
        "unvalued": unvalued_groups(project, project_dir),
        "roll": _roll(project),
        **ratio.study_calls(project, project_dir),
    }


def _skip(settings: dict, groups: list[str]) -> None:
    """Every model skipped in the groups left unvalued: OpenAVMKit then values none of their parcels."""
    main = settings.setdefault("modeling", {}).setdefault("instructions", {}).setdefault("main", {})
    run = [m for m in main.get("run", []) if m != "ensemble"]
    skip = main.setdefault("skip", {})
    for g in groups:
        skip[g] = sorted(set(skip.get(g, [])) | set(run))


def _changes(values, roll_field: str | None, gid: str) -> tuple[float | None, int, int, float | None, float | None]:
    import numpy as np

    mine = values[values["model_group"].astype(str) == gid]
    v = mine[VALUE].to_numpy(dtype=float)
    total = float(np.nansum(v)) if np.isfinite(v).any() else None
    if roll_field is None or roll_field not in mine:
        return None, 0, 0, total, None
    r = mine[roll_field].to_numpy(dtype=float)
    both = np.isfinite(v) & np.isfinite(r) & (r > 0)
    if not both.any():
        return None, 0, 0, total, None
    q = v[both] / r[both]
    return (
        float(np.median(q) - 1),
        int((q > 1 + BIG_CHANGE).sum()),
        int((q < 1 - BIG_CHANGE).sum()),
        total,
        float(r[both].sum()),
    )


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    import numpy as np
    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    if not (steps.handoff(pdir, "2-clean")).is_file():
        raise RuntimeError("Prepare the fields first: the models start from what it writes.")
    tmp = steps.workdir(out_dir(pdir))
    from oakbox import clean

    steps.note_excluded(tmp, clean.excluded(project))
    depends = STEP.now(project, pdir)
    s: ratio.RatioState = project.ratio
    start, end, _ = ratio.window(project, project_dir=pdir)
    roll = _roll(project)
    leave = unvalued_groups(project, pdir)
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit import progress
    from openavmkit.data import SalesUniversePair, read_split_keys
    from openavmkit.value_studies import run_value_field_studies

    groups = [g.id for g in project.groups]
    modeled = model.to_model(project, pdir)
    own = {g: {e.key: e.name for e in model.group_models(project, pdir, g)} for g in groups if g in modeled}
    t0 = time.time()

    def inside(e) -> None:
        parts = (e.step or "").split(":")
        if len(parts) == 3 and parts[0] == "model" and parts[1] in groups:
            done = groups.index(parts[1]) / max(len(groups), 1)
            name = next((g.name for g in project.groups if g.id == parts[1]), parts[1])
            engine = own.get(parts[1], {}).get(parts[2]) or model.ENGINES.get(parts[2], (parts[2],))[0]
            # A part the user can skip (Skip on the progress): this model in this group.
            steps.emit(step="models", fraction=0.1 + 0.75 * done, message=f"{name}: training {engine}", part=e.step)
        else:
            steps.emit(detail=e.message)

    skips, skip_check = model.skippable(pdir, MODULE)
    with (
        warnings.catch_warnings(record=True) as caught,
        progress.reporting(inside, skip=skip_check),
        steps.heartbeat(),
    ):
        warnings.simplefilter("always")
        sup, settings, dropped, gnames = model.for_models(project, modeled, own)
        _skip(settings, leave)
        steps.emit(step="models", fraction=0.1, message="Training the final models")
        try:
            results = pl.finalize_models(
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
            raise model.explain_crash(e, project, pdir, {}, sup, settings, gnames, own) from e
        model.release_workers()

        steps.emit(step="values", fraction=0.86, message="Collecting the values")
        universe = sup.universe.copy()
        values = pd.DataFrame({"key": universe["key"].astype(str), "model_group": universe["model_group"].astype(str)})
        sales = sup.sales.copy()
        ks = sales["key_sale"].astype(str)
        made: dict[str, float] = {}  # parcel -> its final value
        oof: dict[str, float] = {}  # sale -> its out-of-fold value
        held: set[str] = set()  # the sales the final models never trained on
        for g, r in results.items():
            if g in leave or r is None or "ensemble" not in r.model_results:
                continue
            e = r.model_results["ensemble"]
            p = e.field_prediction
            made.update(zip(e.df_universe["key"].astype(str), e.df_universe[p].astype(float), strict=True))
            oof.update(zip(e.df_test["key_sale"].astype(str), e.df_test[p].astype(float), strict=True))
            _, train = read_split_keys(g)
            trained = set(map(str, train))
            held.update(k for k in e.df_test["key_sale"].astype(str) if k not in trained)
        v = _look(values["key"], made)
        values[VALUE] = v.where(~(v < 0))
        values["below_zero"] = (v < 0).to_numpy()
        if roll is not None and roll[0] in universe:
            values[roll[0]] = np.asarray(pd.to_numeric(universe[roll[0]], errors="coerce"), dtype=float)
        # Per sale: out of fold; and the final value on the sales it never trained on (held out).
        by_key = dict(zip(values["key"], values[VALUE].astype(float), strict=True))
        sales["oak_oof"] = _look(ks, oof)
        sales["oak_held"] = _look(sales["key"], by_key).where(ks.isin(list(held)))
        _keep_sales(sales, universe, tmp)
        steps.emit(step="comps", fraction=0.87, message="Finding each sale's comparable sales")
        _fit_comps(project, pdir, tmp)
        universe[VALUE] = values[VALUE].to_numpy()
        # The studies want each field on the parcels too, blank: a blank on a sale would otherwise be filled with its
        # parcel's (OpenAVMKit's hydration), and every sale would be "held out".
        universe["oak_oof"] = np.nan
        universe["oak_held"] = np.nan
        study_fields = [FIELDS[k] for k in SETS]
        if roll is not None and roll[0] in universe:
            # The roll on the same sales as each set: those the model values there, so the two compare like for like.
            on_sale = _look(sales["key"], dict(zip(values["key"], values[roll[0]].astype(float), strict=True)))
            for k in SETS:
                mine = _look(sales["key"], by_key) if k == "valued" else sales[FIELDS[k]]
                sales[ROLLS[k]] = on_sale.where(mine.notna())
                universe[ROLLS[k]] = np.nan
            # And the roll itself, for its horizontal equity: every parcel's value, sold or not.
            study_fields += [ROLLS[k] for k in SETS] + [roll[0]]
        steps.emit(step="study", fraction=0.9, message="Checking the values against the sales")
        cls = ratio.classes(project)
        studies = run_value_field_studies(
            SalesUniversePair(sales=sales, universe=universe),
            settings,
            study_fields,
            start_date=str(start),
            end_date=str(end),
            sale_field="sale_price" if s.price == "sold" else "sale_price_time_adj",
            trim_outliers=s.trim,
            median_ci="iaao",
            standards=ratio.engine_standards(project),
            classes={g: (None if c == "none" else c) for g, c in cls.items()},
            outpath=str(tmp / "studies"),
        )

    steps.emit(step="receipt", fraction=0.97, message="Counting")
    # For the map: where each parcel is, and its finished area (value per area).
    area = "bldg_area_finished_sqft" if project.units == "imperial" else "bldg_area_finished_sqm"
    for c in ("latitude", "longitude", area):
        if c in universe:
            values[c] = np.asarray(pd.to_numeric(universe[c], errors="coerce"), dtype=float)
    if area in values:
        values = values.rename(columns={area: "area"})
    values.to_parquet(tmp / "values.parquet", index=False)
    shown = [g for g in project.groups if g.id in modeled]

    def result(field: str, label: str) -> ratio.FieldResult | None:
        study = studies.get(field)
        if not study or not int((study["overall"].get("ratio") or {}).get("count") or 0):
            return None
        path = tmp / "studies" / f"{field}.sales.parquet"
        table = pd.read_parquet(path) if path.is_file() else None
        if table is None:
            table = pd.DataFrame({c: [] for c in ("model_group", "sale_price", "ratio", "trimmed")})
        return ratio.FieldResult(
            field=field,
            name=label,
            groups=[
                ratio.study_view(g.id, g.name, g.color, cls.get(g.id), study["groups"][g.id], table)
                for g in shown
                if g.id in study["groups"]
            ],
            overall=ratio.study_view("", "All model groups", "#888888", None, study["overall"], table),
            trimmed=[],
        )

    def spread(field: str | None) -> dict[str, tuple[int | None, float | None]]:
        """Horizontal equity is of the parcels' values, not the sales': the same whichever sales judge them. Group
        ("" for all) -> (equity clusters, median CHD)."""
        study = studies.get(field or "")
        if not study:
            return {}
        out = {
            gid: ((g.get("horizontal") or {}).get("clusters"), (g.get("horizontal") or {}).get("median_chd"))
            for gid, g in study["groups"].items()
        }
        h = study["overall"].get("horizontal") or {}
        out[""] = (h.get("clusters"), h.get("median_chd"))
        return out

    def with_spread(res: ratio.FieldResult | None, by: dict[str, tuple[int | None, float | None]]):
        if res is not None:
            for g in [*res.groups, res.overall]:
                if g.id in by:
                    g.clusters, g.median_chd = by[g.id]
        return res

    model_spread = spread(VALUE)
    roll_spread = spread(roll[0] if roll else None)
    sets = []
    for k in SETS:
        m = with_spread(result(FIELDS[k], "Model values"), model_spread)
        r = with_spread(result(ROLLS[k], roll[1]), roll_spread) if roll is not None else None
        sets.append(SetResult(key=k, sales=m.overall.sales + m.overall.trimmed if m else 0, model=m, roll=r))

    per = values.groupby("model_group").size().to_dict()
    tried = model.STEP.state(project, pdir, check=False).receipt
    why = {g.id: g.skipped for g in tried.groups} if tried else {}
    out = []
    for g in project.groups:
        mine = values["model_group"] == g.id
        n_valued = int(values.loc[mine, VALUE].notna().sum())
        med, up, down, total, roll_total = _changes(values, roll[0] if roll else None, g.id)
        reason = (
            model.NOT_MODELED
            if g.id not in modeled
            else "Left unvalued (Small groups)"
            if g.id in leave
            else (why.get(g.id) or "No model produced values for it")
            if not n_valued
            else None
        )
        out.append(
            GroupValues(
                id=g.id,
                name=g.name,
                color=g.color,
                parcels=int(per.get(g.id, 0)),
                valued=n_valued,
                unvalued=reason,
                blanked=int(values.loc[mine, "below_zero"].sum()),
                median_change=med,
                up=up,
                down=down,
                total=total,
                roll_total=roll_total,
            )
        )
    mine_notes = steps.engine_notes(caught)
    receipt = FinalReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        start=start,
        end=end,
        price=s.price,
        trim=s.trim,
        roll=roll[1] if roll else None,
        sets=sets,
        groups=out,
        notes=[
            *model.skipped_notes(project, own, skips),
            *dropped,
            *list(dict.fromkeys(str(w.message) for w in mine_notes if model.SKIPPED_BY_ENGINE not in str(w.message))),
        ][:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": depends}), encoding="utf-8")
    steps.publish(tmp, out_dir(pdir))
    valued = sum(g.valued for g in out)
    steps.emit(step="done", fraction=1.0, message=f"{valued:,} of {len(values):,} parcels valued")


# ---------- The map ----------


SALES = "sales.parquet"  # every valid sale of a valued group, its out-of-fold value and its fields (Outliers)


def _keep_sales(sales, universe, tmp: Path) -> None:
    """For Outliers: each valid sale the models valued out of fold, with every field of its parcel (as at its sale),
    the time-adjusted price the ratios are on (`oak_price`), its value (`oak_oof`) and ratio (`oak_ratio`)."""
    import numpy as np
    import pandas as pd
    from openavmkit.data import SalesUniversePair, get_hydrated_sales_from_sup

    t = get_hydrated_sales_from_sup(SalesUniversePair(sales=sales, universe=universe))
    t = pd.DataFrame(t.drop(columns=[c for c in ("geometry",) if c in t.columns]))
    # The models value at the valuation date, as the time-adjusted prices they learn from: sales of every year are
    # compared with that (the study's own price setting is about the window's sales only).
    field = "sale_price_time_adj" if "sale_price_time_adj" in t else "sale_price"
    t["oak_price"] = pd.to_numeric(t[field], errors="coerce")
    t["oak_ratio"] = t["oak_oof"] / t["oak_price"].where(t["oak_price"] > 0)
    keep = t["oak_ratio"].notna() & np.isfinite(t["oak_ratio"])
    if "valid_sale" in t:
        keep &= t["valid_sale"].astype("boolean").fillna(False)
    t = pd.DataFrame(t[keep]).reset_index(drop=True)
    for c in t.columns:  # mixed columns (objects of numbers and text) as text: Parquet takes one type a column
        if t[c].dtype == object:
            t[c] = t[c].map(lambda v: None if v is None or (isinstance(v, float) and v != v) else str(v))
    t.to_parquet(tmp / SALES, index=False)


def _fit_comps(project, pdir: Path, tmp: Path) -> None:
    """Each valued group's comp trees (OpenAVMKit's layered comps), for Outliers: fitted here, while the run is
    running anyway, so Outliers opens without waiting for them."""
    import pandas as pd

    from oakbox import outliers

    t = pd.read_parquet(tmp / SALES)
    t["model_group"] = t["model_group"].astype(str)
    for g in sorted(set(t["model_group"])):
        outliers.fit_comps(project, pdir, t, g, tmp / outliers.COMPS_DIR / f"{g}.json")


class ParcelPoints(BaseModel):
    """Every parcel with a place, as columns (compact for half a million): the map draws them as they come."""

    groups: list[str] = Field(description="Model group ids; `group` indexes into it.")
    lon: list[float]
    lat: list[float]
    group: list[int]
    value: list[float | None] = Field(description="The model value; null: none (unvalued, or below zero).")
    roll: list[float | None] = Field(description="The roll's value; null: none, or no roll loaded.")
    area: list[float | None] = Field(description="Finished area; null: none.")
    key: list[str]


def parcel_points(project_dir: Path) -> ParcelPoints | None:
    import numpy as np
    import pandas as pd

    path = out_dir(project_dir) / "values.parquet"
    if not path.is_file():
        return None
    v = pd.read_parquet(path)
    if "latitude" not in v or "longitude" not in v:
        return ParcelPoints(groups=[], lon=[], lat=[], group=[], value=[], roll=[], area=[], key=[])
    v = cast(pd.DataFrame, v[v["latitude"].notna() & v["longitude"].notna()])
    groups = sorted(set(v["model_group"].astype(str)))
    at = {g: i for i, g in enumerate(groups)}
    rolls = [c for c in v.columns if c.endswith("_market_value")]

    def col(name: str | None) -> list[float | None]:
        if name is None or name not in v:
            return [None] * len(v)
        x = np.round(np.asarray(v[name], dtype=float), 2)
        return [None if not np.isfinite(a) else float(a) for a in x]

    return ParcelPoints(
        groups=groups,
        lon=np.round(np.asarray(v["longitude"], dtype=float), 6).tolist(),
        lat=np.round(np.asarray(v["latitude"], dtype=float), 6).tolist(),
        group=[at[g] for g in v["model_group"].astype(str)],
        value=col(VALUE),
        roll=col(rolls[0] if rolls else None),
        area=col("area"),
        key=v["key"].astype(str).tolist(),
    )


def sale_points(project_dir: Path, which: SetKey, group: str | None) -> list[ratio.MapPoint]:
    """Each sale a set judges the values on, with its place and ratio (out of fold, held out, or as valued)."""
    import pandas as pd

    path = out_dir(project_dir) / "studies" / f"{FIELDS[which]}.sales.parquet"
    if not path.is_file():
        return []
    t = pd.read_parquet(path)
    if "latitude" not in t or "longitude" not in t:
        return []
    if group:
        t = cast(pd.DataFrame, t[t["model_group"].astype(str) == group])
    t = cast(pd.DataFrame, t[t["latitude"].notna() & t["longitude"].notna()])
    return [
        ratio.MapPoint(lat=float(a), lon=float(b), ratio=float(r), price=float(p), value=float(x), trimmed=bool(m))
        for a, b, r, p, x, m in zip(
            t["latitude"], t["longitude"], t["ratio"], t["sale_price"], t["value"], t["trimmed"], strict=True
        )
    ]


# ---------- The step's state ----------


class FinalView(steps.RunView):
    receipt: FinalReceipt | None
    accepted: bool


STEP = steps.Step(
    MODULE,
    "Finalize",
    FinalReceipt,
    key=settings_key,
    after=model.STEP,
    again="Finalize again first: something changed since.",
)


def blocked(project: Project, project_dir: Path) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    return model.not_installed(model.engines_used(project, project_dir))


def view(project: Project, project_dir: Path) -> FinalView:
    stop = blocked(project, project_dir)
    s = STEP.state(project, project_dir, check=not stop)
    from oakbox import clean

    return FinalView(
        status=s.status,
        job=s.job,
        receipt=s.receipt,
        stale=s.stale,
        blocked=stop,
        accepted=s.accepted,
        excluded_since=steps.excluded_since(out_dir(project_dir), clean.excluded(project)) if s.receipt else 0,
    )


def start(project: Project, project_dir: Path) -> None:
    STEP.start(project.id, project_dir, blocked(project, project_dir))


def accept(project: Project, project_dir: Path) -> None:
    if blocked(project, project_dir):
        raise ValueError(STEP.again)
    STEP.accept(project, project_dir)


if __name__ == "__main__":
    steps.main(run)

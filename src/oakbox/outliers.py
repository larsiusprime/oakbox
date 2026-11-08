"""6. Models › Outliers (SPEC F9, slice 3): the sales the models valued furthest from their price, and why.

After Finalize, per model group: every valid sale's out-of-fold value (what the models said without having seen it,
`final.SALES`), the sales outside a ratio band (OpenAVMKit's 0.75-1.25, as its notebook's `identify_outliers`) the
outliers. For one: its comparable sales, and how it's unlike the others (each field, where it sits among the group's
sales and against its comps). For the group: what the misses have in common (each field, how much of the models'
error lines up with it, and whether it beats chance), and whether the errors cluster on the map.

The user's call on each says why it's off, and goes where it belongs:
- the sale isn't a market sale: Check sales' Exclude, with the reason;
- the data is wrong or missing: a patch (projects.Patch, OpenAVMKit's tweak), kept and exported;
- it's in the wrong group: the parcel moved by hand (projects.ModelGroup.keys);
- the model misses something: a note, beside what the misses have in common.
"""

from __future__ import annotations

import datetime as dt
import math
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import final, model
from oakbox.datafiles import BaseModel
from oakbox.projects import OutlierCall, OutlierWhy, Patch, Project

if TYPE_CHECKING:
    import pandas as pd

COMPS = 5
MAX_UNLIKE = 40
Reason = Literal[
    "related", "multi_parcel", "partial", "wrong_price", "distressed", "changed", "not_open_market", "other"
]
REASONS: dict[str, str] = {
    "related": "related parties",
    "multi_parcel": "sold with other parcels",
    "partial": "partial interest",
    "wrong_price": "wrong price",
    "distressed": "foreclosure or short sale",
    "changed": "changed after it sold",
    "not_open_market": "not an open-market sale",
    "other": "other",
}
SKIP = {
    "key",
    "key_sale",
    "key2",
    "key3",
    "geometry",
    "latitude",
    "longitude",
    "latitude_norm",
    "longitude_norm",
    "model_group",
}


# ---------- The sales ----------

_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _sales(project_dir: Path) -> pd.DataFrame | None:
    import pandas as pd

    path = final.out_dir(project_dir) / final.SALES
    if not path.is_file():
        return None
    stamp = path.stat().st_mtime
    hit = _cache.get(str(path))
    if hit and hit[0] == stamp:
        return hit[1]
    t = pd.read_parquet(path)
    t["key"] = t["key"].astype(str)
    t["key_sale"] = t["key_sale"].astype(str)
    t["model_group"] = t["model_group"].astype(str)
    _cache[str(path)] = (stamp, t)
    return t


def _candidates(project: Project, project_dir: Path, t: pd.DataFrame) -> list[model.Variable]:
    """The fields to look through: every variable there can be (in the models or not) the sales have."""
    return [
        v
        for v in model.variables(project, project_dir)
        if v.field in t.columns and v.field not in SKIP and not v.field.endswith("_log")
    ]


def in_model(project: Project, project_dir: Path, group: str) -> set[str]:
    """The fields a group's models use: their lists' variables, and their location stacks."""
    from oakbox import varlists

    lists = varlists.lists(project, project_dir)
    by = {x.id: x for x in lists}
    out: set[str] = set()
    for e in model.group_models(project, project_dir, group, lists):
        if e.list_id and e.list_id in by:
            out |= set(by[e.list_id].variables)
        out |= set(e.locations or [])
    return out


def _outside(t: pd.DataFrame, project: Project):
    o = project.outliers
    return (t["oak_ratio"] < o.low) | (t["oak_ratio"] > o.high)


def _text(v: object) -> str | None:
    """A value in words: thousands separated, at most two decimals, blank as None."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        f = float(v)
        if abs(f) >= 1000:
            return f"{f:,.0f}"
        return f"{f:.2f}".rstrip("0").rstrip(".") if f != int(f) else f"{int(f)}"
    s = str(v)
    if s in ("True", "False"):
        return "yes" if s == "True" else "no"
    return s if s.strip() else None


def _fmt(field: str, v: object) -> str | None:
    """A field's value in words: a year as a year (2018, not 2,018)."""
    if "year" in field and (n := _num(v)) is not None and n == int(n):
        return str(int(n))
    return _text(v)


def _frame(x) -> pd.DataFrame:
    """A selection of rows, as the DataFrame it is (for the type checker)."""
    return cast("pd.DataFrame", x)


def _nums(x) -> pd.Series:
    """A column as floats: blank where not a number."""
    import pandas as pd

    return cast("pd.Series", pd.to_numeric(x, errors="coerce")).astype(float)


def _col(t: pd.DataFrame, c: str) -> list[float | None]:
    """A column's numbers (None where blank or missing)."""
    return [_num(v) for v in t[c]] if c in t else [None] * len(t)


def _num(v: object) -> float | None:
    try:
        f = float(cast(float, v))
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ---------- The list and the map ----------


class OutlierSale(BaseModel):
    key_sale: str
    key: str
    address: str | None
    group: str
    date: str
    sold: float = Field(description="What it sold for.")
    price: float = Field(description="The price, time-adjusted to the valuation date (as the models value).")
    value: float = Field(description="The models' value of it, out of fold (they hadn't seen it).")
    ratio: float
    roll: float | None = Field(description="The roll's value of the parcel, if a roll was loaded.")
    lat: float | None
    lon: float | None
    call: OutlierWhy | None
    note: str
    applied: bool = Field(description="The call is done where it belongs (Apply my calls); false: on the list only.")


class OutlierPoint(BaseModel):
    key_sale: str
    lat: float
    lon: float
    ratio: float
    out: bool = Field(description="Outside the band: an outlier.")


class OutlierGroupCount(BaseModel):
    id: str
    name: str
    sales: int
    outliers: int


class OutlierView(BaseModel):
    ready: bool = Field(description="Finalize has run since Outliers came: the sales and their values are there.")
    groups: list[OutlierGroupCount]
    group: str | None
    low: float
    high: float
    outliers: list[OutlierSale] = Field(description="Worst first: the lowest ratios, then the highest.")
    points: list[OutlierPoint] = Field(description="Every sale of the group with a place: the outliers among them.")
    calls: int = Field(description="Outliers of the group with a call made.")
    pending: list[OutlierWhy] = Field(description="The kinds of call made and not yet applied, in every group.")
    to_apply: int = Field(description="Calls made and not yet applied, in every group (notes on the model aside).")


def _sale(r, project: Project) -> OutlierSale:
    roll = final._roll(project)
    call = project.outliers.calls.get(str(r["key_sale"]))
    return OutlierSale(
        key_sale=str(r["key_sale"]),
        key=str(r["key"]),
        address=_text(r.get("address")),
        group=str(r["model_group"]),
        date=str(r["sale_date"])[:10],
        sold=float(r["sale_price"]),
        price=float(r["oak_price"]),
        value=float(r["oak_oof"]),
        ratio=float(r["oak_ratio"]),
        roll=_num(r.get(roll[0])) if roll else None,
        lat=_num(r.get("latitude")),
        lon=_num(r.get("longitude")),
        call=call.why if call else None,
        note=call.note if call else "",
        applied=bool(call and call.applied),
    )


def view(project: Project, project_dir: Path, group: str | None) -> OutlierView:
    o = project.outliers
    t = _sales(project_dir)
    if t is None:
        return OutlierView(
            ready=False,
            groups=[],
            group=None,
            low=o.low,
            high=o.high,
            outliers=[],
            points=[],
            calls=0,
            pending=[],
            to_apply=0,
        )
    out = _outside(t, project)
    names = {g.id: g.name for g in project.groups}
    groups = [
        OutlierGroupCount(
            id=str(g), name=names.get(str(g)) or str(g), sales=int((t["model_group"] == g).sum()), outliers=int(n)
        )
        for g, n in out.groupby(t["model_group"]).sum().items()
    ]
    order = {g.id: i for i, g in enumerate(project.groups)}
    groups.sort(key=lambda g: order.get(g.id, 99))
    if group not in {g.id for g in groups}:
        group = next((g.id for g in groups if g.outliers), groups[0].id if groups else None)
    fit_missing(project, project_dir, group)  # a run from before the comp trees were saved: made meanwhile
    mine = _frame(t[t["model_group"] == group])
    mine_out = _frame(mine[out[mine.index]])
    low = _frame(mine_out[mine_out["oak_ratio"] < o.low]).sort_values(by="oak_ratio")
    high = _frame(mine_out[mine_out["oak_ratio"] > o.high]).sort_values(by="oak_ratio", ascending=False)
    rows = [_sale(r, project) for _, r in low.iterrows()] + [_sale(r, project) for _, r in high.iterrows()]
    placed = _frame(
        mine[mine["latitude"].notna() & mine["longitude"].notna()] if "latitude" in mine else mine.iloc[0:0]
    )
    points = [
        OutlierPoint(key_sale=str(k), lat=float(a), lon=float(b), ratio=round(float(r), 4), out=bool(x))
        for k, a, b, r, x in zip(
            placed["key_sale"],
            placed["latitude"],
            placed["longitude"],
            placed["oak_ratio"],
            out[placed.index],
            strict=True,
        )
    ]
    return OutlierView(
        ready=True,
        groups=groups,
        group=group,
        low=o.low,
        high=o.high,
        outliers=rows,
        points=points,
        calls=sum(1 for r in rows if r.call),
        pending=pending(project),
        to_apply=sum(1 for c in o.calls.values() if not c.applied and c.why != "model"),
    )


# ---------- One sale: its comps, and how it's unlike the others ----------


class OutlierComp(BaseModel):
    key_sale: str
    key: str
    address: str | None
    date: str
    price: float
    ratio: float
    away: float | None = Field(description="Miles (imperial) or kilometres away.")
    lat: float | None
    lon: float | None
    fields: dict[str, str | None] = Field(description="The compared fields' values, in words.")


class OutlierUnlike(BaseModel):
    field: str
    name: str
    numeric: bool
    this: str | None
    comps: str | None = Field(description="Its comps' median (a number) or most common value (a category).")
    pct: float | None = Field(description="A number: where it sits among the group's sales, 0-100.")
    share: float | None = Field(description="A category: the share of the group's sales with its value.")
    flag: bool = Field(description="It stands out: among the group's extremes, or unlike its comps.")
    in_model: bool


class OutlierPatchField(BaseModel):
    field: str
    name: str
    numeric: bool
    now: str | None


class OutlierCondition(BaseModel):
    field: str
    name: str
    words: str = Field(description='What its comps share in it: "is N0_2", "over 1,306", "1,306 to 1,950".')


class OutlierMember(BaseModel):
    lat: float
    lon: float


class OutlierDetail(BaseModel):
    sale: OutlierSale
    comps: list[OutlierComp] = Field(description="Its comps nearest it on the map (up to 5), for the table.")
    members: list[OutlierMember] = Field(description="Every comp's place, for the map.")
    basis: Literal["impr", "land", "price"] | None = Field(
        description="What the comps are compared on: price per finished area, per land area, price; None: no comps."
    )
    conditions: list[OutlierCondition] = Field(description="What makes them its comps: its comp tree's path.")
    depth: int = Field(description="The conditions kept (each a split of the comp tree).")
    full_depth: int = Field(description="How deep its own path goes: kept fewer when too few other sales were left.")
    n_comps: int = Field(description="Its comps: the sales meeting every condition, it left out.")
    per_area: float | None = Field(description="Their mean price per area (basis impr or land).")
    compared: list[str] = Field(description="The fields the comps are shown with (OutlierComp.fields), in order.")
    mine: dict[str, str | None] = Field(description="The sale's own values of the compared fields, in words.")
    names: dict[str, str]
    comps_say: float | None = Field(description="What the comps say it's worth: their price per area times its own.")
    comps_ratio: float | None = Field(description="The models' median ratio on the comps.")
    unlike: list[OutlierUnlike]
    patchable: list[OutlierPatchField] = Field(description="The parcel's fields a patch can correct, as they are now.")
    groups: list[tuple[str, str]] = Field(description="(id, name) of the groups it can be moved to.")
    units: Literal["mi", "km"]
    at_sale: list[list[str]] = Field(
        default_factory=list,
        description="[column, value]: the sale's own values in the columns only the sales file has (REMODELED, "
        "SALE_TYPE): context, not model variables.",
    )


def _area_field(project: Project) -> str:
    return "bldg_area_finished_sqft" if project.units == "imperial" else "bldg_area_finished_sqm"


def _km(lat1, lon1, lat2, lon2):
    import numpy as np

    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ---------- The comp trees (OpenAVMKit's layered comps: outliers.fit_comp_models) ----------

COMPS_DIR = "comps"  # out/oakbox/final/comps/<group>.json: each valued group's comp trees, made by Finalize
_fitting = threading.Lock()


def comp_features(project: Project, project_dir: Path, group: str) -> list[str]:
    """What a group's comps are alike on: its layered comps model's variables if it has one, else its first
    machine-learning list's (as OpenAVMKit's identify_outliers)."""
    from oakbox import varlists

    lists = varlists.lists(project, project_dir)
    by = {x.id: x for x in lists}
    for e in model.group_models(project, project_dir, group, lists):
        if e.engine == "lcomp" and e.list_id in by:
            return list(by[e.list_id].variables)
    first = varlists.for_group(lists, group, "ml")
    return list(first.variables) if first else []


def _comps_path(project_dir: Path, group: str) -> Path:
    return final.out_dir(project_dir) / COMPS_DIR / f"{group}.json"


def fit_comps(project: Project, project_dir: Path, t: pd.DataFrame, group: str, out: Path) -> None:
    """Fit a group's comp trees on its sales and save them (Finalize; or Outliers, for a run from before)."""
    import json

    from openavmkit.outliers import fit_comp_models

    g = _frame(t[t["model_group"] == group])
    unit = "sqft" if project.units == "imperial" else "sqm"
    m = fit_comp_models(g, comp_features(project, project_dir, group), unit, price_field="oak_price")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(m.to_dict()), encoding="utf-8")
    tmp.replace(out)


def comp_models(project: Project, project_dir: Path, group: str):
    """A group's comp trees: as Finalize saved them, else fitted now (once: a second asker waits for the first)."""
    import json

    from openavmkit.outliers import CompModels

    path = _comps_path(project_dir, group)
    sales = final.out_dir(project_dir) / final.SALES
    with _fitting:
        if not path.is_file() or path.stat().st_mtime < sales.stat().st_mtime:
            t = _sales(project_dir)
            if t is None:
                return None
            fit_comps(project, project_dir, t, group, path)
        return CompModels.from_dict(json.loads(path.read_text(encoding="utf-8")))


def fit_missing(project: Project, project_dir: Path, first: str | None) -> None:
    """In the background: every group's comp trees that aren't there yet (a project finalized before they were made
    there), the one shown first."""
    t = _sales(project_dir)
    if t is None:
        return
    groups = sorted(set(t["model_group"]), key=lambda g: g != first)
    if all(_comps_path(project_dir, g).is_file() for g in groups):
        return

    def work() -> None:
        for g in groups:
            try:
                comp_models(project, project_dir, g)
            except Exception:  # noqa: BLE001 - asked again when the sale is opened, and said there
                pass

    threading.Thread(target=work, daemon=True).start()


def _shared(c: dict) -> str:
    """A field's merged conditions in words (OpenAVMKit's summarize_conditions)."""
    f = c["field"]
    if c["is"] is not None:
        return f"is {_fmt(f, c['is']) or 'blank'}"
    if c["is_not"]:
        vals = [_fmt(f, v) or "blank" for v in c["is_not"]]
        return "isn't " + (vals[0] if len(vals) == 1 else ", ".join(vals[:-1]) + f" or {vals[-1]}")
    lo, hi = c["over"], c["at_most"]
    if lo is not None and hi is not None:
        return f"over {_fmt(f, lo)}, at most {_fmt(f, hi)}"
    return f"over {_fmt(f, lo)}" if lo is not None else f"at most {_fmt(f, hi)}"


# ---------- One sale ----------


def detail(project: Project, project_dir: Path, key_sale: str) -> OutlierDetail:
    from openavmkit.outliers import compare_fields, find_comps, summarize_conditions

    from oakbox import fields as field_names
    from oakbox.errors import NotFound

    t = _sales(project_dir)
    if t is None:
        raise NotFound("Finalize first.")
    hit = t[t["key_sale"] == key_sale]
    if hit.empty:
        raise NotFound(f"No sale {key_sale}.")
    me = hit.iloc[0]
    group = str(me["model_group"])
    g = _frame(t[t["model_group"] == group])
    cands = _candidates(project, project_dir, t)
    used = in_model(project, project_dir, group)
    names = (field_names.names() | field_names.MADE_NAMES) | {v.field: v.name for v in cands}
    area = _area_field(project)
    imperial = project.units == "imperial"
    models = comp_models(project, project_dir, group)
    found = find_comps(models, g, me, min_comps=COMPS) if models is not None else None
    members = _frame(g[g["key_sale"].isin(found.keys)]) if found else g.iloc[0:0]
    away = None
    if _num(me.get("latitude")) is not None and len(members) and "latitude" in members:
        away = _km(float(me["latitude"]), float(me["longitude"]), members["latitude"], members["longitude"])
    if away is not None:
        members = members.assign(_km=away.to_numpy()).sort_values(by="_km")
    compared = [
        f
        for f in (area, "bldg_year_built", "bldg_quality_num", "land_area_sqft" if imperial else "land_area_sqm")
        if f in t.columns
    ]
    comps = []
    for _, r in members.head(COMPS).iterrows():
        km = _num(r.get("_km"))
        comps.append(
            OutlierComp(
                key_sale=str(r["key_sale"]),
                key=str(r["key"]),
                address=_text(r.get("address")),
                date=str(r["sale_date"])[:10],
                price=float(r["oak_price"]),
                ratio=float(r["oak_ratio"]),
                away=None if km is None else round(km / 1.609344 if imperial else km, 2),
                lat=_num(r.get("latitude")),
                lon=_num(r.get("longitude")),
                fields={f: _fmt(f, r.get(f)) for f in compared},
            )
        )
    rows = compare_fields(
        me, g, found.keys if found else [], [v.field for v in cands], {v.field for v in cands if v.numeric}
    )
    unlike = [
        OutlierUnlike(
            field=x["field"],
            name=names.get(x["field"]) or x["field"],
            numeric=x["numeric"],
            this=_fmt(x["field"], x["value"]),
            comps=_fmt(x["field"], x["comps"]),
            pct=x["pct"],
            share=x["share"],
            flag=x["flag"],
            in_model=x["field"] in used,
        )
        for x in rows
    ]
    unlike.sort(key=lambda u: (not u.flag, not u.in_model))
    patchable = [
        OutlierPatchField(field=v.field, name=v.name, numeric=v.numeric, now=_fmt(v.field, me.get(v.field)))
        for v in cands
        if v.field in patch_fields(project_dir)
    ]
    return OutlierDetail(
        sale=_sale(me, project),
        comps=comps,
        members=[
            OutlierMember(lat=la, lon=lo)
            for la, lo in zip(_col(members, "latitude"), _col(members, "longitude"), strict=True)
            if la is not None and lo is not None
        ],
        basis=cast("Literal['impr', 'land', 'price']", found.basis) if found else None,
        conditions=[
            OutlierCondition(field=c["field"], name=names.get(c["field"]) or c["field"], words=_shared(c))
            for c in summarize_conditions(found.conditions if found else [])
        ],
        depth=found.depth if found else 0,
        full_depth=found.full_depth if found else 0,
        n_comps=len(found.keys) if found else 0,
        per_area=found.per_area if found else None,
        compared=compared,
        mine={f: _fmt(f, me.get(f)) for f in compared},
        names={f: names.get(f) or f for f in compared},
        comps_say=found.says if found else None,
        comps_ratio=float(members["oak_ratio"].median()) if len(members) else None,
        unlike=unlike[:MAX_UNLIKE],
        patchable=patchable,
        groups=[(x.id, x.name) for x in project.groups if x.id != group],
        units="mi" if imperial else "km",
        at_sale=_at_sale(project, project_dir, me),
    )


def _at_sale(project: Project, project_dir: Path, me) -> list[list[str]]:
    """The sale's row in the sales file, by its parcel and date: its values only that file has."""
    from oakbox.wizard.sales_only import context

    try:
        return context(project, project_dir / "in", str(me.get("key")), str(me.get("sale_date"))[:10])
    except Exception:  # noqa: BLE001 - context only: the details show without it
        return []


def patch_fields(project_dir: Path) -> set[str]:
    """The fields a patch can correct: those the parcels have once the data's brought in (OpenAVMKit's tweak runs
    there, after enrichment), not those made later from them (a building's age: patch the year it was built)."""
    import pyarrow.parquet as pq

    from oakbox import steps

    path = steps.look(project_dir, "1-assemble-universe")
    if not path.is_file():
        return set()
    return set(pq.ParquetFile(path).schema_arrow.names) - SKIP


# ---------- The group: what the misses have in common ----------


class OutlierPattern(BaseModel):
    field: str
    name: str
    in_model: bool
    bucket: str = Field(description='The sales it\'s about: "pool: yes", "lot size over 12,000".')
    n: int = Field(description="Sales in it.")
    misses: int = Field(description="Outliers in it.")
    off: float = Field(description="The models' average error on them: -0.18 is valued 18% low.")
    rest_off: float = Field(description="On the group's other sales.")
    share: float = Field(description="Of the models' error, the share that lines up with the field (0-1).")
    chance: float = Field(description="How often shuffled errors line up as much (0-1): lower is surer.")
    goes_with: str | None = Field(description="A field ranked above whose sales these mostly are.")


class OutlierCommon(BaseModel):
    group: str
    sales: int
    outliers: int
    patterns: list[OutlierPattern]
    clustered: bool | None = Field(description="Errors more alike between neighbours than chance; None: no places.")
    moran: float | None = Field(description="Moran's I of the errors over each sale's 8 nearest (0: none).")


def _bucket_words(field: str, name: str, b: list | tuple) -> str:
    """OpenAVMKit's bucket in words: "Pool: yes", "Lot size: under 6,000", "…: 1,200 to 1,800", "…: blank"."""
    kind = b[0]
    if kind == "under":
        return f"{name}: under {_fmt(field, b[1])}"
    if kind == "over":
        return f"{name}: {_fmt(field, b[1])} and over"
    if kind == "between":
        return f"{name}: {_fmt(field, b[1])} to {_fmt(field, b[2])}"
    if kind == "is":
        return f"{name}: {_fmt(field, b[1]) or 'blank'}"
    return f"{name}: blank"


def common(project: Project, project_dir: Path, group: str) -> OutlierCommon:
    """What a group's misses have in common (OpenAVMKit's outliers.error_patterns and error_clustering)."""
    from openavmkit.outliers import error_clustering, error_patterns

    from oakbox.errors import NotFound

    t = _sales(project_dir)
    if t is None:
        raise NotFound("Finalize first.")
    g = _frame(t[t["model_group"] == group]).reset_index(drop=True)
    out = cast("pd.Series", _outside(g, project)).to_numpy()
    cands = _candidates(project, project_dir, t)
    names: dict[str, str] = {v.field: v.name for v in cands}
    used = in_model(project, project_dir, group)
    found = error_patterns(
        g,
        [v.field for v in cands],
        ratio_field="oak_ratio",
        numeric={v.field for v in cands if v.numeric},
        outliers=out,
    )
    clustered, moran = error_clustering(g, ratio_field="oak_ratio")
    return OutlierCommon(
        group=group,
        sales=len(g),
        outliers=int(out.sum()),
        patterns=[
            OutlierPattern(
                field=x["field"],
                name=names.get(x["field"]) or x["field"],
                in_model=x["field"] in used,
                bucket=_bucket_words(x["field"], names.get(x["field"]) or x["field"], x["bucket"]),
                n=x["n"],
                misses=x["outliers"],
                off=x["off"],
                rest_off=x["rest_off"],
                share=x["share"],
                chance=x["chance"],
                goes_with=names.get(x["goes_with"], x["goes_with"]) if x["goes_with"] else None,
            )
            for x in found[:15]
        ],
        clustered=clustered,
        moran=moran,
    )


# ---------- The calls ----------


class OutlierCallBody(BaseModel):
    why: OutlierWhy
    note: str = ""
    reason: Reason | None = Field(default=None, description="The sale isn't a market sale: why (required).")
    group: str | None = Field(default=None, description="It's in the wrong group: the group to move it to.")
    field: str | None = Field(default=None, description="The data is wrong: the field to patch.")
    now: str | None = Field(default=None, description="The data is wrong: its corrected value.")
    source: str = Field(default="", description="The data is wrong: where the correction comes from.")


def decide(project: Project, project_dir: Path, key_sale: str, body: OutlierCallBody) -> None:
    """Make (or change) the call on an outlying sale. It's kept on the list, changing nothing, until Apply my calls
    (apply): the outliers can be gone through without the steps after going out of date at each."""
    import pandas as pd

    t = _sales(project_dir)
    if t is None:
        raise ValueError("Finalize first.")
    hit = t[t["key_sale"] == key_sale]
    if hit.empty:
        raise ValueError(f"No sale {key_sale}.")
    me = hit.iloc[0]
    note = body.note.strip()
    call = OutlierCall(why=body.why, note=note, key=str(me["key"]), at=dt.datetime.now())
    if body.why == "invalid":
        if body.reason is None:
            raise ValueError("Say why it isn't a market sale.")
        if body.reason == "other" and not note:
            raise ValueError("Say what makes it not a market sale.")
        call.reason = body.reason
    elif body.why == "group":
        to = next((x for x in project.groups if x.id == body.group), None)
        if to is None or to.id == str(me["model_group"]):
            raise ValueError("Pick the group it belongs in.")
        call.group = to.id
    elif body.why == "data":
        field = body.field
        raw = (body.now or "").strip()
        if not field or not raw:
            raise ValueError("Say which field, and what it should be.")
        if field not in patch_fields(project_dir):
            raise ValueError("That field can't be patched: patch the one it's worked out from.")
        numeric = field in t.columns and pd.api.types.is_numeric_dtype(t[field])
        now: str | float = raw
        if numeric:
            try:
                now = float(raw.replace(",", ""))
            except ValueError as e:
                raise ValueError(f"{raw} isn't a number.") from e
        call.field, call.now, call.source = field, now, body.source.strip()
        call.was = _num(me.get(field)) if numeric else _text(me.get(field))
    undo(project, key_sale)  # a changed call: the old one (and, if applied, what it did) goes first
    project.outliers.calls[key_sale] = call


def pending(project: Project) -> list[OutlierWhy]:
    """The kinds of call made and not yet applied."""
    return sorted({c.why for c in project.outliers.calls.values() if not c.applied and c.why != "model"})


def apply(project: Project, project_dir: Path) -> list[OutlierWhy]:
    """Apply my calls: each call not yet applied done where it belongs. Returns the kinds applied."""
    from oakbox import clean, salereview

    done: set[OutlierWhy] = set()
    for key_sale, c in project.outliers.calls.items():
        if c.applied:
            continue
        if c.why == "invalid":
            words = REASONS.get(c.reason or "other", "other") + (f": {c.note}" if c.note else "")
            if project.clean.location is None:
                clean.decide(project, project_dir)
            salereview.mark(project, key_sale, "exclude", f"Outliers: {words}")
        elif c.why == "group":
            to = next((x for x in project.groups if x.id == c.group), None)
            if to is None:
                continue  # the group's gone since: the call stays on the list
            for x in project.groups:
                if c.key in x.keys:
                    x.keys.remove(c.key)
            to.keys.append(c.key)
        elif c.why == "data" and c.field and c.now is not None:
            project.patches.append(
                Patch(
                    key=c.key,
                    field=c.field,
                    was=c.was,
                    now=c.now,
                    source=c.source,
                    at=c.at,
                    by=_user(),
                    sale=key_sale,
                )
            )
        c.applied = True
        done.add(c.why)
    return sorted(done)


def _user() -> str:
    import getpass

    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no user name: none written
        return ""


def undo(project: Project, key_sale: str) -> None:
    """Take back the call on a sale, and, if it was applied, what it did."""
    call = project.outliers.calls.pop(key_sale, None)
    if call is None or not call.applied:
        return
    if call.why == "invalid":
        m = project.clean.marks.get(key_sale)
        if m is not None and m.action == "exclude" and m.note.startswith("Outliers:"):
            project.clean.marks.pop(key_sale, None)
    elif call.why == "group":
        for x in project.groups:
            x.keys = [k for k in x.keys if k != call.key]
    elif call.why == "data":
        project.patches = [p for p in project.patches if p.sale != key_sale]


# ---------- Patches ----------


class OutlierPatchRow(BaseModel):
    i: int
    key: str
    field: str
    name: str
    was: str | None
    now: str | None
    source: str
    at: str
    by: str
    sale: str | None


def patch_rows(project: Project) -> list[OutlierPatchRow]:
    from oakbox import fields

    names = fields.names() | fields.MADE_NAMES
    return [
        OutlierPatchRow(
            i=i,
            key=p.key,
            field=p.field,
            name=names.get(p.field) or p.field,
            was=_text(p.was),
            now=_text(p.now),
            source=p.source,
            at=p.at.isoformat(timespec="minutes"),
            by=p.by,
            sale=p.sale,
        )
        for i, p in enumerate(project.patches)
    ]


def patches_csv(project: Project) -> str:
    """Every patch, for whoever keeps the data: the parcel, the field, what it was and is, where from, who, when."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["key", "field", "was", "now", "source", "by", "at", "sale"])
    for p in project.patches:
        w.writerow(
            [
                p.key,
                p.field,
                "" if p.was is None else p.was,
                p.now,
                p.source,
                p.by,
                p.at.isoformat(timespec="seconds"),
                p.sale or "",
            ]
        )
    return buf.getvalue()


def remove_patch(project: Project, i: int) -> None:
    if not 0 <= i < len(project.patches):
        raise ValueError("No such patch.")
    p = project.patches.pop(i)
    if p.sale and (c := project.outliers.calls.get(p.sale)) and c.why == "data":
        if not any(q.sale == p.sale for q in project.patches):
            project.outliers.calls.pop(p.sale, None)


class OutlierBand(BaseModel):
    low: float = Field(gt=0, lt=1)
    high: float = Field(gt=1, lt=10)

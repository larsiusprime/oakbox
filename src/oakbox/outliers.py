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
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import final, model
from oakbox.datafiles import BaseModel
from oakbox.projects import OutlierCall, OutlierWhy, Patch, Project

if TYPE_CHECKING:
    import pandas as pd

MIN_BUCKET = 10  # sales a bucket needs for its average error to be read
SHUFFLES = 300  # the shuffles chance is judged by
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


class OutlierDetail(BaseModel):
    sale: OutlierSale
    comps: list[OutlierComp]
    compared: list[str] = Field(description="The fields the comps are shown with (OutlierComp.fields), in order.")
    mine: dict[str, str | None] = Field(description="The sale's own values of the compared fields, in words.")
    names: dict[str, str]
    comps_say: float | None = Field(description="What the comps say it's worth: their price per finished area.")
    comps_ratio: float | None = Field(description="The models' median ratio on the comps.")
    unlike: list[OutlierUnlike]
    patchable: list[OutlierPatchField] = Field(description="The parcel's fields a patch can correct, as they are now.")
    groups: list[tuple[str, str]] = Field(description="(id, name) of the groups it can be moved to.")
    units: Literal["mi", "km"]


def _area_field(project: Project) -> str:
    return "bldg_area_finished_sqft" if project.units == "imperial" else "bldg_area_finished_sqm"


def _km(lat1, lon1, lat2, lon2):
    import numpy as np

    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _comps(t: pd.DataFrame, me, numeric: list[str]) -> pd.DataFrame:
    """The sales most like it: closest on the models' numbers (in the group's spreads) and on the map."""
    import numpy as np

    others = _frame(t[t["key_sale"] != me["key_sale"]])
    if others.empty:
        return others
    score = np.zeros(len(others))
    used = 0
    for f in numeric:
        x = _num(me.get(f))
        col = _nums(others[f])
        sd = float(col.std())
        if x is None or not math.isfinite(sd) or sd == 0:
            continue
        score += np.nan_to_num(((col - x) / sd).to_numpy(), nan=2.0) ** 2
        used += 1
    if _num(me.get("latitude")) is not None and "latitude" in others:
        km = _km(float(me["latitude"]), float(me["longitude"]), others["latitude"], others["longitude"]).to_numpy()
        scale = float(np.nanmedian(km)) or 1.0
        score += 2 * np.nan_to_num(km / scale, nan=3.0) ** 2
        used += 2
    score = score / max(used, 1)
    return others.assign(_score=score).nsmallest(COMPS, "_score")


def detail(project: Project, project_dir: Path, key_sale: str) -> OutlierDetail:
    import numpy as np
    import pandas as pd

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
    area = _area_field(project)
    numeric = [v.field for v in cands if v.numeric and v.field in used] or [
        f for f in (area, "land_area_sqft", "land_area_sqm", "bldg_age_years", "bldg_quality_num") if f in t
    ]
    c = _comps(g, me, numeric)
    imperial = project.units == "imperial"
    compared = [
        f
        for f in (area, "bldg_year_built", "bldg_quality_num", "land_area_sqft" if imperial else "land_area_sqm")
        if f in t.columns
    ]
    from oakbox import fields as field_names

    names = (field_names.names() | field_names.MADE_NAMES) | {v.field: v.name for v in cands}
    comps = []
    for _, r in c.iterrows():
        away = None
        if _num(me.get("latitude")) is not None and _num(r.get("latitude")) is not None:
            km = float(_km(float(me["latitude"]), float(me["longitude"]), float(r["latitude"]), float(r["longitude"])))
            away = round(km / 1.609344 if imperial else km, 2)
        comps.append(
            OutlierComp(
                key_sale=str(r["key_sale"]),
                key=str(r["key"]),
                address=_text(r.get("address")),
                date=str(r["sale_date"])[:10],
                price=float(r["oak_price"]),
                ratio=float(r["oak_ratio"]),
                away=away,
                lat=_num(r.get("latitude")),
                lon=_num(r.get("longitude")),
                fields={f: _fmt(f, r.get(f)) for f in compared},
            )
        )
    comps_say = None
    my_area = _num(me.get(area))
    if not c.empty and my_area and area in c:
        per = (_nums(c["oak_price"]) / _nums(c[area])).to_numpy()
        per = per[np.isfinite(per) & (per > 0)]
        comps_say = float(np.median(per) * my_area) if len(per) else None
    elif not c.empty:
        comps_say = float(c["oak_price"].median())
    comps_ratio = float(c["oak_ratio"].median()) if not c.empty else None

    unlike = []
    for v in cands:
        col = cast("pd.Series", g[v.field])
        x = me.get(v.field)
        cc = cast("pd.Series", c[v.field]) if v.field in c else pd.Series(dtype=object)
        if v.numeric:
            vals = _nums(col).dropna()
            xn = _num(x)
            cn = _nums(cc).dropna()
            cm = float(cn.median()) if len(cn) else None
            pct = share = None
            flag = False
            if xn is not None and len(vals):
                pct = float(((vals < xn).mean() + 0.5 * (vals == xn).mean()) * 100)
                iqr = float(vals.quantile(0.75) - vals.quantile(0.25))
                flag = pct < 5 or pct > 95 or (cm is not None and iqr > 0 and abs(xn - cm) > iqr)
            elif xn is None:
                flag = bool(vals.size) and col.isna().mean() < 0.2
            unlike.append(
                OutlierUnlike(
                    field=v.field,
                    name=v.name,
                    numeric=True,
                    this=_fmt(v.field, xn),
                    comps=_fmt(v.field, cm),
                    pct=pct,
                    share=share,
                    flag=bool(flag),
                    in_model=v.field in used,
                )
            )
        else:
            vals = col.dropna().astype(str)
            xs = _text(x)
            cs = cc.dropna().astype(str)
            mode = cs.mode().iloc[0] if len(cs) else None
            agree = float((cs == mode).mean()) if mode is not None else 0.0
            share = float((vals == xs).mean()) if xs is not None and len(vals) else None
            flag = (share is not None and share < 0.05) or (
                mode is not None and xs is not None and xs != mode and agree >= 0.6
            )
            unlike.append(
                OutlierUnlike(
                    field=v.field,
                    name=v.name,
                    numeric=False,
                    this=xs,
                    comps=mode,
                    pct=None,
                    share=share,
                    flag=bool(flag),
                    in_model=v.field in used,
                )
            )
    unlike.sort(key=lambda u: (not u.flag, not u.in_model))
    patchable = [
        OutlierPatchField(field=v.field, name=v.name, numeric=v.numeric, now=_fmt(v.field, me.get(v.field)))
        for v in cands
        if v.field in patch_fields(project_dir)
    ]
    return OutlierDetail(
        sale=_sale(me, project),
        comps=comps,
        compared=compared,
        mine={f: _fmt(f, me.get(f)) for f in compared},
        names={f: names.get(f) or f for f in compared},
        comps_say=comps_say,
        comps_ratio=comps_ratio,
        unlike=unlike[:MAX_UNLIKE],
        patchable=patchable,
        groups=[(x.id, x.name) for x in project.groups if x.id != group],
        units="mi" if imperial else "km",
    )


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


def _buckets(col: pd.Series, numeric: bool) -> tuple[list[int], list[str]]:
    """Each sale's bucket (-1: none read), and the buckets' labels."""
    import numpy as np

    codes = np.full(len(col), -1, dtype=int)
    labels: list[str] = []
    blank = col.isna().to_numpy()
    x = _nums(col) if numeric else None
    if numeric and x is not None and x.nunique() > 6:
        xs = x.to_numpy()
        edges = sorted(set(np.nanquantile(xs, [0.2, 0.4, 0.6, 0.8]).tolist()))
        pos = np.searchsorted(edges, xs, side="right")
        for i in range(len(edges) + 1):
            if i == 0:
                labels.append(f"under {_text(edges[0])}")
            elif i == len(edges):
                labels.append(f"{_text(edges[-1])} and over")
            else:
                labels.append(f"{_text(edges[i - 1])} to {_text(edges[i])}")
        codes = np.where(blank, -1, pos)
    else:
        s = cast("pd.Series", (_nums(col) if numeric else col).map(_text)).where(~col.isna())
        counts = s.value_counts()
        for v in counts.index:
            if counts[v] >= MIN_BUCKET:
                codes[(s == v).to_numpy()] = len(labels)
                labels.append(_text(v) or "blank")
    if blank.sum() >= MIN_BUCKET:
        codes[blank] = len(labels)
        labels.append("blank")
    return codes.tolist(), labels


def _eta(codes, n_b: int, r, perms):
    """The share of the error's spread between the buckets (one-way ANOVA's R²): for r, and for each shuffle."""
    import numpy as np

    ok = codes >= 0
    c = codes[ok]
    if n_b < 2 or len(c) < 2 * MIN_BUCKET:
        return None, None
    counts = np.bincount(c, minlength=n_b).astype(float)
    use = counts > 0

    def one(vals):  # vals: (k, m) rows of errors
        sums = np.stack([np.bincount(c, weights=row, minlength=n_b) for row in vals])
        mean = vals.mean(axis=1, keepdims=True)
        between = ((sums[:, use] / counts[use] - mean) ** 2 * counts[use]).sum(axis=1)
        total = ((vals - mean) ** 2).sum(axis=1)
        return between / np.where(total > 0, total, 1)

    return float(one(r[ok][None, :])[0]), one(perms[:, ok])


def common(project: Project, project_dir: Path, group: str) -> OutlierCommon:
    import numpy as np

    from oakbox.errors import NotFound

    t = _sales(project_dir)
    if t is None:
        raise NotFound("Finalize first.")
    g = _frame(t[t["model_group"] == group]).reset_index(drop=True)
    out = cast("pd.Series", _outside(g, project)).to_numpy()
    r = np.log(g["oak_ratio"].to_numpy(dtype=float))
    rng = np.random.default_rng(0)
    perms = np.stack([rng.permutation(r) for _ in range(SHUFFLES)]) if len(r) else np.zeros((0, 0))
    used = in_model(project, project_dir, group)
    found: list[tuple[OutlierPattern, set[int]]] = []
    for v in _candidates(project, project_dir, t) if len(g) >= 2 * MIN_BUCKET else []:
        codes_l, labels = _buckets(cast("pd.Series", g[v.field]), v.numeric)
        codes = np.asarray(codes_l)
        eta, shuffled = _eta(codes, len(labels), r, perms)
        if eta is None or shuffled is None:
            continue
        chance = float((shuffled >= eta).mean())
        if chance >= 0.05 or eta < 0.02:
            continue
        mean = r[codes >= 0].mean()
        best, pull = -1, -1.0
        for b in range(len(labels)):
            m = codes == b
            if m.sum() >= MIN_BUCKET and (p := m.sum() * (r[m].mean() - mean) ** 2) > pull:
                best, pull = b, p
        if best < 0:
            continue
        m = codes == best
        name = v.name
        bucket = f"{name}: {labels[best]}"
        found.append(
            (
                OutlierPattern(
                    field=v.field,
                    name=name,
                    in_model=v.field in used,
                    bucket=bucket,
                    n=int(m.sum()),
                    misses=int((m & out).sum()),
                    off=float(math.expm1(r[m].mean())),
                    rest_off=float(math.expm1(r[~m].mean())) if (~m).any() else 0.0,
                    share=round(eta, 4),
                    chance=round(chance, 4),
                    goes_with=None,
                ),
                set(np.flatnonzero(m).tolist()),
            )
        )
    found.sort(key=lambda x: -x[0].share)
    for i, (p, members) in enumerate(found):
        for q, theirs in found[:i]:
            if len(members & theirs) / max(len(members | theirs), 1) >= 0.5:
                p.goes_with = q.name
                break
    clustered, moran = _clustered(g, r, rng)
    return OutlierCommon(
        group=group,
        sales=len(g),
        outliers=int(out.sum()),
        patterns=[p for p, _ in found[:15]],
        clustered=clustered,
        moran=moran,
    )


def _clustered(g: pd.DataFrame, r, rng) -> tuple[bool | None, float | None]:
    """Moran's I of the errors over each sale's 8 nearest sales, and whether it beats 199 shuffles."""
    import numpy as np

    if "latitude" not in g or len(g) < 30:
        return None, None
    ok = g["latitude"].notna().to_numpy() & g["longitude"].notna().to_numpy()
    if ok.sum() < 30:
        return None, None
    from sklearn.neighbors import NearestNeighbors

    lat = g["latitude"].to_numpy(dtype=float)[ok]
    lon = g["longitude"].to_numpy(dtype=float)[ok]
    xy = np.column_stack([lat, lon * np.cos(np.radians(lat.mean()))])
    k = min(8, len(xy) - 1)
    nb = NearestNeighbors(n_neighbors=k + 1).fit(xy).kneighbors(xy, return_distance=False)[:, 1:]
    z = r[ok] - r[ok].mean()
    denom = float((z**2).sum()) or 1.0

    def moran(zz) -> float:
        return float((zz * zz[nb].mean(axis=1)).sum() / denom)

    i = moran(z)
    beats = np.mean([moran(rng.permutation(z)) >= i for _ in range(199)])
    return bool(beats < 0.05), round(i, 4)


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

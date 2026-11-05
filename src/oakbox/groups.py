"""Step 2, Model groups: parcels valued together, each a rule on parcel universe fields; first match wins (SPEC §3.5).

Everything here runs on what Bring in data wrote (out/oakbox/bring_in/): the parcel universe and the sales record,
read once and kept while the files are unchanged. A preview runs the rules with OpenAVMKit's own filter code, in
order, as its model group tagging does, and says where each parcel lands. Sales follow their parcel's group.

The map gets the parcel shapes once, as GeoJSON in the parcel universe's order, so a preview only sends, per
parcel, the index of its group.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.bring_in import out_dir
from oakbox.datafiles import BaseModel, Condition, Rule
from oakbox.errors import NotFound, NotReady
from oakbox.projects import ModelGroup, Project, group_filter

MIN_SALES = 15  # fewer improved sales than this: too few to model (SPEC §3.5)
MIN_EQUITY = 20  # fewer: too few for a vertical-equity test
VALUES_SHOWN = 500
# Not for grouping: IDs, shapes, what OpenAVMKit works out about the shapes, and yes/no flags.
SKIP = {"key", "key2", "key3", "geometry", "address", "latitude", "longitude", "latitude_norm", "longitude_norm"}
SKIP_PREFIX = ("geom_", "polar_", "dist_to_", "proximity_to_", "within_", "is_", "land_area_gis", "key_")
# Shown first when a parcel is inspected (when the parcel universe has them).
INSPECT = [
    "address",
    "land_class",
    "bldg_type",
    "bldg_desc",
    "bldg_units",
    "bldg_area_finished_sqft",
    "bldg_area_finished_sqm",
    "bldg_year_built",
    "land_area_sqft",
    "land_area_sqm",
    "zoning",
    "neighborhood",
    "assr_market_value",
]
COLORS = ["#6f9be0", "#e8955a", "#a77fd8", "#4fae86", "#d2b44a", "#d9677f", "#4bb3c4", "#8c6d4f", "#9bbf4a", "#c779c0"]
UNASSIGNED = "#9a9a9a"


# ---------- The parcel universe and the sales record, as Bring in data left them ----------


def _stamp(path: Path) -> tuple[str, float]:
    if not path.is_file():
        raise NotReady("Bring in data first: model groups are made from its parcel universe.")
    return str(path), path.stat().st_mtime


@lru_cache(maxsize=4)
def _universe(stamp: tuple[str, float]):
    import pandas as pd

    return pd.read_parquet(stamp[0]).reset_index(drop=True)


@lru_cache(maxsize=4)
def _sales(stamp: tuple[str, float], ustamp: tuple[str, float]):
    """Valid sales, each with its parcel's row in the parcel universe (pos)."""
    import pandas as pd

    s = pd.read_parquet(stamp[0])
    if "valid_sale" in s.columns:
        s = s[s["valid_sale"].fillna(False).astype(bool)]
    u = _universe(ustamp)
    pos = pd.Series(range(len(u)), index=u["key"].astype(str))
    s = s.assign(pos=pd.Series(s["key"]).astype(str).map(lambda k: pos.get(k))).dropna(subset=["pos"])
    s["pos"] = s["pos"].astype(int)
    s["vacant"] = s["vacant_sale"].fillna(False).astype(bool) if "vacant_sale" in s.columns else False
    return s.reset_index(drop=True)


def _data(project_dir: Path):
    ustamp = _stamp(out_dir(project_dir) / "universe.parquet")
    sstamp = _stamp(out_dir(project_dir) / "sales.parquet")
    return _universe(ustamp), _sales(sstamp, ustamp)


def _numeric(s) -> bool:
    import pandas as pd

    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _text(v) -> str:
    import pandas as pd

    if v is None or (not isinstance(v, (list, tuple)) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.0f}" if v == round(v) and abs(v) < 1e15 else f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


# ---------- Fields to group on ----------


class GroupField(BaseModel):
    name: str
    label: str
    kind: Literal["category", "number"]
    distinct: int


def _labels() -> dict[str, str]:
    from oakbox.fields import dictionary
    from oakbox.wizard import RENAMED

    return {d.key: RENAMED.get(d.key, (d.name, ""))[0] for d in dictionary()}


def fields(project_dir: Path) -> list[GroupField]:
    """The parcel universe's fields a rule can test: categories first (fewest values first), then numbers."""
    u, _ = _data(project_dir)
    labels = _labels()
    out = []
    for c in u.columns:
        name = str(c)
        if (
            name in SKIP
            or name.startswith(SKIP_PREFIX)
            or name.endswith(("_src", "_raw", "_norm", "_log"))
            or "_in_" in name
            or "_given_" in name
        ):
            continue
        s = u[c]
        if s.dropna().empty or str(s.dtype) == "bool":
            continue
        out.append(
            GroupField(
                name=name,
                label=labels.get(name, name),
                kind="number" if _numeric(s) else "category",
                distinct=int(s.nunique()),
            )
        )
    # Property-type fields first (what groups are usually made from), then by how few values they have.
    first = {f: i for i, f in enumerate(SUGGEST_FIELDS)}
    return sorted(
        out,
        key=lambda f: (f.kind == "number", first.get(f.name, 99), f.distinct if f.kind == "category" else 0, f.label),
    )


class GroupValue(BaseModel):
    value: str = Field(description='As a rule names it ("" for blank).')
    parcels: int
    vacant: int
    sales: int = Field(description="Valid sales of these parcels.")


class GroupValues(BaseModel):
    field: str
    rows: list[GroupValue]
    more: int = Field(description="GroupValues not shown.")


def values(project_dir: Path, field: str) -> GroupValues:
    import pandas as pd

    u, s = _data(project_dir)
    if field not in u.columns:
        raise NotFound(field)
    text = u[field].map(_text)
    vacant = u["is_vacant"].fillna(False).astype(bool) if "is_vacant" in u.columns else pd.Series(False, index=u.index)
    sold = s["pos"].value_counts().reindex(u.index, fill_value=0)
    df = pd.DataFrame({"v": text, "vac": vacant, "sales": sold.values})
    g = df.groupby("v").agg(parcels=("v", "size"), vacant=("vac", "sum"), sales=("sales", "sum"))
    g = pd.DataFrame(g).sort_values(by="parcels", ascending=False)
    rows = [
        GroupValue(value=str(v), parcels=int(r.parcels), vacant=int(r.vacant), sales=int(r.sales))
        for v, r in g.head(VALUES_SHOWN).iterrows()
    ]
    return GroupValues(field=field, rows=rows, more=max(0, len(g) - VALUES_SHOWN))


# ---------- Where each parcel lands ----------


def numeric_fields(project_dir: Path, groups: list[ModelGroup]) -> list[ModelGroup]:
    """Each group with the fields its rule tests that are numbers in the parcel universe (so its filter compares
    numbers)."""
    u, _ = _data(project_dir)
    out = []
    for g in groups:
        tested = {c.column for c in g.rule.conditions}
        numeric = sorted(c for c in tested if c in u.columns and _numeric(u[c]))
        out.append(g.model_copy(update={"numeric": numeric}))
    return out


def _matches(u, g: ModelGroup):
    """Which parcels meet the group's rule (by OpenAVMKit's filter code); None if it can't run yet."""
    from openavmkit.filters import resolve_filter

    if any(c.column not in u.columns for c in g.rule.conditions):
        return None
    f = group_filter(g)
    if not f:
        return None
    return resolve_filter(u, f).fillna(False).astype(bool).to_numpy()


def assign(u, groups: list[ModelGroup]):
    """Per parcel, the index of its group (-1: unassigned), and per group, the parcels its rule meets."""
    import numpy as np

    out = np.full(len(u), -1, dtype=int)
    met = []
    for i, g in enumerate(groups):
        m = _matches(u, g)
        met.append(m)
        if m is not None:
            out[(out == -1) & m] = i
    return out, met


class GroupCheck(BaseModel):
    level: Literal["ok", "warn", "bad"]
    text: str


class GroupStats(BaseModel):
    id: str = Field(description='The group, or "" for unassigned.')
    modeled: bool = Field(default=True, description="Modeled: as chosen, else proposed (enough sales).")
    parcels: int
    vacant: int = Field(description="Parcels without a building.")
    sales: int = Field(description="Valid improved sales.")
    vacant_sales: int
    median_price: float | None = Field(description="Of the improved sales.")
    first_year: int | None
    last_year: int | None
    checks: list[GroupCheck]


class GroupMove(BaseModel):
    from_id: str = Field(description='The group in the saved groups ("" unassigned).')
    to_id: str = Field(description='The group in these groups ("" unassigned).')
    parcels: int
    sold: int = Field(description="Of them, parcels with a valid sale.")


class GroupsPreview(BaseModel):
    assign: list[int] = Field(description="Per parcel (in the shapes' order), the index of its group; -1: none.")
    saved: list[int] = Field(description="The same for the saved groups.")
    stats: list[GroupStats] = Field(description="Per group, then unassigned last.")
    moves: list[GroupMove] = Field(description="Parcels in a different group than in the saved groups, by from and to.")
    total: int


def _stats(u, s, where, gid: str, met, label: str) -> GroupStats:
    import numpy as np

    vacant = u["is_vacant"].fillna(False).astype(bool).to_numpy() if "is_vacant" in u.columns else np.zeros(len(u))
    n = int(where.sum())
    gs = s[where[s["pos"].to_numpy()]]
    improved = gs[~gs["vacant"]]
    years = gs["sale_date"].dt.year if "sale_date" in gs.columns and len(gs) else None
    st = GroupStats(
        id=gid,
        parcels=n,
        vacant=int(vacant[where].sum()),
        sales=len(improved),
        vacant_sales=int(gs["vacant"].sum()),
        median_price=float(improved["sale_price"].median()) if len(improved) and "sale_price" in gs else None,
        first_year=int(years.min()) if years is not None else None,
        last_year=int(years.max()) if years is not None else None,
        checks=[],
    )
    st.checks = _checks(st, met, label)
    return st


def _checks(st: GroupStats, met, label: str) -> list[GroupCheck]:
    out: list[GroupCheck] = []
    if st.id == "":
        if st.parcels:
            out.append(GroupCheck(level="bad", text=f"{st.parcels:,} parcels in no group: they won't be valued"))
        return out
    if met is None:
        return [GroupCheck(level="bad", text="Its rule isn't finished: choose a field and its values")]
    if not met.any():
        return [GroupCheck(level="bad", text="No parcel meets its rule")]
    if st.parcels == 0:
        return [
            GroupCheck(
                level="bad",
                text=f"Every parcel its rule meets ({int(met.sum()):,}) is in a group above it",
            )
        ]
    if st.sales < MIN_SALES:
        out.append(
            GroupCheck(level="bad", text=f"{st.sales:,} improved sales: too few to model ({MIN_SALES} or more needed)")
        )
    elif st.sales < MIN_EQUITY:
        out.append(
            GroupCheck(
                level="warn",
                text=f"{st.sales:,} improved sales: too few for a vertical-equity test ({MIN_EQUITY} or more)",
            )
        )
    else:
        years = f", {st.first_year}–{st.last_year}" if st.first_year and st.first_year != st.last_year else ""
        out.append(GroupCheck(level="ok", text=f"{st.sales:,} improved sales{years}"))
    if st.parcels >= 20 and st.vacant / st.parcels > 0.8:
        pct = round(100 * st.vacant / st.parcels)
        out.append(
            GroupCheck(
                level="warn",
                text=f"{pct}% of its parcels look vacant (no building size): is building data missing for them?",
            )
        )
    return out


def is_modeled(g: ModelGroup, sales: int | None) -> bool:
    """As chosen; else proposed: yes with enough improved sales to model (or while they aren't counted yet)."""
    return g.modeled if g.modeled is not None else sales is None or sales >= MIN_SALES


def preview(project: Project, project_dir: Path, groups: list[ModelGroup]) -> GroupsPreview:
    u, s = _data(project_dir)
    groups = numeric_fields(project_dir, groups)
    now, met = assign(u, groups)
    saved_groups = numeric_fields(project_dir, project.groups)
    before, _ = assign(u, saved_groups)
    stats = [_stats(u, s, now == i, g.id, met[i], g.name) for i, g in enumerate(groups)]
    for g, st in zip(groups, stats, strict=False):
        st.modeled = is_modeled(g, st.sales)
    stats.append(_stats(u, s, now == -1, "", None, "Unassigned"))
    ids = [g.id for g in groups]
    saved_ids = [g.id for g in saved_groups]
    # Compare by group id, so reordering alone isn't a move.
    import numpy as np

    now_id = np.array([*ids, ""], dtype=object)[now]  # -1 picks the last: unassigned
    before_id = np.array([*saved_ids, ""], dtype=object)[before]
    import pandas as pd

    sold = np.zeros(len(u), dtype=int)
    sold[pd.Series(s["pos"]).unique().astype(int)] = 1
    df = pd.DataFrame({"a": before_id, "b": now_id, "sold": sold})
    df = df[df["a"] != df["b"]]
    moved = pd.DataFrame(df.groupby(["a", "b"]).agg(n=("sold", "size"), k=("sold", "sum")))
    moved = moved.sort_values(by="n", ascending=False)
    return GroupsPreview(
        assign=now.tolist(),
        saved=before.tolist(),
        stats=stats,
        moves=[
            GroupMove(from_id=str(a), to_id=str(b), parcels=int(n), sold=int(k))
            for (a, b), n, k in zip(moved.index, moved["n"], moved["k"], strict=True)
        ],
        total=len(u),
    )


# ---------- One parcel: what it is, its sales, and why it's in its group ----------


class ParcelField(BaseModel):
    label: str
    value: str


class GroupWhy(BaseModel):
    group: str = Field(description="The group's id.")
    order: int = Field(description="1 for the first group.")
    met: bool
    text: str


class ParcelSale(BaseModel):
    date: str
    price: float | None
    vacant: bool


class ParcelInspect(BaseModel):
    index: int
    key: str
    group: str = Field(description='Its group\'s id, "" for none.')
    fields: list[ParcelField]
    sales: list[ParcelSale]
    why: list[GroupWhy] = Field(
        description="The groups in order up to the one it's in, then any later one it also meets."
    )
    like: list[int] = Field(description="Parcels with the same values in the fields the rules test.")
    like_sold: int
    like_text: str


def _value_text(u, pos: int, field: str) -> str:
    v = u[field].iloc[pos]
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and "year" not in field and abs(v) >= 10_000:
        return f"{v:,.0f}"
    t = _text(v)
    return t if t else "blank"


def _meets(u, pos: int, g: ModelGroup, c: Condition) -> bool:
    from openavmkit.filters import resolve_filter

    one = g.model_copy(update={"rule": Rule(join="all", conditions=[c])})
    f = group_filter(one)
    return bool(f) and bool(resolve_filter(u.iloc[[pos]], f).fillna(False).astype(bool).iloc[0])


OP_WORDS = {
    "isin": "is",
    "notin": "isn't",
    "==": "is",
    "!=": "isn't",
    "contains": "contains",
    ">": "is over",
    "<": "is under",
    ">=": "is at least",
    "<=": "is at most",
}


def _says(c: Condition, labels: dict[str, str], u, pos: int) -> str:
    label = labels.get(c.column, c.column).lower()
    if c.op == "isempty":
        return f"{label} is blank"
    if c.op == "notempty":
        return f"{label} is {_value_text(u, pos, c.column)}"
    if c.op in ("isin", "==") or c.op == "contains":
        return f"{label} {OP_WORDS[c.op]} {_value_text(u, pos, c.column) if c.op != 'contains' else c.values[0]}"
    return f"{label} {OP_WORDS[c.op]} {c.values[0] if c.values else ''} ({_value_text(u, pos, c.column)})"


def inspect(project_dir: Path, groups: list[ModelGroup], pos: int) -> ParcelInspect:
    import numpy as np

    u, s = _data(project_dir)
    if not 0 <= pos < len(u):
        raise NotFound(pos)
    groups = numeric_fields(project_dir, groups)
    now, met = assign(u, groups)
    labels = _labels()
    tested = list(dict.fromkeys(c.column for g in groups for c in g.rule.conditions if c.column in u.columns))
    shown = list(dict.fromkeys([f for f in INSPECT if f in u.columns] + tested))
    pairs = [ParcelField(label=labels.get(f, f), value=_value_text(u, pos, f)) for f in shown]
    why = []
    mine = int(now[pos])
    for i, g in enumerate(groups):
        m = met[i]
        hit = bool(m is not None and m[pos])
        if i > mine >= 0 and not hit:
            continue
        if m is None:
            text = "its rule isn't finished"
        elif hit:
            # The conditions it met: "land use is COMM".
            text = "; ".join(_says(c, labels, u, pos) for c in g.rule.conditions if _meets(u, pos, g, c))
        else:
            # The values it was tested on: "land use COMM, building type 01-SFR".
            cols = list(dict.fromkeys(c.column for c in g.rule.conditions))
            text = ", ".join(f"{labels.get(c, c).lower()} {_value_text(u, pos, c)}" for c in cols if c in u.columns)
        why.append(GroupWhy(group=g.id, order=i + 1, met=hit, text=text))
    import pandas as pd

    ps = pd.DataFrame(s[s["pos"] == pos])
    if "sale_date" in ps.columns:
        ps = ps.sort_values(by="sale_date")
    sales = [
        ParcelSale(
            date=_text(r.get("sale_date"))[:10] if "sale_date" in ps.columns else "",
            price=float(r["sale_price"]) if "sale_price" in ps.columns and r["sale_price"] == r["sale_price"] else None,
            vacant=bool(r["vacant"]),
        )
        for _, r in ps.iterrows()
    ]
    # Parcels like this one: the same values in the category fields the rules test.
    cats = [c for c in tested if not _numeric(u[c])]
    like = np.ones(len(u), dtype=bool)
    for c in cats:
        v = u[c].iloc[pos]
        like &= (u[c].isna() if v is None or v != v else u[c] == v).to_numpy()
    idx = np.flatnonzero(like) if cats else np.array([pos])
    sold = set(s["pos"].tolist())
    like_text = ", ".join(f"{labels.get(c, c).lower()} {_value_text(u, pos, c)}" for c in cats)
    return ParcelInspect(
        index=pos,
        key=str(u["key"].iloc[pos]),
        group=groups[mine].id if mine >= 0 else "",
        fields=pairs,
        sales=sales,
        why=why,
        like=idx.tolist()[:50_000],
        like_sold=sum(1 for i in idx if int(i) in sold),
        like_text=like_text,
    )


# ---------- The parcel shapes, for the map ----------


def shapes_path(project_dir: Path) -> Path:
    """GeoJSON of the parcel universe's shapes in its order, in degrees, simplified for the screen. Made from
    Bring in data's results the first time it's asked for, and again when they change."""
    import pandas as pd

    base = out_dir(project_dir)
    src = base / "sup.pickle"
    stamp = _stamp(src)
    out = project_dir / "out" / "oakbox" / "groups" / "shapes.geojson"
    meta = out.with_suffix(".json")
    if out.is_file() and meta.is_file() and json.loads(meta.read_text(encoding="utf-8")).get("from") == list(stamp):
        return out
    import geopandas as gpd

    sup = pd.read_pickle(src)
    gdf = sup.universe if hasattr(sup, "universe") else sup["universe"]
    u, _ = _data(project_dir)
    gdf = gpd.GeoDataFrame(gdf[["key", "geometry"]], geometry="geometry")
    gdf = gdf.set_index(gdf["key"].astype(str)).reindex(u["key"].astype(str))
    if gdf.crs is not None and not gdf.crs.is_geographic:
        # Simplify in the shapes' own units (about half a metre), then turn into degrees.
        feet = "foot" in str(gdf.crs.axis_info[0].unit_name).lower() if gdf.crs.axis_info else False
        gdf["geometry"] = gdf.geometry.simplify(1.5 if feet else 0.5)
    gdf = gdf.set_crs(gdf.crs or 4326).to_crs(4326) if gdf.crs else gdf
    import shapely

    geoms = shapely.to_geojson(gdf.geometry.to_numpy())  # None for a parcel with no shape
    body = ",".join(
        f'{{"type":"Feature","id":{i},"properties":{{}},"geometry":{_round(g) if g else "null"}}}'
        for i, g in enumerate(geoms)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('{"type":"FeatureCollection","features":[' + body + "]}", encoding="utf-8")
    meta.write_text(json.dumps({"from": list(stamp)}), encoding="utf-8")
    return out


def _round(text: str) -> str:
    """Coordinates to 6 decimals (about 10 cm)."""
    return re.sub(r"(-?\d+\.\d{6})\d+", r"\1", text)


# ---------- A suggested set ----------

# (name, words that put a value in it). The order is the groups' order: specific kinds first, single-family last,
# so a duplex on residential land lands in small multi-family. Each is a pattern matched at the start of a word
# in the value, ignoring case.
SUGGESTED: list[tuple[str, list[str]]] = [
    (
        "Condos & townhomes",
        ["condo", "town", "twnh", "patio", "row ?house", "twin ?home", "high ?rise", "highrs", "hi-rise"],
    ),
    ("Small multi-family", ["duplex", "triplex", "fourplex", "quadplex", "multi-family<", "multi family<", "2-4"]),
    ("Apartments", ["apart", "apt"]),
    ("Manufactured homes", ["mobile", "manufactured", "manuf"]),
    (
        "Commercial & industrial",
        ["comm(?!on)", "office", "ind", "retail", "hotel", "motel", "warehouse", "store", "bed&b", "bed & b", "leased"],
    ),
    ("Agricultural", ["agri", "farm", "timber", "forest", "ranch", "orchard"]),
    (
        "Public & exempt",
        ["gov", "institut", "school", "park", "church", "relig", "exempt", "cemetery", "funeral", "utility"]
        + ["railroad", "common area", "drainage", "civic", "airport", "golf", "rec/"],
    ),
    ("Single-family", ["sfr", "single", "residential", "vacant", "tiny house", "one family", "1 family"]),
]
# Fields suggestions are made from (and listed first for rules): what the land is used for, then the building.
SUGGEST_FIELDS = ["land_class", "bldg_type", "bldg_desc", "bldg_class"]


def _word_match(value: str, word: str) -> bool:
    return re.search(r"(^|[^a-z])" + word, value.lower()) is not None


def suggest(project_dir: Path) -> list[ModelGroup]:
    """Groups made from the values of the property-type fields the parcel universe has, by the words in them."""
    u, _ = _data(project_dir)
    have = [f for f in SUGGEST_FIELDS if f in u.columns and not _numeric(u[f])]
    taken: dict[str, set[str]] = {f: set() for f in have}
    out: list[ModelGroup] = []
    for name, words in SUGGESTED:
        conditions = []
        for f in have:
            vals = [str(v) for v in u[f].dropna().unique() if str(v).strip()]
            hit = sorted(v for v in vals if v not in taken[f] and any(_word_match(v, w) for w in words))
            if hit:
                taken[f].update(hit)
                conditions.append(Condition(column=f, op="isin", values=hit))
        if conditions:
            out.append(
                ModelGroup(
                    id=_new_id(name, out),
                    name=name,
                    color=COLORS[len(out) % len(COLORS)],
                    rule=Rule(join="any", conditions=conditions),
                )
            )
    return numeric_fields(project_dir, out)


def _new_id(name: str, groups: list[ModelGroup]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "group"
    ids = {g.id for g in groups}
    out, n = base, 2
    while out in ids:
        out, n = f"{base}_{n}", n + 1
    return out


# ---------- The tab's state ----------


class GroupsView(BaseModel):
    ready: bool = Field(description="Bring in data has a receipt to make groups from.")
    start: Literal["scratch", "suggested"] | None
    groups: list[ModelGroup]
    fields: list[GroupField]
    colors: list[str]
    unassigned_color: str = UNASSIGNED
    can_suggest: bool = Field(description="The parcel universe has a property-type field to suggest groups from.")


def view(project: Project, project_dir: Path) -> GroupsView:
    try:
        flds = fields(project_dir)
    except NotReady:
        return GroupsView(
            ready=False, start=project.groups_start, groups=project.groups, fields=[], colors=COLORS, can_suggest=False
        )
    names = {f.name for f in flds}
    return GroupsView(
        ready=True,
        start=project.groups_start,
        groups=project.groups,
        fields=flds,
        colors=COLORS,
        can_suggest=any(f in names for f in SUGGEST_FIELDS),
    )


def clean(project_dir: Path, groups: list[ModelGroup]) -> list[ModelGroup]:
    """Groups as saved: unique ids, names trimmed, and which tested fields are numbers."""
    out: list[ModelGroup] = []
    for g in groups:
        name = g.name.strip() or "Unnamed group"
        gid = g.id if g.id and g.id not in {x.id for x in out} else _new_id(name, out)
        out.append(g.model_copy(update={"id": gid, "name": name}))
    try:
        return numeric_fields(project_dir, out)
    except NotReady:
        return out

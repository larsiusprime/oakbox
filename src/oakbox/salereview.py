"""Check sales' review (SPEC F6): the sales the run set aside, one page at a time, each one's detail (the sales
related to it, those sold with it), and the user's keep or exclude.

It reads the tables the run wrote (clean.py: review.parquet, members.parquet, related.parquet in out/oakbox/clean/);
a mark is saved in the project and applies on the next Check sales.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import Field

from oakbox import cells, clean
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound

if TYPE_CHECKING:
    import pandas as pd

    from oakbox.projects import Project


class ReviewItem(BaseModel):
    key_sale: str
    key: str
    address: str | None
    model_group: str
    group_name: str
    sale_date: str | None
    vacant: bool
    checks: list[str] = Field(description="Every check that flagged it.")
    price: float | None = Field(description="Time-adjusted where time adjustment ran.")
    price_per_area: float | None
    median: float | None = Field(description="Its group's median price per area.")
    ratio: float | None = Field(description="Price per area over the group's median.")
    count: int | None = Field(description="Sales in the group it was compared with.")
    pattern: str | None
    rules: str | None
    flag_only: bool = Field(default=False, description="Flagged, left in: no pattern fits it. The user decides.")
    price_rating: str | None = Field(default=None, description="low, in (range) or high against its group.")
    per_area_rating: str | None = None
    size_rating: str | None = None
    price_median: float | None = None
    price_dist: float | None = Field(default=None, description="Standard deviations from its group's median.")
    per_area_dist: float | None = None
    size: float | None = Field(default=None, description="Finished area (improved) or land area (vacant).")
    size_median: float | None = None
    size_dist: float | None = None
    details: dict[str, str] = Field(default_factory=dict, description="Check -> what it found (e.g. built 2023).")
    seller: str | None = None
    buyer: str | None = None
    second_look: bool = Field(description="Found once the sale that hid it was set aside.")
    status: Literal["undecided", "kept", "excluded"]
    note: str


class ReviewPage(BaseModel):
    items: list[ReviewItem]
    total: int = Field(description="Matching the filters.")
    all: int = Field(description="Every sale set aside.")
    undecided: int
    kept: int
    excluded: int
    groups: list[clean.Choice]
    stale: bool = Field(description="Marks changed since the run: they apply on the next Check sales.")
    unit: Literal["sqft", "sqm"] = Field(description="What prices are per: square feet or square metres.")


class Member(BaseModel):
    key_sale: str
    address: str | None
    price_per_area: float | None
    area: float | None
    sale_date: str | None
    flagged: bool
    latitude: float | None
    longitude: float | None


class RelatedSale(BaseModel):
    key_sale: str
    address: str | None
    sale_date: str | None
    price: float | None
    seller: str | None
    buyer: str | None
    distance: float | None = Field(description="Metres from the sale set aside.")
    why: list[Literal["deed", "day_near", "day_buyer", "buyer_year"]] = Field(
        description="Same deed; same day, nearby; same day, same buyer; same buyer within a year."
    )
    set_aside: bool = Field(description="Set aside too.")


NEAR_M = 152.4  # "nearby": within 500 ft
BUYER_DAYS = 365


class TogetherSale(BaseModel):
    key_sale: str
    address: str | None
    group_name: str
    price: float | None
    finished: float | None
    land: float | None
    this: bool = Field(description="The sale being looked at.")
    set_aside: bool


class SaleDetail(BaseModel):
    item: ReviewItem
    area: float | None = Field(description="Finished area (improved) or land area (vacant) it's priced per.")
    year_built: int | None
    raw_price: float | None
    members: list[Member]
    latitude: float | None
    longitude: float | None
    related: list[RelatedSale] = Field(default_factory=list, description="Up to 30: deed first, then by date.")
    together: list[TogetherSale] = Field(
        default_factory=list,
        description="The sales on its deed the same day (or, without a deed, the same day at the same price), itself "
        "included: likely one sale of several parcels.",
    )
    together_by: Literal["deed", "price"] | None = Field(default=None, description="How they were found.")
    deed: str | None = Field(default=None, description="Its deed ID (or book and page).")


def _review(project_dir: Path):
    import pandas as pd

    path = clean.out_dir(project_dir) / "review.parquet"
    return pd.read_parquet(path) if path.is_file() else clean.empty_frame("key_sale", "check")


def _items(project: Project, project_dir: Path) -> list[ReviewItem]:
    r = _review(project_dir)
    if len(r) == 0:
        return []
    names = {g.id: g.name for g in project.groups} | {
        clean.UNKNOWN: "Unassigned",
        clean.NO_PARCEL: clean.NO_PARCEL_NAME,
    }
    marks: dict[str, clean.SaleMark] = project.clean.marks
    out: list[ReviewItem] = []
    for key, rows in r.groupby("key_sale", sort=False):
        key = str(key)
        if set(rows["check"]) == {"excluded"} and key not in marks:
            continue
        cluster = rows[rows["check"] == "cluster"]
        c = cluster.iloc[0] if len(cluster) else rows.iloc[0]
        first = rows.iloc[0]
        mark = marks.get(key)
        price = cells.number(c.get("price")) if len(cluster) else None
        if price is None:
            price = cells.number(first.get("sale_price_time_adj")) or cells.number(first.get("sale_price"))
        out.append(
            ReviewItem(
                key_sale=key,
                key=str(first.get("key", "")),
                address=cells.text(first.get("address")),
                model_group=clean.group_of(first.get("model_group")),
                group_name=names.get(
                    clean.group_of(first.get("model_group")), clean.group_of(first.get("model_group"))
                ),
                sale_date=cells.text(first.get("sale_date")),
                vacant=bool(first.get("vacant_sale") or False),
                checks=[str(x) for x in rows["check"] if x != "excluded"],
                price=price,
                price_per_area=cells.number(c.get("price_per_area")) if len(cluster) else None,
                median=cells.number(c.get("median")) if len(cluster) else None,
                ratio=cells.number(c.get("relative_ratio")) if len(cluster) else None,
                count=int(c["count"]) if len(cluster) and cells.number(c.get("count")) is not None else None,
                pattern=cells.text(c.get("pattern")) if len(cluster) else None,
                rules=cells.text(c.get("rules")) if len(cluster) else None,
                flag_only=bool(len(cluster) and bool(c.get("flag_only")) and len(rows) == len(cluster)),
                price_rating=cells.text(c.get("price_rating")) if len(cluster) else None,
                per_area_rating=cells.text(c.get("per_area_rating")) if len(cluster) else None,
                size_rating=cells.text(c.get("size_rating")) if len(cluster) else None,
                price_median=cells.number(c.get("price_median")) if len(cluster) else None,
                price_dist=cells.number(c.get("price_dist")) if len(cluster) else None,
                per_area_dist=cells.number(c.get("med_dist_stdevs")) if len(cluster) else None,
                size=cells.number(c.get("size")) if len(cluster) else None,
                size_median=cells.number(c.get("size_median")) if len(cluster) else None,
                size_dist=cells.number(c.get("size_dist")) if len(cluster) else None,
                details={
                    str(x["check"]): str(x["detail"])
                    for _, x in rows.iterrows()
                    if "detail" in rows and cells.text(x.get("detail"))
                },
                seller=cells.text(first.get("deed_grantor")),
                buyer=cells.text(first.get("deed_grantee")),
                second_look=bool(len(cluster) and cells.number(c.get("scrutiny_pass")) == 2),
                status="kept" if mark and mark.action == "keep" else "excluded" if mark else "undecided",
                note=mark.note if mark else "",
            )
        )
    # Furthest from their group first; then the rest.
    out.sort(key=lambda i: (i.ratio is None, -abs(cells.log_floor(i.ratio)) if i.ratio else 0, i.key_sale))
    return out


def review(
    project: Project,
    project_dir: Path,
    group: str | None = None,
    check: str | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    pattern: str | None = None,
) -> ReviewPage:
    items = _items(project, project_dir)
    groups = sorted({(i.model_group, i.group_name) for i in items}, key=lambda x: x[1])
    picked = [
        i
        for i in items
        if (not group or i.model_group == group)
        and (not check or check in i.checks)
        and (not status or i.status == status)
        and (not pattern or pattern in (i.pattern or "").split(","))
    ]
    v = clean.view(project, project_dir)
    return ReviewPage(
        items=picked[offset : offset + limit],
        total=len(picked),
        all=len(items),
        undecided=sum(1 for i in items if i.status == "undecided"),
        kept=sum(1 for i in items if i.status == "kept"),
        excluded=sum(1 for i in items if i.status == "excluded"),
        groups=[clean.Choice(value=g, label=n) for g, n in groups],
        stale=v.stale,
        unit="sqft" if project.units == "imperial" else "sqm",
    )


def detail(project: Project, project_dir: Path, key_sale: str) -> SaleDetail:
    import pandas as pd

    item = next((i for i in _items(project, project_dir) if i.key_sale == key_sale), None)
    if item is None:
        raise NotFound(key_sale)
    r = _review(project_dir)
    row = r[r["key_sale"] == key_sale].iloc[0]
    unit = "sqft" if project.units == "imperial" else "sqm"
    area = cells.number(row.get(f"land_area_{unit}" if item.vacant else f"bldg_area_finished_{unit}"))
    members: list[Member] = []
    path = clean.out_dir(project_dir) / "members.parquet"
    ss = r.loc[(r["key_sale"] == key_sale) & (r["check"] == "cluster"), "ss_id"]
    if path.is_file() and len(ss):
        m = pd.read_parquet(path)
        m = m[m["ss_id"].astype(str) == str(ss.iloc[0])]
        for _, x in m.iterrows():
            a = x.get(f"land_area_{unit}" if item.vacant else f"bldg_area_finished_{unit}")
            members.append(
                Member(
                    key_sale=str(x["key_sale"]),
                    address=cells.text(x.get("address")),
                    price_per_area=cells.number(x.get("price_per_area")),
                    area=cells.number(a),
                    sale_date=cells.text(x.get("sale_date")),
                    flagged=bool(x.get("flagged")),
                    latitude=cells.number(x.get("latitude")),
                    longitude=cells.number(x.get("longitude")),
                )
            )
        members.sort(key=lambda x: (x.price_per_area is None, x.price_per_area or 0))
    year = cells.number(row.get("bldg_year_built"))
    aside = {i.key_sale for i in _items(project, project_dir)}
    together, by, deed = _together(project, project_dir, key_sale, item, aside)
    return SaleDetail(
        together=together,
        together_by=by,
        deed=deed,
        related=_related(project_dir, key_sale, aside),
        item=item,
        area=area,
        year_built=int(year) if year else None,
        raw_price=cells.number(row.get("sale_price")),
        members=members,
        latitude=cells.number(row.get("latitude")),
        longitude=cells.number(row.get("longitude")),
    )


def _together(project: Project, project_dir: Path, key_sale: str, item, aside: set[str]):
    """The sales recorded with this one: on its deed the same day when it was flagged for that, else the same day at
    the same price; itself first."""
    import pandas as pd

    path = clean.out_dir(project_dir) / "related.parquet"
    by = "deed" if "dupe_deed_date" in item.checks else "price" if "dupe_date_price" in item.checks else None
    if by is None or not path.is_file():
        return [], None, None
    r = pd.read_parquet(path)
    me = r[r["key_sale"] == key_sale]
    if not len(me):
        return [], None, None
    m = me.iloc[0]
    day = pd.to_datetime(r["sale_date"], errors="coerce").dt.normalize()
    same_day = day == pd.to_datetime(m.get("sale_date"), errors="coerce").normalize()
    deed = cells.text(m.get("deed")) if "deed" in r else None
    if by == "deed" and deed:
        hit = same_day & (r["deed"].astype(str) == str(m["deed"]))
    else:
        by = "price"
        hit = same_day & (cells.numbers(r, "sale_price") == cells.number(m.get("sale_price")))
    unit = "sqft" if project.units == "imperial" else "sqm"
    names = {g.id: g.name for g in project.groups} | {
        clean.UNKNOWN: "Unassigned",
        clean.NO_PARCEL: clean.NO_PARCEL_NAME,
    }
    rows = r[hit].head(60)
    out = [
        TogetherSale(
            key_sale=str(x["key_sale"]),
            address=cells.text(x.get("address")),
            group_name=names.get(clean.group_of(x.get("model_group")), clean.group_of(x.get("model_group"))),
            price=cells.number(x.get("sale_price")),
            finished=cells.number(x.get(f"bldg_area_finished_{unit}")),
            land=cells.number(x.get(f"land_area_{unit}")),
            this=str(x["key_sale"]) == key_sale,
            set_aside=str(x["key_sale"]) in aside,
        )
        for _, x in rows.iterrows()
    ]
    out.sort(key=lambda x: (not x.this, x.address or ""))
    return out, by, deed


def _buyer(v) -> str:
    text = cells.text(v) or ""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9& ]", " ", text.upper())).strip()


def _related(project_dir: Path, key_sale: str, aside: set[str]) -> list[RelatedSale]:
    """Sales that may be part of the same transaction, or the same buyer's: the same deed, the same day within 500 ft,
    the same day to the same buyer, the same buyer within a year."""
    import numpy as np
    import pandas as pd

    path = clean.out_dir(project_dir) / "related.parquet"
    if not path.is_file():
        return []
    r = pd.read_parquet(path)
    me = r[r["key_sale"] == key_sale]
    if not len(me):
        return []
    m = me.iloc[0]
    others = r[r["key_sale"] != key_sale].copy()
    when = cast("pd.Series", pd.to_datetime(others["sale_date"], errors="coerce")) if "sale_date" in others else None
    mine_when = pd.to_datetime(m.get("sale_date"), errors="coerce")
    day = (when.dt.normalize() == mine_when.normalize()) if when is not None and pd.notna(mine_when) else None
    why: dict[str, pd.Series] = {}
    if "deed" in others and cells.text(m.get("deed")) and str(m["deed"]).strip().lower() not in ("", "nan", "none"):
        why["deed"] = others["deed"].astype(str) == str(m["deed"])
    distance = pd.Series(np.nan, index=others.index)
    if (
        {"latitude", "longitude"} <= set(others.columns)
        and cells.number(m.get("latitude"))
        and cells.number(m.get("longitude"))
    ):
        lat1, lon1 = np.radians(float(m["latitude"])), np.radians(float(m["longitude"]))
        lat2, lon2 = np.radians(cells.numbers(others, "latitude")), np.radians(cells.numbers(others, "longitude"))
        a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
        distance = cast("pd.Series", 2 * 6_371_000 * np.arcsin(np.sqrt(a)))
        if day is not None:
            why["day_near"] = day & distance.le(NEAR_M)
    buyer = _buyer(m.get("deed_grantee"))
    if buyer and "deed_grantee" in others and when is not None and pd.notna(mine_when):
        same = cast("pd.Series", others["deed_grantee"]).map(_buyer) == buyer
        why["day_buyer"] = same & day if day is not None else same & False
        gap = (when - mine_when).abs().dt.days
        why["buyer_year"] = same & gap.le(BUYER_DAYS) & ~why["day_buyer"]
    if not why:
        return []
    hit = cast("pd.Series", pd.concat(list(why.values()), axis=1).fillna(False).any(axis=1))
    out = []
    for idx in [i for i, yes in zip(others.index, hit.tolist(), strict=True) if yes]:
        x = others.loc[idx]
        out.append(
            RelatedSale(
                key_sale=str(x["key_sale"]),
                address=cells.text(x.get("address")),
                sale_date=cells.text(x.get("sale_date")),
                price=cells.number(x.get("sale_price")),
                seller=cells.text(x.get("deed_grantor")),
                buyer=cells.text(x.get("deed_grantee")),
                distance=cells.number(distance.get(idx)),
                why=[cast(Any, k) for k, v in why.items() if bool(v.get(idx, False))],
                set_aside=str(x["key_sale"]) in aside,
            )
        )
    out.sort(key=lambda x: ("deed" not in x.why, x.sale_date or ""))
    return out[:30]


def mark(project: Project, key_sale: str, action: Literal["keep", "exclude"] | None, note: str) -> None:
    """Keep a sale set aside (a note says why it's a market sale), exclude a sale, or undo either."""
    if action is None:
        project.clean.marks.pop(key_sale, None)
        return
    if action == "keep" and not note.strip():
        raise ValueError("Say why it's a market sale: a note is needed to put it back.")
    project.clean.marks[key_sale] = clean.SaleMark(action=action, note=note.strip())

"""Nearby sales and buildings: OpenAVMKit's spatial lag, as OAK box offers it (SPEC F9).

Each parcel gets the distance-weighted average of its nearest sales' prices, and of its nearest parcels'
characteristics, as variables to model with. This is which averages are offered, the settings that ask OpenAVMKit
for them, and what the model run does with them (prices under their plain name, groups too small to average, averages
that came out all zero).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from oakbox import fields
from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    from oakbox.projects import Project


class LagState(BaseModel):
    """Nearby sales and buildings (OpenAVMKit's spatial lag): each parcel gets the distance-weighted average of its
    nearest sales' prices, and of its nearest parcels' characteristics, offered as variables."""

    on: bool = True
    borrow: dict[str, list[str]] = Field(
        default_factory=dict, description="Model group -> other groups whose sales it also averages (its own always)."
    )
    fields: list[str] = Field(default_factory=list, description="Fields averaged besides OpenAVMKit's own.")
    k: int = Field(default=5, ge=1, le=50, description="How many of the nearest each average is of (OpenAVMKit's 5).")
    skip: list[str] = Field(
        default_factory=list,
        description="OpenAVMKit's own averages not wanted (stable names): not worked out (spatial_lag.only) nor"
        " offered as variables.",
    )


# Nearby sales and buildings (spatial lag). OpenAVMKit names a price lag after the price it averages (sale_price, or
# sale_price_time_adj with time adjustment), so OAK box offers them under the plain name and writes the one it is.
LAG = "spatial_lag_"
LAG_PRICE = "spatial_lag_sale_price"


# Any column at all: for listing every average OpenAVMKit can make, whatever the data has.
class _Everything(set):
    def __contains__(self, item: object) -> bool:
        return True


ALL_COLUMNS = _Everything()
# OpenAVMKit's own parcel fields it averages (k nearest each), with what they need to be there.
LAG_OWN = (
    "floor_area_ratio",
    "bedroom_density",
    "bldg_age_years",
    "bldg_effective_age_years",
    "bldg_quality_num",
    "bldg_condition_num",
)


def lag_fields(project: Project, columns: list[str] | set[str], everything: bool = False) -> list[tuple[str, str]]:
    """(field, name) of each nearby-average variable offered, by its stable name: the sales' price and price per
    finished area, then the parcels' fields OpenAVMKit averages that are there, then the user's own. Those of
    OpenAVMKit's own the user unticked are left out, unless `everything`."""
    u = "sqft" if project.units == "imperial" else "sqm"
    unit = "sq ft" if u == "sqft" else "m²"
    have = columns if isinstance(columns, set) else set(columns)
    names = fields.names() | fields.MADE_NAMES
    out = [(LAG_PRICE, "Nearby sale price"), (f"{LAG_PRICE}_impr_{u}", f"Nearby price per finished {unit}")]
    own = [f"bldg_area_finished_{u}", f"land_area_{u}", *LAG_OWN]
    needs = {
        "floor_area_ratio": [f"bldg_area_finished_{u}", f"land_area_{u}"],
        "bedroom_density": ["bldg_rooms_bed", f"land_area_{u}"],
    }
    short = {
        f"bldg_area_finished_{u}": "finished area",
        f"land_area_{u}": "land area",
        "floor_area_ratio": "floor area ratio",
        "bedroom_density": "bedrooms per land area",
        "bldg_age_years": "building age",
        "bldg_effective_age_years": "effective age",
        "bldg_quality_num": "quality",
        "bldg_condition_num": "condition",
    }
    for f in [*own, *project.model.lag.fields]:
        if all(x in have for x in needs.get(f, [f])) and (LAG + f) not in [x for x, _ in out]:
            out.append((LAG + f, f"Nearby {short.get(f) or (names.get(f) or f.replace('_', ' ')).lower()}"))
    if everything:
        return out
    mine = {LAG + f for f in project.model.lag.fields}
    return [(f, n) for f, n in out if f in mine or f not in project.model.lag.skip]


def lag_own(project: Project, columns: list[str] | set[str]) -> list[tuple[str, str]]:
    """OpenAVMKit's own nearby averages there can be here (whether ticked or not): the prices, and the parcels' fields
    it averages that are there."""
    plain = project.model_copy(update={"model": project.model.model_copy(update={"lag": LagState()})})
    return lag_fields(plain, columns, everything=True)


def lag_actual(field: str, sale_field: str) -> str:
    """A nearby-average variable's name as OpenAVMKit writes it: the price lags carry the price field's name."""
    return field.replace(LAG_PRICE, f"spatial_lag_{sale_field}", 1) if field.startswith(LAG_PRICE) else field


def sale_field(project: Project) -> str:
    """The price OpenAVMKit models (and averages nearby): time adjusted when Check sales adjusts it."""
    return "sale_price_time_adj" if project.clean.time_adjust else "sale_price"


def lag_stable(sup, sale: str):
    """The nearby price averages under their stable names (spatial_lag_sale_price…), as variables are offered: a copy
    of OpenAVMKit's columns named after the price averaged (spatial_lag_sale_price_time_adj…)."""
    if sale == "sale_price":
        return sup
    actual = f"spatial_lag_{sale}"
    for df in (sup.sales, sup.universe):
        for c in [c for c in df.columns if c.startswith(actual) and not c.endswith("_confidence")]:
            df[c.replace(actual, LAG_PRICE, 1)] = df[c]
    return sup


def lag_zeros(sales, universe, settings: dict, groups: dict[str, str]) -> dict[str, list[str]]:
    """Group -> the nearby averages its models use that are 0 for all its parcels: OpenAVMKit's stand-in when there
    are too few sales to average (k + 1 or fewer training sales), which a model would read as "nearby, it's worth
    nothing"."""
    import numpy as np
    import pandas as pd

    lists = settings.get("variable_lists", {})
    main = settings.get("modeling", {}).get("models", {}).get("main", {})
    out: dict[str, list[str]] = {}
    for g in groups:
        used: set[str] = set()
        for entry in (main.get(g) or {}).values():
            ivs = entry.get("ind_vars") if isinstance(entry, dict) else None
            if isinstance(ivs, str) and ivs.startswith("$$variable_lists."):
                ivs = lists.get(ivs.split(".", 1)[1], [])
            used |= {v for v in ivs or [] if isinstance(v, str) and v.startswith(LAG)}
        rows = universe[universe["model_group"] == g] if "model_group" in universe else universe.iloc[0:0]
        for v in sorted(used):
            x = (
                np.nan_to_num(np.asarray(pd.to_numeric(pd.Series(rows[v]), errors="coerce"), dtype=float))
                if v in rows
                else None
            )
            if x is None or (len(x) and not x.any()):  # not worked out at all (its group too small), or all 0
                out.setdefault(g, []).append(v)
    return out


def drop_lag_zeros(
    settings: dict, zeros: dict[str, list[str]], names: dict[str, str], labels: dict[str, str] | None = None
) -> list[str]:
    """Leaves each group's all-zero nearby averages out of its models, in the settings the run passes OpenAVMKit (the
    file is left as it is), and says so, a line per group. A model left with no variable stops the run."""
    lists = settings.get("variable_lists", {})
    main = settings.get("modeling", {}).get("models", {}).get("main", {})
    for g, gone in zeros.items():
        for key, entry in (main.get(g) or {}).items():
            ivs = entry.get("ind_vars") if isinstance(entry, dict) else None
            if isinstance(ivs, str) and ivs.startswith("$$variable_lists."):
                ivs = lists.get(ivs.split(".", 1)[1], [])
            if not isinstance(ivs, list) or not set(gone) & set(ivs):
                continue
            kept = [v for v in ivs if v not in gone]
            if not kept and key != "default":
                raise ValueError(
                    f"Too few sales near {names.get(g, g)}'s parcels to average, and {key} has no other variable:"
                    " let the group borrow another group's sales (Variables › Nearby sales and buildings), or give"
                    " the model more variables."
                )
            entry["ind_vars"] = kept
    said = labels or {}
    return [
        f"{names.get(g, g)}: {', '.join(said.get(v, v) for v in gone)} left out of its models: too few of"
        " its sales to average (0 for every parcel). Let it borrow another group's sales (Variables › Nearby sales"
        " and buildings)."
        for g, gone in zeros.items()
    ]


# OpenAVMKit looks up each parcel's k nearest parcels in its group (outside the test sales): a group with fewer stops
# it (an IndexError). At least this many, and twice k.
LAG_MIN_PARCELS = 10


def lag_prune(settings: dict, universe) -> list[str]:
    """Takes groups with too few parcels to average (fewer than LAG_MIN_PARCELS) out of the spatial lag, in the
    settings the run passes OpenAVMKit; their nearby averages are then blank, left out of their models as any
    average there's nothing to work out from (drop_lag_zeros). The groups taken out."""
    lag = settings.get("data", {}).get("process", {}).get("enrich", {}).get("spatial_lag") or {}
    groups = lag.get("model_groups") or {}
    counts = universe["model_group"].astype(str).value_counts() if "model_group" in universe else {}
    k = max([int(lag.get("sale_price", 5)), *(int(x) for x in (lag.get("fields") or {}).values())])
    few = [g for g in groups if int(counts.get(g, 0)) < max(LAG_MIN_PARCELS, 2 * k)]
    for g in few:
        del groups[g]
    for g in groups.values():
        g["sample_from"] = [x for x in g.get("sample_from", []) if x not in few] or g.get("sample_from", [])
    return few


def lag_settings(project: Project, modeled: list[str], columns: list[str] | set[str]) -> dict:
    """data.process.enrich.spatial_lag: each modeled group averages its own sales and any it borrows; and only the
    averages picked are worked out (`only`, OpenAVMKit #414): the sales' prices as `sales`, the
    parcels' fields (OpenAVMKit's own picked, and the user's) as `fields`, the k nearest each (5 to start).
    `columns`: the prepared universe's, so a field it doesn't have isn't asked for."""
    lag = project.model.lag
    if not lag.on or not modeled:
        return {}
    u = "sqft" if project.units == "imperial" else "sqm"
    price = {LAG_PRICE: "price", f"{LAG_PRICE}_impr_{u}": "price_impr"}
    chosen = [f for f, _ in lag_fields(project, columns)]
    return {
        "only": True,
        "sale_price": lag.k,  # OpenAVMKit's name for how many sales the price averages are of
        "sales": [price[f] for f in chosen if f in price],
        "fields": {f.removeprefix(LAG): lag.k for f in chosen if f not in price},
        "model_groups": {g: {"sample_from": [g, *[x for x in lag.borrow.get(g, []) if x != g]]} for g in modeled},
    }

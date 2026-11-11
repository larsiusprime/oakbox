"""Step 4, Check my values (SPEC F8): the values on the roll now, against what parcels sold for. OpenAVMKit's
value-field studies (`run_value_field_studies`) on Check sales' hand-off: per model group and overall, the level
(median ratio with the IAAO's order-statistic interval), uniformity (COD), vertical equity (PRD, PRB, VEI) and
horizontal equity (spread within the equity clusters), judged against a standards profile (IAAO by default, every
target editable), outlying ratios trimmed and listed. Nothing is modeled; it runs in a process of its own
(`python -m oakbox.ratio <project id>`) and writes out/oakbox/ratio/: the receipt, OpenAVMKit's study files and the
sales studied. Its calls are the project's `ratio` state: OAK box passes them to OpenAVMKit directly (settings.json
has no place for them).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from pydantic import Field

from oakbox import cells, clean, fields, steps
from oakbox.datafiles import BaseModel
from oakbox.errors import NotReady
from oakbox.valuesets import ROLL, ValueSet, loaded_value_sets, value_field

if TYPE_CHECKING:
    from oakbox.projects import Project

MODULE = "ratio"
# The value checked: the whole parcel's market value (land and improvement values aren't sold on their own).
FIELD = "assr_market_value"
PropertyClass = Literal[
    "residential",
    "residential_homogeneous",
    "residential_rural",
    "apartments",
    "commercial",
    "vacant",
    "agricultural",
    "none",
]
CATEGORIES: tuple[PropertyClass, ...] = (
    "residential",
    "residential_homogeneous",
    "residential_rural",
    "apartments",
    "commercial",
    "vacant",
    "agricultural",
)
MIN_PROPOSED = 30  # the proposed window reaches back until it holds this many sales
NOMINAL = 1_000  # prices under this are nominal deeds, not prices (as Data's sale price check)


def out_dir(project_dir: Path) -> Path:
    return steps.out_dir(project_dir, MODULE)


# Check my values starts from Check sales as it ran: the copies it keeps in its own folder, never out/2-clean-*,
# which Prepare the fields (step 5) writes again, filled and folded.


def _hand_off(project_dir: Path) -> Path:
    return clean.out_dir(project_dir) / "sup.pickle"


def _hydrated(project_dir: Path) -> Path:
    return clean.out_dir(project_dir) / clean.SALES_KEPT


# ---------- The calls ----------


class CodRange(BaseModel):
    low: float = Field(description="Below it, suspect: possibly sales chasing.")
    high: float


def _cod(low: float, high: float):
    return Field(default_factory=lambda: CodRange(low=low, high=high))


class Targets(BaseModel):
    """What counts as good enough: the IAAO's targets as the Standard on Ratio Studies exposure draft (May 2026) sets
    them, each editable. The PRD is reported, not judged: the draft no longer uses it for compliance."""

    level_low: float = 0.90
    level_high: float = 1.10
    prb_good: float = Field(default=0.05, description="Within ±: good.")
    prb_bad: float = Field(default=0.10, description="Outside ±: unacceptable.")
    vei: float = Field(default=10.0, description="The most a VEI may stray, percent, before it can be a finding.")
    min_sales: int = Field(default=5, description="Fewer sales: shown, not judged.")
    residential: CodRange = _cod(5.0, 15.0)
    residential_homogeneous: CodRange = _cod(4.0, 10.0)
    residential_rural: CodRange = _cod(10.0, 20.0)
    apartments: CodRange = _cod(7.0, 20.0)
    commercial: CodRange = _cod(10.0, 25.0)
    vacant: CodRange = _cod(10.0, 20.0)
    agricultural: CodRange = _cod(10.0, 25.0)

    def cod(self, cls: str) -> CodRange | None:
        return getattr(self, cls, None) if cls in CATEGORIES else None

    def standards(self) -> dict:
        return {
            "level": [self.level_low, self.level_high],
            "prb": [-self.prb_good, self.prb_good],
            "prb_unacceptable": [-self.prb_bad, self.prb_bad],
            "vei": self.vei,
            "min_sales": self.min_sales,
            "cod": {c: [self.cod(c).low, self.cod(c).high] for c in CATEGORIES},  # type: ignore[union-attr]
        }


# The IAAO's property categories (the exposure draft's Table 7), as standards are named when they're the IAAO's.
IAAO_NAMES: dict[str, str] = {
    "residential": "Residential improved",
    "residential_homogeneous": "Residential, homogeneous (condos)",
    "residential_rural": "Residential, rural or manufactured",
    "apartments": "Multi-unit apartments",
    "commercial": "Commercial, industrial, retail",
    "vacant": "Vacant land",
    "agricultural": "Agricultural land",
}


class Standard(BaseModel):
    """A set of targets the values are judged against (the IAAO's for a property category, or a state's, an
    office's), and the model groups it judges."""

    id: str
    name: str
    level_low: float = Field(default=0.90, description="Level: the median ratio, from.")
    level_high: float = 1.10
    cod_low: float = Field(default=5.0, description="Uniformity: the COD, from (below it, suspect).")
    cod_high: float = 15.0
    prb_good: float = Field(default=0.05, description="PRB within ±: good.")
    prb_bad: float = Field(default=0.10, description="PRB outside ±: unacceptable.")
    vei: float = Field(default=10.0, description="The most a VEI may stray, percent, before it can be a finding.")
    min_sales: int = Field(default=5, description="Fewer sales: shown, not judged.")
    groups: list[str] | None = Field(default=None, description="The model groups it judges; None: proposed.")


def iaao_standards(targets: Targets | None = None) -> list[Standard]:
    """The IAAO's, one standard per property category (from older projects' targets, when they changed them)."""
    t = targets or Targets()
    out = []
    for c in CATEGORIES:
        cod = t.cod(c) or CodRange(low=5.0, high=15.0)
        out.append(
            Standard(
                id=c,
                name=IAAO_NAMES[c],
                level_low=t.level_low,
                level_high=t.level_high,
                cod_low=cod.low,
                cod_high=cod.high,
                prb_good=t.prb_good,
                prb_bad=t.prb_bad,
                vei=t.vei,
                min_sales=t.min_sales,
            )
        )
    return out


class RatioState(BaseModel):
    start: dt.date | None = Field(default=None, description="First sale date; None: proposed.")
    end: dt.date | None = Field(default=None, description="Last sale date; None: the day before valuation.")
    price: Literal["sold", "time_adjusted"] = "sold"
    source: Literal["iaao", "custom"] = Field(default="iaao", description="Whose standards: the IAAO's or custom.")
    standards: list[Standard] | None = Field(default=None, description="The standards; None: the IAAO's as they are.")
    # Before standards: one set of targets and a category per group. Read once, into the standards.
    targets: Targets = Field(default_factory=Targets)
    classes: dict[str, PropertyClass] = Field(default_factory=dict, description="Group -> class; missing: proposed.")
    trim: bool = Field(default=True, description="Leave outlying ratios (1.5 x IQR) out of the statistics, listed.")
    region: str | None = Field(
        default=None, description='The location for neighbourhood price levels; "" none; None: Check sales\' location.'
    )
    check: bool | None = Field(default=None, description="Check the existing values (False: skip); None: not asked.")
    sets: list[str] | None = Field(default=None, description="The value sets to check (ids); None: every one.")
    groups: list[str] | None = Field(default=None, description="The model groups to check (ids); None: every one.")


def checked_sets(project: Project) -> list[ValueSet]:
    """The value sets to check: those with a market value loaded, as chosen."""
    s: RatioState = project.ratio
    return [v for v in loaded_value_sets(project) if s.sets is None or v.id in s.sets]


def checked_groups(project: Project, project_dir: Path | None = None) -> list:
    """The groups to check: as chosen; else every one modeled (Model groups › Check them)."""
    s: RatioState = project.ratio
    if s.groups is not None:
        return [g for g in project.groups if g.id in s.groups]
    from oakbox import assemble, projects

    modeled = assemble.modeled(project, project_dir or projects.project_dir(project.id))
    return [g for g in project.groups if g.id in modeled]


def _first_field(project: Project) -> str:
    sets = checked_sets(project)
    return value_field(sets[0].id) if sets else FIELD


def proposed_class(group_id: str, name: str) -> PropertyClass:
    """From the model group's name, the exposure draft's property category (Table 7): exempt and public land isn't
    judged; condos and townhomes are a homogeneous residential market; apartments are multi-unit; commercial,
    industrial and retail are commercial; the rest residential."""
    text = f"{group_id} {name}".lower()
    if re.search(r"exempt|public|government|institution|church|school", text):
        return "none"
    if re.search(r"agri|farm|ranch|timber", text):
        return "agricultural"
    if re.search(r"vacant|land\b|lots?\b", text):
        return "vacant"
    if re.search(r"condo|townho", text):
        return "residential_homogeneous"
    if re.search(r"manufactured|mobile|rural|seasonal", text):
        return "residential_rural"
    if re.search(r"small|duplex|triplex", text):
        return "residential"
    if re.search(r"apartment|multi", text):
        return "apartments"
    if re.search(r"commercial|industrial|office|retail|hotel|warehouse|income", text):
        return "commercial"
    return "residential"


def standards(project: Project) -> list[Standard]:
    s: RatioState = project.ratio
    return s.standards if s.standards is not None else iaao_standards(s.targets)


def classes(project: Project) -> dict[str, str]:
    """Model group -> the id of the standard that judges it, or "none". Once any standard's groups are chosen, they
    are the whole answer; before, each group's is proposed from its name (an IAAO category that's a standard)."""
    s: RatioState = project.ratio
    stds = standards(project)
    if any(x.groups is not None for x in stds):
        chosen = {g: x.id for x in stds for g in (x.groups or [])}
        return {g.id: chosen.get(g.id, "none") for g in project.groups}
    ids = {x.id for x in stds}
    out = {}
    for g in project.groups:
        c = s.classes.get(g.id) or proposed_class(g.id, g.name)
        out[g.id] = c if c in ids else "none"
    return out


def standard_of(project: Project) -> dict[str, Standard | None]:
    """Model group -> the standard that judges it (None: not judged)."""
    by_id = {x.id: x for x in standards(project)}
    return {g: by_id.get(c) for g, c in classes(project).items()}


def engine_standards(project: Project) -> dict:
    """The standards as OpenAVMKit's value studies read them: each one a class, with all its own targets."""
    stds = standards(project)
    return {
        **Targets().standards(),
        "cod": {x.id: [x.cod_low, x.cod_high] for x in stds},
        "by_class": {
            x.id: {
                "level": [x.level_low, x.level_high],
                "prb": [-x.prb_good, x.prb_good],
                "prb_unacceptable": [-x.prb_bad, x.prb_bad],
                "vei": x.vei,
                "min_sales": x.min_sales,
            }
            for x in stds
        },
    }


# ---------- Before running: what's there, and the window proposed ----------


class GroupSetup(BaseModel):
    id: str
    name: str
    color: str
    cls: str = Field(description='The standard that judges it (its id), or "none".')
    proposed: bool = Field(description="Its standard is proposed from the group's name, not chosen.")
    sales: int = Field(description="Sales studied in the window.")


class SalesLine(BaseModel):
    sign: Literal["", "-", "="]
    count: int
    text: str


def region(project: Project) -> str:
    """The location field for neighbourhood price levels: chosen, else where Check sales compares sales."""
    s: RatioState = project.ratio
    return s.region if s.region is not None else (project.clean.location or "")


class SetChoice(BaseModel):
    id: str
    name: str
    roll: bool


class RatioSetup(BaseModel):
    check: bool | None = Field(description="Check the existing values (False: skipped); None: not asked yet.")
    sets: list[SetChoice] = Field(description="The value sets with a market value: the ones that can be checked.")
    chosen_sets: list[str]
    all_groups: list[clean.Choice] = Field(description="Every model group, to choose from.")
    chosen_groups: list[str]
    parcels: int = Field(description="Parcels with an assessed market value above zero.")
    valuation_date: dt.date
    start: dt.date
    end: dt.date
    proposed_start: dt.date
    window_proposed: bool = Field(description="The window is the one proposed (not chosen).")
    first_sale: dt.date | None
    last_sale: dt.date | None
    year_before: int = Field(description="Sales studied in the year before the valuation date (the IAAO's window).")
    price: Literal["sold", "time_adjusted"]
    time_adjusted: bool = Field(description="Check sales brought prices to the valuation date (time adjustment on).")
    source: Literal["iaao", "custom"]
    standards: list[Standard] = Field(description="Each with the groups it judges (as chosen, or proposed).")
    iaao: bool = Field(description="The standards are the IAAO's as they are (nothing changed).")
    groups: list[GroupSetup]
    funnel: list[SalesLine]
    trim: bool
    region: str = Field(description='The location for neighbourhood price levels; "" none.')
    regions: list[clean.Choice] = Field(description="The location fields there are.")


def _sales(project_dir: Path):
    import pandas as pd

    path = _hydrated(project_dir)
    if not path.is_file():
        return None
    s = pd.read_parquet(path)
    s["sale_date"] = pd.to_datetime(s["sale_date"], errors="coerce")
    return s


def _studied(sales, field: str):
    """Sales a value answers to: valid for a ratio study (the parcel looks as it did when sold), a price and a
    value."""
    ok = sales["valid_for_ratio_study"].fillna(False).astype(bool) if "valid_for_ratio_study" in sales else True
    value = cells.numbers(sales, field)
    return ok & cells.numbers(sales, "sale_price").gt(0) & value.notna()


def _in(sales, start: dt.date, end: dt.date):
    import pandas as pd

    return sales["sale_date"].ge(pd.Timestamp(start)) & sales["sale_date"].lt(pd.Timestamp(end) + pd.Timedelta(days=1))


def _years_back(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def window(project: Project, sales=None, project_dir: Path | None = None) -> tuple[dt.date, dt.date, dt.date]:
    """(start, end, proposed start). The end: the day before the valuation date. The proposed start: the year before
    it (the IAAO's window), reaching back a year at a time (up to five) until there are enough sales."""
    s: RatioState = project.ratio
    val = project.valuation_date or dt.date(int(project.tax_year), 1, 1)
    end = s.end or (val - dt.timedelta(days=1))
    proposed = _years_back(val, 1)
    if sales is None and project_dir is not None:
        sales = _sales(project_dir)
    if sales is not None and len(sales):
        field = _first_field(project)
        ok = _studied(sales, field) if field in sales else None
        for years in range(1, 6):
            start = _years_back(val, years)
            proposed = start
            if ok is not None and int((ok & _in(sales, start, end)).sum()) >= MIN_PROPOSED:
                break
    return s.start or proposed, end, proposed


def setup(project: Project, project_dir: Path) -> RatioSetup:
    import pandas as pd

    s: RatioState = project.ratio
    sales = _sales(project_dir)
    if sales is None:
        raise NotReady("Check sales first: this starts from its hand-off.")
    universe_path = clean.out_dir(project_dir) / clean.UNIVERSE_KEPT
    universe = pd.read_parquet(universe_path, columns=None) if universe_path.is_file() else sales
    start, end, proposed = window(project, sales)
    val = project.valuation_date or dt.date(int(project.tax_year), 1, 1)
    field = _first_field(project)
    parcels = int(cells.numbers(universe, field).gt(0).sum()) if field in universe else 0
    studied = _studied(sales, field) if field in sales else pd.Series(False, index=sales.index)
    inside = _in(sales, start, end)
    year_before = int((studied & _in(sales, _years_back(val, 1), val - dt.timedelta(days=1))).sum())
    group_of = clean.model_groups_of(sales)
    cls = classes(project)
    groups = [
        GroupSetup(
            id=g.id,
            name=g.name,
            color=g.color,
            cls=cls[g.id],
            proposed=not any(x.groups is not None for x in standards(project)),
            sales=int((studied & inside & (group_of == g.id)).sum()),
        )
        for g in checked_groups(project)
    ]
    dates = sales["sale_date"].dropna()
    n_all = len(sales)
    n_window = int(inside.sum())
    funnel = [
        SalesLine(sign="", count=n_all, text="for modeling, from Check sales"),
        SalesLine(sign="-", count=n_all - n_window, text=f"outside the window ({start} to {end})"),
        SalesLine(
            sign="-",
            count=int((inside & ~studied).sum()),
            text="the parcel changed since (sold vacant, built on now, or the reverse), or no value",
        ),
        SalesLine(sign="=", count=int((studied & inside).sum()), text="sales the values answer to"),
    ]
    from oakbox import assemble

    modeled = assemble.modeled(project, project_dir)
    return RatioSetup(
        check=s.check,
        sets=[SetChoice(id=v.id, name=v.name, roll=v.id == ROLL) for v in loaded_value_sets(project)],
        chosen_sets=[v.id for v in checked_sets(project)],
        # Only the groups modeled are offered (Model groups › Check them).
        all_groups=[clean.Choice(value=g.id, label=g.name) for g in project.groups if g.id in modeled],
        chosen_groups=[g.id for g in checked_groups(project)],
        parcels=parcels,
        valuation_date=val,
        start=start,
        end=end,
        proposed_start=proposed,
        window_proposed=s.start is None,
        first_sale=dates.min().date() if len(dates) else None,
        last_sale=dates.max().date() if len(dates) else None,
        year_before=year_before,
        price=s.price,
        time_adjusted=project.clean.time_adjust and "sale_price_time_adj" in sales,
        source=s.source,
        standards=[
            x.model_copy(update={"groups": [g.id for g in project.groups if cls.get(g.id) == x.id]})
            for x in standards(project)
        ],
        iaao=s.standards is None,
        groups=groups,
        funnel=funnel,
        trim=s.trim,
        region=region(project),
        regions=[
            clean.Choice(value=f, label=fields.names().get(f) or f)
            for f in clean.location_fields(project_dir, universe)
            if f in sales
        ],
    )


# ---------- The run ----------


class Verdict(BaseModel):
    """True met, False missed, None neither (or not judged)."""

    judged: bool
    level: bool | None = Field(default=None, description="Missed only when its whole confidence interval is outside.")
    cod: bool | None = None
    cod_low: bool | None = Field(default=None, description="Under the range: suspect, possibly sales chasing.")
    cod_target: list[float] | None = None
    prb: bool | None = Field(default=None, description="Met within the good range, missed outside the unacceptable.")
    vei: bool | None = Field(default=None, description="Missed only when significantly outside.")


class Figures(BaseModel):
    """A study's statistics: of the sales kept after trimming, or of every sale."""

    sales: int
    median: float | None
    low: float | None = Field(description="The median's interval (90%, the IAAO's order statistics).")
    high: float | None
    cod: float | None
    prd: float | None
    prb: float | None
    mki: float | None = Field(default=None, description="Modified Kakwani Index: 1 is equitable.")
    vei: float | None
    vei_significance: float | None
    vei_verdict: str | None = Field(description="compliant, not_significant, regressive, progressive, insufficient.")
    verdict: Verdict | None = None


class Stratum(BaseModel):
    n: int
    median: float | None
    low: float | None
    high: float | None


class Fifth(BaseModel):
    low: float
    high: float
    sales: int
    median: float


class RegionStratum(BaseModel):
    n: int
    regions: int
    level: float | None = Field(description="The regions' median price level (market value proxy).")
    median: float | None
    low: float | None
    high: float | None


class RegionStats(BaseModel):
    """The median ratio by the price level of the region each sale is in (openratiostudy.com's neighbourhood price
    levels; not an IAAO test)."""

    field: str
    regions: int
    sales: int
    strata: list[RegionStratum]
    vei: float | None
    vei_significance: float | None
    vei_verdict: str


class Study(BaseModel):
    """One model group's (or all groups') study of one value field."""

    id: str = Field(description='The model group; "" for all groups.')
    name: str
    color: str
    cls: str | None = Field(description="The standard that judges it (its id); None: not judged.")
    sales: int = Field(description="Sales in the statistics (after trimming).")
    trimmed: int
    parcels: int
    median: float | None
    low: float | None = Field(description="The median's interval (90%, the IAAO's order statistics).")
    high: float | None
    cod: float | None
    prd: float | None
    prb: float | None
    mki: float | None = None
    vei: float | None
    vei_significance: float | None
    vei_verdict: str | None = Field(description="compliant, not_significant, regressive, progressive, insufficient.")
    every: Figures | None = Field(
        default=None, description="The same statistics on every sale, untrimmed: beside, never compared."
    )
    strata: list[Stratum] = Field(default_factory=list, description="The VEI's percentile groups, low to high.")
    fifths: list[Fifth] = Field(default_factory=list, description="Median ratio by fifths of sales, by price.")
    clusters: int | None = Field(default=None, description="Groups of similar parcels (equity clusters).")
    median_chd: float | None = Field(default=None, description="Their median spread of values (CHD).")
    verdict: Verdict | None = None
    regions: RegionStats | None = None


class Trimmed(BaseModel):
    key_sale: str
    group: str
    group_name: str
    address: str | None
    sale_date: str | None
    price: float
    value: float
    ratio: float
    nominal: bool = Field(description=f"A price under {NOMINAL:,}: likely a nominal deed, not a sale.")


class FieldResult(BaseModel):
    field: str
    name: str
    groups: list[Study]
    overall: Study
    trimmed: list[Trimmed] = Field(description="Furthest from the rest first.")


class RatioReceipt(BaseModel):
    ran_at: str
    seconds: float
    engine: str
    start: dt.date
    end: dt.date
    price: Literal["sold", "time_adjusted"]
    trim: bool
    results: list[FieldResult]
    notes: list[str] = Field(default_factory=list)


def study_calls(project: Project, project_dir: Path) -> dict:
    """The calls that decide how values are studied against the sales: the window, the price, the trimming, the
    standards, the classes and the region. Checking the roll's values and Finalize's study of the model values both
    depend on them, so a new call goes here, for both."""
    start, end, _ = window(project, project_dir=project_dir)
    s: RatioState = project.ratio
    return {
        "window": [str(start), str(end)],
        "price": s.price,
        "trim": s.trim,
        "standards": [x.model_dump(exclude={"groups"}) for x in standards(project)],
        "classes": classes(project),
        "region": region(project),
    }


def settings_key(project: Project, project_dir: Path) -> dict:
    """What a run depends on: the Check sales run it starts from, the values checked, and the study's calls."""
    return {
        "clean": clean.STEP.ran_at(project_dir),
        "fields": [value_field(v.id) for v in checked_sets(project)],
        "groups": [(g.id, g.name) for g in checked_groups(project)],
        "names": [v.name for v in checked_sets(project)],
        **study_calls(project, project_dir),
    }


def _fifths(table, group: str | None) -> list[Fifth]:
    import pandas as pd

    t = table[~table["trimmed"].astype(bool)]
    if group is not None:
        t = t[t["model_group"].astype(str) == group]
    if len(t) < 10:
        return []
    bins = pd.qcut(t["sale_price"].rank(method="first"), 5, labels=False)
    out = []
    for _, part in t.groupby(bins):
        out.append(
            Fifth(
                low=float(part["sale_price"].min()),
                high=float(part["sale_price"].max()),
                sales=len(part),
                median=float(part["ratio"].median()),
            )
        )
    return out


def _figures(data: dict) -> Figures:
    r = data.get("ratio") or {}
    v = data.get("vertical") or {}
    med = r.get("median_ratio") or {}
    verdict = data.get("verdict")
    return Figures(
        sales=int(r.get("count") or 0),
        median=med.get("value"),
        low=med.get("low"),
        high=med.get("high"),
        cod=(r.get("cod") or {}).get("value"),
        prd=(v.get("prd") or {}).get("value"),
        prb=(v.get("prb") or {}).get("value"),
        mki=v.get("mki"),
        vei=v.get("vei"),
        vei_significance=v.get("vei_significance"),
        vei_verdict=v.get("vei_verdict"),
        verdict=Verdict.model_validate(verdict) if verdict else None,
    )


def study_view(gid: str, name: str, color: str, cls, data: dict, table) -> Study:
    """The statistics shown and judged: without the trimmed sales when trimming is on (every sale's beside them)."""
    main = data.get("trimmed_study") or data
    f = _figures(main)
    v = main.get("vertical") or {}
    h = data.get("horizontal") or {}
    return Study(
        id=gid,
        name=name,
        color=color,
        cls=cls,
        sales=f.sales,
        trimmed=len(data.get("trimmed") or []) if gid else int(data.get("count_trimmed") or 0),
        parcels=int(data.get("count_parcels") or 0),
        median=f.median,
        low=f.low,
        high=f.high,
        cod=f.cod,
        prd=f.prd,
        prb=f.prb,
        mki=f.mki,
        vei=f.vei,
        vei_significance=f.vei_significance,
        vei_verdict=f.vei_verdict,
        every=_figures(data) if "trimmed_study" in data else None,
        strata=[Stratum.model_validate(x) for x in v.get("vei_strata") or []],
        fifths=_fifths(table, gid or None),
        clusters=h.get("clusters"),
        median_chd=h.get("median_chd"),
        verdict=f.verdict,
        regions=RegionStats.model_validate(main["regions"]) if main.get("regions") else None,
    )


def run(project_id: str) -> None:
    import warnings
    from importlib.metadata import version

    import pandas as pd

    from oakbox import projects

    project = projects.load(project_id)
    pdir = projects.project_dir(project_id)
    src = _hand_off(pdir)
    if not src.is_file():
        raise RuntimeError("Check sales first: this starts from its hand-off.")
    s: RatioState = project.ratio
    start, end, _ = window(project, project_dir=pdir)
    tmp = steps.workdir(out_dir(pdir))
    depends = STEP.now(project, pdir)  # what it starts from, before anything can change
    os.chdir(pdir)
    from openavmkit import pipeline as pl
    from openavmkit.data import SalesUniversePair
    from openavmkit.value_studies import run_value_field_studies

    t0 = time.time()
    cls = classes(project)
    with warnings.catch_warnings(record=True) as caught, steps.heartbeat():
        warnings.simplefilter("always")
        steps.emit(step="load", fraction=0.0, message="Reading Check sales' hand-off")
        sup = cast(SalesUniversePair, pd.read_pickle(src))
        chosen = [g.id for g in checked_groups(project)]
        if len(chosen) < len(project.groups):  # only the groups chosen, overall too
            # The sales carry their parcel's key, not its group: kept by the parcels kept.
            universe = cast(pd.DataFrame, sup.universe[sup.universe["model_group"].astype(str).isin(chosen)])
            sup = SalesUniversePair(
                sales=cast(pd.DataFrame, sup.sales[sup.sales["key"].isin(universe["key"])]), universe=universe
            )
        sets = {value_field(v.id): v.name for v in checked_sets(project)}
        settings = pl.load_settings()
        steps.emit(step="study", fraction=0.2, message="Checking the values against the sales")
        studies = run_value_field_studies(
            sup,
            settings,
            [f for f in sets if f in sup.universe],
            start_date=str(start),
            end_date=str(end),
            sale_field="sale_price" if s.price == "sold" else "sale_price_time_adj",
            trim_outliers=s.trim,
            median_ci="iaao",
            standards=engine_standards(project),
            region=region(project) or None,
            classes={g: (None if c == "none" else c) for g, c in cls.items()},
            outpath=str(tmp / "studies"),
        )
    steps.emit(step="receipt", fraction=0.9, message="Counting")
    hydrated = _sales(pdir)
    address = (
        dict(zip(hydrated["key_sale"].astype(str), hydrated["address"], strict=False))
        if hydrated is not None and "address" in hydrated
        else {}
    )
    names = {g.id: g.name for g in project.groups}
    results = []
    for field, study in studies.items():
        table = pd.read_parquet(tmp / "studies" / f"{field}.sales.parquet") if s.trim else None
        if table is None:
            table = pd.DataFrame({c: [] for c in ("model_group", "sale_price", "ratio", "trimmed")})
        groups = [
            study_view(g.id, g.name, g.color, cls[g.id], study["groups"][g.id], table)
            for g in checked_groups(project)
            if g.id in study["groups"]
        ]
        trimmed = []
        for gid, g in study["groups"].items():
            for t in g.get("trimmed") or []:
                trimmed.append(
                    Trimmed(
                        key_sale=str(t["key_sale"]),
                        group=gid,
                        group_name=names.get(gid) or gid,
                        address=cells.text(address.get(str(t["key_sale"]))),
                        sale_date=t.get("sale_date"),
                        price=float(t["sale_price"]),
                        value=float(t["value"]),
                        ratio=float(t["ratio"]),
                        nominal=float(t["sale_price"]) < NOMINAL,
                    )
                )
        trimmed.sort(key=lambda x: -abs(cells.log_floor(x.ratio)))
        results.append(
            FieldResult(
                field=field,
                name=sets.get(field) or field,
                groups=groups,
                overall=study_view("", "All model groups", "#888888", None, study["overall"], table),
                trimmed=trimmed,
            )
        )
    mine = steps.engine_notes(caught)
    receipt = RatioReceipt(
        ran_at=dt.datetime.now().isoformat(timespec="seconds"),
        seconds=round(time.time() - t0, 1),
        engine=version("openavmkit"),
        start=start,
        end=end,
        price=s.price,
        trim=s.trim,
        results=results,
        notes=list(dict.fromkeys(str(w.message) for w in mine))[:20],
    )
    (tmp / "receipt.json").write_text(receipt.model_dump_json(indent=1), encoding="utf-8")
    (tmp / "settings.json").write_text(json.dumps({"hash": depends}), encoding="utf-8")
    steps.publish(tmp, out_dir(pdir))
    steps.emit(step="done", fraction=1.0, message=f"{sum(r.overall.sales for r in results):,} sales studied")


# ---------- The step's state ----------


class RatioView(steps.RunView):
    receipt: RatioReceipt | None
    accepted: bool
    has_values: bool = Field(description="Some existing values (the roll, a vendor's AVM) have a market value.")
    skipped: bool = Field(description="The user chose not to check them.")


STEP = steps.Step(
    MODULE,
    "Check my values",
    RatioReceipt,
    key=settings_key,
    after=clean.STEP,
    again="Check the values again first: something changed since they were checked.",
    place="Evaluate",
)


def blocked(project: Project, project_dir: Path) -> list[str]:
    waiting = STEP.waiting(project, project_dir)
    if waiting:
        return [waiting]
    if not _hand_off(project_dir).is_file() or not _hydrated(project_dir).is_file():
        return ["Run Check sales again first: this starts from the sales it kept."]
    return []


def view(project: Project, project_dir: Path) -> RatioView:
    stop = blocked(project, project_dir)
    # What a run would depend on can't be worked out until Check sales is done: not out of date, just blocked.
    s = STEP.state(project, project_dir, check=not stop)
    return RatioView(
        status=s.status,
        job=s.job,
        receipt=s.receipt,
        stale=s.stale,
        blocked=stop,
        accepted=s.accepted,
        has_values=bool(loaded_value_sets(project)),
        skipped=project.ratio.check is False,
    )


def start(project: Project, project_dir: Path) -> None:
    stop = blocked(project, project_dir)
    if not stop:
        sales = _sales(project_dir)
        if project.ratio.check is False:
            stop = ["You chose to skip checking the existing values."]
        elif not checked_sets(project):
            stop = ["No existing values to check: add them on Data › Assessed values."]
        elif sales is None or not any(value_field(v.id) in sales for v in checked_sets(project)):
            stop = ["Run Check sales again first: its sales don't carry the existing values yet."]
    STEP.start(project.id, project_dir, stop)


def accept(project: Project, project_dir: Path) -> None:
    if blocked(project, project_dir):
        raise ValueError(STEP.again)
    STEP.accept(project, project_dir)


class RatioPatch(BaseModel):
    start: dt.date | None = None
    end: dt.date | None = None
    reset_window: bool | None = Field(default=None, description="True: back to the proposed window.")
    price: Literal["sold", "time_adjusted"] | None = None
    source: Literal["iaao", "custom"] | None = Field(default=None, description="Whose standards.")
    start_from: Literal["iaao", "empty"] | None = Field(
        default=None, description="Custom: start from the IAAO's figures, or with no standard."
    )
    standards: list[Standard] | None = Field(default=None, description="Every standard, as it is to be.")
    reset_standards: bool | None = Field(default=None, description="True: back to the IAAO's.")
    trim: bool | None = None
    region: str | None = Field(default=None, description='A location field; "" for none.')
    check: bool | None = Field(default=None, description="Check the existing values (true) or skip (false).")
    sets: list[str] | None = Field(default=None, description="The value sets to check.")
    groups: list[str] | None = Field(default=None, description="The model groups to check.")


def change(project: Project, body: RatioPatch) -> None:
    s: RatioState = project.ratio
    if body.reset_window:
        s.start = s.end = None
    if body.start is not None:
        s.start = body.start
    if body.end is not None:
        s.end = body.end
    if s.start and s.end and s.start > s.end:
        raise ValueError("The window starts after it ends.")
    if body.price is not None:
        s.price = body.price
    if body.source == "iaao" or body.reset_standards:
        s.source, s.standards = "iaao", None
    elif body.source == "custom":
        s.source = "custom"
        s.standards = iaao_standards(s.targets) if body.start_from != "empty" else []
    if body.standards is not None:
        s.standards = _checked(body.standards)
    if body.trim is not None:
        s.trim = body.trim
    if body.region is not None:
        s.region = body.region
    if body.check is not None:
        s.check = body.check
    if body.sets is not None:
        if not body.sets:
            raise ValueError("Choose at least one set of values to check.")
        s.sets = body.sets
    if body.groups is not None:
        if not body.groups:
            raise ValueError("Choose at least one model group to check.")
        from oakbox import assemble, projects

        every = assemble.modeled(project, projects.project_dir(project.id))
        s.groups = None if set(body.groups) == every else body.groups


def _checked(stds: list[Standard]) -> list[Standard]:
    """Standards as saved: named, each id and name once, ranges the right way round, a group in one at most (the
    last that names it)."""
    seen_ids: set[str] = set()
    names: set[str] = set()
    owner: dict[str, int] = {}
    for i, x in enumerate(stds):
        if not x.name.strip():
            raise ValueError("Every standard needs a name.")
        if x.id in seen_ids or x.name.strip() in names:
            raise ValueError(f"There's already a standard called {x.name.strip()}.")
        seen_ids.add(x.id)
        names.add(x.name.strip())
        if x.level_low > x.level_high or x.cod_low > x.cod_high or x.prb_good > x.prb_bad:
            raise ValueError(f"{x.name}: a range starts above where it ends.")
        for g in x.groups or []:
            owner[g] = i
    return [
        x.model_copy(
            update={
                "name": x.name.strip(),
                "groups": None if x.groups is None else [g for g in x.groups if owner.get(g) == i],
            }
        )
        for i, x in enumerate(stds)
    ]


def points(project_dir: Path, field: str, group: str | None) -> list[tuple[float, float, bool]]:
    """Each sale studied: (price, ratio, trimmed), for the chart."""
    import pandas as pd

    path = out_dir(project_dir) / "studies" / f"{field}.sales.parquet"
    if not path.is_file():
        return []
    t = pd.read_parquet(path)
    if group:
        t = t[t["model_group"].astype(str) == group]
    return [(float(p), float(r), bool(x)) for p, r, x in zip(t["sale_price"], t["ratio"], t["trimmed"], strict=True)]


class MapPoint(BaseModel):
    lat: float
    lon: float
    ratio: float
    price: float
    value: float
    trimmed: bool
    key_sale: str | None = Field(default=None, description="The sale: Extreme ratios picks it on the map.")


def map_points(project_dir: Path, field: str, group: str | None) -> list[MapPoint]:
    """Each sale studied that has coordinates, for the ratio map."""
    import pandas as pd

    path = out_dir(project_dir) / "studies" / f"{field}.sales.parquet"
    if not path.is_file():
        return []
    t = pd.read_parquet(path)
    if "latitude" not in t or "longitude" not in t:
        return []
    if group:
        t = t[t["model_group"].astype(str) == group]
    lat, lon = cells.numbers(t, "latitude"), cells.numbers(t, "longitude")
    t = t[lat.notna() & lon.notna()]
    keys = t["key_sale"].astype(str) if "key_sale" in t else [None] * len(t)
    return [
        MapPoint(
            lat=float(a), lon=float(b), ratio=float(r), price=float(p), value=float(v), trimmed=bool(x), key_sale=k
        )
        for a, b, r, p, v, x, k in zip(
            t["latitude"], t["longitude"], t["ratio"], t["sale_price"], t["value"], t["trimmed"], keys, strict=True
        )
    ]


class RegionPoints(BaseModel):
    """Each sale studied with a place, by its region (neighbourhood), as columns, for Neighbourhood price levels'
    map: each coloured by its region's median ratio (the outlying ratios left out of it, as in the statistics)."""

    lon: list[float]
    lat: list[float]
    region: list[int] = Field(description="Index into regions.")
    regions: list[str]
    median: list[float | None] = Field(description="Each region's median ratio.")
    sales: list[int] = Field(description="Each region's sales counted in its median.")
    overall: float | None = Field(default=None, description="The median ratio of all of them, the same way.")


def region_points(project_dir: Path, field: str, region: str, group: str | None) -> RegionPoints:
    import numpy as np
    import pandas as pd

    empty = RegionPoints(lon=[], lat=[], region=[], regions=[], median=[], sales=[], overall=None)
    path = out_dir(project_dir) / "studies" / f"{field}.sales.parquet"
    if not region or not path.is_file():
        return empty
    t = pd.read_parquet(path)
    if any(c not in t for c in ("latitude", "longitude", "ratio", region)):
        return empty
    if group:
        t = cast(pd.DataFrame, t[t["model_group"].astype(str) == group])
    t = t.assign(
        la=cells.numbers(t, "latitude"),
        lo=cells.numbers(t, "longitude"),
        r=cells.numbers(t, "ratio"),
        g=t[region].astype("string").fillna(""),
    )
    t = cast(pd.DataFrame, t[t["la"].notna() & t["lo"].notna() & (t["g"] != "")])
    kept = t[~t["trimmed"].astype(bool)] if "trimmed" in t else t
    by = kept.groupby("g")["r"]
    med = {str(k): float(v) for k, v in by.median().items()}
    n = {str(k): int(v) for k, v in by.count().items()}
    names = sorted(str(g) for g in t["g"].unique())
    rs = np.asarray(kept["r"], dtype=float)
    rs = rs[np.isfinite(rs)]
    at = {g: i for i, g in enumerate(names)}
    return RegionPoints(
        lon=np.round(np.asarray(t["lo"], dtype=float), 6).tolist(),
        lat=np.round(np.asarray(t["la"], dtype=float), 6).tolist(),
        region=[at[g] for g in t["g"]],
        regions=[str(g) for g in names],
        median=[round(med[g], 4) if g in med and np.isfinite(med[g]) else None for g in names],
        sales=[n.get(g, 0) for g in names],
        overall=round(float(np.median(rs)), 4) if len(rs) else None,
    )


class SimilarPoints(BaseModel):
    """Every parcel with a place and a group of similar parcels, as columns, for Similar parcels' map: each coloured by
    how far apart its group's values are (its CHD)."""

    lon: list[float]
    lat: list[float]
    chd: list[float | None] = Field(description="Its group of similar parcels' CHD; null: a group of one.")
    size: list[int] = Field(description="Parcels in its group of similar parcels.")
    cluster: list[int] = Field(default=[], description="Index into clusters: its group of similar parcels.")
    clusters: list[str] = Field(default=[], description="Each group's id (model group:cluster), for its members.")


class SimilarMember(BaseModel):
    key: str
    lat: float
    lon: float
    value: float | None


class SimilarGroup(BaseModel):
    """One group of similar parcels: each parcel's ID, place and value (the field studied), dearest first."""

    cluster: str
    chd: float | None
    median: float | None
    members: list[SimilarMember]


def similar_group(project_dir: Path, field: str, cluster: str) -> SimilarGroup:
    import numpy as np
    import pandas as pd

    path = clean.out_dir(project_dir) / clean.UNIVERSE_KEPT
    group, _, he = cluster.partition(":")
    cols = ["key", "latitude", "longitude", "model_group", "he_id", field]
    empty = SimilarGroup(cluster=cluster, chd=None, median=None, members=[])
    if not path.is_file():
        return empty
    u = pd.read_parquet(path)
    if any(c not in u for c in cols):
        return empty
    u = cast(pd.DataFrame, u[cols])
    u = cast(pd.DataFrame, u[(u["model_group"].astype(str) == group) & (u["he_id"].astype(str) == he)])
    v = cells.numbers(u, field)
    la, lo = cells.numbers(u, "latitude"), cells.numbers(u, "longitude")
    ok = la.notna() & lo.notna()
    valued = np.asarray(v.where(v > 0).dropna(), dtype=float)
    med = float(np.median(valued)) if len(valued) else None
    chd = round(float(100 * np.mean(np.abs(valued - med)) / med), 1) if med and len(valued) >= 2 else None
    members = [
        SimilarMember(key=str(k), lat=float(a), lon=float(b), value=None if pd.isna(x) else float(x))
        for k, a, b, x in zip(u["key"][ok], la[ok], lo[ok], v[ok], strict=True)
    ]
    members.sort(key=lambda m: -(m.value if m.value is not None else float("-inf")))
    return SimilarGroup(cluster=cluster, chd=chd, median=med, members=members)


def similar_points(project_dir: Path, field: str, group: str | None) -> SimilarPoints:
    """Each parcel's group of similar parcels (the equity clusters, he_id) and that group's spread of `field`'s
    values: the CHD, 100 x the mean absolute difference from the group's median over the median."""
    import numpy as np
    import pandas as pd

    empty = SimilarPoints(lon=[], lat=[], chd=[], size=[], cluster=[], clusters=[])
    path = clean.out_dir(project_dir) / clean.UNIVERSE_KEPT
    if not path.is_file():
        return empty
    cols = ["latitude", "longitude", "model_group", "he_id", field]
    u = pd.read_parquet(path)
    if any(c not in u for c in cols):
        return empty
    u = cast(pd.DataFrame, u[cols])
    if group:
        u = cast(pd.DataFrame, u[u["model_group"].astype(str) == group])
    u = u.assign(v=cells.numbers(u, field), la=cells.numbers(u, "latitude"), lo=cells.numbers(u, "longitude"))
    u = cast(pd.DataFrame, u[u["la"].notna() & u["lo"].notna()])
    # Each cluster within its model group: the ids are numbered per group.
    key = u["model_group"].astype(str) + ":" + u["he_id"].astype(str)
    valued = u["v"].where(u["v"] > 0)
    med = cast(pd.Series, valued.groupby(key).transform("median"))
    dev = cast(pd.Series, (valued - med).abs().groupby(key).transform("mean"))
    n = cast(pd.Series, valued.groupby(key).transform("count"))
    chd = (100 * dev / med).where((n >= 2) & (med > 0))
    codes, uniques = pd.factorize(key)
    return SimilarPoints(
        lon=np.round(np.asarray(u["lo"], dtype=float), 6).tolist(),
        lat=np.round(np.asarray(u["la"], dtype=float), 6).tolist(),
        chd=[None if not np.isfinite(x) else round(float(x), 1) for x in np.asarray(chd, dtype=float)],
        size=[int(x) for x in key.map(key.value_counts())],
        cluster=[int(x) for x in codes],
        clusters=[str(x) for x in uniques],
    )


if __name__ == "__main__":
    steps.main(run)

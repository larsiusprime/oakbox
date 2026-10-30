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
from typing import Literal, cast

from pydantic import Field

from oakbox import clean, steps
from oakbox.datafiles import BaseModel

MODULE = "ratio"
# The value checked: the whole parcel's market value (land and improvement values aren't sold on their own).
FIELD = "assr_market_value"
FIELD_NAME = "Assessed market value"
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
    return project_dir / "out" / "oakbox" / "ratio"


def _hydrated(project_dir: Path) -> Path:
    return project_dir / "out" / "look" / "2-clean-sales-hydrated.parquet"


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


class RatioState(BaseModel):
    start: dt.date | None = Field(default=None, description="First sale date; None: proposed.")
    end: dt.date | None = Field(default=None, description="Last sale date; None: the day before valuation.")
    price: Literal["sold", "time_adjusted"] = "sold"
    targets: Targets = Field(default_factory=Targets)
    classes: dict[str, PropertyClass] = Field(default_factory=dict, description="Group -> class; missing: proposed.")
    trim: bool = Field(default=True, description="Leave outlying ratios (1.5 x IQR) out of the statistics, listed.")
    region: str | None = Field(
        default=None, description='The location for neighbourhood price levels; "" none; None: Check sales\' location.'
    )


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


def classes(project) -> dict[str, PropertyClass]:
    s: RatioState = project.ratio
    return {g.id: s.classes.get(g.id) or proposed_class(g.id, g.name) for g in project.groups}


# ---------- Before running: what's there, and the window proposed ----------


class GroupSetup(BaseModel):
    id: str
    name: str
    color: str
    cls: PropertyClass
    proposed: bool = Field(description="The class is proposed from the group's name, not chosen.")
    sales: int = Field(description="Sales studied in the window.")


class SalesLine(BaseModel):
    sign: Literal["", "-", "="]
    count: int
    text: str


def region(project) -> str:
    """The location field for neighbourhood price levels: chosen, else where Check sales compares sales."""
    s: RatioState = project.ratio
    return s.region if s.region is not None else (project.clean.location or "")


class RatioSetup(BaseModel):
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
    targets: Targets
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
    value = clean._numbers(sales, field)
    return ok & clean._numbers(sales, "sale_price").gt(0) & value.notna()


def _in(sales, start: dt.date, end: dt.date):
    import pandas as pd

    return sales["sale_date"].ge(pd.Timestamp(start)) & sales["sale_date"].lt(pd.Timestamp(end) + pd.Timedelta(days=1))


def _years_back(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def window(project, sales=None, project_dir: Path | None = None) -> tuple[dt.date, dt.date, dt.date]:
    """(start, end, proposed start). The end: the day before the valuation date. The proposed start: the year before
    it (the IAAO's window), reaching back a year at a time (up to five) until there are enough sales."""
    s: RatioState = project.ratio
    val = project.valuation_date or dt.date(int(project.tax_year), 1, 1)
    end = s.end or (val - dt.timedelta(days=1))
    proposed = _years_back(val, 1)
    if sales is None and project_dir is not None:
        sales = _sales(project_dir)
    if sales is not None and len(sales):
        ok = _studied(sales, FIELD) if FIELD in sales else None
        for years in range(1, 6):
            start = _years_back(val, years)
            proposed = start
            if ok is not None and int((ok & _in(sales, start, end)).sum()) >= MIN_PROPOSED:
                break
    return s.start or proposed, end, proposed


def setup(project, project_dir: Path) -> RatioSetup:
    import pandas as pd

    s: RatioState = project.ratio
    sales = _sales(project_dir)
    if sales is None:
        raise LookupError("Check sales first: this starts from its hand-off.")
    universe_path = project_dir / "out" / "look" / "2-clean-universe.parquet"
    universe = pd.read_parquet(universe_path, columns=None) if universe_path.is_file() else sales
    start, end, proposed = window(project, sales)
    val = project.valuation_date or dt.date(int(project.tax_year), 1, 1)
    parcels = int(clean._numbers(universe, FIELD).gt(0).sum()) if FIELD in universe else 0
    studied = _studied(sales, FIELD) if FIELD in sales else pd.Series(False, index=sales.index)
    inside = _in(sales, start, end)
    year_before = int((studied & _in(sales, _years_back(val, 1), val - dt.timedelta(days=1))).sum())
    group_of = clean._groups(sales)
    cls = classes(project)
    groups = [
        GroupSetup(
            id=g.id,
            name=g.name,
            color=g.color,
            cls=cls[g.id],
            proposed=g.id not in s.classes,
            sales=int((studied & inside & (group_of == g.id)).sum()),
        )
        for g in project.groups
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
    return RatioSetup(
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
        targets=s.targets,
        groups=groups,
        funnel=funnel,
        trim=s.trim,
        region=region(project),
        regions=[
            clean.Choice(value=f, label=clean._names().get(f) or f)
            for f in clean._locations(project_dir, universe)
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
    cls: PropertyClass | None
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


def settings_key(project, project_dir: Path) -> dict:
    """What a run depends on: the Check sales run it starts from, and the calls."""
    r, _ = clean.STEP.ran(project_dir)
    start, end, _ = window(project, project_dir=project_dir)
    s: RatioState = project.ratio
    return {
        "clean": r.ran_at if r else None,
        "fields": [FIELD],
        "window": [str(start), str(end)],
        "price": s.price,
        "trim": s.trim,
        "targets": s.targets.model_dump(),
        "classes": classes(project),
        "groups": [(g.id, g.name) for g in project.groups],
        "region": region(project),
    }


def settings_hash(project, project_dir: Path) -> str:
    return steps.key_hash(settings_key(project, project_dir))


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


def _study(gid: str, name: str, color: str, cls, data: dict, table) -> Study:
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
    src = pdir / "out" / "2-clean-sup.pickle"
    if not src.is_file():
        raise RuntimeError("Check sales first: this starts from its hand-off.")
    s: RatioState = project.ratio
    start, end, _ = window(project, project_dir=pdir)
    tmp = steps.workdir(out_dir(pdir))
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
        settings = pl.load_settings()
        steps.emit(step="study", fraction=0.2, message="Checking the values against the sales")
        studies = run_value_field_studies(
            sup,
            settings,
            [FIELD] if FIELD in sup.universe else [],
            start_date=str(start),
            end_date=str(end),
            sale_field="sale_price" if s.price == "sold" else "sale_price_time_adj",
            trim_outliers=s.trim,
            median_ci="iaao",
            standards=s.targets.standards(),
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
            _study(g.id, g.name, g.color, cls[g.id], study["groups"][g.id], table)
            for g in project.groups
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
                        address=clean._text(address.get(str(t["key_sale"]))),
                        sale_date=t.get("sale_date"),
                        price=float(t["sale_price"]),
                        value=float(t["value"]),
                        ratio=float(t["ratio"]),
                        nominal=float(t["sale_price"]) < NOMINAL,
                    )
                )
        trimmed.sort(key=lambda x: -abs(clean._log(x.ratio)))
        results.append(
            FieldResult(
                field=field,
                name=FIELD_NAME if field == FIELD else field,
                groups=groups,
                overall=_study("", "All model groups", "#888888", None, study["overall"], table),
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
    (tmp / "settings.json").write_text(json.dumps({"hash": settings_hash(project, pdir)}), encoding="utf-8")
    steps.publish(tmp, out_dir(pdir))
    steps.emit(step="done", fraction=1.0, message=f"{sum(r.overall.sales for r in results):,} sales studied")


# ---------- The step's state ----------


class RatioView(steps.RunView):
    receipt: RatioReceipt | None
    accepted: bool


STEP = steps.Step(
    MODULE,
    RatioReceipt,
    key=settings_key,
    again="Check the values again first: something changed since they were checked.",
)


def blocked(project, project_dir: Path) -> list[str]:
    if (
        not clean.STEP.accepted(project, project_dir)
        or not (project_dir / "out" / "2-clean-sup.pickle").is_file()
        or not _hydrated(project_dir).is_file()
    ):
        return ["Press Looks right on Check sales first: this starts from the sales it kept."]
    return []


def view(project, project_dir: Path) -> RatioView:
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
    )


def start(project, project_dir: Path) -> None:
    stop = blocked(project, project_dir)
    if not stop:
        sales = _sales(project_dir)
        if sales is None or FIELD not in sales:
            stop = ["The parcels have no assessed market value (assr_market_value) to check."]
    STEP.start(project.id, project_dir, stop)


def accept(project, project_dir: Path) -> None:
    if blocked(project, project_dir):
        raise ValueError(STEP.again)
    STEP.accept(project, project_dir)


class RatioPatch(BaseModel):
    start: dt.date | None = None
    end: dt.date | None = None
    reset_window: bool | None = Field(default=None, description="True: back to the proposed window.")
    price: Literal["sold", "time_adjusted"] | None = None
    targets: Targets | None = None
    classes: dict[str, PropertyClass] | None = Field(default=None, description="Merged into the groups' classes.")
    trim: bool | None = None
    region: str | None = Field(default=None, description='A location field; "" for none.')


def change(project, body: RatioPatch) -> None:
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
    if body.targets is not None:
        s.targets = body.targets
    if body.classes is not None:
        s.classes = {**s.classes, **body.classes}
    if body.trim is not None:
        s.trim = body.trim
    if body.region is not None:
        s.region = body.region


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
    lat, lon = clean._numbers(t, "latitude"), clean._numbers(t, "longitude")
    t = t[lat.notna() & lon.notna()]
    return [
        MapPoint(lat=float(a), lon=float(b), ratio=float(r), price=float(p), value=float(v), trimmed=bool(x))
        for a, b, r, p, v, x in zip(
            t["latitude"], t["longitude"], t["ratio"], t["sale_price"], t["value"], t["trimmed"], strict=True
        )
    ]


if __name__ == "__main__":
    steps.main(run)

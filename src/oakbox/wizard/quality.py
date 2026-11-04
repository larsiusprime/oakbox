"""Quality and condition (F3d): a number where higher is better. Words and letter grades put in order (known
vocabularies, or the user's tiers), a column scaled, and the evidence for its order from the sales: price by tier,
and age for a condition. Also the candidate columns for these fields.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import (
    AREA_FIELDS,
    SQFT_PER,
    BaseModel,
    DataFile,
    Scale,
    scale_calc,
    scale_helper,
    small_unit,
)
from oakbox.projects import Project
from oakbox.wizard.base import PAIRS, SCALED, YES
from oakbox.wizard.checks import _pct
from oakbox.wizard.files import Files, file_stamp, sales_file, values_of
from oakbox.wizard.models import Check
from oakbox.wizard.money import _plain, _read_numbers, _symbol
from oakbox.wizard.rules import rule_complete, rule_result

# ---------- Quality and condition: a number where higher is better (F3d) ----------

QUALITY_NAMES = re.compile(r"qual|grade", re.IGNORECASE)
CONDITION_NAMES = re.compile(r"cond|depr|good|cdu", re.IGNORECASE)
FEW_SALES = 10  # a tier with fewer sales than this says so, and isn't counted as out of order
TREND = 0.3  # a rank correlation with age beyond this says which way a condition column runs

# Tier names whose order is known, worst to best: the score only orders them.
WORD_SCORES = {
    **dict.fromkeys(("unsound", "un"), 0),
    **dict.fromkeys(("verypoor", "vp"), 1),
    **dict.fromkeys(("poor", "pr", "p"), 2),
    **dict.fromkeys(("fair", "fr", "f"), 3),
    **dict.fromkeys(("belowaverage", "belowavg", "ba"), 3.5),
    **dict.fromkeys(("average", "avg", "av", "a", "normal", "typical"), 4),
    **dict.fromkeys(("aboveaverage", "aboveavg", "aa"), 4.5),
    **dict.fromkeys(("good", "gd", "g"), 5),
    **dict.fromkeys(("verygood", "vg"), 6),
    **dict.fromkeys(("excellent", "ex", "exc", "e"), 7),
    **dict.fromkeys(("low", "lowcost", "cheap"), 1),
}


def _letter(v: str) -> float | None:
    # A, B+, C-, and with a number (B+5, A-10: Guilford's grade adjustments, in percent)
    # (a number only after a sign: C1 is a condition rating, not a grade)
    m = re.fullmatch(r"(A{1,3}|[A-F])\s*(?:([+-])\s*(\d{1,2})|([+-]{0,2}))", v.strip().upper())
    if not m:
        return None
    base = 5 + len(m[1]) - 1 if m[1].startswith("A") else {"B": 4, "C": 3, "D": 2, "E": 1, "F": 0}[m[1]]
    if m[3]:
        return base + (1 if m[2] == "+" else -1) * int(m[3]) / 100
    return base + 0.3 * (m[4].count("+") - m[4].count("-"))


def _words(v: str) -> float | None:
    return WORD_SCORES.get(re.sub(r"[^a-z]", "", re.sub(r"^\s*\d+\W*", "", v.lower())))


def _uad(v: str) -> float | None:
    m = re.fullmatch(r"[QC]\s*-?\s*(\d)", v.strip().upper())
    return -int(m[1]) if m else None


def _numbered(v: str) -> float | None:
    m = re.match(r"^\s*(-?\d+(\.\d+)?)", v)
    return float(m[1]) if m else None


VOCABULARIES = [
    ("letter grades, AA best", _letter),
    ("words, Excellent best", _words),
    ("Q1–Q6 or C1–C6, 1 best", _uad),
    ("numbered, higher is better", _numbered),
]


def tier_order(values: list[str]) -> tuple[list[tuple[str, float]], str | None, list[str]]:
    """Tiers worst to best with equal steps (1, 2, 3…; the same for names meaning the same), the vocabulary that
    ordered them, and those it didn't know (put last, for the user to place)."""
    best = max(VOCABULARIES, key=lambda vc: sum(vc[1](v) is not None for v in values))
    name, score = best
    # Only a vocabulary that knows most of the names orders them: one stray match (C-5 as a condition) isn't one.
    if sum(score(v) is not None for v in values) < max(1, len(values) / 2):
        return [(v, float(i + 1)) for i, v in enumerate(sorted(values))], None, sorted(values)
    known = sorted((v for v in values if score(v) is not None), key=lambda v: (score(v), v))
    unknown = sorted(v for v in values if score(v) is None)
    out: list[tuple[str, float]] = []
    n, last = 0, None
    for v in known:
        s = score(v)
        if s != last:
            n, last = n + 1, s
        out.append((v, float(n)))
    for v in unknown:
        n += 1
        out.append((v, float(n)))
    return out, name, unknown


def _qc_values(files: Files, entry: DataFile, column: str) -> tuple[str, ...]:
    return values_of(file_stamp(files.in_dir / entry.filename), entry.layer, column)


def _new_scale(files: Files, entry: DataFile, key: str, column: str, given: Scale | None = None) -> Scale:
    """A scale for a column: the user's, with the column's range filled in; or a first one that says nothing yet
    (a category: tiers to rank; numbers: which way they run, and for condition whether they're 0-1 fractions)."""
    values = _qc_values(files, entry, column)
    if not _plain(values) or (given is not None and given.kind == "tiers"):
        return Scale(kind="tiers", tiers=dict(given.tiers) if given and given.kind == "tiers" else {})
    nums = [float(v) for v in values if v]
    s = given.model_copy(update={"tiers": {}}) if given is not None else Scale()
    if nums:
        s.low, s.high = min(nums), max(nums)
        if given is None and key == "bldg_condition_num":
            s.fraction = 0 <= s.low and s.high <= 1
    return s


def _scaled(nums: list[float], s: Scale) -> list[float]:
    """Numbers as the scale's calc writes them (scale_calc)."""
    if s.kind in ("pct_good", "pct_depr"):
        pct = [v * 100 for v in nums] if s.fraction else nums
        return [100 - v for v in pct] if s.kind == "pct_depr" else pct
    if s.kind == "lower" and s.low is not None and s.high is not None:
        return [s.low + s.high - v for v in nums]
    return list(nums)


def short_number(v: float) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".") if v != round(v) else f"{v:,.0f}"


def _scale_check(files: Files, entry: DataFile, key: str, column: str, s: Scale) -> Check:
    """'✓ 0.15–4.5 · 47 values', '✓ as % good: 0.12 → 88 · median 84', or what's still to say."""
    import statistics

    raw = _qc_values(files, entry, column)
    if s.kind == "tiers":
        distinct = {v for v in raw if v}
        if not s.tiers:
            return Check(ok=True, warn=True, text=f"rank its {len(distinct):,} tiers")
        ranked = {k.strip() for k in s.tiers}
        numbers = sorted(set(s.tiers.values()))
        text = f"{len(ranked & distinct):,} tiers ranked, {short_number(numbers[0])}–{short_number(numbers[-1])}"
        missing = distinct - ranked
        if missing:
            return Check(ok=True, warn=True, text=f"{text} · {len(missing):,} not ranked (read as missing)")
        return Check(ok=True, text=f"✓ {text}")
    nums = [float(v) for v in raw if v]
    if s.kind is None:
        return Check(
            ok=True,
            warn=True,
            text="say which way is better" if key == "bldg_quality_num" else "say what the numbers mean",
        )
    if not nums:
        return Check(ok=True, warn=True, text="no values")
    out = _scaled(nums, s)
    if s.kind in ("pct_good", "pct_depr"):
        median = short_number(statistics.median(out))
        text = f"as % good: {short_number(nums[0])} → {short_number(out[0])} · median {median}"
        outside = sum(1 for v in out if v < -0.5 or v > 100.5)
        if outside:
            hint = "written as 0–100, not fractions?" if s.fraction else "written as fractions, 0–1?"
            return Check(ok=True, warn=True, text=f"{text} · {outside:,} outside 0–100: {hint}")
        return Check(ok=True, text=f"✓ {text}")
    if s.kind == "life":
        return Check(ok=True, text=f"✓ years left · median {short_number(statistics.median(out))}")
    text = f"{short_number(min(nums))}–{short_number(max(nums))}"  # how many values: on its "N values" button
    return Check(ok=True, text=f"✓ {text}" + (" · flipped, so higher is better" if s.kind == "lower" else ""))


# Evidence: what the choices are checked against. Optional: each part says what it's based on, and what's missing.


def _field_by_id(
    project: Project, files: Files, key: str, match: str, only: DataFile | None = None
) -> dict[str, float]:
    """A loaded parcel field as numbers, by parcel ID (the first row of each): areas in the project's unit. From the
    first parcel file that loads it, or from the one file given."""
    import pandas as pd

    f = next(
        (
            x
            for x in ([only] if only is not None else project.files)
            if key in x.load
            and match in x.load
            and x.holds not in ("sales", "overlay", "unused")
            and x.name in files.preview
        ),
        None,
    )
    if f is None:
        return {}
    stamp = file_stamp(files.in_dir / f.filename)
    column = f.load[key][0]
    if key in f.numbers:
        nums = list(_read_numbers(stamp, f.layer, column, f.numbers[key].model_dump_json()))
    else:
        nums = pd.Series(pd.to_numeric(pd.Series(values_of(stamp, f.layer, column)), errors="coerce")).tolist()
    factor = 1.0
    if key in AREA_FIELDS:
        factor = SQFT_PER[f.area_units.get(key, small_unit(project.units))] / SQFT_PER[small_unit(project.units)]
    out: dict[str, float] = {}
    for i, v in zip(files.ids(f.name, match), nums, strict=True):
        if i and v == v and i not in out:
            out[i] = float(v) * factor
    return out


def _ages(project: Project, files: Files, match: str) -> tuple[dict[str, float], str | None]:
    """Each building's age at the valuation date, from the effective year built (or, failing that, year built)."""
    year = project.valuation_date.year if project.valuation_date else project.tax_year
    for key, basis in (("bldg_effective_year_built", "effective age"), ("bldg_year_built", "age (year built)")):
        built = _field_by_id(project, files, key, match)
        ages = {i: year - v for i, v in built.items() if 1700 <= v <= 2100}
        if ages:
            return ages, basis
    return {}, None


def _sales_evidence(project: Project, files: Files, match: str) -> tuple[list[tuple[str, float]], list[str]]:
    """(parcel ID, price) for each sale to compare against, and notes on what that's based on."""
    import pandas as pd

    sales = sales_file(project)
    if sales is None or "sale_price" not in sales.load or sales.name not in files.preview:
        return [], ["No sales yet: add them to compare by price."]
    if sales.match != match:
        return [], ["The sales join the parcels on another ID: no price comparison."]
    stamp = file_stamp(files.in_dir / sales.filename)
    column = sales.load["sale_price"][0]
    if "sale_price" in sales.numbers:
        prices = list(_read_numbers(stamp, sales.layer, column, sales.numbers["sale_price"].model_dump_json()))
    else:
        prices = pd.Series(pd.to_numeric(pd.Series(values_of(stamp, sales.layer, column)), errors="coerce")).tolist()
    notes = []
    rule = sales.rules.get("valid_sale")
    if rule is not None and rule_complete(rule):
        valid = rule_result(files, sales, rule)[2].tolist()
        notes.append("valid sales")
    elif "valid_sale" in sales.load:
        valid = [v.lower() in YES for v in values_of(stamp, sales.layer, sales.load["valid_sale"][0])]
        notes.append("valid sales")
    else:
        valid = [True] * len(prices)
        notes.append("all sales: no valid-sale rule yet")
    rows = [
        (i, float(p))
        for i, p, ok in zip(files.ids(sales.name, match), prices, valid, strict=True)
        if ok and i and p == p and p > 0
    ]
    return rows, notes


class PriceGroup(BaseModel):
    sales: int
    median: float | None
    price: float | None = None


def _price_by(
    project: Project, files: Files, match: str, group: dict[str, str]
) -> tuple[dict[str, PriceGroup], str | None, list[str]]:
    """Median price per sq ft (or sale price, without a building size) for each group of parcels."""
    import statistics

    rows, notes = _sales_evidence(project, files, match)
    if not rows:
        return {}, None, notes
    size = _field_by_id(project, files, "bldg_area_finished_sqft", match)
    unit = "sq ft" if small_unit(project.units) == "sqft" else "m²"
    basis = f"price per {unit}" if size else "sale price"
    if not size:
        notes.append("no building size: choose it on this step for a fairer comparison")
    by: dict[str, list[float]] = {}
    whole: dict[str, list[float]] = {}
    for i, price in rows:
        g = group.get(i)
        if g is None:
            continue
        if size:
            area = size.get(i, 0)
            if area <= 0:
                continue
            whole.setdefault(g, []).append(price)
            price = price / area
        by.setdefault(g, []).append(price)
    out = {
        g: PriceGroup(
            sales=len(v),
            median=statistics.median(v),
            price=statistics.median(whole[g]) if size else statistics.median(v),
        )
        for g, v in by.items()
    }
    if not out:
        notes.append("no sales found these parcels")
    return out, basis, notes


def _by_parcel(files: Files, entry: DataFile, column: str) -> dict[str, str]:
    """A column's value for each parcel (its first row: the main building card)."""
    values = _qc_values(files, entry, column)
    out: dict[str, str] = {}
    for i, v in zip(files.ids(entry.name, entry.match), values, strict=True):
        if i and v and i not in out:
            out[i] = v
    return out


def _trend(project: Project, files: Files, entry: DataFile, column: str) -> tuple[float | None, str | None]:
    """The rank correlation of a numbers column with age, and which age it's against."""
    import pandas as pd

    ages, basis = _ages(project, files, entry.match)
    if not ages:
        return None, None
    pairs = [(float(v), ages[i]) for i, v in _by_parcel(files, entry, column).items() if i in ages]
    if len(pairs) < 20:
        return None, basis
    df = pd.DataFrame({"v": [p[0] for p in pairs], "age": [p[1] for p in pairs]}).rank()
    r = float(pd.Series(df["v"]).corr(pd.Series(df["age"])))
    return (None if r != r else r), basis


class Tier(BaseModel):
    value: str
    count: int = Field(description="Rows (building cards) with it.")
    number: float | None = Field(description="Its number: the saved one, or the suggested one. None: not ranked.")
    sales: int
    median: float | None = Field(description="Median price per sq ft (or sale price) of its sales.")
    price: float | None = Field(default=None, description="Median sale price of its sales.")


class TiersPreview(BaseModel):
    key: str
    column: str
    tiers: list[Tier] = Field(description="Worst to best: as saved, or as suggested.")
    saved: bool
    recognised: str | None = Field(description="The kind of tier names that set the suggested order.")
    unplaced: list[str] = Field(description="Tier names the suggestion didn't know: put last, to be placed.")
    basis: str | None = Field(description="What the medians are: price per sq ft, or sale price.")
    notes: list[str]
    symbol: str
    few: int = FEW_SALES


def tiers_preview(project: Project, in_dir: Path, key: str, file: str, column: str) -> TiersPreview:
    """A category's tiers, worst to best, with a number each and what they sell for."""
    if key not in SCALED:
        raise LookupError(key)
    files = Files(project, in_dir)
    if files.column(file, column) is None:
        raise ValueError(f"{file} has no column {column}.")
    entry = files.entry(file)
    counts = Counter(v for v in _qc_values(files, entry, column) if v)
    saved = entry.scales.get(key)
    use_saved = bool(saved and saved.kind == "tiers" and saved.tiers and entry.load.get(key, [None])[0] == column)
    suggested, recognised, unplaced = tier_order(list(counts))
    if use_saved and saved:
        numbers = {k.strip(): v for k, v in saved.tiers.items()}
        order = sorted(counts, key=lambda v: (numbers.get(v, float("inf")), v))
        ranked = [(v, numbers.get(v)) for v in order]
    else:
        ranked = [(v, n) for v, n in suggested]
    prices, basis, notes = _price_by(project, files, entry.match, _by_parcel(files, entry, column))
    return TiersPreview(
        key=key,
        column=column,
        tiers=[
            Tier(
                value=v,
                count=counts[v],
                number=n,
                sales=prices[v].sales if v in prices else 0,
                median=prices[v].median if v in prices else None,
                price=prices[v].price if v in prices else None,
            )
            for v, n in ranked
        ],
        saved=use_saved,
        recognised=recognised,
        unplaced=unplaced,
        basis=basis,
        notes=notes,
        symbol=_symbol(project),
    )


class Band(BaseModel):
    label: str
    count: int
    raw: float | None = Field(description="The median as written.")
    value: float | None = Field(description="The median as read (higher is better).")


class ValueBand(BaseModel):
    """Sales of parcels whose value, as read, falls in a band: one row per value when there are few."""

    label: str = Field(description='The value as read ("7"), or a range ("under 40", "40–55", "85 and up").')
    original: str = Field(default="", description='The value as the file writes it ("2"), or its range ("0.1–0.4").')
    text: str = Field(description='The text the parcels carry beside it ("C-"), most common first; "" none.')
    sales: int
    price: float | None = Field(description="Median sale price.")
    per_area: float | None = Field(description="Median price per area of building; None without a building size.")
    type_sales: int = Field(default=0, description="Sales of the most common type among them.")
    type_price: float | None = Field(default=None, description="Median sale price of the most common type.")


class ScaleSample(BaseModel):
    raw: str
    value: float


class ScalePreview(BaseModel):
    key: str
    column: str
    scale: Scale
    kinds: list[str] = Field(description="The meanings to choose from, for this field.")
    fraction_found: bool = Field(description="Every value is between 0 and 1.")
    trend: float | None = Field(description="Rank correlation with age: positive, it rises as buildings age.")
    fits: list[str] = Field(
        description="Meanings that fit the trend with age (higher is better as buildings are newer)."
    )
    age_basis: str | None
    by_age: list[Band]
    price_basis: str | None
    by_value: list[ValueBand] = Field(
        description="The value as read (one row each when few, else five bands), with what its sales went for."
    )
    by_type: str = Field(default="", description='The type compared alone ("SFR_DETACHED"); "" none.')
    type_field: str = Field(default="", description="The field the type is read from (land_class…).")
    notes: list[str]
    median: float | None
    samples: list[ScaleSample]
    calc: list | None = Field(description="The calc it writes; None when the column is loaded as it is.")
    load: dict[str, list[str]] = Field(description="What it loads.")
    symbol: str


AGE_BANDS = [
    (0, 10, "under 10 years"),
    (10, 25, "10–25"),
    (25, 50, "25–50"),
    (50, 75, "50–75"),
    (75, 1e9, "75 and over"),
]
GOOD_BANDS = [(-1e9, 50, "under 50"), (50, 70, "50–70"), (70, 85, "70–85"), (85, 95, "85–95"), (95, 1e9, "95 and over")]


def scale_preview(
    project: Project, in_dir: Path, key: str, file: str, column: str, scale: Scale | None
) -> ScalePreview:
    """A numbers column read with a meaning: against age (newer should be better) and what it sells for."""
    import statistics

    if key not in SCALED:
        raise LookupError(key)
    files = Files(project, in_dir)
    if files.column(file, column) is None:
        raise ValueError(f"{file} has no column {column}.")
    entry = files.entry(file)
    raw = _qc_values(files, entry, column)
    if not _plain(raw):
        raise ValueError(f"{column} isn't numbers: rank its tiers instead.")
    saved = entry.scales.get(key) if entry.load.get(key, [None])[0] == column else None
    s = _new_scale(files, entry, key, column, scale or saved)
    nums = [float(v) for v in raw if v]
    kinds = ["higher", "lower"] if key == "bldg_quality_num" else ["pct_good", "pct_depr", "higher", "lower", "life"]
    trend, age_basis = _trend(project, files, entry, column)
    fits: list[str] = []
    if trend is not None and abs(trend) >= TREND:
        fits = ["pct_depr", "lower"] if trend > 0 else ["pct_good", "higher", "life"]
    # Age says which way condition runs; quality needn't follow age, so it isn't held to it.
    fits = [k for k in fits if k in kinds] if key == "bldg_condition_num" else []
    read = s.kind is not None
    convert = (lambda xs: _scaled(xs, s)) if read else (lambda xs: xs)
    notes: list[str] = []
    by_age: list[Band] = []
    ages, _ = _ages(project, files, entry.match)
    values = {i: float(v) for i, v in _by_parcel(files, entry, column).items()}
    if ages:
        for lo, hi, label in AGE_BANDS:
            xs = [v for i, v in values.items() if i in ages and lo <= ages[i] < hi]
            if xs:
                by_age.append(
                    Band(label=label, count=len(xs), raw=statistics.median(xs), value=statistics.median(convert(xs)))
                )
    else:
        notes.append("No year built or effective year built: choose one on this step to compare with age.")
    by_value: list[ValueBand] = []
    price_basis = None
    by_type = type_field = ""
    if read and values:
        as_read = dict(zip(values, convert(list(values.values())), strict=True))
        by_value, price_basis, by_type, type_field, price_notes = _value_bands(
            project, files, entry, key, as_read, s, values
        )
        notes += price_notes
    seen: list[str] = []
    for v in raw:
        if v and v not in seen:
            seen.append(v)
        if len(seen) == 6:
            break
    out = convert([float(v) for v in seen])
    if scale_calc(scale_helper(key), s) is None:
        written = ({key: [column, "float"]}, None)
    else:
        written = ({scale_helper(key): [column, "float"]}, scale_calc(scale_helper(key), s))
    return ScalePreview(
        key=key,
        column=column,
        scale=s,
        kinds=kinds,
        fraction_found=bool(nums) and min(nums) >= 0 and max(nums) <= 1,
        trend=trend,
        fits=fits,
        age_basis=age_basis,
        by_age=by_age,
        price_basis=price_basis,
        by_value=by_value,
        by_type=by_type,
        type_field=type_field,
        notes=notes,
        median=statistics.median(convert(nums)) if nums and read else None,
        samples=[ScaleSample(raw=r, value=v) for r, v in zip(seen, out, strict=True)],
        calc=written[1] if read else None,
        load=written[0] if read else {},
        symbol=_symbol(project),
    )


# The parcel fields that say what kind of property it is, in the order tried: the first one loaded is used to compare
# like with like (a grade is often tied to a type: the lowest only on small houses, the middle mostly townhouses).
TYPE_FIELDS = ("land_class", "bldg_type", "bldg_desc", "bldg_class", "bldg_style")
# At most this many values as read: a row each. More, and they're cut into five bands with as many parcels each.
FEW_VALUES = 10


def _text_by_id(project: Project, files: Files, key: str, match: str) -> dict[str, str]:
    """A loaded parcel field as text, by parcel ID (the first row of each), from the first parcel file loading it."""
    f = next(
        (
            x
            for x in project.files
            if key in x.load
            and match in x.load
            and x.holds not in ("sales", "overlay", "unused")
            and x.name in files.preview
        ),
        None,
    )
    return _by_parcel(files, f, f.load[key][0]) if f is not None else {}


def _value_cuts(as_read: dict[str, float], kind: str | None) -> list[tuple[float, float, str]]:
    """(low, high, label) bands of values as read: each value its own when there are few; percentages in fixed
    bands; else five bands with as many parcels each, labelled as ranges (low included, high not)."""
    distinct = sorted(set(as_read.values()))
    if len(distinct) <= FEW_VALUES:
        return [(v, v, short_number(v)) for v in distinct]
    if kind in ("pct_good", "pct_depr"):
        return GOOD_BANDS
    ordered = sorted(as_read.values())
    cuts = sorted({ordered[int(q * (len(ordered) - 1))] for q in (0.2, 0.4, 0.6, 0.8)} - {ordered[0]})
    edges = [-1e18, *cuts, 1e18]
    out = []
    for lo, hi in zip(edges, edges[1:], strict=False):
        if lo == -1e18:
            label = f"under {short_number(hi)}" if hi != 1e18 else "all"
        elif hi == 1e18:
            label = f"{short_number(lo)} and up"
        else:
            label = f"{short_number(lo)}–{short_number(hi)}"
        out.append((lo, hi, label))
    return out


def _value_bands(
    project: Project,
    files: Files,
    entry: DataFile,
    key: str,
    as_read: dict[str, float],
    s: Scale,
    raw: dict[str, float] | None = None,
) -> tuple[list[ValueBand], str | None, str, str, list[str]]:
    """Each band's sales: median price, price per area, and the price among the most common type alone. A grade's
    price per area mostly says how big its buildings are and what kind they are, so on its own it can run the
    wrong way; the price within one type is the fairer read."""
    import statistics

    bands = _value_cuts(as_read, s.kind)

    def band_of(v: float) -> str | None:
        for lo, hi, label in bands:
            if (lo == hi and v == lo) or (lo != hi and lo <= v < hi):
                return label
        return None

    label_of = {i: b for i, v in as_read.items() if (b := band_of(v)) is not None}
    by_band: dict[str, set[float]] = {}
    for i, b in label_of.items():
        if raw and i in raw:
            by_band.setdefault(b, set()).add(raw[i])
    rows, notes = _sales_evidence(project, files, entry.match)
    notes = [n for n in notes if n != "valid sales"]
    if not rows:
        return [], None, "", "", notes
    sold = [(i, p, label_of[i]) for i, p in rows if i in label_of]
    if not sold:
        return [], None, "", "", [*notes, "no sales found these parcels"]
    size = _field_by_id(project, files, "bldg_area_finished_sqft", entry.match)
    unit = "sq ft" if small_unit(project.units) == "sqft" else "m²"
    if not size:
        notes.append("no building size: choose it on this step to see the price per area")
    pair = PAIRS.get(key)
    texts = _text_by_id(project, files, pair, entry.match) if pair else {}
    types: dict[str, str] = {}
    type_field = ""
    for k in TYPE_FIELDS:
        types = _text_by_id(project, files, k, entry.match)
        if types:
            type_field = k
            break
    kinds = Counter(types[i] for i, _, _ in sold if i in types)
    main = kinds.most_common(1)[0][0] if len(kinds) > 1 else ""
    out = []
    for _, _, label in bands:
        mine = [(i, p) for i, p, b in sold if b == label]
        if not mine:
            continue
        areas = [p / size[i] for i, p in mine if size.get(i, 0) > 0]
        same = [p for i, p in mine if main and types.get(i) == main]
        said = Counter(texts[i] for i, _ in mine if texts.get(i)).most_common(3)
        # As the file writes it: one value, or the range of the band's parcels (a flipped band runs the other way).
        written = sorted(by_band.get(label, ()))
        original = (
            ""
            if not written
            else short_number(written[0])
            if len(written) == 1
            else f"{short_number(written[0])}–{short_number(written[-1])}"
        )
        out.append(
            ValueBand(
                label=label,
                original=original,
                text=" / ".join(t for t, _ in said),
                sales=len(mine),
                price=statistics.median(p for _, p in mine),
                per_area=statistics.median(areas) if areas else None,
                type_sales=len(same),
                type_price=statistics.median(same) if same else None,
            )
        )
    return out, f"price per {unit}" if size else None, main, type_field if main else "", notes


class Candidate(BaseModel):
    file: str
    column: str
    kind: Literal["numbers", "text"]
    filled: float = Field(description="Share of rows not blank.")
    distinct: int
    low: float | None
    high: float | None
    samples: list[str]
    notes: list[str]
    warn: bool
    loaded_as: Literal["number", "category"] | None


def candidates(project: Project, in_dir: Path, key: str) -> list[Candidate]:
    """Columns that look like quality (or condition), each checked over every row, to choose from side by side."""
    if key not in PAIRS:
        raise LookupError(key)
    num = key if key in SCALED else PAIRS[key]
    txt = PAIRS[num]
    names = QUALITY_NAMES if num == "bldg_quality_num" else CONDITION_NAMES
    files = Files(project, in_dir)
    out = []
    for f in project.files:
        if f.holds in ("sales", "overlay", "unused") or f.name not in files.preview:
            continue
        loaded = {spec[0]: k for k, spec in f.load.items() if k in (num, txt)}
        for col in files.columns(f.name):
            looks = names.search(col.name) and not re.search(r"air|hvac", col.name, re.IGNORECASE)
            if not looks and col.name not in loaded:
                continue
            values = values_of(file_stamp(in_dir / f.filename), f.layer, col.name)
            filled = [v for v in values if v]
            distinct = set(filled)
            numbers = bool(filled) and _plain(values)
            nums = [float(v) for v in filled] if numbers else []
            notes: list[str] = []
            warn = False
            if not filled:
                notes.append("Empty")
                warn = True
            elif len(distinct) == 1:
                notes.append("One value on every row: tells nothing apart")
                warn = True
            if values and len(filled) / len(values) < 0.5 and filled:
                notes.append(f"{_pct(len(values) - len(filled), len(values))} blank")
                warn = True
            if numbers and len(distinct) > 1:
                if min(nums) >= 0 and max(nums) <= 1:
                    notes.append("Fractions, 0–1")
                if num == "bldg_condition_num":
                    trend, basis = _trend(project, files, f, col.name)
                    if trend is not None and trend >= TREND:
                        notes.append(f"Rises with {basis}: % depreciation, or lower is better")
                    elif trend is not None and trend <= -TREND:
                        notes.append(f"Falls with {basis}: % good, or higher is better")
            elif filled and len(distinct) > 1:
                if "cdu" in col.name.lower() or distinct <= {"EX", "VG", "GD", "AV", "FR", "PR", "VP", "UN"}:
                    notes.append("CDU: condition, desirability and utility in one rating, so more than condition")
                with_pct = next((v for v in filled[:500] if re.search(r"\d\s*%", v)), None)
                if with_pct:
                    notes.append(f"A code and a percent in one ({with_pct})")
                _, recognised, unplaced = tier_order(sorted(distinct))
                if len(distinct) > 30:
                    notes.append(f"{len(distinct):,} different values: many tiers to rank")
                elif recognised and not unplaced:
                    notes.append(f"Tiers: {recognised}")
                else:
                    notes.append(f"{len(distinct):,} tiers, order not recognised")
            as_ = loaded.get(col.name)
            out.append(
                Candidate(
                    file=f.name,
                    column=col.name,
                    kind="numbers" if numbers else "text",
                    filled=len(filled) / len(values) if values else 0,
                    distinct=len(distinct),
                    low=min(nums) if nums else None,
                    high=max(nums) if nums else None,
                    samples=list(dict.fromkeys(filled))[:4],
                    notes=notes,
                    warn=warn,
                    loaded_as="number" if as_ == num else "category" if as_ == txt else None,
                )
            )
    return out

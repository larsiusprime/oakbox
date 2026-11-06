"""Areas and money (F3d): the unit an area column is in and whether its sizes look right, and money written as
text: its number format, reading it, and whether the amounts (a sale price, an assessed value) look right.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from oakbox.datafiles import (
    AREA_FIELDS,
    SQFT_PER,
    BaseModel,
    DataFile,
    NumberFormat,
    number_calc,
    number_helper,
    small_unit,
)
from oakbox.errors import NotFound
from oakbox.projects import Project
from oakbox.wizard.files import Files, file_stamp, values_of
from oakbox.wizard.models import Check

# ---------- Areas: the unit a column is in (F3d) ----------

UNIT_WORDS = {
    "sqft": "sq ft",
    "sqm": "m²",
    "acres": "acres",
    "hectares": "ha",
    "sqyd": "sq yd",
    "tsubo": "tsubo",
    "pyeong": "pyeong",
    "mu": "mu",
}
# A typical parcel or building, in square feet, outside these is likely in the wrong unit.
PLAUSIBLE_SQFT = {"land_area_sqft": (500, 5_000_000), "bldg_area_finished_sqft": (200, 50_000)}
PLAUSIBLE_SQFT["bldg_area_footprint_sqft"] = PLAUSIBLE_SQFT["bldg_area_finished_sqft"]


def area_check(files: Files, entry: DataFile, key: str, column: str, unit: str, units: str) -> Check:
    """'✓ 0.114 acres → 4,966 sq ft', and a warning when the typical size says the unit is wrong."""
    import statistics

    target = small_unit(units)
    factor = SQFT_PER[unit] / SQFT_PER[target]
    nums = []
    for v in values_of(file_stamp(files.in_dir / entry.filename), entry.layer, column):
        try:
            nums.append(float(v))
        except ValueError:
            continue
    nums = [n for n in nums if n > 0]
    if not nums:
        return Check(ok=True, text="✓ numbers")
    sample = next(n for n in nums)
    shown = f"{sample:,.3f}".rstrip("0").rstrip(".")
    text = f"{shown} {UNIT_WORDS[unit]} → {sample * factor:,.0f} {UNIT_WORDS[target]}"
    if unit == target:
        text = f"in {UNIT_WORDS[unit]}"
    median_sqft = statistics.median(nums) * SQFT_PER[unit]
    low, high = PLAUSIBLE_SQFT.get(key, (0, float("inf")))
    if median_sqft < low:
        return Check(ok=True, warn=True, text=f"{text} · very small: is it in a bigger unit?")
    if median_sqft > high:
        return Check(ok=True, warn=True, text=f"{text} · very large: is it in a smaller unit?")
    return Check(ok=True, text=f"✓ {text}")


class Bin(BaseModel):
    low: float
    high: float
    count: int


class FieldSpread(BaseModel):
    """A number field's values as loaded (sizes in the project's unit, years as years): bins across the middle 98%,
    and what's outside."""

    unit: str = Field(description='The unit, as words (sq ft, m²); "" for years.')
    year: bool = Field(default=False, description="Years: bins labelled as years, never in decimals.")
    bins: list[Bin]
    below: int = Field(description="Sizes under the first bin (the smallest 1%).")
    above: int = Field(description="Sizes over the last bin (the largest 1%).")
    empty: int = Field(description="Rows with no value: blank, zero (none), or not a number.")
    median: float | None
    total: int


def _step(span: float, bins: int, whole: bool = False) -> float:
    """A round bin width (1, 2, 2.5 or 5 × a power of ten) giving about this many bins across the span; at least 1,
    and never 2.5, for whole numbers (years)."""
    raw = span / bins if span > 0 else 1.0
    if whole:
        raw = max(raw, 1.0)
        power = 10 ** math.floor(math.log10(raw))
        return next(m * power for m in (1, 2, 5, 10) if m * power >= raw)
    power = 10 ** math.floor(math.log10(raw))
    return next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)


def field_histogram(project: Project, in_dir: Path, key: str, bins: int = 24) -> FieldSpread:
    """How a number field's values spread, read as it's loaded: an area in its unit, converted to the project's; a
    year as a year (0, written for none, left out)."""
    import statistics

    files = Files(project, in_dir)
    entry = next(
        (f for f in project.files if key in f.load and f.holds not in ("sales", "overlay", "unused")),
        None,
    )
    target = small_unit(project.units)
    if entry is None:
        raise NotFound(key)
    column = entry.load[key][0]
    year = "year" in key
    area = key in AREA_FIELDS
    factor = SQFT_PER[entry.area_units.get(key, target)] / SQFT_PER[target] if area else 1.0
    raw = values_of(file_stamp(files.in_dir / entry.filename), entry.layer, column)
    nums = []
    for v in raw:
        try:
            n = float(v) * factor
        except ValueError:
            continue
        if n == n and (1700 <= n <= 2100 if year else n > 0):
            nums.append(n)
    out = FieldSpread(
        unit=UNIT_WORDS[target] if area else "",
        year=year,
        bins=[],
        below=0,
        above=0,
        empty=len(raw) - len(nums),
        median=None,
        total=len(raw),
    )
    if not nums:
        return out
    ordered = sorted(nums)
    low = ordered[int(0.01 * (len(ordered) - 1))]
    high = ordered[int(0.99 * (len(ordered) - 1))]
    width = _step(high - low, bins, whole=year)
    start = math.floor(low / width) * width
    count = max(1, math.ceil((high - start) / width + 1e-9))
    counts = [0] * count
    for n in nums:
        i = math.floor((n - start) / width)
        if n < start:
            out.below += 1
        elif i >= count:
            out.above += 1
        else:
            counts[i] += 1
    out.bins = [Bin(low=start + i * width, high=start + (i + 1) * width, count=c) for i, c in enumerate(counts)]
    out.median = statistics.median(nums)
    return out


# ---------- Money: reading it when it's written as text, and whether the amounts look right (F3d) ----------


def is_money(key: str) -> bool:
    return key == "sale_price" or (key.startswith(("assr_", "vset")) and key.endswith("_value"))


# Written where there's no amount: read as missing, not as a failure.
PLACEHOLDERS = {"", "-", "--", "n/a", "na", "none", "null", "nan", "tbd", "?", "unknown"}
NOMINAL = 1_000  # sale prices under this are nominal (a $10 deed), not a market price
TOO_BIG = 50_000_000  # a typical amount over this is likely in cents
COMMA_STYLES = ("1.234,56", "1 234,56")
EXCEL = re.compile(r"^\s*\$?\s*[-+]?\d(\.\d+)?[eE]\+?\d+\s*$")


def plain_numbers(values: tuple[str, ...]) -> bool:
    """Every value a plain number (or blank), as OpenAVMKit reads a float column."""
    for v in values:
        if v:
            try:
                float(v)
            except ValueError:
                return False
    return True


def detect_number_format(values: tuple[str, ...], style: str) -> tuple[NumberFormat, bool]:
    """How a column writes its amounts, and whether the decimal mark is a guess ("1.234": one or a thousand?).

    The marks the values settle (250,000.00; 250.000,00; 12,5) decide it; failing that, the project's style."""
    filled = [v.strip().rstrip(")") for v in values if v.strip()]
    # 12,5 or 1.234,56 or 1.234.567: a decimal comma. 12.5 or 1,234.56 or 1,234,567: a decimal point.
    comma = sum(1 for v in filled if re.search(r"\d,\d{1,2}$|\d\.\d{3},|\d\.\d{3}\.\d{3}", v))
    dot = sum(1 for v in filled if re.search(r"\d\.\d{1,2}$|\d,\d{3}\.|\d,\d{3},\d{3}", v))
    if comma != dot:
        decimal = "," if comma > dot else "."
        guess = False
    else:
        decimal = "," if style in COMMA_STYLES else "."
        guess = any(re.search(r"^\D*\d{1,3}[.,]\d{3}\D*$", v) for v in filled)
    suffixes = any(re.search(r"\d\s*[kKmM]$", v) for v in filled)
    return NumberFormat(decimal=decimal, suffixes=suffixes), guess


@lru_cache(maxsize=64)
def read_numbers(stamp: tuple[str, float, int], layer: str | None, column: str, fmt: str) -> tuple[float, ...]:
    """The column read by OpenAVMKit's own calc, as number_calc writes it for the format (JSON)."""
    import pandas as pd
    from openavmkit.calculations import perform_calculations

    values = pd.Series(values_of(stamp, layer, column, raw=True), dtype="string")
    df = pd.DataFrame({number_helper("x"): values.mask(values.str.strip() == "")})
    out = perform_calculations(df, {"x": number_calc("x", NumberFormat.model_validate_json(fmt))})["x"]
    return tuple(float(v) for v in out.tolist())


class NumberSample(BaseModel):
    raw: str
    read: float | None = Field(description="As OpenAVMKit reads it, or None if it doesn't.")


class ScaleHint(BaseModel):
    scale: float = Field(description="The scale to read it with instead.")
    reason: str
    short: str


class NumberPreview(BaseModel):
    key: str
    column: str
    format: NumberFormat
    detected: NumberFormat
    guessed: bool = Field(description="The decimal mark is the project's, as the values don't settle it.")
    symbol: str = Field(description="The project's currency symbol, for showing amounts.")
    total: int
    blank: int = Field(description="Blank, or a placeholder (N/A, TBD, -).")
    read: int
    failed: int
    zero: int
    nominal: int = Field(description=f"Above zero but under {NOMINAL:,}: a nominal deed, not a price.")
    negative: int
    excel: int = Field(description="Written as Excel writes big numbers (1.11E+06): the exact amount is lost.")
    median: float | None
    low: float | None = Field(description="10th percentile.")
    high: float | None = Field(description="90th percentile.")
    assessed: float | None = Field(description="Sale prices: the typical ratio of price to assessed value.")
    assessed_field: str | None
    hint: ScaleHint | None
    samples: list[NumberSample] = Field(description="Ones that don't read first, then a spread of ones that do.")


def currency_symbol(project: Project) -> str:
    from oakbox.projects import locales

    found = next((c["symbol"] for c in locales()["currencies"] if c["code"] == project.currency), project.currency)
    return found if len(found) == 1 else f"{found} "


def _amount(symbol: str, v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{symbol}{v / 1e6:,.2f}M"
    if abs(v) >= 10_000:
        return f"{symbol}{v / 1000:,.0f}K"
    return f"{symbol}{v:,.0f}" if v == round(v) else f"{symbol}{v:,.2f}"


def _assessed_ratio(
    project: Project, files: Files, entry: DataFile, prices: list[float]
) -> tuple[float | None, str | None]:
    """Sale prices: the median of price ÷ the parcel's assessed value, over sales that find one."""
    import statistics

    if entry.holds != "sales" or entry.match not in entry.load:
        return None, None
    for key in ("assr_market_value", "assr_land_value"):
        parcel = next(
            (f for f in project.files if key in f.load and entry.match in f.load and f.holds != "sales"), None
        )
        if parcel is None:
            continue
        stamp = file_stamp(files.in_dir / parcel.filename)
        fmt = parcel.numbers.get(key, NumberFormat()).model_dump_json()
        values = read_numbers(stamp, parcel.layer, parcel.load[key][0], fmt)
        by_id: dict[str, float] = {}
        for i, v in zip(files.ids(parcel.name, entry.match), values, strict=True):
            by_id.setdefault(i, v)
        ratios = [
            p / a
            for i, p in zip(files.ids(entry.name, entry.match), prices, strict=True)
            if p == p and p >= NOMINAL and (a := by_id.get(i, 0.0)) == a and a > 0
        ]
        if len(ratios) >= 20:
            return statistics.median(ratios), key
    return None, None


def _number_stats(project: Project, files: Files, entry: DataFile, key: str, column: str, fmt: NumberFormat) -> dict:
    import statistics

    stamp = file_stamp(files.in_dir / entry.filename)
    raw = values_of(stamp, entry.layer, column, raw=True)
    read = read_numbers(stamp, entry.layer, column, fmt.model_dump_json())
    blank = sum(1 for v in raw if v.strip().lower() in PLACEHOLDERS)
    got = [v for v in read if v == v]
    positive = sorted(v for v in got if v > 0)
    median = statistics.median(positive) if positive else None
    ratio, against = _assessed_ratio(project, files, entry, list(read)) if key == "sale_price" else (None, None)
    hint = None
    symbol = currency_symbol(project)
    if ratio is not None and (ratio >= 30 or ratio <= 1 / 30):
        times = 10 ** round(-math.log10(ratio))
        word = "thousands" if times == 1000 else "cents" if times == 0.01 else f"× {times:g}"
        hint = ScaleHint(
            scale=fmt.scale * times,
            reason=f"Prices are about {ratio:,.3g} times the assessed values: they look like {word}.",
            short=f"in {word}?",
        )
    elif median is not None and median < NOMINAL and (key != "sale_price" or ratio is None):
        hint = ScaleHint(
            scale=fmt.scale * 1000,
            reason=f"A typical amount of {_amount(symbol, median)} is too small: it looks like thousands.",
            short="in thousands?",
        )
    elif median is not None and median > TOO_BIG and ratio is None:
        hint = ScaleHint(
            scale=fmt.scale / 100,
            reason=f"A typical amount of {_amount(symbol, median)} is too big: it looks like cents.",
            short="in cents?",
        )

    def pct(q: float) -> float | None:
        return positive[min(len(positive) - 1, int(q * len(positive)))] if positive else None

    return dict(
        raw=raw,
        values=read,
        total=len(raw),
        blank=blank,
        read=len(got),
        failed=len(raw) - blank - len(got),
        zero=sum(1 for v in got if v == 0),
        nominal=sum(1 for v in got if 0 < v < NOMINAL),
        negative=sum(1 for v in got if v < 0),
        excel=sum(1 for v in raw if EXCEL.match(v) and abs(float(re.sub(r"[^0-9.eE+-]", "", v))) >= 1e5),
        median=median,
        low=pct(0.1),
        high=pct(0.9),
        assessed=ratio,
        assessed_field=against,
        hint=hint,
    )


def money_check(
    project: Project, files: Files, entry: DataFile, key: str, column: str, fmt: NumberFormat | None
) -> Check:
    """'✓ median $254K', or what's wrong: values that don't read, a scale that looks off, Excel's rounding."""
    s = _number_stats(project, files, entry, key, column, fmt or NumberFormat())
    if s["read"] == 0:
        return Check(ok=False, text="doesn't read as numbers: say how to read it")
    parts = [
        f"median {_amount(currency_symbol(project), s['median'])}" if s["median"] is not None else "none above zero"
    ]
    warn = False
    if s["failed"]:
        parts.append(f"{s['failed']:,} don't read")
        warn = True
    if s["hint"] is not None:
        parts.append(s["hint"].short)
        warn = True
    if s["excel"]:
        parts.append(f"{s['excel']:,} rounded by Excel")
        warn = True
    return Check(ok=True, warn=warn, text=("" if warn else "✓ ") + " · ".join(parts))


def number_preview(
    project: Project, in_dir: Path, name: str, key: str, column: str, fmt: NumberFormat | None
) -> NumberPreview:
    """A money column read with a format, as OpenAVMKit will: counts, the spread, a scale check, samples."""
    files = Files(project, in_dir)
    if not is_money(key):
        raise NotFound(key)
    if files.column(name, column) is None:
        raise ValueError(f"{name} has no column {column}.")
    entry = files.entry(name)
    stamp = file_stamp(in_dir / entry.filename)
    detected, guessed = detect_number_format(values_of(stamp, entry.layer, column), project.numbers)
    use = fmt or entry.numbers.get(key) or detected
    s = _number_stats(project, files, entry, key, column, use)
    raw, values = s.pop("raw"), s.pop("values")
    bad = list(
        dict.fromkeys(v for v, x in zip(raw, values, strict=True) if v.strip().lower() not in PLACEHOLDERS and x != x)
    )
    odd = list(
        dict.fromkeys(
            i
            for i, (v, x) in enumerate(zip(raw, values, strict=True))
            if x == x and (x <= 0 or x < NOMINAL or EXCEL.match(v))
        )
    )
    good = [i for i, x in enumerate(values) if x == x]
    step = max(1, len(good) // 6)
    picked = sorted(set(odd[:2] + good[::step][:6]))
    samples = [NumberSample(raw=v, read=None) for v in bad[:3]]
    seen = {x.raw for x in samples}
    for i in picked:
        if raw[i] not in seen and len(samples) < 9:
            samples.append(NumberSample(raw=raw[i], read=values[i]))
            seen.add(raw[i])
    return NumberPreview(
        key=key,
        column=column,
        format=use,
        detected=detected,
        guessed=guessed,
        symbol=currency_symbol(project),
        samples=samples,
        **s,
    )

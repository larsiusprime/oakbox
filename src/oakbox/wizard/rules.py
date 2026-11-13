"""Yes/no rules and dates (F3d): the values of a column, the rules for a valid and a vacant sale and a preview of
what they keep, and how a date column is written and what it reads as.
"""

from __future__ import annotations

import random
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox import fields
from oakbox.datafiles import (
    BaseModel,
    DataFile,
    Rule,
    rule_fields,
    rule_filter,
)
from oakbox.dates import date_format_of, iso_day
from oakbox.errors import NotFound
from oakbox.projects import Project
from oakbox.wizard.base import DATE_WORDS
from oakbox.wizard.checks import share_text
from oakbox.wizard.files import Files, dictionary_by_key, file_stamp, sales_file, values_of
from oakbox.wizard.models import Check, Source
from oakbox.wizard.money import read_numbers

# ---------- Yes/no rules (valid and vacant sale) and dates: previews (F3d) ----------


class ValueCount(BaseModel):
    value: str = Field(description='"" for blank.')
    count: int


@lru_cache(maxsize=256)
def value_counts(stamp: tuple[str, float, int], layer: str | None, column: str) -> tuple[tuple[str, int], ...]:
    """A column's values (trimmed, as shown) with how many rows have each, most common first; blanks as ''."""
    import pandas as pd

    # Counted and sorted in pandas (most common first, then by value): a price column's 600,000 distinct values
    # took a second in Python.
    vc = pd.Series(values_of(stamp, layer, column), dtype=object).value_counts().rename_axis("v").reset_index(name="n")
    vc = vc.sort_values(["n", "v"], ascending=[False, True], kind="stable")
    return tuple(zip(vc["v"].tolist(), vc["n"].astype(int).tolist(), strict=True))


def distinct_count(files: Files, source: Source) -> int | None:
    if source.file not in files.preview or files.column(source.file, source.column) is None:
        return None
    f = files.entry(source.file)
    return _distinct(file_stamp(files.in_dir / f.filename), f.layer, source.column)


@lru_cache(maxsize=256)
def _distinct(stamp: tuple[str, float, int], layer: str | None, column: str) -> int:
    """How many different values a column has, blanks left out: counted, not sorted (value_counts sorts them all)."""
    import pandas as pd

    return int(pd.Series(values_of(stamp, layer, column), dtype=object).replace("", None).nunique())


class ColumnValues(BaseModel):
    file: str
    column: str
    rows: int
    blank: int
    distinct: int = Field(description="Different values, not counting blank.")
    values: list[ValueCount] = Field(description="Most common first; blank last. At most `limit`.")
    more: int = Field(description="Values not listed (search to narrow).")


ValueSort = Literal["count", "value"]


def sort_counts(pairs: list[tuple[str, int]], sort: ValueSort | None, desc: bool) -> list[tuple[str, int]]:
    """(value, rows) by rows, or by value (numbers as numbers, before text); None keeps the order they came in."""
    if sort is None:
        return pairs
    if sort == "count":
        return sorted(pairs, key=lambda p: p[1], reverse=desc)

    def key(p: tuple[str, int]) -> tuple[int, float, str]:
        try:
            return (0, float(p[0].replace(",", "")), "")
        except ValueError:
            return (1, 0.0, p[0].lower())

    return sorted(pairs, key=key, reverse=desc)


def column_values(
    project: Project,
    in_dir: Path,
    file: str,
    column: str,
    search: str = "",
    limit: int = 500,
    sort: ValueSort | None = None,
    desc: bool = True,
):
    """Every value of a file's column with its row count, for the values list beside a field (most common first,
    unless sorted otherwise)."""
    files = Files(project, in_dir)
    if file not in files.preview or files.column(file, column) is None:
        raise NotFound(f"{file}.{column}")
    f = files.entry(file)
    counts = value_counts(file_stamp(in_dir / f.filename), f.layer, column)
    fmt = date_format_of(files, f, column)
    if fmt is not None:  # dates as YYYY-MM-DD, each day's rows together (times of day, ways of writing it)
        merged: dict[str, int] = {}
        for v, n in counts:
            d = iso_day(v, fmt) if v else ""
            merged[d] = merged.get(d, 0) + n
        counts = tuple(sorted(merged.items(), key=lambda x: -x[1]))
    blank = next((n for v, n in counts if v == ""), 0)
    listed = [(v, n) for v, n in counts if v]
    q = search.strip().lower()
    hits = [(v, n) for v, n in listed if q in v.lower()] if q else listed
    hits = sort_counts(hits, sort, desc)
    shown = hits[:limit]
    return ColumnValues(
        file=file,
        column=column,
        rows=sum(n for _, n in counts),
        blank=blank,
        distinct=len(listed),
        values=[ValueCount(value=v, count=n) for v, n in shown],
        more=len(hits) - len(shown),
    )


class RuleRow(BaseModel):
    cells: list[str]
    yes: bool


class RulePreview(BaseModel):
    key: str
    file: str
    yes: int
    total: int
    columns: list[str] = Field(description="The columns the rule tests, for the rows.")
    as_read: list[str] = Field(description="Columns shown in the rows as read (money written as text), not as written.")
    values: dict[str, list[ValueCount]] = Field(description="Per column tested, its values, most common first.")
    more: dict[str, int] = Field(description="Per column, how many other values there are.")
    rows: list[RuleRow] = Field(description="A few rows of each outcome.")
    calc: list = Field(description="The OpenAVMKit calc it writes.")
    load: dict[str, list[str]] = Field(description="Columns it loads so the calc can test them.")


VALUES_SHOWN = 60


@lru_cache(maxsize=64)
def _counts(stamp: tuple[str, float, int], layer: str | None, column: str) -> tuple[tuple[str, int], ...]:
    counts = Counter(values_of(stamp, layer, column, raw=True))
    return tuple(sorted(counts.items(), key=lambda vc: (-vc[1], vc[0])))


def rule_result(files: Files, entry: DataFile, rule: Rule):
    """The rule run by OpenAVMKit's own filter code on the file's rows, typed as OpenAVMKit loads them."""
    import pandas as pd
    from openavmkit.filters import resolve_filter

    names = rule_fields(entry.load, rule)
    stamp = file_stamp(files.in_dir / entry.filename)
    frame = {}
    for column, (field, kind) in names.items():
        values = pd.Series(values_of(stamp, entry.layer, column, raw=True))
        if field in entry.numbers and entry.load.get(field, [None])[0] == column:
            frame[field] = pd.Series(read_numbers(stamp, entry.layer, column, entry.numbers[field].model_dump_json()))
        elif kind == "float":
            frame[field] = pd.to_numeric(values.str.strip(), errors="coerce")
        else:
            frame[field] = values.mask(values.str.strip() == "").astype("string")
    df = pd.DataFrame(frame)
    filt = rule_filter(rule, names)
    if not filt or df.empty:
        return names, filt, pd.Series(False, index=df.index)
    # OpenAVMKit reads a missing result as no (na_false).
    return names, filt, resolve_filter(df, filt).fillna(False).astype(bool)


def rule_complete(rule: Rule) -> bool:
    return bool(rule.conditions) and all(c.values or c.op in ("isempty", "notempty") for c in rule.conditions)


def rule_check(files: Files, entry: DataFile, key: str, rule: Rule) -> Check:
    if any(files.column(entry.name, c.column) is None for c in rule.conditions):
        return Check(ok=False, text="a column it tests isn't in the file")
    if not rule_complete(rule):
        return Check(ok=False, text="choose which values mean yes")
    try:
        _, _, result = rule_result(files, entry, rule)
    except Exception as e:  # noqa: BLE001 - a rule OpenAVMKit can't run shows on its row
        return Check(ok=False, text=f"OpenAVMKit can't run this: {e}")
    yes, total = int(result.sum()), len(result)
    word = {"valid_sale": "valid", "vacant_sale": "vacant"}.get(key, "yes")
    text = f"{yes:,} of {total:,} {word} ({share_text(yes, total)})"
    # All or nothing is legal, but usually means the wrong values were picked.
    return Check(ok=True, text=("✓ " if 0 < yes < total else "") + text, warn=yes in (0, total))


def _rule_entry(project: Project, key: str) -> DataFile:
    sales = sales_file(project)
    d = dictionary_by_key().get(key)
    if sales is None:
        raise ValueError("Add the sales record first.")
    if d is None or d.type != "boolean":
        raise NotFound(key)
    return sales


def rule_preview(project: Project, in_dir: Path, key: str, rule: Rule) -> RulePreview:
    """What a rule makes of the sales file: how many yes, the values of the columns it tests, a few rows."""
    entry = _rule_entry(project, key)
    files = Files(project, in_dir)
    for c in rule.conditions:
        if files.column(entry.name, c.column) is None:
            raise ValueError(f"{entry.name} has no column {c.column}.")
    stamp = file_stamp(in_dir / entry.filename)
    columns = list(dict.fromkeys(c.column for c in rule.conditions))
    values, more = {}, {}
    for column in columns:
        counts = _counts(stamp, entry.layer, column)
        values[column] = [ValueCount(value="" if not v.strip() else v, count=n) for v, n in counts[:VALUES_SHOWN]]
        more[column] = max(0, len(counts) - VALUES_SHOWN)
    names, filt, result = rule_result(files, entry, rule) if rule_complete(rule) else ({}, [], None)
    rows: list[RuleRow] = []
    # A price is tested as read ($1,000 against 1.2 in thousands is 1,200), so the rows show it that way.
    as_read = [c for c in columns if any(entry.load.get(f, [None])[0] == c for f in entry.numbers)]
    if result is not None and columns:
        cells = {c: values_of(stamp, entry.layer, c, raw=True) for c in columns}
        for c in as_read:
            field = next(f for f in entry.numbers if entry.load.get(f, [None])[0] == c)
            read = read_numbers(stamp, entry.layer, c, entry.numbers[field].model_dump_json())
            cells[c] = tuple("" if v != v else f"{v:,.2f}".removesuffix(".00") for v in read)
        rng = random.Random(0)
        for want in (True, False):
            idx = [i for i, x in enumerate(result.tolist()) if x == want]
            for i in sorted(rng.sample(idx, min(4, len(idx)))):
                rows.append(RuleRow(cells=[cells[c][i] for c in columns], yes=want))
    total = len(values_of(stamp, entry.layer, columns[0], raw=True)) if columns else 0
    load = {field: [column, kind] for column, (field, kind) in names.items() if field not in entry.load}
    return RulePreview(
        key=key,
        file=entry.name,
        yes=int(result.sum()) if result is not None else 0,
        total=total,
        columns=columns,
        as_read=as_read,
        values=values,
        more=more,
        rows=rows,
        calc=["?", filt] if filt else [],
        load=load,
    )


def set_rule(project: Project, in_dir: Path, key: str, rule: Rule) -> None:
    """Work a yes/no field out from the sales file's columns (OpenAVMKit's ["?", filter] calc)."""
    entry = _rule_entry(project, key)
    files = Files(project, in_dir)
    for c in rule.conditions:
        if files.column(entry.name, c.column) is None:
            raise ValueError(f"{entry.name} has no column {c.column}.")
    if not rule.conditions:
        raise ValueError("A rule needs at least one test.")
    entry.load.pop(key, None)
    entry.calc.pop(key, None)
    entry.rules[key] = rule
    if key not in project.wizard.decided:
        project.wizard.decided.append(key)


class DateSample(BaseModel):
    raw: str
    read: str | None = Field(description="As OpenAVMKit reads it (year-month-day), or None if it doesn't.")


class DateFormat(BaseModel):
    format: str
    words: str


class YearCount(BaseModel):
    year: int
    count: int


class DatePreview(BaseModel):
    format: str
    words: str
    total: int
    blank: int
    read: int
    failed: int
    first: str | None
    last: str | None
    samples: list[DateSample] = Field(description="Ones that don't read first, then a spread of ones that do.")
    also: list[DateFormat] = Field(description="Other formats that read every date too, but differently.")
    formats: list[DateFormat]
    by_year: list[YearCount] = Field(default_factory=list, description="How many read in each year, oldest first.")


@lru_cache(maxsize=128)
def parse_dates(stamp: tuple[str, float, int], layer: str | None, column: str, fmt: str):
    """The column read with a date format the way OpenAVMKit does (pd.to_datetime with format=)."""
    import pandas as pd

    values = pd.Series(values_of(stamp, layer, column, raw=True))
    try:
        return pd.to_datetime(values.mask(values.str.strip() == ""), format=fmt)
    except (ValueError, TypeError):
        return pd.to_datetime(values.mask(values.str.strip() == ""), format=fmt, errors="coerce", exact=True)


def _date_stats(files: Files, name: str, column: str, fmt: str) -> tuple[int, int, int]:
    """(rows, blank, read)."""
    entry = files.entry(name)
    stamp = file_stamp(files.in_dir / entry.filename)
    values = values_of(stamp, entry.layer, column, raw=True)
    blank = sum(1 for v in values if not v.strip())
    read = int(parse_dates(stamp, entry.layer, column, fmt).notna().sum())
    return len(values), blank, read


def _also(files: Files, name: str, column: str, fmt: str) -> list[str]:
    """Formats that also read every date but give different dates (day/month or month/day): worth a look."""
    entry = files.entry(name)
    stamp = file_stamp(files.in_dir / entry.filename)
    col = files.column(name, column)
    samples = col.samples if col else []
    mine = parse_dates(stamp, entry.layer, column, fmt)
    out = []
    for other in fields.DATE_FORMATS:
        if other == fmt or not samples or not all(p for p in fields.check_dates(samples, other).parsed):
            continue
        theirs = parse_dates(stamp, entry.layer, column, other)
        if theirs.notna().sum() == mine.notna().sum() and not theirs.equals(mine):
            out.append(other)
    return out


def date_check(files: Files, name: str, column: str, fmt: str) -> Check:
    total, blank, read = _date_stats(files, name, column, fmt)
    words = DATE_WORDS.get(fmt, fmt)
    failed = total - blank - read
    if read == 0:
        return Check(ok=False, text=f"doesn't read as {words}")
    if failed:
        return Check(ok=True, warn=True, text=f"reads as {words} · {failed:,} don't read")
    also = _also(files, name, column, fmt)
    if also:
        return Check(ok=True, warn=True, text=f"reads as {words}, or as {DATE_WORDS.get(also[0], also[0])}?")
    return Check(ok=True, text=f"✓ reads as {words}")


def date_preview(project: Project, in_dir: Path, name: str, column: str, fmt: str) -> DatePreview:
    """A column read with a date format: how many read, the range, samples, and look-alike formats."""
    files = Files(project, in_dir)
    if files.column(name, column) is None:
        raise ValueError(f"{name} has no column {column}.")
    entry = files.entry(name)
    stamp = file_stamp(in_dir / entry.filename)
    total, blank, read = _date_stats(files, name, column, fmt)
    parsed = parse_dates(stamp, entry.layer, column, fmt)
    values = values_of(stamp, entry.layer, column, raw=True)
    # Which read, all at once; written back as text only for the few shown (838,000 one by one took 1.5 s).
    ok_mask = parsed.notna().to_numpy()
    bad = list(dict.fromkeys(v for v, ok in zip(values, ok_mask, strict=True) if not ok and v.strip()))[:4]
    good_idx = [int(i) for i in ok_mask.nonzero()[0]]
    step = max(1, len(good_idx) // 6)
    good = [good_idx[i] for i in range(0, len(good_idx), step)][: 8 - len(bad)]
    samples = [DateSample(raw=v, read=None) for v in bad] + [
        DateSample(raw=values[i], read=parsed.iloc[i].strftime("%Y-%m-%d")) for i in good
    ]
    ok = parsed.dropna()
    return DatePreview(
        format=fmt,
        words=DATE_WORDS.get(fmt, fmt),
        total=total,
        blank=blank,
        read=read,
        failed=total - blank - read,
        first=ok.min().strftime("%Y-%m-%d") if len(ok) else None,
        last=ok.max().strftime("%Y-%m-%d") if len(ok) else None,
        samples=samples,
        also=[DateFormat(format=f, words=DATE_WORDS.get(f, f)) for f in _also(files, name, column, fmt)],
        formats=[DateFormat(format=f, words=DATE_WORDS.get(f, f)) for f in fields.DATE_FORMATS],
        by_year=[YearCount(year=int(y), count=int(c)) for y, c in sorted(ok.dt.year.value_counts().items())],
    )

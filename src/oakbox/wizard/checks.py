"""The Fields wizard's checks and guesses: whether a column's values pass a field's check, how the IDs of a file
join (and repeat), and the modest guesses (SPEC D45) of which column holds an ID or a field.
"""

from __future__ import annotations

import re

from oakbox.datafiles import (
    Holds,
)
from oakbox.fields import Column, DictionaryField
from oakbox.wizard.base import ALIASES, DATE_WORDS, ID_NAMES, NO, SALE_ID_NAMES, YES, normalized
from oakbox.wizard.files import Files, is_more_sales, sales_file
from oakbox.wizard.models import Check, Issue, Repeats

# ---------- Checks ----------


def _floats(samples: list[str]) -> list[float] | None:
    out = []
    for s in samples:
        try:
            out.append(float(s))
        except ValueError:
            return None
    return out


def field_check(d: DictionaryField, col: Column) -> tuple[Check, list[str] | None]:
    """Whether a column reads as a field's type, and the load spec to write when it does."""
    samples = col.samples
    if d.type in ("number", "percent"):
        nums = [] if col.type == "number" and not samples else _floats(samples)
        if nums is None:
            bad = next(s for s in samples if _floats([s]) is None)
            return Check(ok=False, text=f"not numbers: {bad}"), None
        if "year" in d.key and nums:
            # 0 is how many rolls write "none" (no renovation, no building): only the rest need be years.
            years = [n for n in nums if n != 0]
            if not years or not all(1700 <= n <= 2100 for n in years):
                bad = next((n for n in years if not 1700 <= n <= 2100), None)
                return Check(ok=False, text="not years" + (f": {bad:g}" if bad is not None else "")), None
            text = f"✓ {int(min(years))}–{int(max(years))}"
            if len(years) < len(nums):
                text += (
                    " · 0 = no renovation: the year built" if d.key == "bldg_effective_year_built" else " · 0 = none"
                )
            return Check(ok=True, text=text), [col.name, "float"]
        return Check(ok=True, text="✓ numbers"), [col.name, "float"]
    if d.type == "date":
        if col.type == "date":
            return Check(ok=True, text="✓ dates"), [col.name]
        if col.date_format:
            words = DATE_WORDS.get(col.date_format, col.date_format)
            return Check(ok=True, text=f"✓ reads as {words}"), [col.name, "datetime", col.date_format]
        return Check(ok=False, text="doesn't read as a date"), None
    if d.type == "boolean":
        lowered = [s.lower() for s in samples]
        if col.type != "yes/no" and any(v not in YES | NO for v in lowered):
            bad = next(s for s, v in zip(samples, lowered, strict=True) if v not in YES | NO)
            return Check(ok=False, text=f"not yes/no: {bad}"), None
        yes = sorted({s for s, v in zip(samples, lowered, strict=True) if v in YES}) or ["true"]
        return Check(ok=True, text=f"✓ {', '.join(yes)} = yes, blank = no"), [col.name, "bool", "na_false"]
    if d.key.endswith("_txt") and col.type == "number":
        return Check(ok=False, text="numbers: use the number field"), None
    return Check(ok=True, text="✓ text"), [col.name, "string"]


# Stray repeats: fewer than both of these. More means several rows per parcel (SPEC F3d).
FEW_SHARE, FEW_ROWS = 0.01, 10
# Sales finding a parcel: below MATCH_MIN blocks a run, below MATCH_OK is worth reconciling (F3d).
MATCH_MIN, MATCH_OK = 0.5, 0.95


def _repeats_of(files: Files, name: str, field: str) -> Repeats:
    entry = files.entry(name)
    values = files.ids(name, field)
    present = [v for v in values if v]
    counts: dict[str, int] = {}
    for v in present:
        counts[v] = counts.get(v, 0) + 1
    extra = len(present) - len(counts)
    return Repeats(
        rows=len(values),
        blank=len(values) - len(present),
        distinct=len(counts),
        repeated=sum(1 for n in counts.values() if n > 1),
        extra=extra,
        singles=sum(1 for n in counts.values() if n == 1),
        few=extra < FEW_ROWS and extra < FEW_SHARE * max(len(present), 1),
        policy=entry.dupes,
        sort=entry.dupes_sort,
        descending=entry.dupes_desc,
        blank_ok=entry.blank_ok,
    )


def check_ids(files: Files, name: str, holds: Holds | None, base: str | None) -> tuple[Check | None, Repeats | None]:
    """The result on one line ("219,381 parcels"), and anything worth a look as separate issues."""
    from oakbox.wizard.condos import unit_ids, units_view  # condos reads the checks: imported here, not above

    f = files.entry(name)
    match = "key" if name == base else f.match
    made = is_more_sales(f) and "key_sale" in f.calc
    if made:  # details on a made sale ID: their own made from their parcel ID and date
        match = "key"
    spec = f.load.get(match)
    if not spec or name not in files.preview:
        return None, None
    r = _repeats_of(files, name, match)
    present = [v for v in files.ids(name, match) if v]
    flagged = r if (r.extra or r.blank) else None
    issues: list[Issue] = []
    more_sales = is_more_sales(f)
    # One row each is expected of a parcel file (per parcel) and of more sales details (per sale).
    # (A parcel ID repeats in details on a made sale ID: a parcel sold more than once.)
    one_each = holds in ("parcels", "parcel_rows") or (more_sales and not made)
    if r.extra and one_each and (r.few or r.policy):
        repeated = counted(r.repeated, "repeated ID")
        if r.policy is None:  # nothing chosen yet (OpenAVMKit would keep the first)
            issues.append(Issue(text=repeated, resolved=False, todo=f"{repeated} to decide"))
        else:
            how = "all dropped" if r.policy == "all" else "first kept"
            issues.append(Issue(text=f"{repeated}, {how}", resolved=True))
    if r.blank:
        outcome = "won't match a sale" if more_sales else "won't match a parcel" if holds == "sales" else "dropped"
        # Blank IDs wreck joins: on a parcel file they block until confirmed as dropped.
        blocking = holds == "parcels" and not r.blank_ok
        blank = counted(r.blank, "blank ID")
        todo = f"{blank} to confirm"
        issues.append(Issue(text=f"{blank}, {outcome}", resolved=r.blank_ok, blocking=blocking, todo=todo))
    open_issues = any(not i.resolved for i in issues)
    blocked = any(i.blocking for i in issues)
    if more_sales:
        main = sales_file(files.project)
        # (On a made sale ID the parcel ID repeats: a parcel sold more than once. Its made IDs are what count.)
        if r.extra and not r.few and r.policy is None and not made:
            text = f"{counted(r.repeated, 'repeated sale ID')} ({counted(r.extra, 'extra row')}): choose what to do"
            return Check(ok=False, text=text, issues=issues), flagged
        from oakbox.wizard.rows import sale_keys

        if main is None or not ("key_sale" in main.load or "key_sale" in main.calc):
            text = "the sales record has no sale ID to join on"
            return Check(ok=False, text=text, issues=issues), flagged
        if "key_sale" in main.calc and "sale_date" not in f.load:
            return Check(
                ok=False, text="pick its sale date: its sale ID is made from parcel ID + date", issues=issues
            ), flagged
        # Its sale IDs: its column's, or made from its own parcel ID and date as the sales record's are.
        mine = sale_keys(files, f) if "key_sale" in main.calc else set(present)
        found = len(mine & sale_keys(files, main))
        share = found / len(mine) if mine else 0.0
        if share < MATCH_MIN and "key_sale" in main.calc:
            text = (
                f"{share_text(found, len(mine))} match a sale. Most don't: are these sales of their own? "
                "Then append them as extra rows"
            )
            return Check(ok=False, text=text, warn=True, issues=issues, share=share), flagged
        text = f"{share_text(found, len(mine))} match a sale"
        warn = open_issues or share < MATCH_OK
        return Check(ok=share >= MATCH_MIN, text=text, warn=warn, issues=issues, share=share), flagged
    if holds == "parcel_rows":
        # More parcels: each a parcel of its own; one already in the universe is kept once, the universe's.
        parcels = parcel_ids(files, base, "key")
        new = len(set(present) - parcels)
        text = f"{r.distinct:,} parcels · {new:,} new, {r.distinct - new:,} already in the universe"
        return Check(ok=not blocked, text=text, warn=open_issues, issues=issues), flagged
    if holds in ("sales", "sale_rows"):
        flagged = r if r.blank else None
        if base is None or base == name:
            return Check(ok=True, text=f"{r.rows:,} sales", warn=open_issues, issues=issues), flagged
        base_ids = parcel_ids(files, base, match)
        if match == "key":
            base_ids = base_ids | unit_ids(files)  # units that find their building are parcels too
        found = sum(1 for v in present if v in base_ids)
        share = found / r.rows if r.rows else 0.0
        text = f"{share_text(found, r.rows)} match"
        # Under half matching is a blocker; under 95% worth reconciling (SPEC F3d).
        warn = open_issues or share < MATCH_OK
        return Check(ok=share >= MATCH_MIN, text=text, warn=warn, issues=issues, share=share), flagged
    if holds == "permits":
        # Many permits to a parcel is expected; what matters is that they find their parcel.
        base_ids = parcel_ids(files, base, match) | unit_ids(files)
        found = sum(1 for v in present if v in base_ids)
        share = found / r.rows if r.rows else 0.0
        text = f"{r.rows:,} permits · {share_text(found, r.rows)} match"
        warn = open_issues or share < MATCH_OK
        return Check(ok=share >= MATCH_MIN, text=text, warn=warn, issues=issues, share=share), flagged
    if holds != "parcels":
        text = "several rows per parcel" if r.extra and not r.few else "one row per parcel"
        return Check(ok=True, text=text, warn=open_issues, issues=issues), flagged
    share = None
    if name != base:
        # Units that find their building are parcels too, for every other file (their building cards, say).
        parcels = parcel_ids(files, base, match) | (unit_ids(files) if match == "key" and f.units is None else set())
        found = len(set(present) & parcels)
        share = found / len(set(present)) if present else 0.0
    if r.extra and not r.few and r.policy is None:
        text = f"{counted(r.repeated, 'repeated ID')} ({counted(r.extra, 'extra row')}): choose what to do"
        return Check(ok=False, text=text, issues=issues, share=share), flagged
    kept = r.singles if r.policy == "all" else r.distinct
    tick = "" if open_issues else "✓ "
    if name == base:
        text = f"{tick}{kept:,} parcels" + ("" if issues else ", all different")
        return Check(ok=not blocked, text=text, warn=open_issues, issues=issues), flagged
    share = share or 0.0
    if f.units is not None and present:
        # Units that find their building's shape join as well as rows with a shape of their own.
        v = units_view(files.project, files, f)
        share = min(1.0, share + v.linked / len(set(present)))
        pct = share_text(round(share * 1000), 1000)
        text = f"{tick}one row per parcel · {pct} match (units by their parcel)"
        warn = open_issues or share < MATCH_OK
        return Check(ok=share >= MATCH_MIN and not blocked, text=text, warn=warn, issues=issues, share=share), flagged
    text = f"{tick}one row per parcel · {share_text(round(share * 1000), 1000)} match"
    warn = open_issues or share < MATCH_OK
    ok = share >= MATCH_MIN and not blocked
    return Check(ok=ok, text=text, warn=warn, issues=issues, share=share), flagged


def parcel_ids(files: Files, base: str | None, field: str = "key") -> set[str]:
    if base is None or base not in files.preview:
        return set()
    return {v for v in files.ids(base, field) if v}


def counted(n: int, word: str) -> str:
    """'1 ID', '3 IDs', '1,204 extra rows'."""
    return f"{n:,} {word}" if n == 1 else f"{n:,} {word}s"


def share_text(n: int, total: int) -> str:
    if not total:
        return "0%"
    p = 100 * n / total
    return f"{p:.1f}%" if 99 < p < 100 or 0 < p < 1 else f"{p:.0f}%"


# ---------- Guesses ----------


def _names(d: DictionaryField) -> set[str]:
    return {normalized(d.key), normalized(d.name), *ALIASES.get(d.key, [])}


def guess_id(files: Files, name: str, holds: Holds, base_column: str | None) -> str | None:
    cols = files.columns(name)
    named = [c.name for c in cols if ID_NAMES.fullmatch(normalized(c.name))]
    if base_column and base_column in {c.name for c in cols} and base_column not in named:
        named.insert(0, base_column)
    named.sort(key=lambda c: (c != base_column, _id_rank(c)))
    for column in named[:4]:
        values = files.values(name, column)
        present = [v for v in values if v]
        if not present:
            continue
        if holds == "sales" or len(set(present)) >= 0.99 * len(present):
            return column
    return None


def _id_rank(column: str) -> int:
    n = normalized(column)
    for i, word in enumerate(("pin", "apn", "parcel", "prop", "account", "acct", "key", "geoid", "folio", "id")):
        if n.startswith(word):
            return i
    return 99


def guess_sale_id(files: Files, name: str) -> str | None:
    for c in files.columns(name):
        if SALE_ID_NAMES.fullmatch(normalized(c.name)):
            present = [v for v in files.values(name, c.name) if v]
            if present and len(set(present)) == len(present):
                return c.name
    return None


def guess_field(files: Files, d: DictionaryField, candidates: list[str], used: dict[str, dict[str, str]]):
    names = _names(d)
    for name in candidates:
        for col in files.columns(name):
            if col.name in used.get(name, {}) or normalized(col.name) not in names:
                continue
            if d.key == "address" and re.search(r"mail|owner", col.name, re.IGNORECASE):
                continue  # the situs address, never the owner's mailing address
            check, spec = field_check(d, col)
            if check.ok and spec:
                return name, spec
    return None

"""Deeds (F3f) and permits (F3g): the deed fields and what sales scrutiny will make of them, and the permits
file, the meaning of each permit type and the fields it needs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from oakbox import projects
from oakbox.datafiles import (
    DataFile,
    PermitMeaning,
    Permits,
)
from oakbox.projects import Project
from oakbox.wizard.base import normalized
from oakbox.wizard.files import Files, file_stamp, row_count, values_of
from oakbox.wizard.models import DeedsCheck, PermitKind, PermitsView
from oakbox.wizard.rules import VALUES_SHOWN, date_check, parse_dates, value_counts

# ---------- Deeds (F3f) ----------


def deeds_check(project: Project, files: Files) -> DeedsCheck | None:
    """What sales scrutiny will find (notebook 2): sales sharing a deed ID and a sale date are one sale of several
    parcels. Worked out from the sales file the deed fields and the sale date are both in."""
    import pandas as pd

    deed = projects.deed_field(project)
    if deed is None:
        return None
    wanted = ["deed_id"] if deed == "deed_id" else ["deed_book", "deed_page"]
    need = [*wanted, "sale_date"]
    f = next((f for f in project.files if f.holds == "sales" and all(k in f.load for k in need)), None)
    if f is None or f.name not in files.preview:
        return None
    stamp = file_stamp(files.in_dir / f.filename)

    def text(key: str) -> pd.Series:
        return pd.Series(values_of(stamp, f.layer, f.load[key][0], raw=True)).astype(str).str.strip()

    parts = [text(k) for k in wanted]
    blank = pd.concat([p.str.lower().isin(["", "nan", "none", "null"]) for p in parts], axis=1).any(axis=1)
    ids = parts[0] if len(parts) == 1 else parts[0] + "-" + parts[1]
    spec = f.load["sale_date"]
    when = (
        parse_dates(stamp, f.layer, spec[0], spec[2])
        if len(spec) > 2
        else pd.Series(values_of(stamp, f.layer, spec[0]))
    )
    together = (ids + "|" + when.astype(str))[~blank]
    counts = together.value_counts()
    shared = counts[counts > 1]
    n_blank = int(pd.Series(blank).sum())
    if len(shared):
        words = f"{len(shared):,} deeds have more than one sale on the same day: {int(shared.sum()):,} sales"
        words += ", likely sales of several parcels together. Sales scrutiny (notebook 2) sets them aside."
    else:
        words = "No deed has more than one sale on the same day."
    if n_blank:
        words += f" {n_blank:,} {'sale has' if n_blank == 1 else 'sales have'} no deed ID."
    return DeedsCheck(ok=True, text=words, deeds=len(shared), sales=int(shared.sum()), blank=n_blank)


NAME_FIELDS = {
    "seller": "deed_grantor",
    "buyer": "deed_grantee",
    "seller_surname": "deed_grantor_surname",
    "buyer_surname": "deed_grantee_surname",
}


def deed_names(project: Project, in_dir: Path) -> dict:
    """The buyers' and sellers' names (and surnames, where loaded) as written, from the sales file that has the most
    of them; {} without any."""
    files = Files(project, in_dir)
    sales = [f for f in project.files if f.holds == "sales" and f.name in files.preview]
    f = max(sales, key=lambda f: sum(k in f.load for k in NAME_FIELDS.values()), default=None)
    if f is None or not any(k in f.load for k in NAME_FIELDS.values()):
        return {}
    stamp = file_stamp(files.in_dir / f.filename)
    out: dict = {"file": f.name}
    for key, field in NAME_FIELDS.items():
        if field in f.load:
            out[key] = list(values_of(stamp, f.layer, f.load[field][0]))
    return out


# ---------- Permits (F3g) ----------

PERMIT_WORDS: list[tuple[re.Pattern, PermitMeaning]] = [
    (re.compile(r"demo|wreck|raze|tear", re.IGNORECASE), "teardown"),
    (re.compile(r"addition|remodel|renovat|rehab|convers|gut", re.IGNORECASE), "major"),
    (re.compile(r"alter|repair|interior|kitchen|bath|finish", re.IGNORECASE), "minor"),
]
PERMIT_TYPE_NAMES = re.compile(r"(work|permit|job)?(class|type|kind|desc|category|scope)", re.IGNORECASE)
PERMIT_DATE_NAMES = re.compile(r"issue|permit.?date|applied|date", re.IGNORECASE)


def guess_meaning(value: str) -> PermitMeaning:
    return cast(PermitMeaning, next((m for rx, m in PERMIT_WORDS if rx.search(value)), "none"))


def permits_view(project: Project, files: Files) -> PermitsView | None:
    f = projects.permits_file(project)
    if f is None or f.name not in files.preview:
        return None
    p = f.permits or Permits()
    date = span = None
    if p.date and p.date_format and files.column(f.name, p.date) is not None:
        date = date_check(files, f.name, p.date, p.date_format)
        when = parse_dates(file_stamp(files.in_dir / f.filename), f.layer, p.date, p.date_format).dropna()
        if len(when):
            span = f"{when.min():%Y-%m-%d} to {when.max():%Y-%m-%d}"
    kinds: list[PermitKind] = []
    more = 0
    if p.type and files.column(f.name, p.type) is not None:
        counts = [(v, n) for v, n in value_counts(file_stamp(files.in_dir / f.filename), f.layer, p.type) if v]
        more = max(0, len(counts) - VALUES_SHOWN)
        for v, n in counts[:VALUES_SHOWN]:
            said = p.means.get(v)
            kinds.append(PermitKind(value=v, count=n, means=said or guess_meaning(v), guessed=said is None))
    loaded = {k for x in project.files if x.holds in ("parcels", "sales") for k in x.load}
    return PermitsView(
        file=f.name,
        settings=p,
        rows=row_count(files, f.name) or 0,
        date=date,
        span=span,
        kinds=kinds,
        more=more,
        year_built="bldg_year_built" in loaded,
        ready=projects.permits_ready(f),
    )


def permits_left(project: Project) -> list[str]:
    f = projects.permits_file(project)
    if f is None:
        return []
    p = f.permits or Permits()
    out = []
    if not p.date or not p.date_format:
        out.append("Pick the date each permit was issued")
    if not p.type:
        out.append("Pick the column that says what each permit is")
    return out


def guess_permits(files: Files, f: DataFile) -> Permits:
    """The date column (the first that reads as a date, issue dates first) and the type column (a few kinds,
    named like a type or class), and what each kind means from its words."""
    cols = files.columns(f.name)
    dated = [c for c in cols if c.date_format and c.name not in f.load.get("key", [])]
    dated.sort(key=lambda c: (not re.search(r"issue", c.name, re.IGNORECASE), not PERMIT_DATE_NAMES.search(c.name)))
    p = Permits()
    if dated:
        p.date, p.date_format = dated[0].name, dated[0].date_format
    stamp = file_stamp(files.in_dir / f.filename)
    best = None
    for c in cols:
        if c.type != "text" or c.date_format or c.name in (f.load.get("key") or [None])[:1]:
            continue
        n = len([v for v, _ in value_counts(stamp, f.layer, c.name) if v])
        if 2 <= n <= 60:
            score = (bool(PERMIT_TYPE_NAMES.search(normalized(c.name))), -n)
            if best is None or score > best[0]:
                best = (score, c.name)
    if best:
        p.type = best[1]
        p.means = {v: guess_meaning(v) for v, _ in value_counts(stamp, f.layer, p.type) if v}
    return p


def set_permits(project: Project, in_dir: Path, name: str, permits: Permits | None, guess: bool = False) -> None:
    """A file's permits set-up; None stops using it as permits. guess: work out the columns from the file."""
    files = Files(project, in_dir)
    entry = files.entry(name)
    if permits is None:
        entry.holds, entry.permits = "unused", None
        return
    if entry.holds != "permits":
        raise ValueError(f"{name} isn't the permits file.")
    if guess:
        permits = guess_permits(files, entry)
    for column in (permits.date, permits.type):
        if column is not None and files.column(name, column) is None:
            raise ValueError(f"{name} has no column {column}.")
    if permits.type and entry.permits and permits.type != entry.permits.type:
        # A new type column: its own values, guessed from their words.
        stamp = file_stamp(in_dir / entry.filename)
        permits.means = {v: guess_meaning(v) for v, _ in value_counts(stamp, entry.layer, permits.type) if v}
    entry.permits = permits

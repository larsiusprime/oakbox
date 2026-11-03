"""Buyers' and sellers' surnames (Data › Deeds, SPEC F3f): how the names are written, so sales scrutiny can find a
buyer and seller who share one (possibly between family).

Nothing is guessed silently. The format is guessed from the names and shown with a live preview of real names and the
surname read from each; the user confirms it, picks another, or writes a regular expression with a `surname` group.
Names too irregular for that are better split before they come in: the Seller surname and Buyer surname fields are
used as given. OpenAVMKit reads the names (`surnames`), with the pattern written to
analysis.sales_scrutiny.same_surname.pattern.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from oakbox.datafiles import BaseModel

FormatId = Literal["first_word", "before_comma", "last_word", "custom"]


class NameFormat(BaseModel):
    id: FormatId
    label: str
    example: str
    pattern: str


FORMATS = [
    NameFormat(
        id="first_word",
        label="Surname first",
        example="SMITH JOHN A",
        pattern=r"^\s*(?P<surname>[A-Za-z][A-Za-z'\-]*)",
    ),
    NameFormat(
        id="before_comma",
        label="Surname, a comma, then given names",
        example="Smith, John A",
        pattern=r"^\s*(?P<surname>[^,]+),",
    ),
    NameFormat(
        id="last_word",
        label="Surname last",
        example="John A Smith Jr",
        pattern=r"(?P<surname>[A-Za-z][A-Za-z'\-]*)\.?\s*(?:,?\s*(?:JR|SR|II|III|IV)\.?)?\s*$",
    ),
]
BY_ID = {f.id: f for f in FORMATS}
SAMPLE = 5_000  # names read for the guess and the counts


class NameRow(BaseModel):
    seller: str
    buyer: str
    seller_surnames: list[str]
    buyer_surnames: list[str]
    shared: list[str]


class NamesView(BaseModel):
    """What the deed names say, read with a format: the saved one, or one being tried."""

    available: bool = Field(description="Seller and buyer names (or surnames) are loaded from one sales file.")
    file: str | None
    surname_fields: bool = Field(description="Seller and buyer surnames are loaded as fields: used as given.")
    formats: list[NameFormat]
    guess: FormatId | None = Field(description="What the names look like.")
    why: str = Field(description="Why that guess, in words.")
    format: FormatId | None = Field(description="Saved; None: not confirmed yet (the guess is used).")
    pattern: str = Field(description="The pattern read with (saved, tried or the guess's).")
    error: str | None = Field(description="What's wrong with a pattern being tried.")
    rows: list[NameRow] = Field(description="Up to 6 sales sharing a surname, then up to 6 that don't.")
    read: int = Field(description="Names read as people, with a surname.")
    companies: int = Field(description="Names skipped: companies, trusts, banks, governments.")
    unread: int = Field(description="Names the pattern found no surname in.")
    shared: int = Field(description="Sales whose buyer and seller share a surname.")
    sales: int = Field(description="Sales with both names, in the sample.")
    sampled: bool = Field(default=False, description=f"Only the first {SAMPLE:,} sales were read.")


def guess(names: list[str]) -> tuple[FormatId | None, str]:
    """The format the names look written in, and why."""
    from openavmkit.sales_scrutiny_study import SURNAME_SKIP_WORDS

    skip = {w.strip(".") for w in SURNAME_SKIP_WORDS}
    people = [n for n in names if n.strip() and not any(w.upper().strip(".") in skip for w in n.split())]
    if not people:
        return None, "No names of people to go by."
    comma = sum("," in n for n in people) / len(people)
    caps = sum(n == n.upper() for n in people) / len(people)
    if comma >= 0.5:
        return "before_comma", f"{comma:.0%} of the names have a comma: surname, then given names."
    if caps >= 0.8:
        return (
            "first_word",
            f"{caps:.0%} of the names are in capitals without a comma, the way recorders write SURNAME GIVEN.",
        )
    return "last_word", f"{1 - caps:.0%} of the names are in mixed case, the way people write Given Surname."


def check_pattern(pattern: str) -> str | None:
    """What's wrong with a pattern, in words; None when it can be used."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"It isn't a regular expression OpenAVMKit can read: {e}."
    if "surname" not in rx.groupindex:
        return "It needs a group named surname, like (?P<surname>…), around the part that is the surname."
    return None


def view(
    project,
    in_dir: Path,
    format: FormatId | None = None,
    pattern: str | None = None,
) -> NamesView:
    """The names read with the saved format, or with a format (and, for custom, a pattern) being tried."""
    from openavmkit.sales_scrutiny_study import SURNAME_SKIP_WORDS, surnames

    from oakbox import wizard

    c = project.clean
    data = wizard.deed_names(project, in_dir)
    sellers, buyers = (data.get("seller") or [])[:SAMPLE], (data.get("buyer") or [])[:SAMPLE]
    given_s, given_b = (data.get("seller_surname") or [])[:SAMPLE], (data.get("buyer_surname") or [])[:SAMPLE]
    g, why = guess(sellers + buyers)
    chosen: FormatId | None = format or c.name_format or g
    if chosen == "custom":
        pat = pattern if pattern is not None else (c.name_pattern or "")
    else:
        pat = BY_ID[chosen].pattern if chosen else BY_ID["first_word"].pattern
    error = check_pattern(pat) if pat else "Write a regular expression with a group named surname."
    rows: list[NameRow] = []
    read = companies = unread = shared_n = sales = 0
    skip = {w.strip(".") for w in SURNAME_SKIP_WORDS}
    n = max(len(sellers), len(buyers), len(given_s), len(given_b))

    def at(values: list[str], i: int) -> str:
        return values[i] if i < len(values) else ""

    for i in range(n):
        seller, buyer = at(sellers, i), at(buyers, i)
        gs, gb = at(given_s, i), at(given_b, i)
        if not (seller or gs) or not (buyer or gb):
            continue
        sales += 1
        found = []
        for name, given in ((seller, gs), (buyer, gb)):
            if given:
                found.append(surnames(given, r"(?P<surname>.+)"))
                continue
            got = [] if error else surnames(name, pat)
            if got:
                read += 1
            elif any(w.upper().strip(".") in skip for w in re.findall(r"[A-Za-z][A-Za-z'.\-]*", name)):
                companies += 1
            else:
                unread += 1
            found.append(got)
        both = sorted(set(found[0]) & set(found[1]))
        shared_n += bool(both)
        rows.append(
            NameRow(
                seller=gs or seller,
                buyer=gb or buyer,
                seller_surnames=found[0],
                buyer_surnames=found[1],
                shared=both,
            )
        )
    # Some that share a surname, then some that don't, as they come.
    rows = [r for r in rows if r.shared][:6] + [r for r in rows if not r.shared][:6]
    return NamesView(
        available=bool((sellers or given_s) and (buyers or given_b)),
        file=data.get("file"),
        surname_fields=bool(given_s and given_b),
        formats=FORMATS,
        guess=g,
        why=why,
        format=c.name_format,
        pattern=pat,
        error=error,
        rows=rows,
        read=read,
        companies=companies,
        unread=unread,
        shared=shared_n,
        sales=sales,
        sampled=n >= SAMPLE,
    )


def save(project, format: FormatId, pattern: str | None) -> None:
    if format == "custom":
        problem = check_pattern(pattern or "")
        if problem:
            raise ValueError(problem)
        project.clean.name_pattern = pattern
    elif format not in BY_ID:
        raise ValueError(f"No name format {format}.")
    project.clean.name_format = format


def pattern(project) -> str | None:
    """The pattern sales scrutiny reads names with: the confirmed one; None: OpenAVMKit's default (surname first)."""
    c = project.clean
    if c.name_format == "custom":
        return c.name_pattern
    if c.name_format:
        return BY_ID[c.name_format].pattern
    return None

"""Reconcile (F3d): cleaning up IDs so the sales find their parcels. How the sales match with a set of clean-up
steps, samples of each side, and a suggestion of steps that match more of them.
"""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from oakbox.datafiles import (
    BaseModel,
    CleanStep,
    DataFile,
    Match,
    clean_calc,
)
from oakbox.projects import Project
from oakbox.wizard.checks import parcel_ids
from oakbox.wizard.files import Files, file_stamp, is_more_sales, sales_file, values_of

# ---------- Reconcile: clean up IDs so the sales find their parcels (F3d) ----------


class Sample(BaseModel):
    raw: str = Field(description="As written in the file.")
    clean: str = Field(description="After the clean-up steps.")
    hit: bool = Field(description="Sales: finds a parcel. Parcels: has a sale.")


class Suggestion(BaseModel):
    text: str = Field(description="'Remove leading zeros from the parcel IDs; trim spaces from the sales IDs'.")
    base_steps: list[CleanStep]
    file_steps: list[CleanStep]
    share: float


class Reconcile(BaseModel):
    file: str = Field(description="The file being joined.")
    base: str = Field(description="What it joins to: the parcel universe, or the main sales file.")
    kind: Literal["sales", "parcels", "more_sales"] = Field(
        description="sales: the main sales file to the parcels; parcels: more parcel details to the parcels; "
        "more_sales: more sales details to the main sales file."
    )
    field: Match = Field(description="The ID they join on.")
    file_column: str
    base_column: str
    matched: int
    total: int
    parcels: int = Field(description="Distinct parcel IDs on the universe side, after its steps.")
    share: float
    saved_share: float = Field(description="The share with the steps as saved, before these changes.")
    file_samples: list[Sample]
    base_samples: list[Sample]
    suggestion: Suggestion | None
    writes: dict[str, list] = Field(description="entry -> the calc it writes for the ID (only files with steps).")


SampleView = Literal["unmatched", "random"]
SAMPLES = 6


def _sides(project: Project, in_dir: Path, name: str) -> tuple[Files, DataFile, DataFile, Match]:
    """A file and what it joins to: the parcel universe, or (more sales details) the main sales file."""
    files = Files(project, in_dir)
    entry = files.entry(name)
    if is_more_sales(entry):
        main = sales_file(project)
        if main is None or "key_sale" not in main.load:
            raise ValueError("The sales record has no sale ID column to join on.")
        target = main
    else:
        base = project.wizard.base
        if base is None or base == name or base not in files.preview:
            raise ValueError("Add the parcel universe first.")
        target = files.entry(base)
    if entry.match not in entry.load or entry.match not in target.load:
        raise ValueError(f"Pick the ID column of {name} first.")
    return files, entry, target, entry.match


def _matched(file_ids: tuple[str, ...], base_set: set[str] | frozenset[str]) -> int:
    return sum(1 for v in file_ids if v and v in base_set)


# What the suggestion tries on each side, simplest first.
_TRIES: list[list[CleanStep]] = [
    [],
    [CleanStep(kind="trim")],
    [CleanStep(kind="zeros")],
    [CleanStep(kind="trim"), CleanStep(kind="zeros")],
    [CleanStep(kind="remove", text="-")],
    [CleanStep(kind="remove", text="- ")],
    [CleanStep(kind="remove", text="- "), CleanStep(kind="zeros")],
    [CleanStep(kind="remove", text="-. /"), CleanStep(kind="zeros")],
    [CleanStep(kind="upper")],
    [CleanStep(kind="trim"), CleanStep(kind="upper")],
]


def describe_steps(steps: list[CleanStep]) -> str:
    names = {"zeros": "remove leading zeros", "trim": "trim spaces", "upper": "make letters capitals"}
    out = []
    for st in steps:
        if st.kind == "remove":
            out.append("remove hyphens" if st.text == "-" else f"remove {' '.join(repr(c) for c in st.text)}")
        else:
            out.append(names.get(st.kind, st.kind))
    return " and ".join(out)


def _side(files: Files, f: DataFile, field: str) -> tuple[tuple[str, float, int], str | None, str] | None:
    """What a file's ID field is read from: its file as it stands, its layer, the column."""
    spec = f.load.get(field)
    if spec is None or f.name not in files.preview:
        return None
    return file_stamp(files.in_dir / f.filename), f.layer, spec[0]


def _cleaned(uniques: Any, steps: list[CleanStep]) -> Any:
    """clean_value on every distinct ID at once, in Arrow (the steps a suggestion tries: trim, zeros, remove, upper);
    blanks stay blank."""
    import pyarrow as pa
    import pyarrow.compute as pc

    s = uniques
    blank = pc.equal(pc.utf8_trim_whitespace(s), "")  # pyright: ignore[reportAttributeAccessIssue]
    for st in steps:
        if st.kind == "zeros":
            s = pc.utf8_ltrim(s, characters="0")  # pyright: ignore[reportAttributeAccessIssue]
        elif st.kind == "remove":
            for c in st.text:
                s = pc.replace_substring(s, pattern=c, replacement="")  # pyright: ignore[reportAttributeAccessIssue]
        elif st.kind == "trim":
            s = pc.utf8_trim_whitespace(s)  # pyright: ignore[reportAttributeAccessIssue]
        elif st.kind == "upper":
            s = pc.utf8_upper(s)  # pyright: ignore[reportAttributeAccessIssue]
    return pc.if_else(blank, pa.scalar("", pa.string()), s)  # pyright: ignore[reportAttributeAccessIssue]


@lru_cache(maxsize=16)
def _match_table(base: tuple, file: tuple) -> Any:
    """How many of the file's rows find an ID on the base side, for each pair of clean-ups tried (_TRIES): a
    len(_TRIES) x len(_TRIES) table, base tries down, file tries across. Worked out on the distinct IDs, in Arrow."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc

    def distinct(side: tuple) -> tuple[Any, Any]:
        enc = pa.array(values_of(*side, raw=True), type=pa.string()).dictionary_encode()
        counts = np.bincount(enc.indices.to_numpy(zero_copy_only=False), minlength=len(enc.dictionary))
        return enc.dictionary, counts

    b_uniques, _ = distinct(base)
    f_uniques, f_counts = distinct(file)
    cleaned = [_cleaned(b_uniques, t) for t in _TRIES] + [_cleaned(f_uniques, t) for t in _TRIES]
    # One numbering for every cleaned ID on both sides, so "in the base set" is an array lookup.
    enc = pa.chunked_array(cleaned).combine_chunks().dictionary_encode()
    allcodes = enc.indices.to_numpy(zero_copy_only=False)
    blanks = np.flatnonzero(pc.equal(enc.dictionary, "").to_numpy(zero_copy_only=False))  # pyright: ignore[reportAttributeAccessIssue]
    n = len(_TRIES)
    nb, nf = len(b_uniques), len(f_uniques)
    table = np.zeros((n, n), dtype=np.int64)
    for b in range(n):
        has = np.zeros(len(enc.dictionary), dtype=bool)
        has[allcodes[b * nb : (b + 1) * nb]] = True
        has[blanks] = False
        for f in range(n):
            at = n * nb + f * nf
            table[b, f] = int(f_counts[has[allcodes[at : at + nf]]].sum())
    return table


def suggest_match(
    files: Files, entry: DataFile, base: DataFile, field: Match, now: float, kind: str = "sales"
) -> Suggestion | None:
    """The simplest clean-up pair from a few common ones that matches clearly more sales. Only a suggestion."""
    total = len(files.ids(entry.name, field))
    if not total:
        return None
    b_side, f_side = _side(files, base, field), _side(files, entry, field)
    if b_side is None or f_side is None:
        return None
    table = _match_table(b_side, f_side)
    best: tuple[float, int, int, int] | None = None
    for b in range(len(_TRIES)):
        for f in range(len(_TRIES)):
            share = int(table[b, f]) / total
            score = (share, -(len(_TRIES[b]) + len(_TRIES[f])), b, f)
            if best is None or score[:2] > best[:2]:
                best = score
    if best is None or best[0] < now + 0.01:
        return None
    share, _, b, f = best
    parts = []
    target, mine = ("sale IDs", f"{entry.name} IDs") if kind == "more_sales" else ("parcel IDs", f"{entry.name} IDs")
    if kind == "sales":
        mine = "sales IDs"

    def on(steps: list[CleanStep], what: str) -> str:
        return f"{describe_steps(steps)} {'in' if all(st.kind == 'upper' for st in steps) else 'from'} the {what}"

    if _TRIES[b]:
        parts.append(on(_TRIES[b], target))
    if _TRIES[f]:
        parts.append(on(_TRIES[f], mine))
    text = "; ".join(parts)
    return Suggestion(text=text[:1].upper() + text[1:], base_steps=_TRIES[b], file_steps=_TRIES[f], share=share)


def reconcile(
    project: Project,
    in_dir: Path,
    name: str,
    file_steps: list[CleanStep],
    base_steps: list[CleanStep],
    view: SampleView = "unmatched",
    seed: int = 0,
    suggest: bool = False,
) -> Reconcile:
    """How the sales match with these steps, and samples of each side: the live view of the dialog."""
    files, entry, base, field = _sides(project, in_dir, name)
    file_ids = files.ids(name, field, file_steps)
    base_ids = files.ids(base.name, field, base_steps)
    base_set = {v for v in base_ids if v}
    file_set = {v for v in file_ids if v}
    saved = _matched(files.ids(name, field), parcel_ids(files, base.name, field))
    matched = _matched(file_ids, base_set)
    total = len(file_ids)
    rng = random.Random(seed)
    file_raw = values_of(file_stamp(in_dir / entry.filename), entry.layer, entry.load[field][0], raw=True)
    base_raw = values_of(file_stamp(in_dir / base.filename), base.layer, base.load[field][0], raw=True)

    def pick(raw: tuple[str, ...], ids: tuple[str, ...], keep) -> list[tuple[str, str]]:
        seen: dict[str, str] = {}
        for r, c in zip(raw, ids, strict=True):
            if r not in seen and keep(c):
                seen[r] = c
        chosen = rng.sample(list(seen.items()), min(SAMPLES, len(seen)))
        return sorted(chosen, key=lambda rc: rc[0])

    hit_file = (lambda c: not (c and c in base_set)) if view == "unmatched" else (lambda c: True)
    file_samples = [
        Sample(raw=r, clean=c, hit=bool(c) and c in base_set) for r, c in pick(file_raw, file_ids, hit_file)
    ]
    base_samples = [Sample(raw=r, clean=c, hit=c in file_set) for r, c in pick(base_raw, base_ids, bool)]
    writes = {n: clean_calc(field, st) for n, st in ((base.name, base_steps), (name, file_steps)) if st}
    kind = "more_sales" if is_more_sales(entry) else "sales" if entry.holds == "sales" else "parcels"
    return Reconcile(
        file=name,
        base=base.name,
        kind=kind,
        field=field,
        file_column=entry.load[field][0],
        base_column=base.load[field][0],
        matched=matched,
        total=total,
        parcels=len(base_set),
        share=matched / total if total else 0.0,
        saved_share=saved / total if total else 0.0,
        file_samples=file_samples,
        base_samples=base_samples,
        suggestion=suggest_match(files, entry, base, field, matched / total if total else 0.0, kind)
        if suggest
        else None,
        writes=writes,
    )


def set_reconcile(
    project: Project, in_dir: Path, name: str, file_steps: list[CleanStep], base_steps: list[CleanStep]
) -> None:
    """Save the clean-up steps on both sides of the join; OpenAVMKit runs them as calcs when it loads."""
    files, entry, base, field = _sides(project, in_dir, name)
    for f, steps in ((entry, file_steps), (base, base_steps)):
        if steps:
            f.clean[field] = steps
        else:
            f.clean.pop(field, None)

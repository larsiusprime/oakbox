"""Rows for parcels missing from the parcel universe (F3d): why a file's IDs find no parcel. Written another way
(a clean-up would match them), a few odd rows, or parcels left out of the map, and which file holds them.
"""

from __future__ import annotations

import string
from functools import lru_cache

from oakbox.datafiles import (
    EXTRA_IDS,
    DataFile,
)
from oakbox.projects import Project
from oakbox.wizard.checks import MATCH_MIN, MATCH_OK, counted, parcel_ids
from oakbox.wizard.condos import unit_ids, unshaped_rows
from oakbox.wizard.files import Files, cleaned_ids, file_stamp, is_more_sales, row_count, steps_key
from oakbox.wizard.ids import Suggestion, describe_steps, suggest_match
from oakbox.wizard.models import MissingParcels, WizardFile

# ---------- Rows for parcels missing from the parcel universe (F3d) ----------

MISSING_SHAPED = 0.8  # this share of the unmatched IDs written like the universe's: not a matter of cleaning
MISSING_GAIN = 0.02  # a clean-up that matches this many more rows makes it a matter of cleaning after all
MISSING_FEW = 10  # fewer parcels than this: odd rows (a parcel combined away), not parcels left out of the map


_SHAPES = str.maketrans(
    {
        **{c: "9" for c in "0123456789"},
        **{c: "A" for c in string.ascii_uppercase},
        **{c: "a" for c in string.ascii_lowercase},
    }
)


def _shape(v: str) -> str:
    """How an ID is written: digits as 9, capitals as A, small letters as a, the rest as is ("0012-001" →
    "9999-999", "r0123456" → "a9999999")."""
    return v.translate(_SHAPES)


@lru_cache(maxsize=8)
def _shapes_of(ids: frozenset[str]) -> frozenset[str]:
    """Every way the parcel universe writes its IDs: worked out once (500,000 IDs, every wizard click, took 2 s)."""
    return frozenset(v.translate(_SHAPES) for v in ids)


def _near(v: str, known: set[str] | frozenset[str]) -> bool:
    """One digit off another ID in known (a keying slip): 1234 for 1284."""
    for i, ch in enumerate(v):
        if ch.isdigit():
            for d in "0123456789":
                if d != ch and f"{v[:i]}{d}{v[i + 1 :]}" in known:
                    return True
    return False


def _slips(missing: set[str], known: set[str] | frozenset[str], matched: list[str]) -> int:
    """About how many of the missing IDs are keying slips. Where IDs are packed close (short numbers), plenty of
    real IDs are one digit off another too: what counts is how much more often the missing ones are than the
    matched ones."""
    sample = sorted(missing)[:3000]
    near = sum(1 for v in sample if _near(v, known)) / len(sample)
    peers = matched[:2000]
    base = sum(1 for v in peers if _near(v, known)) / len(peers) if peers else 0.0
    if base >= 0.9:
        return 0
    return round(max(0.0, (near - base) / (1 - base)) * len(missing))


@lru_cache(maxsize=256)
def _column_ids(stamp: tuple[str, float, int], layer: str | None, column: str, steps: str) -> frozenset[str]:
    return frozenset(v for v in cleaned_ids(stamp, layer, column, steps) if v)


def _unmatched(files: Files, f: DataFile, base: DataFile) -> tuple[set[str], int]:
    """(the parcel IDs a file's rows have that the parcel universe lacks, how many rows have one)."""
    known = parcel_ids(files, base.name, f.match) | (unit_ids(files) if f.match == "key" else set())
    return _missing_of(files.ids(f.name, f.match), frozenset(known))


@lru_cache(maxsize=16)
def _missing_of(ids: tuple[str, ...], known: frozenset[str]) -> tuple[set[str], int]:
    missing = [v for v in ids if v and v not in known]
    return set(missing), len(missing)


def diagnose_missing(project: Project, files: Files, out: list[WizardFile]) -> None:
    """Tell rows whose IDs are written differently (Reconcile cleans those up) from rows for parcels the parcel
    universe doesn't have: condo units on the roll but not the map, newer parcels, a file not added. For the
    second, say so, name a file in the project that has them, and the other files missing the same IDs."""
    base = project.base_file()
    if base is None or base.name not in files.preview:
        return
    gaps: dict[str, tuple[set[str], int]] = {}
    known = parcel_ids(files, base.name)
    for wf in out:
        f = files.entry(wf.name)
        if wf.base or wf.id_check is None or f.match not in ("key", *EXTRA_IDS) or is_more_sales(f):
            continue
        if wf.holds not in ("sales", "parcels", "permits"):
            continue
        gaps[wf.name] = _unmatched(files, f, base)
    base_shapes: frozenset[str] | None = None  # only worked out when a file needs it
    for wf in out:
        if wf.name not in gaps or wf.id_check is None or (wf.id_check.share or 0) >= MATCH_OK:
            continue
        missing, rows = gaps[wf.name]
        if len(missing) < MISSING_FEW:
            continue
        f = files.entry(wf.name)
        total = len(files.ids(f.name, f.match))
        now = (total - rows) / total if total else 0.0
        shapeless = wf.holds == "parcels" and wf.unshaped >= 0.5 * (wf.rows or 1) and wf.units is None
        if base_shapes is None:
            base_shapes = _shapes_of(parcel_ids(files, base.name))
        shaped = sum(1 for v in missing if _shape(v) in base_shapes) / len(missing)
        if (wf.id_check.share or 0) < MATCH_MIN and not shapeless and shaped >= MISSING_SHAPED:
            # Fewer than half, written like parcel IDs: more likely another numbering than half the parcels
            # missing. (Written otherwise, it's for Reconcile.)
            column = wf.id_column or "the ID column"
            line = (
                f"Fewer than half find a parcel: is {column} the parcel ID, the same one the parcel universe "
                f"uses? Or does {base.filename} cover a smaller area than {f.filename}?"
            )
            if suggest_match(files, f, base, f.match, now + MISSING_GAIN - 0.01, "parcels") is None:
                wf.not_in_universe = MissingParcels(
                    kind="other_id", rows=rows, ids=len(missing), lines=[line], title="Under half match"
                )
            continue
        # A clean-up that matches clearly more: a matter of cleaning, for Reconcile.
        found = suggest_match(files, f, base, f.match, now + MISSING_GAIN - 0.01, "parcels")
        if found is not None or shaped < MISSING_SHAPED:
            continue
        what = {"sales": "sales", "permits": "permits"}.get(wf.holds or "", "rows")
        title = f"{counted(rows, {'sales': 'sale', 'permits': 'permit'}.get(wf.holds or '', 'row'))} off the map"
        what = f"{what[:-1]} is" if rows == 1 else f"{what} are"
        ids = f" ({counted(len(missing), 'parcel ID')})" if len(missing) != rows else ""
        # A clean-up too small to be the story (under 2 points) can still match a few: say which, and how many.
        kind = "sales" if wf.holds == "sales" else "parcels"
        small = suggest_match(files, f, base, f.match, now - 0.01 + 1e-9, kind)
        some = round((small.share - now) * total) if small is not None else 0
        lines = [
            f"{rows:,} {what} for parcels that aren't in the parcel universe{ids}. "
            + (
                f"Their IDs are written like the parcel universe's, so cleaning up won't help most of them: "
                f"{some:,} more match if you {_beyond(small, f, base)} (Reconcile\u2026)."
                if small is not None and some > 0
                else "Their IDs are written like the parcel universe's, so cleaning them up won't help."
            )
        ]
        if shapeless:
            lines.append(
                "Its rows have no shape of their own, and you said on Condo units that no parcels are units: "
                "they're left out."
                if project.wizard.condos is False
                else "Its rows have no shape of their own: if they're condos or other units on a parcel they share, "
                "set them up on the Condo units step."
            )
        # A file in the project that has them: added, but not joined as parcels.
        # A file in the project that has them, not joined as parcels yet (unless this file holds them itself).
        # Keying slips, where the rows aren't units waiting to be set up.
        matched = [v for v in files.ids(f.name, f.match) if v and v in known]
        slips = 0 if shapeless else _slips(missing, known, matched)
        if slips >= MISSING_FEW and slips >= 0.2 * len(missing):
            lines.append(
                f"About {slips:,} of them look like keying slips: one digit off a parcel ID. See them to check; "
                f"fixing them is for the file they came from."
            )
        if slips >= 0.8 * len(missing):
            wf.not_in_universe = MissingParcels(rows=rows, ids=len(missing), lines=lines, title=title)
            continue
        units = shapeless
        holder = None if shapeless else _holder(project, files, f, missing, base)
        if holder is not None:
            name, column, n = holder
            them = f"{n:,} of them {'is' if n == 1 else 'are'} in {name} ({column})"
            if files.entry(name).holds == "parcels":
                units = True
                lines.append(
                    f"{them}, whose rows have no shape of their own: condos or other units, it seems. Set them up on "
                    f"the Condo units step."
                )
            else:
                lines.append(
                    f"{them}. If its rows are condos or other units without a shape of their own, join it on More "
                    f"files (more about each parcel, on {column}), then set them up on the Condo units step."
                )
        elif not shapeless:
            lines.append(
                f"Usually they're parcels kept outside {base.filename}: condos and other units without a shape of "
                f"their own (timeshares, homes in a mobile-home park, buildings on leased land), or parcels made "
                f"since. Have a file with them? Add it on More files; units are set up on the Condo units step."
            )
        for other, (theirs, _) in gaps.items():
            same = len(missing & theirs)
            held = holder is not None and other == holder[0]
            if other != wf.name and not held and same >= 10 and same >= 0.3 * min(len(missing), len(theirs)):
                lines.append(
                    f"{other} lacks {same:,} of the same parcel{'' if same == 1 else 's'} too: "
                    f"they're missing from the parcel universe, not written differently."
                )
        wf.not_in_universe = MissingParcels(rows=rows, ids=len(missing), lines=lines, units=units, title=title)


def _beyond(sug: Suggestion, f: DataFile, base: DataFile) -> str:
    """A suggestion in words, leaving out the sides already cleaned that way: "trim spaces from the sales IDs"."""
    parts = []
    if sug.base_steps and sug.base_steps != base.clean.get(f.match, []):
        parts.append(f"{describe_steps(sug.base_steps)} from the parcel IDs")
    if sug.file_steps and sug.file_steps != f.clean.get(f.match, []):
        mine = "sales IDs" if f.holds == "sales" else f"{f.name} IDs"
        parts.append(f"{describe_steps(sug.file_steps)} from the {mine}")
    return " and ".join(parts) or "clean them up"


def _holder(
    project: Project, files: Files, f: DataFile, missing: set[str], base: DataFile
) -> tuple[str, str, int] | None:
    """The project file (not joined as parcels yet) with a column holding the most of these IDs, cleaned as this
    file's are, or as the parcel universe's (as it would be, joined to it): at least half of them, or 20."""
    tries = {steps_key(f.clean.get(f.match, [])), steps_key(base.clean.get(f.match, []))}
    best = None
    for g in project.files:
        if g is f or g is base or g.holds in ("overlay", "sales", "permits") or g.units is not None:
            continue
        if g.name not in files.preview:
            continue
        # A file joined as parcel details adds no parcels, unless its rows are parcels without a shape (units).
        if g.holds == "parcels" and unshaped_rows(files, g, base.name) < 0.5 * (row_count(files, g.name) or 1):
            continue
        stamp = file_stamp(files.in_dir / g.filename)
        for c in files.columns(g.name):
            for steps in tries:
                n = len(missing & _column_ids(stamp, g.layer, c.name, steps))
                if (n >= 20 or n >= 0.5 * len(missing)) and (best is None or n > best[2]):
                    best = (g.name, c.name, n)
    return best

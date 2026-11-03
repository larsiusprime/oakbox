"""Values read out of OpenAVMKit's tables, one way everywhere: a number (finite, or none), a column of numbers or of
yes/no, a cell as text."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import pandas as pd


def number(v) -> float | None:
    """A number, or None for a blank, a text, NaN or infinity (none of which JSON can carry)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def numbers(df, column: str) -> pd.Series:
    """A column as numbers (blank where it isn't one); all blank when there's no such column."""
    import pandas as pd

    if column not in df:
        return pd.Series(float("nan"), index=df.index, dtype=float)
    return cast("pd.Series", pd.to_numeric(df[column], errors="coerce")).astype(float)


def yes(df, column: str) -> pd.Series:
    """A yes/no column as True/False (no where blank or missing)."""
    return numbers(df, column).fillna(0).astype(bool)


def text(v) -> str | None:
    """A cell as text: a date as its day; None for a blank."""
    import pandas as pd

    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return str(v.date())
    return str(v)


def log_floor(x: float) -> float:
    """The natural log, or a very low number for 0 or less: for sorting ratios by how far they are from 1."""
    return math.log(x) if x > 0 else -50.0

"""Every date OAK box shows is YYYY-MM-DD, however the file writes it (AGENTS.md, 2026-11-08).

A date column is read with its format: the one chosen when it's loaded as a date field (a sale date's
`["SALE_DT", "datetime", "%m/%d/%Y %H:%M"]`), else the one OAK box found it written in (`Column.date_format`). A value
that doesn't read as a date is shown as written. Only the "As written" side of a date field's reading (Sale date's
table) shows the file's own way: that's what it's there for.
"""

from __future__ import annotations

from datetime import datetime

from oakbox.datafiles import DataFile


def column_format(entry: DataFile, column: str, found: str | None = None) -> str | None:
    """The format a file's column is read with: its date field's, else the one found for it (`found`)."""
    for spec in entry.load.values():
        if spec and spec[0] == column and len(spec) > 2 and spec[1] == "datetime":
            return spec[2]
    return found


def iso_day(value: str, fmt: str | None) -> str:
    """A date as YYYY-MM-DD; as written if it doesn't read as one."""
    v = value.strip()
    if not v or fmt is None:
        return value
    try:
        return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
    except ValueError:
        pass
    # A format with a time read where the value has none, or the other way round: the date part alone.
    head = fmt.split(" ")[0]
    try:
        return datetime.strptime(v.split(" ")[0], head).strftime("%Y-%m-%d")
    except ValueError:
        return value


def date_format_of(files, entry: DataFile, column: str) -> str | None:
    """A file's column's date format, if it holds dates: as loaded, else as found in its first rows."""
    c = files.column(entry.name, column)
    found = None
    if c is not None and c.type == "date":
        found = "%Y-%m-%d %H:%M:%S"  # a date the file stores as one (Parquet, a GeoPackage), as text
    elif c is not None and c.type == "text":
        found = c.date_format
    return column_format(entry, column, found)

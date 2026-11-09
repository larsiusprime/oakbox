"""Each CSV the project reads, converted once to Parquet, so a column reads in milliseconds (SPEC §5).

The previews, checks and comparisons read a file a column at a time: from a 220 MB CSV each read is about a second
(Guilford, NC's parcels), from Parquet 0.04 s. So each CSV is converted once, when it's added (in the background,
with its progress), into `out/oakbox/cache/<name>-<size>-<mtime>.parquet`: every column as text, exactly as the CSV
is read for a preview (dtype str, blanks as ""). A read before it's done reads the CSV as before (it starts the
conversion if nothing has): nothing waits on it. A changed file is a new conversion; the old one is removed. Only
OAK box's own reads use it: OpenAVMKit reads the files themselves.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CACHE = ("out", "oakbox", "cache")
CHUNK = 25_000  # rows a chunk: progress is told between chunks, and a cancel is heard there


@dataclass
class Reading:
    """A conversion: how far through the file, and since when."""

    started: float
    fraction: float = 0.0
    done: bool = False
    error: str | None = None
    cancel: bool = False
    cancel_asked: bool = False  # stopped by the user: it may be started again
    lock: threading.Lock = field(default_factory=threading.Lock)


_readings: dict[str, Reading] = {}
_guard = threading.Lock()


def cache_path(path: Path) -> Path | None:
    """Where a CSV's Parquet copy goes (None: not a CSV). In the project's out/ beside in/, keyed by size and time."""
    if path.suffix.lower() != ".csv" or not path.is_file():
        return None
    st = path.stat()
    return path.parent.parent.joinpath(*CACHE) / f"{path.stem}-{st.st_size}-{st.st_mtime_ns}.parquet"


def _reading(path: Path) -> Reading:
    with _guard:
        r = _readings.get(str(path))
        if r is None:
            r = _readings[str(path)] = Reading(started=time.time())
        return r


def ensure(path: Path) -> Path | None:
    """The CSV's Parquet copy, made now if it isn't there (a second asker waits for the first). None: not a CSV, or
    it couldn't be made (the CSV is read as it is)."""
    target = cache_path(path)
    if target is None:
        return None
    if target.is_file():
        return target
    r = _reading(target)
    with r.lock:
        if target.is_file():
            return target
        try:
            _convert(path, target, r)
        except Exception as e:  # noqa: BLE001 - the CSV is read as it is instead
            r.error = str(e)
            return None
    return target if target.is_file() else None


def _convert(path: Path, target: Path, r: Reading) -> None:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    from oakbox.datafiles import csv_encoding

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    size = max(path.stat().st_size, 1)
    r.started, r.fraction, r.done, r.error, r.cancel_asked = time.time(), 0.0, False, None, False
    writer = None
    try:
        with path.open("rb") as fh:
            chunks = pd.read_csv(
                fh, dtype=str, keep_default_na=False, chunksize=CHUNK, encoding=csv_encoding(path) or "utf-8"
            )
            for chunk in chunks:
                if r.cancel:
                    raise InterruptedError("stopped")
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(tmp, table.schema, compression="zstd")
                writer.write_table(table.cast(writer.schema))
                r.fraction = min(fh.tell() / size, 0.99)
        if writer is None:  # no rows: the columns alone
            names = pd.read_csv(path, nrows=0, encoding=csv_encoding(path) or "utf-8").columns
            pq.write_table(pa.table({str(c): pa.array([], pa.string()) for c in names}), tmp)
        else:
            writer.close()
            writer = None
        tmp.replace(target)
        for old in target.parent.glob(f"{path.stem}-*.parquet"):
            if old != target and old.name.rsplit("-", 2)[0] == path.stem:
                old.unlink(missing_ok=True)  # the file changed since: its old copy
        r.fraction, r.done = 1.0, True
    finally:
        if writer is not None:
            writer.close()
        tmp.unlink(missing_ok=True)
        r.cancel = False


def start(path: Path, again: bool = False) -> None:
    """Convert in the background (a file just added), unless it's done or under way: its progress is status(). Not
    after it failed or the user stopped it, unless again (they asked)."""
    target = cache_path(path)
    if target is None or target.is_file():
        return
    r = _reading(target)
    if r.lock.locked() or (r.error and not again):
        return  # under way, or it failed or was stopped (read as a CSV)
    threading.Thread(target=ensure, args=(path,), daemon=True).start()


def ready(path: Path) -> Path | None:
    """The Parquet copy if it's there; else None (read the CSV), and the conversion started if it isn't going."""
    target = cache_path(path)
    if target is None:
        return None
    if target.is_file():
        return target
    start(path)
    return None


def stop(path: Path) -> None:
    target = cache_path(path)
    if target is not None and (r := _readings.get(str(target))) is not None and not r.done:
        r.cancel = r.cancel_asked = True


State = Literal["none", "ready", "reading", "failed", "waiting", "stopped"]


@dataclass
class Status:
    state: State  # "none" (not a CSV), "ready", "reading", "failed", "waiting" (not started), "stopped"
    fraction: float
    seconds: float
    left: float | None
    error: str | None = None


def status(path: Path) -> Status:
    target = cache_path(path)
    if target is None:
        return Status("none", 1.0, 0.0, 0.0)
    if target.is_file():
        return Status("ready", 1.0, 0.0, 0.0)
    r = _readings.get(str(target))
    if r is None:
        return Status("waiting", 0.0, 0.0, None)
    if r.error and r.cancel_asked:
        return Status("stopped", r.fraction, 0.0, None)
    if r.error:
        return Status("failed", r.fraction, 0.0, None, r.error)
    spent = time.time() - r.started
    left = spent / r.fraction * (1 - r.fraction) if r.fraction > 0.05 else None
    return Status("reading", r.fraction, spent, left)

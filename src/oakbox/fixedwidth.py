"""Fixed-width text exports (SPEC §4.1): layouts, PACS export detection, streaming conversion.

Exports are read straight out of their zip as a stream and never unpacked: a
Travis CAD export is 0.5 GB zipped and 17.8 GB unpacked. Conversion keeps only
the chosen fields and works on blocks of records with numpy, so a 4.9 GB
property file converts in about a minute.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from oakbox.setup import Agg, Collapse, FileUse, RowFilter, SortKey


@cache
def layouts() -> dict[str, dict]:
    out = {}
    for entry in resources.files("oakbox.layouts").iterdir():
        if entry.name.endswith(".json"):
            data = json.loads(entry.read_text())
            out[data["id"]] = data
    return out


def layout_file(layout_id: str, member: str) -> dict:
    return layouts()[layout_id]["files"][Path(member).name.upper()]


# Which files of a PACS export modeling uses, and Oakbox's starting choices for them.
# Owner names and mailing addresses are left out by default: modeling never needs them.
@dataclass(frozen=True)
class MemberDefaults:
    use: FileUse
    description: str
    keep: tuple[str, ...] | None = None  # None: every field except fillers and `drop`
    drop: tuple[str, ...] = ()
    keep_rows: RowFilter | None = None
    collapse: Collapse = field(default_factory=Collapse)


def _sum(*cols: str) -> dict[str, Agg]:
    return dict.fromkeys(cols, "sum")


PACS_DEFAULTS: dict[str, MemberDefaults] = {
    "PROP.TXT": MemberDefaults(
        use="parcels",
        description="One row per property and owner: IDs, situs, legal description, values, state codes.",
        keep=(
            "prop_id",
            "prop_type_cd",
            "prop_val_yr",
            "sup_num",
            "geo_id",
            "py_owner_id",
            "ownership_pct",
            "situs_num",
            "situs_street_prefx",
            "situs_street",
            "situs_street_suffix",
            "situs_unit",
            "situs_city",
            "situs_zip",
            "legal_desc",
            "legal_acreage",
            "land_acres",
            "abs_subdv_cd",
            "hood_cd",
            "block",
            "tract_or_lot",
            "land_hstd_val",
            "land_non_hstd_val",
            "imprv_hstd_val",
            "imprv_non_hstd_val",
            "ag_use_val",
            "ag_market",
            "appraised_val",
            "assessed_val",
            "market_value",
            "imprv_state_cd",
            "land_state_cd",
            "deed_dt",
            "deed_num",
            "hs_exempt",
            "ov65_exempt",
            "entities",
        ),
        keep_rows=RowFilter(column="prop_type_cd", values=["R"]),
        collapse=Collapse(
            sort_by=[SortKey(column="sup_num", descending=True), SortKey(column="ownership_pct", descending=True)]
        ),
    ),
    "LAND_DET.TXT": MemberDefaults(
        use="parcels",
        description="Land segments: several per property, with size and land type.",
        collapse=Collapse(
            sort_by=[SortKey(column="size_acres", descending=True)],
            fields={**_sum("size_acres", "size_square_feet", "land_seg_mkt_val", "ag_value"), "land_seg_id": "count"},
        ),
    ),
    "IMP_INFO.TXT": MemberDefaults(
        use="parcels",
        description="Improvements (buildings): several per property, with type and value.",
        collapse=Collapse(
            sort_by=[SortKey(column="imprv_val", descending=True)],
            fields={**_sum("imprv_val"), "imprv_id": "count"},
        ),
    ),
    "IMP_DET.TXT": MemberDefaults(
        use="parcels",
        description="Improvement details (areas of each building): many per property, with year built and area.",
        drop=("sketch_cmds",),
        collapse=Collapse(
            sort_by=[SortKey(column="imprv_det_area", descending=True)],
            fields={**_sum("imprv_det_area", "imprv_det_val"), "yr_built": "min", "imprv_det_id": "count"},
        ),
    ),
}

ID_COLUMN = {"pacs": "prop_id"}


@dataclass
class ExportMember:
    member: str
    label: str
    description: str
    size_bytes: int
    records: int
    used_by_default: bool
    use: FileUse | None


@dataclass
class Export:
    layout_id: str
    name: str
    members: list[ExportMember]
    unknown: list[str]


def detect_export(path: Path) -> Export | None:
    """A zip whose files match a known fixed-width layout, checked on the first record of each."""
    if path.suffix.lower() != ".zip" or not zipfile.is_zipfile(path):
        return None
    with zipfile.ZipFile(path) as z:
        infos = {Path(i.filename).name.upper(): i for i in z.infolist() if not i.is_dir()}
        for lid, layout in layouts().items():
            known = [n for n in infos if n in layout["files"]]
            if "PROP.TXT" not in known:
                continue
            members, ok = [], True
            for n in known:
                info = infos[n]
                spec = layout["files"][n]
                with z.open(info) as fh:
                    first = fh.readline()
                rec = len(first.rstrip(b"\r\n"))
                if first and rec != spec["record_length"]:
                    ok = n != "PROP.TXT"  # a wrong-length main file means a different layout version
                    if not ok:
                        break
                    continue
                d = PACS_DEFAULTS.get(n)
                members.append(
                    ExportMember(
                        member=info.filename,
                        label=spec["label"],
                        description=d.description if d else spec["label"],
                        size_bytes=info.file_size,
                        records=info.file_size // (rec + _eol_len(first)) if first else 0,
                        used_by_default=d is not None,
                        use=d.use if d else None,
                    )
                )
            if ok:
                unknown = sorted(n for n in infos if n not in layout["files"])
                members.sort(key=lambda m: (not m.used_by_default, -m.size_bytes))
                return Export(layout_id=lid, name=layout["name"], members=members, unknown=unknown)
    return None


def _eol_len(line: bytes) -> int:
    return 2 if line.endswith(b"\r\n") else 1 if line.endswith(b"\n") else 0


def default_columns(layout_id: str, member: str) -> list[str]:
    spec = layout_file(layout_id, member)
    d = PACS_DEFAULTS.get(Path(member).name.upper())
    names = [f["name"] for f in spec["fields"] if "filler" not in f["name"].lower()]
    if d is None:
        return names
    if d.keep is not None:
        return [n for n in names if n in d.keep]
    return [n for n in names if n not in d.drop]


def sample_rows(path: Path, member: str, layout_id: str, n: int = 20) -> tuple[list[dict], list[dict]]:
    """First ``n`` records as dicts, plus the field specs (name/number/description)."""
    spec = layout_file(layout_id, member)
    fields = [f for f in spec["fields"] if "filler" not in f["name"].lower()]
    rows = []
    with zipfile.ZipFile(path) as z, z.open(member) as fh:
        for _ in range(n):
            line = fh.readline()
            if not line:
                break
            text = line.decode("latin-1")
            rows.append({f["name"]: text[f["start"] - 1 : f["start"] - 1 + f["width"]].strip() for f in fields})
    return rows, fields


def convert(
    path: Path,
    member: str,
    layout_id: str,
    columns: list[str],
    text_columns: set[str],
    dest: Path,
    on_progress: Callable[[float, str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    block_records: int = 50_000,
) -> int:
    """Stream ``member`` out of the zip into a Parquet file with only ``columns``. Returns rows written.

    Numeric layout fields become floats, except ``text_columns`` (IDs keep leading zeros).
    """
    spec = layout_file(layout_id, member)
    by_name = {f["name"]: f for f in spec["fields"]}
    fields = [by_name[c] for c in columns]
    reclen = spec["record_length"]
    rows = 0
    writer: pq.ParquetWriter | None = None
    tmp = dest.with_suffix(".part")
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(member)
        with z.open(info) as fh:
            first = fh.readline()
            eol = _eol_len(first)
            width = reclen + eol
            pending = first
            total = max(info.file_size, 1)
            done = 0
            while True:
                if cancelled and cancelled():
                    raise InterruptedError("Stopped.")
                chunk = pending + fh.read(block_records * width - len(pending))
                pending = b""
                if not chunk:
                    break
                usable = len(chunk) - len(chunk) % width
                if usable == 0:  # a short last record (no line ending)
                    chunk = chunk.ljust(width, b" ")
                    usable = width
                block, pending = chunk[:usable], chunk[usable:]
                arr = np.frombuffer(block, dtype=np.uint8).reshape(-1, width)
                table = pa.table({f["name"]: _column(arr, f, f["name"] in text_columns) for f in fields})
                if writer is None:
                    writer = pq.ParquetWriter(tmp, table.schema)
                writer.write_table(table)
                rows += len(arr)
                done += usable
                if on_progress:
                    on_progress(min(done / total, 1.0), f"{rows:,} records")
    if writer is None:
        writer = pq.ParquetWriter(tmp, pa.schema([(f["name"], pa.string()) for f in fields]))
    writer.close()
    tmp.replace(dest)
    return rows


def _column(arr: np.ndarray, f: dict, as_text: bool) -> pa.Array:
    a = f["start"] - 1
    raw = np.ascontiguousarray(arr[:, a : a + f["width"]]).view(f"S{f['width']}").ravel()
    text = np.char.strip(np.char.decode(raw, "latin-1"))
    if f["number"] and not as_text:
        values = np.full(len(text), np.nan)
        ok = text != ""
        try:
            values[ok] = text[ok].astype(np.float64)
        except ValueError:  # a stray non-number: convert one by one
            values[ok] = [_to_float(t) for t in text[ok]]
        return pa.array(values, type=pa.float64(), from_pandas=True)
    return pa.array(text.tolist(), type=pa.string())


def _to_float(t: str) -> float:
    try:
        return float(t)
    except ValueError:
        return float("nan")

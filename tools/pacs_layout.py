"""Convert a PACS "Legacy Appraisal Export Layout" workbook into Oakbox's layout JSON.

Usage: uv run --with openpyxl python tools/pacs_layout.py <layout.xlsx> <version> > src/oakbox/layouts/pacs-legacy-<version>.json

The workbook is published by appraisal districts (e.g. Travis CAD's public
information page). Only field names, positions, types and the first line of
each description are kept.
"""

from __future__ import annotations

import json
import re
import sys

import openpyxl


def main() -> None:
    path, version = sys.argv[1], sys.argv[2]
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    files = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        title = next((r[0] for r in rows if isinstance(r[0], str) and "Short file name" in r[0]), None)
        if not title:
            continue
        short = re.search(r"Short file name \(([^)]+)\)", title).group(1).strip()
        long_name = re.search(r"\(([^)]+\.TXT)\)", title)
        m = re.search(r"File #\d+:\s*([^(\n]+)", title)
        label = " ".join((m.group(1) if m else short).split())
        fields, pos, started = [], 1, False
        for r in rows:
            if r[0] == "Field Name":
                started = True
                continue
            if not started or r[0] is None or not isinstance(r[4], (int, float)):
                continue
            width = int(r[4])
            start = int(r[2]) if isinstance(r[2], (int, float)) else pos
            dtype = str(r[1]).strip().lower()
            desc = str(r[5] or "").strip().splitlines()[0] if r[5] else ""
            fields.append(
                {
                    "name": str(r[0]).strip(),
                    "start": start,
                    "width": width,
                    "number": dtype.startswith(("int", "numeric", "decimal")),
                    "description": desc[:120],
                }
            )
            pos = start + width
        if fields:
            files[short] = {
                "label": label,
                "long_name": long_name.group(1) if long_name else short,
                "record_length": pos - 1,
                "fields": fields,
            }
    json.dump({"id": f"pacs-legacy-{version}", "name": f"PACS appraisal export (legacy {version})", "files": files},
              sys.stdout, indent=1)


if __name__ == "__main__":
    main()

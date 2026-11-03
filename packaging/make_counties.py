"""Writes src/oakbox/counties.json: every US county (and equivalent), its FIPS code, state and the rectangle around
it (west, south, east, north, in degrees), from the Census Bureau's TIGERweb: the Census enrichment's county picker,
and which county the parcels are in.

Run when counties change (rarely):

    uv run python packaging/make_counties.py
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/{layer}/query?"
PAGE = 1000


def query(layer: int, fields: str, shapes: bool = False) -> list[dict]:
    out: list[dict] = []
    while True:
        q = {"where": "1=1", "outFields": fields, "returnGeometry": str(shapes).lower(), "f": "json"}
        q |= {"resultOffset": str(len(out)), "resultRecordCount": str(PAGE), "orderByFields": "GEOID"}
        if shapes:
            # Simplified to about a kilometre: enough for the rectangle around each county.
            q |= {"outSR": "4326", "maxAllowableOffset": "0.01"}
        with urllib.request.urlopen(URL.format(layer=layer) + urllib.parse.urlencode(q), timeout=120) as r:  # noqa: S310
            rows = [f["attributes"] | {"_box": _box(f.get("geometry"))} for f in json.loads(r.read())["features"]]
        out += rows
        if len(rows) < PAGE:
            return out


def _box(geometry: dict | None) -> list[float] | None:
    points = [p for ring in (geometry or {}).get("rings", []) for p in ring]
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)]


# Layer 0 is states, 1 counties.
states = {s["STATE"]: s["STUSAB"] for s in query(0, "STATE,STUSAB")}
counties = sorted(
    (
        [c["GEOID"], states[c["STATE"]], c["NAME"], c["_box"]]
        for c in query(1, "GEOID,STATE,NAME", shapes=True)
        if c["STATE"] in states
    ),
    key=lambda c: (c[1], c[2]),
)
rows = ",\n".join(json.dumps(c, ensure_ascii=False) for c in counties)
(ROOT / "src/oakbox/counties.json").write_text(
    f'{{"source": "US Census Bureau TIGERweb", "counties": [\n{rows}\n]}}\n', encoding="utf-8"
)
print(len(counties), "counties")

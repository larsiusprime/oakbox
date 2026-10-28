"""Writes src/oakbox/counties.json: every US county (and equivalent), its FIPS code and state, from the Census
Bureau's TIGERweb, for the Census enrichment's county picker.

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


def query(layer: int, fields: str) -> list[dict]:
    out: list[dict] = []
    while True:
        q = {"where": "1=1", "outFields": fields, "returnGeometry": "false", "f": "json"}
        q |= {"resultOffset": str(len(out)), "resultRecordCount": str(PAGE), "orderByFields": "GEOID"}
        with urllib.request.urlopen(URL.format(layer=layer) + urllib.parse.urlencode(q), timeout=60) as r:  # noqa: S310
            rows = [f["attributes"] for f in json.loads(r.read())["features"]]
        out += rows
        if len(rows) < PAGE:
            return out


# Layer 0 is states, 1 counties.
states = {s["STATE"]: s["STUSAB"] for s in query(0, "STATE,STUSAB")}
counties = sorted(
    ([c["GEOID"], states[c["STATE"]], c["NAME"]] for c in query(1, "GEOID,STATE,NAME") if c["STATE"] in states),
    key=lambda c: (c[1], c[2]),
)
rows = ",\n".join(json.dumps(c, ensure_ascii=False) for c in counties)
(ROOT / "src/oakbox/counties.json").write_text(f'{{"source": "US Census Bureau TIGERweb", "counties": [\n{rows}\n]}}\n')
print(len(counties), "counties")

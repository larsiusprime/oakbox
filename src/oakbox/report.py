"""Step 7, Report (SPEC §4.1-4.3): the model values out of OAK box. **Export**: every parcel's model value beside the
roll's, why a parcel has none, and its sale and ratio where it sold, as CSV, GeoPackage, Excel, Shapefile or
(Geo)Parquet. **Report**: one printable HTML page (print it, or save it as PDF from the browser): a first page a board
member can read, the values judged on the sets of sales the user picks (out of fold, held out, as valued: all three to
start) with the roll's beside them, a ratio map, the median ratio across prices, what every parcel got, and how the
values were made. Both read Finalize's output (final.py); nothing is run."""

from __future__ import annotations

import datetime as dt
import html
import math
import re
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from oakbox import final, ratio
from oakbox.datafiles import BaseModel
from oakbox.errors import NotReady

Format = Literal["csv", "gpkg", "xlsx", "shp", "parquet"]
FORMATS: dict[Format, tuple[str, str]] = {
    "csv": (".csv", "CSV (any spreadsheet)"),
    "gpkg": (".gpkg", "GeoPackage (GIS, with each parcel's shape)"),
    "xlsx": (".xlsx", "Excel"),
    "shp": (".shp", "Shapefile (older GIS)"),
    "parquet": (".parquet", "GeoParquet (with each parcel's shape)"),
}
GEO: set[Format] = {"gpkg", "shp", "parquet"}
EXCEL_ROWS = 1_048_575  # an Excel sheet's rows, less its heading
SHAPEFILE_LIMIT = 2 * 1024**3


def out_dir(project_dir: Path) -> Path:
    return project_dir / "out" / "oakbox" / "report"


def _receipt(project_dir: Path) -> final.FinalReceipt:
    r, _ = final.STEP.ran(project_dir)
    if r is None:
        raise NotReady("Finalize first: there are no model values yet.")
    return r


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return s or "oakbox"


# ---------- Export ----------


def table(project, project_dir: Path):
    """Every parcel: its key, model group, model value, the roll's, the change, value per finished area, why it has no
    value, and its latest sale in the window with the ratio of the value as made to it."""
    import numpy as np
    import pandas as pd

    receipt = _receipt(project_dir)
    v = pd.read_parquet(final.out_dir(project_dir) / "values.parquet")
    names = {g.id: g.name for g in project.groups}
    why = {g.id: g.unvalued for g in receipt.groups}
    roll = next((c for c in v.columns if c.endswith("_market_value")), None)
    unit = "sqft" if project.units == "imperial" else "sqm"
    out = pd.DataFrame({"key": v["key"].astype(str), "model_group": v["model_group"].map(lambda g: names.get(g, g))})
    value = np.asarray(v[final.VALUE], dtype=float)
    out["model_value"] = np.round(value, 0)
    if roll:
        r = np.asarray(v[roll], dtype=float)
        out["roll_value"] = r
        with np.errstate(divide="ignore", invalid="ignore"):
            out["change_pct"] = np.round(np.where(r > 0, 100 * (value / r - 1), np.nan), 1)
    if "area" in v:
        a = np.asarray(v["area"], dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"value_per_{unit}"] = np.round(np.where(a > 0, value / a, np.nan), 2)
    below = v["below_zero"].astype(bool) if "below_zero" in v else pd.Series(False, index=v.index)
    out["no_value_why"] = [
        "valued below zero: left blank" if b else (why.get(g) or "") if not np.isfinite(x) else ""
        for g, x, b in zip(v["model_group"], value, below, strict=True)
    ]
    # The latest sale in the window each parcel had, against the value as made.
    sales = final.out_dir(project_dir) / "studies" / f"{final.VALUE}.sales.parquet"
    if sales.is_file():
        s = pd.read_parquet(sales)
        if "sale_date" in s and "key" in s:
            s = s.sort_values("sale_date").drop_duplicates("key", keep="last")
            keys = s["key"].astype(str).tolist()
            price = dict(zip(keys, s["sale_price"].astype(float), strict=True))
            day = dict(zip(keys, pd.to_datetime(s["sale_date"]).dt.date.astype(str), strict=True))
            q = dict(zip(keys, s["ratio"].astype(float), strict=True))
            out["sale_price"] = [price.get(k) for k in out["key"]]
            out["sale_date"] = [day.get(k) for k in out["key"]]
            out["ratio"] = [None if k not in q else round(q[k], 3) for k in out["key"]]
    for c in ("latitude", "longitude"):
        if c in v:
            out[c] = v[c].to_numpy()
    return cast(pd.DataFrame, out)


class ExportResult(BaseModel):
    path: str = Field(description="Where it was written, from the project's folder.")
    rows: int
    bytes: int
    notes: list[str] = Field(default_factory=list)


def _shapes(project_dir: Path, keys):
    """Each parcel's shape, by key, in the order given; points from latitude and longitude where there's none."""
    import geopandas as gpd
    import pandas as pd

    from oakbox.bring_in import out_dir as bring_in_out

    src = bring_in_out(project_dir) / "sup.pickle"
    if not src.is_file():
        return None
    sup = pd.read_pickle(src)
    u = sup.universe if hasattr(sup, "universe") else sup["universe"]
    if "geometry" not in u:
        return None
    g = gpd.GeoDataFrame(u[["key", "geometry"]], geometry="geometry")
    g = g.set_index(g["key"].astype(str))
    return g.geometry.reindex(pd.Index(keys).astype(str)), g.crs


def export(project, project_dir: Path, fmt: Format) -> ExportResult:
    import geopandas as gpd
    import pandas as pd

    t = table(project, project_dir)
    notes: list[str] = []
    base = out_dir(project_dir) / "export"
    base.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(project.name)}_{project.tax_year}_model_values"
    path = base / (stem + FORMATS[fmt][0])
    if fmt == "csv":
        t.to_csv(path, index=False)
    elif fmt == "xlsx":
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            for i in range(0, max(len(t), 1), EXCEL_ROWS):
                sheet = "Model values" if i == 0 else f"Model values {i // EXCEL_ROWS + 1}"
                t.iloc[i : i + EXCEL_ROWS].to_excel(w, sheet_name=sheet, index=False)
        if len(t) > EXCEL_ROWS:
            notes.append(f"More rows than an Excel sheet holds: split across {math.ceil(len(t) / EXCEL_ROWS)} sheets.")
    else:
        shapes = _shapes(project_dir, t["key"])
        if shapes is not None:
            geometry, crs = shapes
            g = gpd.GeoDataFrame(t, geometry=geometry.to_numpy(), crs=crs)
            missing = g.geometry.isna()
            if missing.any() and "latitude" in t:
                pts = gpd.points_from_xy(t["longitude"], t["latitude"], crs="EPSG:4326")
                if crs is not None:
                    pts = gpd.GeoSeries(pts, crs="EPSG:4326").to_crs(crs).to_numpy()
                g.loc[missing, "geometry"] = pts[missing.to_numpy()]
        else:
            g = gpd.GeoDataFrame(t, geometry=gpd.points_from_xy(t["longitude"], t["latitude"]), crs="EPSG:4326")
            notes.append("No parcel shapes: each parcel is a point at its latitude and longitude.")
        if fmt == "gpkg":
            g.to_file(path, driver="GPKG", layer="model_values")
        elif fmt == "parquet":
            g.to_parquet(path, index=False)
        else:
            # A shapefile's field names are 10 characters at most: shortened, with a key to the full names.
            short: dict[str, str] = {}
            for c in t.columns:
                n = c[:10]
                k = 1
                while n in short.values():
                    n = f"{c[: 10 - len(str(k))]}{k}"
                    k += 1
                short[c] = n
            g.rename(columns=short).to_file(path, driver="ESRI Shapefile")
            key = base / f"{stem}_fields.csv"
            pd.DataFrame({"field": list(short.values()), "full_name": list(short)}).to_csv(key, index=False)
            notes.append(f"Shapefile field names are cut to 10 characters: {key.name} gives the full names.")
            size = sum(p.stat().st_size for p in base.glob(f"{stem}.*"))
            if size > SHAPEFILE_LIMIT:
                notes.append("Over a shapefile's 2 GB: some programs won't open it. GeoPackage has no such limit.")
    return ExportResult(path=str(path.relative_to(project_dir)), rows=len(t), bytes=path.stat().st_size, notes=notes)


# ---------- The report ----------


def _day(at: str) -> str:
    d = dt.date.fromisoformat(at[:10])
    return f"{d:%B} {d.day}, {d.year}"


def _e(x: object) -> str:
    return html.escape(str(x))


def _num(x: float | None, digits: int = 0) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:,.{digits}f}"


def _money(x: float | None, currency: str) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    sign = {"USD": "$", "CAD": "$", "AUD": "$", "NZD": "$", "GBP": "£", "EUR": "€"}.get(currency)
    a = abs(x)
    s = f"{a / 1e9:,.2f}B" if a >= 1e9 else f"{a / 1e6:,.2f}M" if a >= 1e6 else f"{a:,.0f}"
    s = f"{sign}{s}" if sign else f"{s} {currency}"
    return f"−{s}" if x < 0 else s


def _ratio_colour(q: float) -> str:
    """openratiostudy.com's: blue below 1 (deepest at 0.5), white at 1, red above (deepest at 2)."""
    if not math.isfinite(q):
        return "#94a3b8"
    if q <= 1:
        c = round(255 * max(0, min(1, (q - 0.5) / 0.5)))
        return f"rgb({c},{c},255)"
    c = round(255 * (1 - max(0, min(1, q - 1))))
    return f"rgb(255,{c},{c})"


def _mark(ok: bool | None) -> str:
    """A verdict that reads in black and white: ✓ met, ✗ missed, nothing when neither."""
    if ok is None:
        return '<span class="mk"></span>'
    return '<span class="mk ok">✓</span>' if ok else '<span class="mk no">✗</span>'


def _level_word(s: ratio.Study) -> str:
    v = s.verdict
    if v is None or not v.judged or s.median is None:
        return "not judged"
    return "in range" if v.level else "low" if s.median < 1 else "high" if v.level is False else "not proven"


def _vertical(s: ratio.Study) -> tuple[str, bool | None]:
    if s.vei_verdict in ("compliant", "not_significant"):
        return "dearer and cheaper alike", True
    if s.vei_verdict == "regressive":
        return "dearer valued lower", False if s.verdict and s.verdict.judged else None
    if s.vei_verdict == "progressive":
        return "dearer valued higher", False if s.verdict and s.verdict.judged else None
    ok = s.verdict.prb if s.verdict else None
    return ("PRB in range" if ok else "PRB out of range" if ok is False else "not judged"), ok


def _sentence(m: ratio.Study, r: ratio.Study | None, std: ratio.Standard | None) -> str:
    """A model group's line on the first page: what a board member needs, in words, with the figures."""
    if not m.sales or m.median is None:
        return f"<b>{_e(m.name)}</b>: no sales in the window to judge its values by."
    if not (m.verdict and m.verdict.judged):
        return (
            f"<b>{_e(m.name)}</b>: {m.sales:,} sales, too few to judge: values at {_num(m.median, 3)} of sale prices "
            f"at the median (shown, not judged)."
        )
    lo, hi = (std.level_low, std.level_high) if std else (0.90, 1.10)
    target = m.verdict.cod_target or ([std.cod_low, std.cod_high] if std else None)
    cod_t = f"; target {target[0]:g} to {target[1]:g}" if target else ""
    cod_word = "suspiciously even" if m.verdict.cod_low else "uniform" if m.verdict.cod else "too varied"
    vword, _ = _vertical(m)
    vfig = f"VEI {_num(m.vei, 1)}%" if m.vei is not None else f"PRB {_num(m.prb, 3)}"
    line = (
        f"<b>{_e(m.name)}</b>: values sit at {_num(m.median, 3)} of sale prices at the median ({_level_word(m)}; "
        f"target {lo:.2f} to {hi:.2f}), COD {_num(m.cod, 1)} ({cod_word}{cod_t}), {vword} ({vfig}); "
        f"{m.sales:,} sales."
    )
    if r and r.median is not None and r.sales:
        line += f" The roll on the same sales: {_num(r.median, 3)}, COD {_num(r.cod, 1)}."
    return line


def _study_rows(label: str, s: ratio.Study, roll: bool = False) -> str:
    v = s.verdict
    judged = bool(v and v.judged)
    if not s.sales or s.median is None:
        cls = "roll" if roll else ""
        return f'<tr class="{cls}"><td>{_e(label)}</td><td class="n">0</td><td colspan="8">no sales</td></tr>'
    ci = f"{_num(s.low, 3)}–{_num(s.high, 3)}" if s.low is not None and s.high is not None else "—"
    vword, vok = _vertical(s)
    return (
        f'<tr class="{"roll" if roll else ""}"><td>{_e(label)}</td><td class="n">{s.sales:,}</td>'
        f'<td class="n">{_mark(v.level if judged and v else None)} {_num(s.median, 3)}</td><td class="n ci">{ci}</td>'
        f'<td class="n">{_mark((False if v.cod_low else v.cod) if judged and v else None)} {_num(s.cod, 1)}</td>'
        f'<td class="n">{_num(s.prd, 3)}</td><td class="n">{_num(s.prb, 3)}</td>'
        f'<td class="n">{_mark(vok if judged else None)} {_num(s.vei, 1)}{"%" if s.vei is not None else ""}</td>'
        f'<td class="n">{_num(s.median_chd, 1)}</td><td class="w">{_e(vword if judged else "not judged")}</td></tr>'
    )


def _fifths_svg(s: ratio.Study, std: ratio.Standard | None) -> str:
    """The median ratio by fifths of the sales by price: a tilt is vertical inequity."""
    f = s.fifths
    if len(f) < 2:
        return '<p class="quiet">Too few sales to split by price.</p>'
    w, h, pad = 300, 110, 22
    lo_band, hi_band = (std.level_low, std.level_high) if std else (0.90, 1.10)
    # Symmetric about 1, just wide enough for the bars and the target band.
    reach = max(0.15, hi_band - 1 + 0.05, 1 - lo_band + 0.05, *(abs(x.median - 1) + 0.06 for x in f))
    top, bot = 1 + reach, 1 - reach

    def y(q: float) -> float:
        return pad / 2 + (h - pad) * (top - q) / (top - bot)

    bw = (w - pad) / len(f)
    bars = "".join(
        f'<rect x="{pad + i * bw + 4:.1f}" y="{min(y(x.median), y(1)):.1f}" width="{bw - 8:.1f}" '
        f'height="{abs(y(x.median) - y(1)):.1f}" fill="{_ratio_colour(x.median)}" stroke="#333" stroke-width="0.6"/>'
        f'<text x="{pad + i * bw + bw / 2:.1f}" y="{h - 4}" text-anchor="middle">{i + 1}</text>'
        f'<text x="{pad + i * bw + bw / 2:.1f}" y="{y(x.median) + (-3 if x.median >= 1 else 10):.1f}" '
        f'text-anchor="middle">{x.median:.2f}</text>'
        for i, x in enumerate(f)
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Median ratio by fifths of price">'
        f'<rect x="{pad}" y="{y(hi_band):.1f}" width="{w - pad}" height="{y(lo_band) - y(hi_band):.1f}" fill="#eee"/>'
        f'<line x1="{pad}" x2="{w}" y1="{y(1):.1f}" y2="{y(1):.1f}" stroke="#000" stroke-width="0.8"/>'
        f'<text x="2" y="{y(1) + 3:.1f}">1.00</text>{bars}</svg>'
    )


def _map_svg(project_dir: Path, which: final.SetKey) -> str:
    """Each sale in the set, where it is, coloured by its ratio."""
    pts = final.sale_points(project_dir, which, None)
    if not pts:
        return '<p class="quiet">No sales with a place to map.</p>'
    lat0 = sum(p.lat for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    xs = [p.lon * k for p in pts]
    ys = [p.lat for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0) or 1e-6
    sc = 540 / span
    w = round((x1 - x0) * sc) + 20
    h = round((y1 - y0) * sc) + 20

    def at(x: float, yv: float) -> tuple[float, float]:
        return 10 + (x - x0) * sc, h - 10 - (yv - y0) * sc

    dots = []
    for p, x in zip(pts, xs, strict=True):
        cx, cy = at(x, p.lat)
        fill = "#d0d0d0" if p.trimmed else _ratio_colour(p.ratio)
        dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{2.5 if p.trimmed else 3.4}" fill="{fill}"/>')
    return (
        f'<svg viewBox="0 0 {w} {h}" class="map" role="img" aria-label="Map of the sales by ratio">'
        f'<g stroke="#333" stroke-width="0.5">{"".join(dots)}</g></svg>'
        '<p class="legend"><span style="background:rgb(0,0,255)"></span>0.5 or less '
        '<span style="background:rgb(128,128,255)"></span>0.75 <span style="background:#fff"></span>1.0 '
        '<span style="background:rgb(255,128,128)"></span>1.5 <span style="background:rgb(255,0,0)"></span>2 or more '
        '<span style="background:#d0d0d0"></span>trimmed</p>'
    )


CSS = """
:root { --ink:#111; --quiet:#555; --rule:#bbb; }
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 10.5pt/1.45 "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  color: var(--ink);
  background: #f3f3f0;
}
main { max-width: 8.5in; margin: 0 auto; background: #fff; padding: 0.7in 0.75in; }
h1 { font-size: 20pt; margin: 0 0 0.2rem; letter-spacing: -0.01em; }
h2 {
  font-size: 13pt;
  margin: 1.6rem 0 0.4rem;
  padding-bottom: 0.15rem;
  border-bottom: 1.5px solid var(--ink);
}
h3 { font-size: 11pt; margin: 1rem 0 0.3rem; }
p { margin: 0.35rem 0; }
.sub { color: var(--quiet); margin: 0 0 1rem; }
.brief p { margin: 0.5rem 0; }
.quiet { color: var(--quiet); }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 0.4rem 0 0.6rem; }
th, td {
  padding: 0.18rem 0.35rem;
  border-bottom: 0.5px solid var(--rule);
  text-align: left;
  vertical-align: top;
}
th { font-weight: 600; border-bottom: 1px solid var(--ink); }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.ci { color: var(--quiet); }
tr.roll td { color: var(--quiet); font-style: italic; }
tr.grp td { font-weight: 600; border-bottom: none; padding-top: 0.45rem; }
.mk { display: inline-block; width: 1em; font-style: normal; }
.mk.ok { color: #1a7f37; } .mk.no { color: #b42318; font-weight: 700; }
.charts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.6rem 1.2rem; }
.chart { width: 100%; height: auto; font-size: 9px; fill: var(--ink); }
.map { display: block; max-width: 100%; max-height: 6.5in; margin: 0 auto; border: 0.5px solid var(--rule); }
.legend { font-size: 8.5pt; color: var(--quiet); }
.legend span {
  display: inline-block;
  width: 0.8em;
  height: 0.8em;
  border: 0.5px solid #333;
  border-radius: 50%;
  margin: 0 0.2em 0 0.6em;
  vertical-align: -0.1em;
}
dl {
  display: grid;
  grid-template-columns: 11rem 1fr;
  gap: 0.15rem 0.8rem;
  margin: 0.3rem 0;
  font-size: 9.5pt;
}
dt { font-weight: 600; } dd { margin: 0; }
.page { break-before: page; }
.keep { break-inside: avoid; }
footer {
  margin-top: 1.5rem;
  padding-top: 0.4rem;
  border-top: 0.5px solid var(--rule);
  color: var(--quiet);
  font-size: 8.5pt;
}
@page { size: letter; margin: 0.6in 0.65in; }
@media print { body { background: #fff; } main { padding: 0; max-width: none; } h2 { break-after: avoid; } }
"""

STATS = [
    (
        "Median ratio",
        (
            "The middle of the values ÷ sale prices: are values near what parcels sell for? 1.00 is at "
            "the price; the range beside it is its 90% confidence interval."
        ),
    ),
    (
        "COD",
        (
            "Coefficient of dispersion: how far ratios typically sit from the median, as a percent of "
            "it. Lower is more uniform; the target depends on the kind of property."
        ),
    ),
    (
        "PRD",
        (
            "Price-related differential: the mean ratio over the sale-weighted mean. Above 1, dearer "
            "parcels are valued relatively lower."
        ),
    ),
    (
        "PRB",
        "Price-related bias: how the ratio moves as price doubles (a regression). Near 0 is fair.",
    ),
    (
        "VEI",
        (
            "Vertical equity indicator (the IAAO's): the gap in median ratio between the dearest and "
            "cheapest parcels, judged only when significant."
        ),
    ),
    (
        "CHD",
        (
            "Within each group of similar parcels, sold or not, how far their values sit from the "
            "group's median, percent: horizontal equity. Not judged: the IAAO sets no target."
        ),
    ),
]


def build(project, project_dir: Path) -> str:
    """The report, as one HTML page that prints well."""
    receipt = _receipt(project_dir)
    state = project.report
    stds = {s.id: s for s in ratio.standards(project)}
    std_of = {g: stds.get(sid) if isinstance(sid, str) else None for g, sid in ratio.classes(project).items()}
    by_set = {s.key: s for s in receipt.sets}
    chosen = [by_set[k] for k in state.sets if k in by_set and by_set[k].model]
    title = state.title or f"{project.name}: model values, tax year {project.tax_year}"
    place = ", ".join(x for x in (project.jurisdiction, project.region) if x)
    first = chosen[0] if chosen else None
    out: list[str] = []
    out.append(f"<h1>{_e(title)}</h1>")
    out.append(
        f'<p class="sub">{_e(place) + " · " if place else ""}Valuation date '
        f"{_e(project.valuation_date or '—')} · Sales from {_e(receipt.start)} to {_e(receipt.end)} · "
        f"Made {_e(_day(receipt.ran_at))}</p>"
    )
    # In brief.
    valued = sum(g.valued for g in receipt.groups)
    parcels = sum(g.parcels for g in receipt.groups)
    out.append('<h2>In brief</h2><div class="brief">')
    out.append(
        f"<p>{valued:,} of {parcels:,} parcels have a model value. "
        + (
            f"Judged on <b>{_e(final_set_name(first.key))}</b> sales: {_e(SET_WHY[first.key])}</p>"
            if first
            else "No sales to judge them by.</p>"
        )
    )
    if first and first.model:
        rolls = {g.id: g for g in first.roll.groups} if first.roll else {}
        for g in first.model.groups:
            out.append(f"<p>{_sentence(g, rolls.get(g.id), std_of.get(g.id))}</p>")
    left = [g for g in receipt.groups if g.unvalued]
    if left:
        out.append(
            "<p>No model value: "
            + "; ".join(
                f"{_e(g.name)} ({g.parcels:,} {'parcel' if g.parcels == 1 else 'parcels'}: {_e(g.unvalued)})"
                for g in left
            )
            + ".</p>"
        )
    out.append("</div>")
    empty = [k for k in state.sets if k in by_set and not by_set[k].model]
    if empty:
        out.append(
            '<p class="quiet">'
            + " ".join(f"No {final_set_name(k)} sales in the window to judge on ({SET_WHY[k]})" for k in empty)
            + "</p>"
        )
    # The values judged, per set.
    for s in chosen:
        assert s.model is not None
        out.append(f'<section class="keep"><h2>Judged on {_e(final_set_name(s.key))} sales</h2>')
        why = SET_WHY[s.key]
        out.append(f'<p class="quiet">{_e(why[0].upper() + why[1:])} {s.sales:,} sales.</p>')
        out.append(
            '<table><thead><tr><th>Model group</th><th class="n">Sales</th><th class="n">Median ratio</th>'
            '<th class="n">90% interval</th><th class="n">COD</th><th class="n">PRD</th><th class="n">PRB</th>'
            '<th class="n">VEI</th><th class="n">CHD</th><th>Vertical equity</th></tr></thead><tbody>'
        )
        rolls = {g.id: g for g in s.roll.groups} if s.roll else {}
        for g in [*s.model.groups, s.model.overall]:
            out.append(f'<tr class="grp"><td colspan="10">{_e(g.name)}</td></tr>')
            out.append(_study_rows("Model values", g))
            r = rolls.get(g.id) if g.id else (s.roll.overall if s.roll else None)
            if r is not None:
                out.append(_study_rows(receipt.roll or "Roll", r, roll=True))
        out.append("</tbody></table>")
        out.append(
            '<p class="quiet">✓ meets the standard · ✗ misses it · no mark: not judged (too few sales, or not proven '
            "either way). The roll's on the same sales, in italics.</p></section>"
        )
    if first and first.model:
        out.append(f'<section class="page"><h2>Across prices ({_e(final_set_name(first.key))})</h2>')
        out.append(
            '<p class="quiet">The median ratio in each fifth of the sales, cheapest (1) to dearest (5); the grey band '
            'is the target range. A slope is vertical inequity.</p><div class="charts">'
        )
        for g in first.model.groups:
            if g.sales:
                out.append(f'<div class="keep"><h3>{_e(g.name)}</h3>{_fifths_svg(g, std_of.get(g.id))}</div>')
        out.append("</div></section>")
        out.append(f'<section class="keep"><h2>On the map ({_e(final_set_name(first.key))})</h2>')
        out.append(
            '<p class="quiet">Each sale where it is, coloured by its ratio. Clusters of one colour show where values '
            "are off; scattered colour is noise or invalid sales.</p>"
        )
        out.append(_map_svg(project_dir, first.key) + "</section>")
    # What every parcel got.
    out.append(
        '<section class="page"><h2>What every parcel got</h2><table><thead><tr><th>Model group</th>'
        '<th class="n">Parcels</th><th class="n">Valued</th><th class="n">Change from<br>the roll</th>'
        '<th class="n">Up<br>over 20%</th><th class="n">Down<br>over 20%</th><th class="n">Total value</th>'
        '<th class="n">The roll\'s total</th></tr></thead><tbody>'
    )
    cur = project.currency
    for g in receipt.groups:
        if g.unvalued:
            out.append(
                f'<tr><td>{_e(g.name)}</td><td class="n">{g.parcels:,}</td><td colspan="6" class="quiet">'
                f"{_e(g.unvalued)}</td></tr>"
            )
            continue
        ch = f"{100 * g.median_change:+.1f}%" if g.median_change is not None else "—"
        out.append(
            f"<tr><td>{_e(g.name)}{f' ({g.blanked:,} below zero, left blank)' if g.blanked else ''}</td>"
            f'<td class="n">{g.parcels:,}</td><td class="n">{g.valued:,}</td><td class="n">{ch}</td>'
            f'<td class="n">{g.up:,}</td><td class="n">{g.down:,}</td><td class="n">{_money(g.total, cur)}</td>'
            f'<td class="n">{_money(g.roll_total, cur)}</td></tr>'
        )
    out.append("</tbody></table></section>")
    out.append(_method(project, project_dir, receipt, stds))
    out.append(
        f"<footer>Made with OAK box and OpenAVMKit {_e(receipt.engine)}. Values as finalized "
        f"{_e(receipt.ran_at.replace('T', ' '))}.</footer>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body><main>{''.join(out)}</main></body></html>"
    )


SET_WHY: dict[str, str] = {
    "oof": "each sale valued by a model that never saw it (cross-validation), so every sale is judged honestly.",
    "held": "the sales the final models never trained on, valued by the final models.",
    "valued": "every sale, valued by the final models, which trained on most of them: the values as they ship, "
    "but flattering.",
}


def final_set_name(key: str) -> str:
    return {"oof": "out-of-fold", "held": "held-out", "valued": "as-valued"}.get(key, key)


def _method(project, project_dir: Path, receipt: final.FinalReceipt, stds: dict[str, ratio.Standard]) -> str:
    from oakbox import assemble, clean, model, varlists

    out = ['<section class="page"><h2>How the values were made</h2><dl>']
    files = ", ".join(f.name for f in project.files) or "—"
    out.append(f"<dt>Data</dt><dd>{_e(files)}</dd>")
    c, _ = clean.STEP.ran(project_dir)
    if c:
        out.append(
            f"<dt>Sales</dt><dd>{c.start:,} sales read; {c.used:,} kept to model and judge with after Check sales "
            f"({c.set_aside:,} set aside by the sales checks).</dd>"
        )
    ta = getattr(project.clean, "time_adjust", True)
    out.append(
        "<dt>Time adjustment</dt><dd>"
        + ("Sale prices adjusted to the valuation date, per model group." if ta else "None: prices as sold.")
        + "</dd>"
    )
    price = "as sold" if receipt.price == "sold" else "time-adjusted"
    out.append(
        f"<dt>Ratio study</dt><dd>Sales from {_e(receipt.start)} to {_e(receipt.end)}, prices {price}"
        + ("; outlying ratios (1.5 × the interquartile range, at most 10% of a group) left out" if receipt.trim else "")
        + ".</dd>"
    )
    used = sorted({s for g in project.groups for s in [ratio.classes(project).get(g.id)] if isinstance(s, str)})
    std_text = "; ".join(
        f"{_e(stds[s].name)}: median {stds[s].level_low:.2f}–{stds[s].level_high:.2f}, COD {stds[s].cod_low:g}–"
        f"{stds[s].cod_high:g}, PRB within ±{stds[s].prb_good:g}"
        for s in used
        if s in stds
    )
    out.append(f"<dt>Standards</dt><dd>{std_text or 'IAAO'}</dd>")
    out.append(
        "</dl><h3>Models</h3><table><thead><tr><th>Model group</th><th>Models (combined by their median)</th>"
        "</tr></thead><tbody>"
    )
    lists = {x.id: x for x in varlists.lists(project, project_dir)}
    modeled = assemble.modeled(project, project_dir)
    left_out = {g.id for g in receipt.groups if g.unvalued}
    for g in project.groups:
        if g.id not in modeled or g.id in left_out:
            continue
        entries = model.group_models(project, project_dir, g.id, list(lists.values()))
        parts = []
        for e in entries:
            lst = lists.get(e.list_id or "")
            engine = model.ENGINES.get(e.engine, (e.engine,))[0]
            said = [engine] if engine != e.name else []
            if lst:
                said.append(f"{lst.name}: {len(lst.variables)} variables")
            parts.append(_e(e.name) + (f" ({_e(', '.join(said))})" if said else ""))
        out.append(f"<tr><td>{_e(g.name)}</td><td>{'; '.join(parts) or '—'}</td></tr>")
    out.append(
        "</tbody></table><h3>Variables</h3><table><thead><tr><th>List</th><th>Variables</th></tr></thead><tbody>"
    )
    for lst in lists.values():
        out.append(f"<tr><td>{_e(lst.name)}</td><td>{_e(', '.join(lst.variables))}</td></tr>")
    out.append("</tbody></table><h3>The statistics</h3><dl>")
    for name, what in STATS:
        out.append(f"<dt>{_e(name)}</dt><dd>{_e(what)}</dd>")
    out.append("</dl></section>")
    return "".join(out)


def write(project, project_dir: Path) -> Path:
    path = out_dir(project_dir) / f"{_slug(project.name)}_{project.tax_year}_report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(project, project_dir), encoding="utf-8")
    return path


class FormatChoice(BaseModel):
    id: Format
    label: str


class ReportView(BaseModel):
    ready: bool = Field(description="Finalize has run: there are values to export and report.")
    accepted: bool = Field(description="Model values' Looks right was pressed on the values as they are.")
    sets: list[final.SetKey]
    available: list[final.SetKey] = Field(description="The sets with sales to judge on.")
    title: str
    default_title: str
    formats: list[FormatChoice]
    ran_at: str | None


def view(project, project_dir: Path) -> ReportView:
    r, _ = final.STEP.ran(project_dir)
    default = f"{project.name}: model values, tax year {project.tax_year}"
    return ReportView(
        ready=r is not None,
        accepted=final.STEP.accepted(project, project_dir) if r else False,
        sets=project.report.sets,
        available=[s.key for s in r.sets if s.model] if r else [],
        title=project.report.title or default,
        default_title=default,
        formats=[FormatChoice(id=k, label=v[1]) for k, v in FORMATS.items()],
        ran_at=r.ran_at if r else None,
    )


class ReportPatch(BaseModel):
    sets: list[final.SetKey] | None = None
    title: str | None = Field(default=None, description='"" back to the default.')


def change(project, body: ReportPatch) -> None:
    if body.sets is not None:
        if not body.sets:
            raise ValueError("Choose at least one set of sales to judge the values on.")
        project.report.sets = [k for k in final.SETS if k in body.sets]
    if body.title is not None:
        project.report.title = body.title.strip() or None

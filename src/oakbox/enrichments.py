"""Enrichments (F3e): public data about each parcel, which OpenAVMKit downloads while Bring in data runs.

Distances to features from OpenStreetMap, building footprints from Overture Maps, census figures from the US
Census Bureau's ACS and elevation from USGS 3DEP: data.process.enrich's distances (osm: true), overture, census
and dem. Each sends only the rectangle around the parcels (census: the county's code) to a public service. A
failed download never stops the run: Bring in data skips that enrichment and its receipt says why.

The Census API key is the user's, kept in OAK box's own settings on this computer (never in the project folder),
and handed to OpenAVMKit as CENSUS_API_KEY when it runs.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
import time
from functools import cache, lru_cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from oakbox.datafiles import BaseModel, DistanceUnit

if TYPE_CHECKING:
    from oakbox.projects import Project

# ---------- What the user chooses (stored on the project) ----------


class OsmFeature(BaseModel):
    on: bool
    max_distance: float = Field(gt=0, description="Past it, no distance (in the project's long distance unit).")
    top_n: int = Field(default=0, ge=0, le=10, description="Also measured to each of the N largest, by name.")


DistanceKind = Literal["dist_to", "within", "proximity_to"]


class Enrichments(BaseModel):
    distances: bool = True
    features: dict[str, OsmFeature] = Field(default_factory=dict, description="OpenStreetMap feature -> its options.")
    kinds: list[DistanceKind] = Field(
        default_factory=lambda: ["dist_to", "within", "proximity_to"],
        description="Which of the three columns each feature gives (and each of its largest).",
    )
    off: list[str] = Field(
        default_factory=list,
        description="Fields not wanted from footprints, census and elevation (OpenAVMKit's names): dropped as the "
        "run ends; an enrichment with every field off isn't downloaded.",
    )
    footprints: bool = True
    census: bool = False
    census_year: int = 2022
    fips: str | None = Field(default=None, description="The county's five-digit FIPS code.")
    elevation: bool = True
    resolution_m: Literal[10, 30, 60] = 10


class FeatureSpec(BaseModel):
    key: str = Field(description="OpenAVMKit's distances entry (columns are dist_to_osm_<key>).")
    label: str
    what: str
    named: bool = Field(description="Its features have names, so the largest can be measured to one by one.")


# OpenAVMKit's built-in OpenStreetMap features, and one of tags (major roads). Defaults in miles, then km.
FEATURES: list[tuple[FeatureSpec, bool, float, float, int]] = [
    (FeatureSpec(key="water_bodies", label="Water bodies", what="lakes, ponds, rivers", named=True), True, 2, 3, 3),
    (FeatureSpec(key="parks", label="Parks", what="parks, gardens, playgrounds", named=True), True, 1, 1.5, 3),
    (FeatureSpec(key="educational", label="Colleges & universities", what="", named=True), True, 2, 3, 0),
    (FeatureSpec(key="golf_courses", label="Golf courses", what="", named=True), True, 2, 3, 0),
    (FeatureSpec(key="major_roads", label="Major roads", what="motorways, trunk roads", named=False), False, 0.5, 1, 0),
    (FeatureSpec(key="transportation", label="Railways", what="rail, subway, tram", named=False), False, 0.5, 1, 0),
    (FeatureSpec(key="airport", label="Airports", what="", named=True), False, 5, 8, 0),
    (FeatureSpec(key="coastline", label="Coastline", what="", named=False), False, 5, 8, 0),
]
SPECS = {s.key: s for s, *_ in FEATURES}
OSM_TAGS = {"major_roads": {"highway": ["motorway", "trunk"]}}
CENSUS_YEARS = list(range(2018, 2025))
CENSUS_FIELDS = ["median_income", "total_population", "median_g_rent", "median_c_rent"]
KINDS: list[DistanceKind] = ["dist_to", "within", "proximity_to"]


def fields_of(key: str, units: str) -> list[str]:
    """The fields an enrichment adds, as OpenAVMKit names them (distances: per feature, see kinds)."""
    area, length = ("sqft", "ft") if units == "imperial" else ("sqm", "m")
    return {
        "footprints": [f"bldg_area_footprint_{area}", f"bldg_height_{length}"],
        "census": [*CENSUS_FIELDS, "census_tract", "census_block_group"],
        "elevation": [f"elevation_mean_{length}", f"elevation_stdev_{length}", "slope_mean_deg"],
    }.get(key, [])


# What each field is, for the step's field choices.
WHAT = {
    "bldg_area_footprint": "The ground area the parcel's buildings cover",
    "bldg_height": "The tallest building's height, where Overture has it",
    "median_income": "Median household income in the block group (ACS B19013)",
    "total_population": "People living in the block group (ACS B01003)",
    "median_g_rent": "Median gross rent: rent plus utilities (ACS B25064)",
    "median_c_rent": "Median contract rent: the rent alone (ACS B25058)",
    "census_tract": "The census tract: a location, like a neighborhood",
    "census_block_group": "The block group: a smaller location within a tract",
    "elevation_mean": "The parcel's average elevation",
    "elevation_stdev": "How much the elevation varies within the parcel (bumpiness)",
    "slope_mean_deg": "The parcel's average slope, in degrees",
    "dist_to": "Distance to the nearest one; blank past the maximum distance",
    "within": "Whether the parcel is inside one (yes/no)",
    "proximity_to": "Closeness: the maximum distance minus the distance; 0 past it",
}


def what(field: str) -> str:
    return next((v for k, v in WHAT.items() if field.startswith(k)), "")


def long_unit(units: str) -> DistanceUnit:
    return "mile" if units == "imperial" else "km"


def defaults(units: str) -> Enrichments:
    """What the step starts with: distances, footprints and elevation on; census off (it needs a key)."""
    metric = units != "imperial"
    feats = {s.key: OsmFeature(on=on, max_distance=km if metric else mi, top_n=top) for s, on, mi, km, top in FEATURES}
    return Enrichments(features=feats)


def osm_names(e: Enrichments | None) -> set[str]:
    """The distances entries OpenStreetMap features take, so a map layer can't take the same name."""
    if e is None or not e.distances:
        return set()
    return {k for k, f in e.features.items() if f.on}


# ---------- OpenAVMKit's settings ----------


def settings(e: Enrichments | None, units: str, taken: set[str]) -> tuple[dict, dict]:
    """(data.process.enrich entries, OpenStreetMap distances entries). taken: distances entries map layers use."""
    if e is None:
        return {}, {}
    out: dict = {}
    imperial = units == "imperial"
    # An enrichment whose every field is unticked is as good as off: nothing downloaded for nothing.
    wanted = {k: [f for f in fields_of(k, units) if f not in e.off] for k in ("footprints", "census", "elevation")}
    drop = [f for k, fs in wanted.items() if fs for f in fields_of(k, units) if f not in fs]
    if e.footprints and wanted["footprints"]:
        area, length = ("sqft", "ft") if imperial else ("sqm", "m")
        out["overture"] = {
            "enabled": True,
            "footprint": {"units": area, "field": f"bldg_area_footprint_{area}"},
            "height": {"units": length, "field": f"bldg_height_{length}"},
        }
    if e.census and e.fips and wanted["census"]:
        # A block group the ACS gives no figure for takes its tract's; a parcel in a gap between block groups,
        # the nearest within 250 m (OpenAVMKit's census tract_fallback and nearest_m).
        out["census"] = {
            "enabled": True,
            "fips": e.fips,
            "year": e.census_year,
            "tract_fallback": True,
            "nearest_m": 250,
        }
    if e.elevation and wanted["elevation"]:
        out["dem"] = {"enabled": True, "resolution_m": e.resolution_m}
    dists: dict = {}
    if e.distances and e.kinds:
        for key, f in e.features.items():
            if not f.on or key in taken or key not in SPECS:
                continue
            entry: dict = {"osm": True, "max_distance": f.max_distance, "unit": long_unit(units)}
            if key in OSM_TAGS:
                entry["osm_tags"] = OSM_TAGS[key]
            entry |= {"store_top": True, "top_n": f.top_n} if f.top_n and SPECS[key].named else {"store_top": False}
            dists[key] = entry
            # The columns not wanted, the largest features' too (named as they're found: a pattern).
            drop += [c for k in KINDS if k not in e.kinds for c in (f"{k}_osm_{key}", f"{k}_osm_{key}_*")]
    if drop:
        out["drop_fields"] = {"universe": drop, "sales": drop}
    return out, dists


# ---------- The step ----------


class County(BaseModel):
    fips: str
    state: str
    name: str
    box: tuple[float, float, float, float] | None = Field(
        default=None, exclude=True, description="The rectangle around it: west, south, east, north (degrees)."
    )


@cache
def counties() -> list[County]:
    raw = json.loads(resources.files("oakbox").joinpath("counties.json").read_text(encoding="utf-8"))
    return [County(fips=f, state=s, name=n, box=tuple(b) if b else None) for f, s, n, b in raw["counties"]]


def county_at(a: Area | None) -> County | None:
    """The county the parcels are in: of those whose rectangle holds the parcels' middle, the one whose middle is
    nearest it (neighbours' rectangles overlap)."""
    if a is None:
        return None
    x, y = (a.west + a.east) / 2, (a.south + a.north) / 2
    holding = [c for c in counties() if c.box and c.box[0] <= x <= c.box[2] and c.box[1] <= y <= c.box[3]]

    def off(c: County) -> float:
        assert c.box is not None
        return ((c.box[0] + c.box[2]) / 2 - x) ** 2 + ((c.box[1] + c.box[3]) / 2 - y) ** 2

    return min(holding, key=off, default=None)


def county_check(fips: str | None, a: Area | None) -> str | None:
    """Census for a county the parcels aren't in gives them no figures: say so, and which county they're in."""
    chosen = next((c for c in counties() if c.fips == fips), None)
    if chosen is None or chosen.box is None or a is None:
        return None
    x, y = (a.west + a.east) / 2, (a.south + a.north) / 2
    w, s, e, n = chosen.box
    if w <= x <= e and s <= y <= n:
        return None
    here = county_at(a)
    there = f": they look to be in {here.name}, {here.state} ({here.fips})" if here else ""
    return f"Census: the parcels aren't in {chosen.name}, {chosen.state}{there}"


def guess_county(state: str, jurisdiction: str) -> str | None:
    """The county the project's place names: "Guilford County" or "Guilford" in North Carolina."""
    j = jurisdiction.lower().replace("county", "").replace("parish", "").strip()
    if not j:
        return None
    mine = [c for c in counties() if c.state == state.upper()]
    for c in mine:
        if c.name.lower().split(" county")[0].split(" parish")[0].strip() == j:
            return c.fips
    return None


class Area(BaseModel):
    west: float
    south: float
    east: float
    north: float
    km2: float = Field(description="The rectangle around the parcels.")


@lru_cache(maxsize=8)
def _bounds(path: str, mtime: float, size: int, layer: str | None) -> tuple[float, float, float, float] | None:
    import geopandas as gpd

    p = Path(path)
    gdf = gpd.read_parquet(p) if p.suffix.lower() in (".parquet", ".geoparquet") else gpd.read_file(p, layer=layer)
    gdf = gdf[gdf.geometry.notna()]
    if gdf.crs is None or len(gdf) == 0:
        return None
    w, s, e, n = gdf.to_crs(4326).total_bounds
    return float(w), float(s), float(e), float(n)


def area(project: Project, in_dir: Path) -> Area | None:
    base = project.base_file()
    if base is None or not (in_dir / base.filename).is_file():
        return None
    st = (in_dir / base.filename).stat()
    try:
        b = _bounds(str(in_dir / base.filename), st.st_mtime, st.st_size, base.layer)
    except Exception:  # noqa: BLE001 - an unreadable file is the Parcel universe step's to say
        return None
    if b is None:
        return None
    w, s, e, n = b
    km2 = (e - w) * 111.32 * math.cos(math.radians((s + n) / 2)) * (n - s) * 110.57
    return Area(west=w, south=s, east=e, north=n, km2=round(km2, 1))


def suggested_resolution(km2: float | None) -> Literal[10, 30, 60]:
    """Elevation detail for an area this size: 10 m tiles for a city, 30 m for a county, 60 m for more."""
    if km2 is None or km2 <= 600:
        return 10
    return 30 if km2 <= 8_000 else 60


class AddField(BaseModel):
    key: str = Field(description="What ticking it changes: the field (in off), or a distance kind (in kinds).")
    name: str = Field(description="The field as it's named, distances with the feature as <feature>.")
    what: str
    on: bool


class Adds(BaseModel):
    enrichment: str
    fields: list[AddField]


class EnrichView(BaseModel):
    settings: Enrichments
    features: list[FeatureSpec]
    unit: DistanceUnit
    area: Area | None
    resolution: Literal[10, 30, 60] = Field(description="The elevation detail suggested for the area.")
    counties: list[County] = Field(description="The project's state's counties (every county outside the US).")
    county_guess: str | None = Field(description="The county the parcels are in (or else the project's place names).")
    county_off: str | None = Field(default=None, description="Census's county doesn't hold the parcels: why.")
    years: list[int]
    key_saved: bool = Field(description="A Census API key is saved on this computer.")
    key_end: str | None = Field(description="Its last four characters, to recognise it.")
    taken: list[str] = Field(description="Features a map layer already uses the name of: not measured from OSM.")
    adds: list[Adds]


def adds(e: Enrichments, units: str) -> list[Adds]:
    """Each enrichment's fields, ticked or not."""
    out = [
        Adds(
            enrichment="distances",
            fields=[AddField(key=k, name=f"{k}_osm_<feature>", what=WHAT[k], on=k in e.kinds) for k in KINDS],
        )
    ]
    for key in ("footprints", "census", "elevation"):
        fs = [AddField(key=f, name=f, what=what(f), on=f not in e.off) for f in fields_of(key, units)]
        out.append(Adds(enrichment=key, fields=fs))
    return out


def view(project: Project, in_dir: Path, taken: set[str]) -> EnrichView:
    from oakbox import appsettings

    e = project.enrich or defaults(project.units)
    a = area(project, in_dir)
    key = appsettings.load().census_api_key
    state = project.region.upper() if project.country == "US" else ""
    return EnrichView(
        settings=e,
        features=[s for s, *_ in FEATURES],
        unit=long_unit(project.units),
        area=a,
        resolution=suggested_resolution(a.km2 if a else None),
        counties=[c for c in counties() if c.state == state] if state else counties(),
        county_guess=_guess(project, a) if state else None,
        county_off=county_check(e.fips, a) if e.census else None,
        years=CENSUS_YEARS,
        key_saved=bool(key),
        key_end=key[-4:] if key else None,
        taken=sorted(osm_names(e) & taken),
        adds=adds(e, project.units),
    )


def _guess(project: Project, a: Area | None) -> str | None:
    """The county for census figures: the one the project's place names, if the parcels are in it; else the one
    the parcels are in."""
    named = guess_county(project.region, project.jurisdiction)
    if named and not county_check(named, a):
        return named
    here = county_at(a)
    return here.fips if here else named


def start(project: Project, in_dir: Path) -> None:
    """Visiting the step the first time: the defaults, the county from the project's place, the detail for its
    size."""
    if project.enrich is not None:
        return
    e = defaults(project.units)
    a = area(project, in_dir)
    if project.country == "US":
        e.fips = _guess(project, a)
    e.resolution_m = suggested_resolution(a.km2 if a else None)
    project.enrich = e


def set_enrichments(project: Project, e: Enrichments) -> None:
    for k in e.features:
        if k not in SPECS:
            raise ValueError(f"No such feature: {k}")
    if e.fips is not None and not any(c.fips == e.fips for c in counties()):
        raise ValueError(f"No county has the code {e.fips}.")
    known = {f for k in ("footprints", "census", "elevation") for f in fields_of(k, project.units)}
    if unknown := sorted(set(e.off) - known):
        raise ValueError(f"No such field: {', '.join(unknown)}")
    project.enrich = e


def left(project: Project) -> list[str]:
    """What's still to do on the step (none of it stops a run)."""
    from oakbox import appsettings

    e = project.enrich
    out = []
    names = {"footprints": "Building footprints", "census": "Census", "elevation": "Elevation"}
    for key, name in names.items():
        if e is not None and getattr(e, key) and all(f in e.off for f in fields_of(key, project.units)):
            out.append(f"{name}: every field is unticked, so nothing is downloaded")
    if e is not None and e.distances and not e.kinds:
        out.append("Distances: every field is unticked, so nothing is downloaded")
    if e is not None and e.census:
        from oakbox import projects

        if off := county_check(e.fips, area(project, projects.inputs_dir(project.id))):
            out.append(off)
        if not e.fips:
            out.append("Census: pick the county")
        if not appsettings.load().census_api_key:
            out.append("Census: add your API key")
    return out


# ---------- While Bring in data runs ----------


class FeatureResult(BaseModel):
    key: str
    label: str
    status: Literal["ok", "none", "failed"]
    text: str


class EnrichResult(BaseModel):
    key: Literal["distances", "footprints", "census", "elevation"]
    status: Literal["ok", "partial", "skipped"]
    text: str
    fields: list[str] = Field(description="The fields it added.")
    seconds: float
    reused: bool = Field(description="Read from what was downloaded before.")
    features: list[FeatureResult] = Field(default_factory=list, description="distances: each OpenStreetMap feature.")


SOURCES = {
    "distances": "OpenStreetMap contributors (ODbL)",
    "footprints": "Overture Maps",
    "census": "US Census Bureau",
    "elevation": "USGS 3DEP",
}
# OpenAVMKit's functions, and what each is while it runs.
STEPS: dict[str, tuple[Literal["distances", "footprints", "census", "elevation"], str]] = {
    "_enrich_df_overture": ("footprints", "Downloading building footprints from Overture Maps"),
    "_enrich_df_census": ("census", "Downloading census figures"),
    "_enrich_df_distances": ("distances", "Measuring distances to OpenStreetMap features"),
    "_enrich_df_dem": ("elevation", "Downloading elevation from USGS"),
}
LABELS = {  # OpenAVMKit's verbose labels, in its "Failed to get …" messages
    "water_bodies": "water bodies",
    "transportation": "transportation networks",
    "educational": "educational institutions",
    "parks": "parks",
    "golf_courses": "golf courses",
    "coastline": "coastline",
}


# Where each downloads from: asked first, so a service that can't be reached is skipped at once rather than
# waited on (OpenStreetMap's library waits a minute and tries again).
PROBES = {
    "footprints": "https://overturemaps-us-west-2.s3.amazonaws.com/",
    "census": "https://api.census.gov/data.json",
    "elevation": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/",
}
CACHES = {"footprints": "geom/overture", "census": "census", "elevation": "dem/all", "distances": "osm/all"}
# The parts of a run that can be skipped while it runs: their fields are left out, nothing else changes.
SKIPPABLE = ("footprints", "census", "distances", "elevation")


def reachable(url: str, timeout: float = 10) -> str | None:
    """None if the service answers at all (any HTTP status); else why not, in a few words. Asked with requests, as
    the downloads are (OSMnx, OpenAVMKit), so the check and the download can't disagree about a certificate."""
    import requests

    from oakbox.net import USER_AGENT

    host = url.split("/")[2]
    try:
        requests.head(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": USER_AGENT})
    except requests.exceptions.SSLError as e:
        # "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired" -> its last part
        found = re.search(r"verify failed: ([^(')\]]+)", str(e))
        return f"{host}'s certificate couldn't be checked ({found.group(1).strip() if found else 'SSL error'})"
    except requests.exceptions.ProxyError:
        return f"{host} didn't answer (the network's proxy didn't let it through)"
    except requests.exceptions.Timeout:
        return f"{host} didn't answer within {timeout:g} seconds"
    except requests.exceptions.RequestException:
        return f"{host} didn't answer (no connection)"
    return None


def _first_line(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line if len(line) <= 200 else line[:197] + "…"


def instrument(settings: dict, emit) -> list[EnrichResult]:
    """Wrap OpenAVMKit's public-data enrichments so each says when it starts, is timed, and never stops the run:
    one that fails is skipped (its fields left out) and the result says why. Returns the list the results go in.

    OpenAVMKit saves the distances it measured even when a feature's download failed; that's cleared, so running
    again downloads the feature rather than reusing its absence."""
    import warnings

    import osmnx as ox
    from openavmkit import data as engine
    from openavmkit import progress
    from openavmkit.utilities.cache import clear_cache, get_cached_df

    enrich = settings.get("data", {}).get("process", {}).get("enrich", {})
    osm = {k: v for k, v in enrich.get("distances", {}).items() if isinstance(v, dict) and v.get("osm")}
    on = {
        "footprints": bool(enrich.get("overture", {}).get("enabled")),
        "census": bool(enrich.get("census", {}).get("enabled")),
        "distances": bool(osm),
        "elevation": bool(enrich.get("dem", {}).get("enabled")),
    }
    results: list[EnrichResult] = []

    def wrap(name: str, fn):
        key, message = STEPS[name]

        def run(df, *args, **kwargs):
            if not on[key]:
                return fn(df, *args, **kwargs)
            emit(step=key, fraction=None, message=message, part=key)
            before, t0, buf = set(df.columns), time.time(), _Said(emit, key)
            error = None
            try:
                progress.check_skipped(key)  # skipped before it started
            except progress.Skipped:
                results.append(_skipped(key, t0))
                return df
            # Its settings come first after the parcels: OpenAVMKit finds what it saved before by them.
            saved = get_cached_df(df, CACHES[key], "key", args[0]) is not None
            down = None
            if not saved:
                down = reachable(_probe(key))
                if down:
                    # Not asked at all: OpenStreetMap's Overpass is a shared, volunteer-run service, and its rate
                    # limit stays on, so nothing goes to it unchecked.
                    results.append(
                        EnrichResult(
                            key=key,
                            status="skipped",
                            text=f"Skipped: {down}",
                            fields=[],
                            seconds=round(time.time() - t0, 1),
                            reused=False,
                        )
                    )
                    return df
            with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stdout(buf):
                warnings.simplefilter("always")
                try:
                    out = fn(df, *args, **kwargs)
                except progress.Skipped:
                    # Stopped at a checkpoint: the parcels as they came in (nothing half-done kept; OpenAVMKit
                    # saves what it downloaded only once a part is done).
                    results.append(_skipped(key, t0))
                    return df
                except Exception as e:  # noqa: BLE001 - a failed download is skipped, not the run
                    out, error = df, f"{type(e).__name__}: {e}"
            said = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
            log = buf.getvalue()
            # What OpenAVMKit said while it ran, kept for when something needs explaining.
            logs = Path("out") / "oakbox" / "enrich_logs"
            logs.mkdir(parents=True, exist_ok=True)
            (logs / f"{key}.log").write_text("\n".join([log, *said, error or ""]), encoding="utf-8")
            added = [str(c) for c in out.columns if c not in before]
            seconds = round(time.time() - t0, 1)
            results.append(_result(key, out, added, error or down, said, log, osm, seconds, saved))
            if key == "distances" and any(f.status == "failed" for f in results[-1].features):
                clear_cache("osm/all", "df")
            return out

        return run

    def _probe(key: str) -> str:
        return f"{ox.settings.overpass_url}/status" if key == "distances" else PROBES[key]

    from oakbox.net import HOME, USER_AGENT

    # Who's asking, as OpenStreetMap's services ask apps to say (not OSMnx's own name).
    ox.settings.http_user_agent = USER_AGENT
    ox.settings.http_referer = HOME
    ox.settings.overpass_rate_limit = True
    for name in STEPS:
        setattr(engine, name, wrap(name, getattr(engine, name)))
    return results


def _skipped(key, t0: float) -> EnrichResult:
    return EnrichResult(
        key=key,
        status="skipped",
        text="Skipped: you skipped it while it ran",
        fields=[],
        seconds=round(time.time() - t0, 1),
        reused=False,
    )


class _Said(io.StringIO):
    """What OpenAVMKit prints while an enrichment runs: kept for its log, and its latest line passed on to the app
    as what the step is doing (at most a few times a second)."""

    def __init__(self, emit, part: str):
        super().__init__()
        self._emit, self._part, self._last, self._line = emit, part, 0.0, ""

    def write(self, s: str) -> int:
        n = super().write(s)
        self._line += s
        if "\n" in self._line:
            lines = [x.strip() for x in self._line.split("\n")]
            self._line = lines[-1]
            said = next((x for x in reversed(lines[:-1]) if x), "")
            now = time.time()
            if said and now - self._last > 0.3:
                self._last = now
                self._emit(detail=said.lstrip("-> ").strip()[:160], part=self._part)
        return n


def recount(results: list[EnrichResult], universe) -> None:
    """Coverage as the parcel universe ended up (later steps fill in or clear some), in each result's words."""
    for r in results:
        # The fields as they came out: those unticked on the step are dropped as the run ends.
        r.fields = [c for c in r.fields if c in universe.columns]
        if r.status == "ok" and r.key != "distances" and r.fields:
            r.text = _coverage(r.key, universe, r.fields)


def _coverage(key: str, out, added: list[str]) -> str:
    n = len(out)
    if not n:
        return ""

    def have(col: str, positive: bool = False) -> int:
        if col not in out:
            return 0
        s = out[col]
        return int((s.fillna(0) > 0).sum()) if positive else int(s.notna().sum())

    if key == "footprints":
        got = have(next((c for c in added if c.startswith("bldg_area_footprint")), added[0]), positive=True)
        return f"{got:,} parcels ({100 * got / n:.0f}%) have a building"
    if key == "census":
        got = have(next((c for c in CENSUS_FIELDS if c in added), added[0]))
        return f"{got:,} parcels ({100 * got / n:.0f}%) in a block group with figures"
    got = have(next((c for c in added if c.startswith("elevation_mean")), added[0]))
    return "every parcel" if got == n else f"{got:,} parcels ({100 * got / n:.0f}%)"


def _result(key, out, added, error, said, log, osm, seconds, saved) -> EnrichResult:
    """How an enrichment went. error: what stopped it, or the service that couldn't be reached."""
    reused = saved

    def have(col: str, positive: bool = False) -> int:
        if col not in out:
            return 0
        s = out[col]
        return int((s.fillna(0) > 0).sum()) if positive else int(s.notna().sum())

    if key == "distances":
        # OpenAVMKit's OpenStreetMap download prints its error and carries on with nothing: which feature's it was
        # comes from the line before ("Getting parks from OSM...").
        errors: dict[str, str] = {}
        now = None
        for line in log.splitlines():
            if line.startswith("Getting ") and line.endswith(" from OSM..."):
                now = line[len("Getting ") : -len(" from OSM...")]
            elif line.startswith("ERROR") and now and now not in errors:
                errors[now] = line.split(":", 1)[-1].strip()
        feats = []
        for k in osm:
            label = SPECS[k].label if k in SPECS else k
            col = f"dist_to_osm_{k}"
            if col in out:
                within = have(col)
                feats.append(FeatureResult(key=k, label=label, status="ok", text=f"{within:,} parcels within reach"))
                continue
            word = LABELS.get(k, k)
            lines = [*said, *log.splitlines()]
            why = next((m for m in lines if f"Failed to get {word}" in m), None)
            why = why or errors.get(k) or next((m for m in lines if "Failed to enrich with OpenStreetMap" in m), None)
            if why is None and error is None:
                feats.append(FeatureResult(key=k, label=label, status="none", text="none in this area"))
            else:
                text = _first_line((error or why or "").replace("ERROR ", ""))
                feats.append(FeatureResult(key=k, label=label, status="failed", text=text))
        failed = [f for f in feats if f.status == "failed"]
        mine = [c for c in added if "_osm_" in c]
        if failed and len(failed) == len(feats):
            status, text = "skipped", f"Skipped: {failed[0].text}"
        elif failed:
            status, text = (
                "partial",
                f"{len(feats) - len(failed)} of {len(feats)} features; "
                + ", ".join(f.label for f in failed)
                + " failed",
            )
        else:
            found = sum(1 for f in feats if f.status == "ok")
            status, text = "ok", f"{found} of {len(feats)} features found in this area"
        return EnrichResult(
            key=key, status=status, text=text, fields=mine, seconds=seconds, reused=reused, features=feats
        )
    if error or not added:
        why = error or next((m for m in said), None) or "it added nothing"
        return EnrichResult(
            key=key, status="skipped", text=f"Skipped: {_first_line(why)}", fields=[], seconds=seconds, reused=False
        )
    text = _coverage(key, out, added)
    return EnrichResult(key=key, status="ok", text=text, fields=added, seconds=seconds, reused=reused)

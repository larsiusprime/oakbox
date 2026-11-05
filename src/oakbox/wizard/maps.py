"""Where the parcels are on the map, and map layers (F3d): Shapefiles and other layers stamped onto the parcels or
measured to, how many parcels each covers, and its shapes for the map. Also the enrichments' view (F3e).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from oakbox import enrichments
from oakbox.datafiles import (
    BaseModel,
    DataFile,
    Overlay,
)
from oakbox.projects import Project
from oakbox.wizard.files import Files, _by_key, base_file, file_stamp
from oakbox.wizard.models import Check, LayerView, Left
from oakbox.wizard.user_fields import TAKEN

# ---------- Where the parcels are, for the map ----------


class MapView(BaseModel):
    """Where the parcels are, for the map: a sample of their centres, and the polar coordinates' centre."""

    points: list[tuple[float, float]] = Field(description="[latitude, longitude] of up to 3,000 parcel centres.")
    middle: tuple[float, float] | None = Field(description="The middle of all the parcels: the default centre.")
    center: tuple[float, float] | None = Field(description="The centre the user set; None: the middle.")
    parcels: int


@lru_cache(maxsize=8)
def _map_points(stamp: tuple[str, float, int], layer: str | None):
    import geopandas as gpd

    path = Path(stamp[0])
    gdf = (
        gpd.read_parquet(path)
        if path.suffix.lower() in (".parquet", ".geoparquet")
        else gpd.read_file(path, layer=layer)
    )
    gdf = gdf[gdf.geometry.notna()]
    if gdf.crs is None:
        return [], None, len(gdf)
    # The middle as OpenAVMKit works it out (in the file's own coordinates), then in degrees.
    middle = gpd.GeoSeries([gdf.geometry.union_all().centroid], crs=gdf.crs).to_crs(4326).iloc[0]
    sample = gdf.sample(min(3000, len(gdf)), random_state=0) if len(gdf) else gdf
    centres = sample.geometry.centroid.to_crs(4326)
    points = [(round(p.y, 6), round(p.x, 6)) for p in centres]
    return points, (round(middle.y, 6), round(middle.x, 6)), len(gdf)


class LocationMap(BaseModel):
    """A location field on the map: each parcel's centre and which of its areas it's in."""

    name: str
    values: list[str] = Field(description="Its areas, most parcels first.")
    counts: list[int] = Field(description="Parcels in each area, as values.")
    points: list[tuple[float, float, int]] = Field(
        description="[latitude, longitude, area] of up to 20,000 parcel centres; area: its index in values, -1 none."
    )
    parcels: int


@lru_cache(maxsize=8)
def _centres(stamp: tuple[str, float, int], layer: str | None) -> tuple[tuple[float, float] | None, ...]:
    """Every row's centre in degrees, in the file's order (None without a shape)."""
    import geopandas as gpd

    path = Path(stamp[0])
    gdf = (
        gpd.read_parquet(path)
        if path.suffix.lower() in (".parquet", ".geoparquet")
        else gpd.read_file(path, layer=layer)
    )
    if gdf.crs is None:
        return tuple(None for _ in range(len(gdf)))
    centres = gdf.geometry.centroid.to_crs(4326)
    return tuple(None if p is None or p.is_empty else (round(p.y, 6), round(p.x, 6)) for p in centres)


def location_map(project: Project, in_dir: Path, name: str) -> LocationMap:
    """Where each of a location field's areas is: the parcel universe's centres, each with its area."""
    import random
    from collections import Counter

    if name not in project.wizard.locations:
        raise LookupError(name)
    entry = next((f for f in project.files if name in f.load and f.holds not in ("sales", "overlay", "unused")), None)
    base = base_file(project)
    if entry is None or base is None or not (in_dir / base.filename).is_file():
        raise LookupError(name)
    files = Files(project, in_dir)
    values = files.values(entry.name, entry.load[name][0])
    by_id: dict[str, str] = {}
    for i, v in zip(files.ids(entry.name, entry.match), values, strict=False):
        if i and i not in by_id:
            by_id[i] = v
    centres = _centres(file_stamp(in_dir / base.filename), base.layer)
    rows = [(c, by_id.get(i, "")) for i, c in zip(files.ids(base.name, "key"), centres, strict=False) if c is not None]
    counts = Counter(v for _, v in rows if v)
    order = [v for v, _ in counts.most_common()]
    index = {v: k for k, v in enumerate(order)}
    shown = random.Random(0).sample(rows, min(20_000, len(rows)))
    return LocationMap(
        name=name,
        values=order,
        counts=[counts[v] for v in order],
        points=[(c[0], c[1], index.get(v, -1)) for c, v in shown],
        parcels=len(rows),
    )


def map_view(project: Project, in_dir: Path) -> MapView:
    base = base_file(project)
    center = (project.center.latitude, project.center.longitude) if project.center else None
    if base is None or not (in_dir / base.filename).is_file():
        return MapView(points=[], middle=None, center=center, parcels=0)
    points, middle, n = _map_points(file_stamp(in_dir / base.filename), base.layer)
    return MapView(points=points, middle=middle, center=center, parcels=n)


# ---------- Map layers: Shapefiles (F3d) ----------


@lru_cache(maxsize=16)
def _read_geo(stamp: tuple[str, float, int], layer: str | None):
    import geopandas as gpd

    path = Path(stamp[0])
    if path.suffix.lower() in (".parquet", ".geoparquet"):
        gdf = gpd.read_parquet(path)
    else:
        gdf = gpd.read_file(path, layer=layer)
    return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]


def _geo(in_dir: Path, f: DataFile):
    return _read_geo(file_stamp(in_dir / f.filename), f.layer)


@lru_cache(maxsize=16)
def coverage(base: tuple[str, float, int], base_layer: str | None, other: tuple[str, float, int], layer: str | None):
    """(parcels in exactly one shape, in several, in none): their centres, as OpenAVMKit joins them."""
    import geopandas as gpd

    parcels = _read_geo(base, base_layer)
    shapes = _read_geo(other, layer)
    shapes = gpd.GeoDataFrame(shapes[shapes.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]).to_crs(parcels.crs)
    centres = gpd.GeoDataFrame(geometry=parcels.geometry.centroid, crs=parcels.crs)
    hits = gpd.sjoin(centres, gpd.GeoDataFrame(geometry=shapes.geometry), how="inner", predicate="within")
    hits = hits.groupby(level=0).size()
    one = int((hits == 1).sum())
    several = int((hits > 1).sum())
    return one, several, len(parcels) - one - several


def layers(project: Project, in_dir: Path) -> list[LayerView]:
    files = Files(project, in_dir)
    base = base_file(project)
    out = []
    for f in project.files:
        if f.holds != "overlay" or not (in_dir / f.filename).is_file():
            continue
        o = f.overlay or Overlay()
        left: list[Left] = []
        try:
            gdf = _geo(in_dir, f)
        except Exception as e:  # noqa: BLE001 - an unreadable file shows on its card
            gdf = None
            left.append(Left(text=f"can't be read: {e}"))
        kinds = gdf.geometry.geom_type.value_counts().to_dict() if gdf is not None else {}
        # Curved shapes (CurvePolygon, MultiSurface, from some GeoPackage and ArcGIS exports) count as shapes.
        polygons = int(sum(n for k, n in kinds.items() if "Polygon" in k or "Surface" in k))
        points = int(sum(n for k, n in kinds.items() if "Point" in k))
        lines = int(sum(n for k, n in kinds.items() if "Line" in k or "Curve" in k and "Polygon" not in k))
        projected = gdf is not None and gdf.crs is not None
        check = None
        if gdf is not None and not projected:
            left.append(Left(text="has no coordinate system (a .prj file), so it can't be placed"))
        if o.use is None:
            left.append(Left(text="say how to use it", blocking=False))
        elif o.use == "stamp":
            if not polygons:
                left.append(Left(text="has no shapes to fall in: use it for distances"))
            elif not o.fields:
                left.append(Left(text="pick at least one column to copy"))
            elif projected and base is not None and (in_dir / base.filename).is_file():
                one, several, none = coverage(
                    file_stamp(in_dir / base.filename), base.layer, file_stamp(in_dir / f.filename), f.layer
                )
                # Only what isn't zero: "every parcel in one shape", or "1,252 in a shape · 8,107 in none".
                if several == 0 and none == 0:
                    text = "every parcel in one shape"
                else:
                    text = " · ".join(
                        x
                        for x in (
                            f"{one + several:,} in a shape",
                            f"{several:,} in more than one" if several else "",
                            f"{none:,} in none" if none else "",
                        )
                        if x
                    )
                if one + several == 0:
                    left.append(Left(text="no parcel falls in any shape: is it the right place, or projection?"))
                    check = Check(ok=False, text=text)
                else:
                    check = Check(ok=True, warn=several > 0, text=("" if several else "✓ ") + text)
        elif o.use == "distance":
            if not o.feature:
                left.append(Left(text="name the distance"))
            # How many features is in the layer's header already: no check line of its own.
        out.append(
            LayerView(
                name=f.name,
                filename=f.filename,
                columns=files.columns(f.name),
                overlay=o,
                features=len(gdf) if gdf is not None else 0,
                polygons=polygons,
                points=points,
                lines=lines,
                projected=projected,
                check=check,
                left=left,
            )
        )
    return out


def _taken_names(project: Project, skip: str) -> set[str]:
    """Field names already used, other than by the layer being changed."""
    names = {k for f in project.files if f.holds in ("parcels", "sales") for k in f.load}
    for f in project.files:
        if f.holds == "overlay" and f.overlay and f.name != skip:
            names |= {x.name for x in f.overlay.fields}
            if f.overlay.feature:
                names.add(f"dist_to_{f.overlay.feature}")
    # OpenStreetMap features measured to (F3e) take their names in OpenAVMKit's distances too.
    return names | {f"dist_to_{k}" for k in enrichments.osm_names(project.enrich)}


def set_overlay(project: Project, in_dir: Path, name: str, overlay: Overlay | None) -> None:
    """Make a file a map layer used as said (stamp or distance); None sets it aside."""
    entry = next((f for f in project.files if f.name == name), None)
    if entry is None:
        raise LookupError(name)
    if overlay is None:
        entry.holds, entry.overlay = "unused", None
        return
    if entry.name == project.wizard.base:
        raise ValueError("That's the parcel universe.")
    files = Files(project, in_dir)
    if not files.geometry(name):
        raise ValueError(f"{name} has no shapes: a map layer needs geometry.")
    columns = {c.name for c in files.columns(name)}
    by_key = _by_key()
    taken = _taken_names(project, name)

    def check_name(n: str, what: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", n):
            raise ValueError(f"{what}: names use lowercase letters, digits and underscores, and start with a letter.")
        d = by_key.get(n)
        if n in TAKEN or n.startswith("polar_") or (d is not None and d.source in ("derived", "reserved")):
            raise ValueError(f"OpenAVMKit works out {n} itself: choose another name.")
        if n in taken:
            raise ValueError(f"{n} is already used for another field.")

    if overlay.use == "stamp":
        seen = set()
        for x in overlay.fields:
            if x.column not in columns:
                raise ValueError(f"{name} has no column {x.column}.")
            check_name(x.name, x.column)
            if x.name in seen:
                raise ValueError(f"{x.name} is used twice.")
            seen.add(x.name)
    elif overlay.use == "distance":
        if overlay.feature:
            check_name(overlay.feature, "The distance")
            check_name(f"dist_to_{overlay.feature}", "The distance")
        if overlay.name_column is not None and overlay.name_column not in columns:
            raise ValueError(f"{name} has no column {overlay.name_column}.")
        if overlay.store_top and overlay.top_n < 1:
            raise ValueError("Say how many of the largest features get their own distance.")
    entry.holds, entry.overlay, entry.load = "overlay", overlay, {}


class LayerMap(BaseModel):
    shapes: dict = Field(description="The layer's features as GeoJSON in degrees, simplified, at most 2,000.")
    points: list[tuple[float, float]] = Field(description="Parcel centres, as on the Location map.")


def layer_map(project: Project, in_dir: Path, name: str) -> LayerMap:
    import json as _json

    import geopandas as gpd

    entry = next((f for f in project.files if f.name == name and f.holds == "overlay"), None)
    if entry is None:
        raise LookupError(name)
    gdf = _geo(in_dir, entry)
    if gdf.crs is None:
        raise ValueError(f"{name} has no coordinate system, so it can't be placed on a map.")
    shapes = gpd.GeoDataFrame(geometry=gdf.geometry.iloc[:2000], crs=gdf.crs).to_crs(4326)
    shapes["geometry"] = shapes.geometry.simplify(0.00005, preserve_topology=True)
    import shapely

    shapes["geometry"] = shapely.force_2d(shapes.geometry.to_numpy())  # flat: a height draws it out of sight
    return LayerMap(shapes=_json.loads(shapes.to_json()), points=map_view(project, in_dir).points)


# ---------- Enrichments (F3e) ----------


def enrich_view(project: Project, in_dir: Path) -> enrichments.EnrichView:
    taken = {
        f.overlay.feature for f in project.files if f.holds == "overlay" and f.overlay and f.overlay.use == "distance"
    }
    return enrichments.view(project, in_dir, taken)

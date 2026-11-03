/** Every map in OAK box: MapLibre for the street map underneath, deck.gl (WebGL) for what's drawn on it, so a
 * county's half a million parcels draw as smoothly as a few hundred sales. A "Street map" box takes the street map
 * away (a plain background, to see only the colours); the choice carries to every map. */
import type { Layer, PickingInfo } from "@deck.gl/core";
import { MapboxOverlay } from "@deck.gl/mapbox";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import { t } from "../strings";

// MapLibre looks for its worker beside its own file, which the bundle doesn't keep: here it is, bundled.
maplibregl.setWorkerUrl(workerUrl);

const KEY = "oakbox.basemap";

function wanted(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

function remember(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // Not remembered: the next map shows it again.
  }
}

/** [west, south] and [east, north]. */
export type Bounds = [[number, number], [number, number]];

/** The box around [lon, lat] points (and any more boxes); null when there's nothing. */
export function boundsOf(
  points: Iterable<readonly [number, number]>,
  more: (Bounds | null)[] = [],
): Bounds | null {
  let w = Number.POSITIVE_INFINITY;
  let s = Number.POSITIVE_INFINITY;
  let e = Number.NEGATIVE_INFINITY;
  let n = Number.NEGATIVE_INFINITY;
  const add = (lon: number, lat: number) => {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    w = Math.min(w, lon);
    e = Math.max(e, lon);
    s = Math.min(s, lat);
    n = Math.max(n, lat);
  };
  for (const [lon, lat] of points) add(lon, lat);
  for (const b of more) {
    if (!b) continue;
    add(b[0][0], b[0][1]);
    add(b[1][0], b[1][1]);
  }
  return Number.isFinite(w)
    ? [
        [w, s],
        [e, n],
      ]
    : null;
}

/** The box around a GeoJSON collection's coordinates. */
export function boundsOfGeoJson(
  fc: GeoJSON.FeatureCollection | GeoJSON.Feature | null | undefined,
): Bounds | null {
  if (!fc) return null;
  const pts: [number, number][] = [];
  const walk = (c: unknown): void => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      pts.push([c[0], c[1]]);
      return;
    }
    for (const x of c) walk(x);
  };
  const geom = (g: GeoJSON.Geometry | null): void => {
    if (!g) return;
    if (g.type === "GeometryCollection") for (const x of g.geometries) geom(x);
    else walk(g.coordinates);
  };
  if (fc.type === "FeatureCollection") for (const f of fc.features) geom(f.geometry);
  else geom(fc.geometry);
  return boundsOf(pts);
}

/** "#1d5bb8" (or "rgb(1, 2, 3)") → [r, g, b, a], as deck.gl takes colours; alpha 0 to 1. */
export function rgba(colour: string, alpha = 1): [number, number, number, number] {
  const a = Math.round(255 * alpha);
  const m = colour.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3]), a];
  let h = colour.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  const v = Number.parseInt(h.slice(0, 6), 16);
  return Number.isNaN(v) ? [128, 128, 128, a] : [(v >> 16) & 255, (v >> 8) & 255, v & 255, a];
}

// deck.gl's tooltip is styled inline: these replace its dark box with the app's own.
const TIP = {
  maxWidth: "22rem",
  padding: "0.3rem 0.5rem",
  font: "inherit",
  fontSize: "0.8rem",
  color: "#111111",
  background: "#ffffff",
  border: "1px solid #c9ccc4",
  borderRadius: "4px",
};

const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    { id: "plain", type: "background", paint: { "background-color": "#fafafa" } },
    { id: "osm", type: "raster", source: "osm" },
  ],
};

export function MapView({
  layers,
  bounds,
  fitKey,
  resizeKey,
  className,
  label,
  scrollZoom = true,
  tooltip,
  onMap,
  children,
}: {
  /** What's drawn: deck.gl layers. */
  layers: Layer[];
  /** Where to look: fitted when `fitKey` changes (and first shown). */
  bounds: Bounds | null;
  fitKey?: string;
  /** The map's box changed size (docked, full): fitted to it again. */
  resizeKey?: string;
  className: string;
  label: string;
  /** False: the wheel scrolls the page, not the map (a map inside a long step). */
  scrollZoom?: boolean;
  /** What hovering an object says. */
  tooltip?: (info: PickingInfo) => string | null;
  /** The map, once made (and null when gone): for markers of its own, like a pin to drag. */
  onMap?: (m: maplibregl.Map | null) => void;
  children?: React.ReactNode;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [street, setStreet] = useState(wanted);
  const [ready, setReady] = useState(false);
  const first = useRef({ bounds, scrollZoom, street, onMap });

  // The map, once.
  useEffect(() => {
    if (!el.current) return;
    const { bounds: b, scrollZoom: wheel, street: on, onMap: give } = first.current;
    const m = new maplibregl.Map({
      container: el.current,
      style: STYLE,
      ...(b ? { bounds: b, fitBoundsOptions: { padding: 12 } } : { center: [0, 0], zoom: 1 }),
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    });
    m.touchZoomRotate.disableRotation();
    if (!wheel) m.scrollZoom.disable();
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    const o = new MapboxOverlay({ interleaved: false, layers: [] });
    m.addControl(o);
    m.on("load", () => {
      m.setLayoutProperty("osm", "visibility", on ? "visible" : "none");
      setReady(true);
    });
    map.current = m;
    overlay.current = o;
    give?.(m);
    return () => {
      give?.(null);
      m.remove();
      map.current = null;
      overlay.current = null;
      setReady(false);
    };
  }, []);

  useEffect(() => {
    overlay.current?.setProps({
      layers,
      getTooltip: tooltip
        ? (info: PickingInfo) => {
            const text = info.object != null || info.index >= 0 ? tooltip(info) : null;
            return text ? { text, style: TIP } : null;
          }
        : null,
    });
  }, [layers, tooltip]);

  // Fitted when what's shown changes (fitKey), not whenever a new box of the same place comes in.
  const where = useRef(bounds);
  useEffect(() => {
    where.current = bounds;
  });
  useEffect(() => {
    void fitKey;
    const b = where.current;
    if (b && map.current) map.current.fitBounds(b, { padding: 12, duration: 0, maxZoom: 17 });
  }, [fitKey]);

  useEffect(() => {
    void resizeKey;
    const id = setTimeout(() => map.current?.resize(), 50);
    return () => clearTimeout(id);
  }, [resizeKey]);

  useEffect(() => {
    if (ready) map.current?.setLayoutProperty("osm", "visibility", street ? "visible" : "none");
  }, [street, ready]);

  return (
    <div className={`map-view ${className}`}>
      <div ref={el} className="map-canvas" role="img" aria-label={label} />
      <label className="map-street">
        <input
          type="checkbox"
          checked={street}
          onChange={(e) => {
            setStreet(e.target.checked);
            remember(e.target.checked);
          }}
        />
        {t.map.basemap}
      </label>
      {children}
    </div>
  );
}

/** Every map in OAK box: MapLibre for the street map underneath, deck.gl (WebGL) for what's drawn on it, so a
 * county's half a million parcels draw as smoothly as a few hundred sales. The street map is OpenFreeMap's vector
 * style (or a tile server of one's own: the app settings' map_style); a "Street map" box takes it away (a plain
 * background, to see only the colours). Each map starts with it on or off as Settings › Performance says (SPEC §5),
 * and on a computer where maps wait for a click, each starts as a Show map button in its place. Offline, or with the
 * box off, the map is the plain background, and what's drawn on it is all there. */
import type { Layer, PickingInfo } from "@deck.gl/core";
import { MapboxOverlay } from "@deck.gl/mapbox";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { useAppSettings } from "../api/app";
import { openSettings, useResolved } from "../lib/machine";
import { t } from "../wording";
import { InfoTip } from "./Tip";

// MapLibre looks for its worker beside its own file, which the bundle doesn't keep: here it is, bundled.
maplibregl.setWorkerUrl(workerUrl);

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
  // Clear of the pointer (deck.gl puts it at the pointer's tip): below and right of a pointing finger.
  marginLeft: "16px",
  marginTop: "22px",
};

/** No street map: a plain background. */
const PLAIN: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "plain", type: "background", paint: { "background-color": "#fafafa" } }],
};

// Each street map style, fetched once for every map; one that couldn't be fetched (offline) is asked again next time.
const styles = new Map<string, Promise<maplibregl.StyleSpecification>>();

function streetStyle(url: string): Promise<maplibregl.StyleSpecification> {
  let style = styles.get(url);
  if (!style) {
    style = fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.json() as Promise<maplibregl.StyleSpecification>;
    });
    styles.set(url, style);
    style.catch(() => styles.delete(url));
  }
  return style;
}

type Props = Omit<Parameters<typeof MapCanvas>[0], "street"> & {
  /** Opened on purpose (the map window): that was the click, so it doesn't wait for another. */
  asked?: boolean;
};

/** The map, or, where maps wait for a click (Settings › Performance), a panel in its place until Show map. */
export function MapView(props: Props) {
  const r = useResolved();
  const [shown, setShown] = useState(false);
  if (r.maps === "click" && !shown && !props.asked)
    return (
      <div className={`map-view map-wait ${props.className}`}>
        <div className="map-wait-ask">
          <b>{props.label}</b>
          <Button className="button" onPress={() => setShown(true)}>
            {t.map.show}
          </Button>
          <small>
            {t.map.waitNote}{" "}
            <Button className="wiz-link map-wait-settings" onPress={() => openSettings("performance")}>
              {t.map.waitSettings}
            </Button>
          </small>
        </div>
      </div>
    );
  const { asked: _, ...rest } = props;
  return <MapCanvas {...rest} street={r.street_map === "on"} />;
}

function MapCanvas({
  street: startStreet,
  layers,
  bounds,
  fitKey,
  resizeKey,
  className,
  label,
  scrollZoom = true,
  tooltip,
  cursor,
  onMap,
  interleaved = false,
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
  /** True: the wheel always zooms (a map that is the page). "focus": a map inside a page: the wheel zooms once it's
   * clicked (or tabbed) into, and scrolls the page again once something else is. False: never. */
  scrollZoom?: boolean | "focus";
  /** The street map starts on (Settings › Performance); the box turns it on or off on this map. */
  street: boolean;
  /** What hovering an object says. */
  tooltip?: (info: PickingInfo) => string | null;
  /** The pointer over what's drawn: a pointing finger where a click picks something ("pointer"), the map's own
   * drag hand elsewhere (""). */
  cursor?: (info: PickingInfo) => string;
  /** The map, once made (and null when gone): for markers of its own, like a pin to drag. */
  onMap?: (m: maplibregl.Map | null) => void;
  /** What's drawn goes into the map's own canvas (deck.gl interleaved), so a marker of its own (the centre's pin) is
   * always over it, whatever stacks the page's layers. */
  interleaved?: boolean;
  children?: React.ReactNode;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [street, setStreet] = useState(startStreet);
  const [ready, setReady] = useState(false);
  const styleUrl = useAppSettings().data?.map_style;
  const first = useRef({ bounds, scrollZoom, onMap, interleaved });

  // The map, once.
  useEffect(() => {
    if (!el.current) return;
    const { bounds: b, scrollZoom: wheel, onMap: give, interleaved: inCanvas } = first.current;
    const m = new maplibregl.Map({
      container: el.current,
      style: PLAIN,
      ...(b ? { bounds: b, fitBoundsOptions: { padding: 12 } } : { center: [0, 0], zoom: 1 }),
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    });
    m.touchZoomRotate.disableRotation();
    if (wheel !== true) m.scrollZoom.disable();
    // Zooms with the wheel only while it's the thing in use: clicked or tabbed into, until something else is.
    const box = el.current.parentElement ?? el.current;
    const wake = () => m.scrollZoom.enable();
    const off = (e: Event) => {
      if (!box.contains(e.target as Node)) m.scrollZoom.disable();
    };
    if (wheel === "focus") {
      box.addEventListener("pointerdown", wake);
      box.addEventListener("focusin", wake);
      document.addEventListener("pointerdown", off);
      document.addEventListener("focusin", off);
    }
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    const o = new MapboxOverlay({ interleaved: inCanvas, layers: [] });
    m.addControl(o);
    m.on("load", () => setReady(true));
    map.current = m;
    overlay.current = o;
    give?.(m);
    return () => {
      if (wheel === "focus") {
        box.removeEventListener("pointerdown", wake);
        box.removeEventListener("focusin", wake);
        document.removeEventListener("pointerdown", off);
        document.removeEventListener("focusin", off);
      }
      give?.(null);
      m.remove();
      map.current = null;
      overlay.current = null;
      setReady(false);
    };
  }, []);

  useEffect(() => {
    overlay.current?.setProps({
      // Copies, every time: deck.gl sets a layer up once and won't take it back after it's dropped, and the React
      // Compiler can hand back a layer made earlier (shapes, then dots, then those same shapes again).
      layers: layers.map((l) => l.clone({})),
      getTooltip: tooltip
        ? (info: PickingInfo) => {
            const text = info.object != null || info.index >= 0 ? tooltip(info) : null;
            return text ? { text, style: TIP } : null;
          }
        : null,
      // MapLibre owns the pointer (its drag hand): the cursor is set on its canvas while over something, and
      // given back off it.
      onHover: cursor
        ? (info: PickingInfo) => {
            const c = map.current?.getCanvas();
            if (c) c.style.cursor = info.layer ? cursor(info) : "";
          }
        : null,
    });
  }, [layers, tooltip, cursor]);

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

  // The street map once its style has come (the plain background until then, and if it can't come).
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    if (!street || !styleUrl) {
      m.setStyle(PLAIN);
      return;
    }
    let gone = false;
    streetStyle(styleUrl).then(
      (style) => {
        if (!gone) m.setStyle(style);
      },
      () => {
        if (!gone) m.setStyle(PLAIN);
      },
    );
    return () => {
      gone = true;
    };
  }, [street, styleUrl, ready]);

  return (
    <div className={`map-view ${className}`}>
      <div ref={el} className="map-canvas" role="img" aria-label={label} />
      <label className="map-street">
        <input type="checkbox" checked={street} onChange={(e) => setStreet(e.target.checked)} />
        <InfoTip label={t.map.basemap} text={t.map.basemapTip} />
      </label>
      {children}
    </div>
  );
}

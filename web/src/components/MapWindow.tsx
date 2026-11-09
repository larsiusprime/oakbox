/** The map window (SPEC §3.15): one map of the 🌐 Parcel Universe, docked on a side of the main window (or closed),
 * its size set with the divider, remembered on this computer. Zoomed out, the parcels are drawn as cells sized to the
 * zoom (each coloured by its parcels' figure); once a few thousand parcels are in view, their shapes. Coloured by any
 * field of the parcel files, with the histogram's live range as its legend. Tested on Guilford's 220,000 parcels
 * (docs/spec/app.md §3.15): what costs is the number of shapes drawn, so never more than a few thousand. */
import type { Layer, PickingInfo } from "@deck.gl/core";
import { GeoJsonLayer, SolidPolygonLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import type * as maplibregl from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Button, Header, ListBoxItem, ListBoxSection } from "react-aria-components";
import { api, type MapColumn, type MapInfo, unwrap } from "../api/client";
import { type Dock, MAX, MIN, type Side, setDock, sideFor, toggleMap, useDock } from "../lib/mapdock";
import { readShapes, toBinary } from "../lib/shapes";
import { RangedBars, useChosenRange } from "../screens/FieldHistogram";
import { t } from "../wording";
import { CloseButton } from "./Buttons";
import { Combo, Marked, matches } from "./Combo";
import { type Bounds, MapView, rgba } from "./MapView";
import { Waiting } from "./Waiting";

const w = t.mapWindow;

/** Shapes once this few parcels are in view (and around it); cells before. */
const SHAPES_UPTO = 8000;
/** Cell sizes in metres, coarsest first: the finest at least 16 pixels across is drawn. */
const LEVELS = [8000, 4000, 2000, 1000, 500, 250, 125, 60, 30];
const CELL_PX = 16;
/** Sequential, light to dark (ColorBrewer YlGnBu): readable on the street map and without it. */
const RAMP: [number, number, number][] = [
  [255, 255, 204],
  [161, 218, 180],
  [65, 182, 196],
  [44, 127, 184],
  [37, 52, 148],
];
/** A category each, most parcels first; "another value" and blank after them. */
const CATS = [
  "#4e79a7",
  "#f28e2b",
  "#e15759",
  "#76b7b2",
  "#59a14f",
  "#edc948",
  "#b07aa1",
  "#ff9da7",
  "#9c755f",
  "#2f5d9b",
  "#8cd17d",
  "#d37295",
];
const OTHER: [number, number, number, number] = [150, 150, 150, 170];
const BLANK: [number, number, number, number] = [255, 255, 255, 0];
const BLANK_LINE: [number, number, number, number] = [120, 120, 120, 90];

// ---------- The window ----------

export function MapWindow({ projectId }: { projectId: string }) {
  const d = useDock();
  const width = useWindowWidth();
  const side = sideFor(d.side, width);
  const lid = useLidBottom();
  // The page makes room for it: the content's padding on its side (styles.css, html[data-map]).
  useEffect(() => {
    const root = document.documentElement;
    if (!d.open) return;
    root.dataset.map = side;
    root.style.setProperty("--map-frac", String(d.size));
    root.style.setProperty("--lid-bottom", `${lid}px`);
    return () => {
      delete root.dataset.map;
    };
  }, [d.open, side, d.size, lid]);
  // Ctrl+M opens and closes it (the 🗺 Map button on the plate too).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        toggleMap();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (!d.open) return null;
  return (
    <aside className={`mapwin mapwin-${side}`} aria-label={w.label}>
      <Divider side={side} size={d.size} />
      <MapPanel projectId={projectId} dock={d} side={side} narrow={side !== d.side} />
    </aside>
  );
}

function useWindowWidth(): number {
  return useSyncExternalStore(
    (l) => {
      window.addEventListener("resize", l);
      return () => window.removeEventListener("resize", l);
    },
    () => window.innerWidth,
  );
}

/** Where the lid (the plate's oak band) ends: the map docked left, right or top starts below it. */
function useLidBottom(): number {
  const [bottom, setBottom] = useState(0);
  useEffect(() => {
    const lid = document.querySelector(".oak-nav");
    if (!lid) return;
    const measure = () => setBottom(Math.round(lid.getBoundingClientRect().height));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(lid);
    return () => ro.disconnect();
  }, []);
  return bottom;
}

/** The edge to drag: the map's share of the window, from a quarter to 70%. */
function Divider({ side, size }: { side: Side; size: number }) {
  const across = side === "left" || side === "right";
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) => {
      const f =
        side === "right"
          ? 1 - ev.clientX / window.innerWidth
          : side === "left"
            ? ev.clientX / window.innerWidth
            : side === "bottom"
              ? 1 - ev.clientY / window.innerHeight
              : ev.clientY / window.innerHeight;
      setDock({ size: f });
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const grow = { right: "ArrowLeft", left: "ArrowRight", bottom: "ArrowUp", top: "ArrowDown" }[side];
    const shrink = { right: "ArrowRight", left: "ArrowLeft", bottom: "ArrowDown", top: "ArrowUp" }[side];
    if (e.key === grow) setDock({ size: size + 0.05 });
    else if (e.key === shrink) setDock({ size: size - 0.05 });
  };
  return (
    // biome-ignore lint/a11y/useSemanticElements: a draggable divider; <hr> can't take focus or be dragged
    <div
      className={`mapwin-divider mapwin-divider-${across ? "across" : "down"}`}
      role="separator"
      aria-orientation={across ? "vertical" : "horizontal"}
      aria-label={w.divider}
      aria-valuemin={MIN * 100}
      aria-valuemax={MAX * 100}
      aria-valuenow={Math.round(size * 100)}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    />
  );
}

const SIDES: Side[] = ["left", "top", "bottom", "right"];

function MapPanel({
  projectId,
  dock,
  side,
  narrow,
}: {
  projectId: string;
  dock: Dock;
  side: Side;
  narrow: boolean;
}) {
  const info = useQuery({
    queryKey: ["map", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "making" ? 1500 : false),
    meta: { quiet: true },
  });
  const m = info.data;
  const field = m?.fields.find((f) => f.id === dock.field) ?? m?.fields[0] ?? null;
  return (
    <div className="mapwin-in">
      <header className="mapwin-head">
        <b className="mapwin-title">🗺 {w.title}</b>
        {m?.status === "ready" && m.fields.length > 0 && (
          <FieldPick fields={m.fields} value={field?.id ?? null} onChange={(id) => setDock({ field: id })} />
        )}
        <span className="mapwin-tools">
          {!narrow &&
            SIDES.map((s) => (
              <Button
                key={s}
                className={`mapwin-side ${s === side ? "on" : ""}`}
                aria-label={w.dock({ side: s })}
                aria-pressed={s === side}
                onPress={() => setDock({ side: s })}
              >
                <span className={`mapwin-glyph mapwin-glyph-${s}`} aria-hidden="true" />
              </Button>
            ))}
          <CloseButton label={w.close} onPress={() => setDock({ open: false })} />
        </span>
      </header>
      {info.error ? (
        <p className="error mapwin-msg">{info.error.message}</p>
      ) : !m ? (
        <Waiting doing={w.loading} className="mapwin-msg" />
      ) : m.status === "none" ? (
        <p className="mapwin-msg">{w.none}</p>
      ) : m.status === "making" ? (
        <Waiting doing={w.making} className="mapwin-msg" />
      ) : m.status === "failed" ? (
        <p className="error mapwin-msg">{w.failed({ error: m.error ?? "" })}</p>
      ) : (
        <MapBody
          projectId={projectId}
          info={m}
          fieldId={field?.id ?? null}
          label={field?.label ?? ""}
          side={side}
          size={dock.size}
        />
      )}
    </div>
  );
}

function FieldPick({
  fields,
  value,
  onChange,
}: {
  fields: MapInfo["fields"];
  value: string | null;
  onChange: (id: string) => void;
}) {
  const list = (q: string) => fields.filter((f) => matches(f.label, q) || matches(f.file, q));
  const loaded = (q: string) => list(q).filter((f) => f.field);
  const others = (q: string) => list(q).filter((f) => !f.field);
  return (
    <Combo
      label={w.colourBy}
      hideLabel
      className="field choice mapwin-field"
      popoverClassName="popover choice-popover wiz-popover"
      selectedKey={value}
      onChange={onChange}
      count={(q) => [list(q).length, fields.length]}
      first={(q) => list(q)[0]?.id ?? null}
    >
      {(q) => (
        <>
          {loaded(q).length > 0 && (
            <ListBoxSection className="wiz-section">
              <Header className="wiz-section-head">{w.yourFields}</Header>
              {loaded(q).map((f) => (
                <ListBoxItem key={f.id} id={f.id} className="choice-item" textValue={f.label}>
                  <Marked text={f.label} query={q} />
                </ListBoxItem>
              ))}
            </ListBoxSection>
          )}
          {[...new Set(others(q).map((f) => f.file))].map((file) => (
            <ListBoxSection key={file} className="wiz-section">
              <Header className="wiz-section-head">{w.otherColumns({ file })}</Header>
              {others(q)
                .filter((f) => f.file === file)
                .map((f) => (
                  <ListBoxItem key={f.id} id={f.id} className="choice-item mono" textValue={f.label}>
                    <Marked text={f.label} query={q} />
                  </ListBoxItem>
                ))}
            </ListBoxSection>
          ))}
        </>
      )}
    </Combo>
  );
}

// ---------- What's drawn ----------

const bin = async (url: string) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return r.arrayBuffer();
};

function decode(b64: string): ArrayBuffer {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out.buffer;
}

type View = { w: number; s: number; e: number; n: number; mpp: number };
/** What's drawn for the view: cells of a size, or the parcels' shapes, for a box around the view. */
type Plan = { kind: "cells"; level: number; box: View } | { kind: "shapes"; box: View; ids: number[] };

function MapBody({
  projectId,
  info,
  fieldId,
  label,
  side,
  size,
}: {
  projectId: string;
  info: MapInfo;
  fieldId: string | null;
  label: string;
  side: Side;
  size: number;
}) {
  const base = `/api/projects/${encodeURIComponent(projectId)}/map`;
  const centres = useQuery({
    queryKey: ["map-centres", projectId, info.stamp],
    queryFn: async () => new Float32Array(await bin(`${base}/centres`)),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const col = useQuery({
    queryKey: ["map-column", projectId, info.stamp, fieldId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/map/column", {
          params: { path: { project_id: projectId }, query: { field: fieldId ?? "" } },
        }),
      ),
    enabled: !!fieldId,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const [plan, setPlan] = useState<Plan | null>(null);
  const shapes = useQuery({
    queryKey: ["map-shapes", projectId, info.stamp],
    queryFn: async () => readShapes(await bin(`${base}/shapes`)),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: plan?.kind === "shapes",
  });

  // The colour of each parcel (and its place 0..1 on the ramp, for a cell's average), from the field and its range.
  const linkKey = `map:${fieldId}`;
  const range = useRangeOf(linkKey, col.data);
  const paint = useMemo(() => painter(col.data, range), [col.data, range]);

  // Following the view: a new plan only when the view leaves the last one's box, or the zoom wants another size.
  const xy = centres.data;
  const xyNow = useRef(xy);
  useEffect(() => {
    xyNow.current = xy;
  }, [xy]);
  const planNow = useRef(plan);
  useEffect(() => {
    planNow.current = plan;
  }, [plan]);
  const lookNow = useRef<(() => void) | null>(null);
  const watch = useCallback((m: maplibregl.Map | null) => {
    if (!m) {
      lookNow.current = null;
      return;
    }
    let frame = 0;
    const look = () => {
      frame = 0;
      const all = xyNow.current;
      if (!all) return;
      const b = m.getBounds();
      const lat = (m.getCenter().lat * Math.PI) / 180;
      const v: View = {
        w: b.getWest(),
        s: b.getSouth(),
        e: b.getEast(),
        n: b.getNorth(),
        mpp: (40_075_016.686 * Math.cos(lat)) / (512 * 2 ** m.getZoom()),
      };
      const next = planFor(v, all, planNow.current);
      if (next !== planNow.current) {
        planNow.current = next;
        setPlan(next);
      }
    };
    lookNow.current = look;
    m.on("move", () => {
      if (!frame) frame = requestAnimationFrame(look);
    });
    m.on("resize", look);
    m.once("load", look);
  }, []);
  // The centres came after the map: plan now.
  useEffect(() => {
    if (xy) lookNow.current?.();
  }, [xy]);

  const layers = useMemo(() => {
    if (!xy || !plan) return [] as Layer[];
    if (plan.kind === "shapes" && shapes.data) {
      const data = toBinary(shapes.data, plan.ids);
      return [
        new GeoJsonLayer({
          id: "parcels",
          data: data as never,
          pickable: true,
          stroked: true,
          filled: true,
          lineWidthUnits: "pixels",
          getFillColor: (f) => paint.fill(parcelOf(f)),
          getLineColor: (f) => (paint.has(parcelOf(f)) ? [255, 255, 255, 200] : BLANK_LINE),
          getLineWidth: 0.5,
          updateTriggers: { getFillColor: paint, getLineColor: paint },
        }),
      ];
    }
    const level = plan.kind === "cells" ? plan.level : levelFor(plan.box.mpp);
    return [cellsLayer(xy, plan.box, level, paint)];
  }, [xy, plan, shapes.data, paint]);

  const bounds = (info.bounds as Bounds | null | undefined) ?? null;
  const tooltip = useCallback(
    (i: PickingInfo) => {
      const o = i.object as { n?: number; text?: string } | undefined;
      if (o && typeof o.n === "number") return w.cell({ n: o.n, what: o.text ?? "" });
      if (i.index >= 0 && plan?.kind === "shapes") return `${label}: ${paint.text(i.index)}`;
      return null;
    },
    [plan, paint, label],
  );
  return (
    <div className="mapwin-body">
      {centres.error && <p className="error mapwin-msg">{centres.error.message}</p>}
      <MapView
        className="mapwin-map"
        asked
        label={w.mapLabel}
        layers={layers}
        bounds={bounds}
        fitKey={info.stamp}
        resizeKey={`${side}-${size}`}
        onMap={watch}
        tooltip={tooltip}
      />
      <div className="mapwin-legend">
        {col.isPending && fieldId ? (
          <Waiting doing={w.reading} />
        ) : col.error ? (
          <p className="error">{col.error.message}</p>
        ) : col.data?.kind === "number" ? (
          <>
            <div className="mapwin-ramp" aria-hidden="true" />
            <RangedBars
              quantiles={col.data.quantiles}
              count={col.data.have}
              auto={col.data.auto}
              year={/year/i.test(label)}
              unit=""
              linkKey={linkKey}
              label={w.spread({ field: label })}
            />
          </>
        ) : col.data?.kind === "category" ? (
          <ul className="mapwin-cats">
            {col.data.categories.map((c, k) => (
              <li key={c}>
                <span className="mapwin-sw" style={{ background: CATS[k % CATS.length] }} />
                {c} <small>{col.data?.counts[k]?.toLocaleString()}</small>
              </li>
            ))}
            <li>
              <span className="mapwin-sw mapwin-sw-other" />
              {w.other}
            </li>
          </ul>
        ) : null}
        {plan && (
          <small className="mapwin-how">
            {plan.kind === "shapes"
              ? w.howShapes({ n: plan.ids.length })
              : w.howCells({ size: plan.level >= 1000 ? `${plan.level / 1000} km` : `${plan.level} m` })}
          </small>
        )}
      </div>
    </div>
  );
}

/** A binary feature's parcel (shapes.ts: each corner carries its parcel's index). */
function parcelOf(f: unknown): number {
  const p = (f as { properties?: { parcel?: number } }).properties?.parcel;
  return typeof p === "number" ? p : -1;
}

function levelFor(mpp: number): number {
  return [...LEVELS].reverse().find((s) => s / mpp >= CELL_PX) ?? LEVELS[0] ?? 8000;
}

/** The plan for this view: the last one while it still fits; otherwise shapes when few enough parcels are in a box
 * a quarter of the view's size bigger each side, or cells sized to the zoom. */
function planFor(v: View, xy: Float32Array, last: Plan | null): Plan {
  const level = levelFor(v.mpp);
  if (last) {
    const b = last.box;
    const inside = v.w >= b.w && v.e <= b.e && v.s >= b.s && v.n <= b.n;
    const sameZoom =
      last.kind === "shapes" ? b.mpp / v.mpp < 2.5 && v.mpp / b.mpp < 1.6 : last.level === level;
    if (inside && sameZoom) return last;
  }
  const dx = (v.e - v.w) / 4;
  const dy = (v.n - v.s) / 4;
  const box = { w: v.w - dx, e: v.e + dx, s: v.s - dy, n: v.n + dy, mpp: v.mpp };
  const ids: number[] = [];
  for (let i = 0; i < xy.length / 2; i++) {
    const x = xy[2 * i] ?? Number.NaN;
    const y = xy[2 * i + 1] ?? Number.NaN;
    if (x >= box.w && x <= box.e && y >= box.s && y <= box.n) {
      ids.push(i);
      if (ids.length > SHAPES_UPTO) return { kind: "cells", level, box };
    }
  }
  return { kind: "shapes", box, ids };
}

type Paint = {
  /** A parcel's colour. */
  fill: (i: number) => [number, number, number, number];
  /** Its place on the ramp (numbers, 0 to 1) or its category (0.., -1 another value); null blank. */
  at: (i: number) => number | null;
  has: (i: number) => boolean;
  text: (i: number) => string;
  kind: "number" | "category" | "none";
};

function ramp(t: number): [number, number, number, number] {
  const x = Math.min(0.9999, Math.max(0, t)) * (RAMP.length - 1);
  const k = Math.floor(x);
  const f = x - k;
  const a = RAMP[k] ?? [0, 0, 0];
  const b = RAMP[k + 1] ?? a;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 215];
}

function painter(c: MapColumn | undefined, range: { lo: number; hi: number } | null): Paint {
  if (c?.kind === "number" && range) {
    const v = new Float32Array(decode(c.values));
    const log = range.lo > 0 && range.hi / range.lo >= 100;
    const f = log ? Math.log10 : (x: number) => x;
    const lo = f(range.lo);
    const span = f(range.hi) - lo || 1;
    const at = (i: number) => {
      const x = v[i];
      return x === undefined || Number.isNaN(x) ? null : (f(log ? Math.max(x, range.lo) : x) - lo) / span;
    };
    return {
      kind: "number",
      at,
      has: (i) => at(i) !== null,
      fill: (i) => {
        const p = at(i);
        return p === null ? BLANK : ramp(p);
      },
      text: (i) => {
        const x = v[i];
        return x === undefined || Number.isNaN(x) ? w.blank : x.toLocaleString();
      },
    };
  }
  if (c?.kind === "category") {
    const codes = new Uint16Array(decode(c.values));
    const cols = CATS.map((x) => rgba(x, 0.85));
    const at = (i: number) => {
      const k = codes[i] ?? 65535;
      return k === 65535 ? null : k === 65534 ? -1 : k;
    };
    return {
      kind: "category",
      at,
      has: (i) => at(i) !== null,
      fill: (i) => {
        const k = at(i);
        return k === null ? BLANK : k < 0 ? OTHER : (cols[k % cols.length] ?? OTHER);
      },
      text: (i) => {
        const k = at(i);
        return k === null ? w.blank : k < 0 ? w.other : (c.categories[k] ?? "");
      },
    };
  }
  return {
    kind: "none",
    at: () => null,
    has: () => true,
    fill: () => [214, 210, 200, 200],
    text: () => "",
  };
}

type Cell = { polygon: [number, number][]; fill: [number, number, number, number]; n: number; text: string };

/** The parcels in the box, in cells of `level` metres: a cell's colour is its parcels' average place on the ramp
 * (numbers) or their most common category. */
function cellsLayer(xy: Float32Array, box: View, level: number, paint: Paint): Layer {
  const lat0 = (((box.s + box.n) / 2) * Math.PI) / 180;
  const dx = level / (111_320 * Math.cos(lat0));
  const dy = level / 110_540;
  const acc = new Map<string, { n: number; sum: number; have: number; cats: Map<number, number> }>();
  for (let i = 0; i < xy.length / 2; i++) {
    const x = xy[2 * i] ?? Number.NaN;
    const y = xy[2 * i + 1] ?? Number.NaN;
    if (!(x >= box.w && x <= box.e && y >= box.s && y <= box.n)) continue;
    const key = `${Math.floor(x / dx)}:${Math.floor(y / dy)}`;
    let c = acc.get(key);
    if (!c) {
      c = { n: 0, sum: 0, have: 0, cats: new Map() };
      acc.set(key, c);
    }
    c.n++;
    const a = paint.at(i);
    if (a === null) continue;
    c.have++;
    if (paint.kind === "number") c.sum += a;
    else c.cats.set(a, (c.cats.get(a) ?? 0) + 1);
  }
  const cells: Cell[] = [];
  for (const [key, c] of acc) {
    const [gx = 0, gy = 0] = key.split(":").map(Number);
    const x0 = gx * dx;
    const y0 = gy * dy;
    let fill: [number, number, number, number] = [214, 210, 200, 200];
    let text = "";
    if (paint.kind === "number" && c.have) {
      fill = ramp(c.sum / c.have);
    } else if (paint.kind === "category" && c.have) {
      const [top, k] = [...c.cats.entries()].sort((p, q) => q[1] - p[1])[0] ?? [-1, 0];
      fill = top < 0 ? OTHER : rgba(CATS[top % CATS.length] ?? "#999999", 0.85);
      text = w.mostly({ share: Math.round((100 * k) / c.have) });
    } else if (paint.kind !== "none") fill = [235, 235, 235, 160];
    cells.push({
      polygon: [
        [x0, y0],
        [x0 + dx, y0],
        [x0 + dx, y0 + dy],
        [x0, y0 + dy],
      ],
      fill,
      n: c.n,
      text,
    });
  }
  return new SolidPolygonLayer<Cell>({
    id: `cells-${level}`,
    data: cells,
    pickable: true,
    getPolygon: (c) => c.polygon,
    getFillColor: (c) => c.fill,
  });
}

/** The range chosen for the legend's histogram (the automatic one until it's set). */
function useRangeOf(key: string, c: MapColumn | undefined): { lo: number; hi: number } | null {
  const chosen = useChosenRange(key);
  if (chosen) return chosen;
  const [lo, hi] = c?.auto ?? [];
  return lo != null && hi != null ? { lo, hi } : null;
}

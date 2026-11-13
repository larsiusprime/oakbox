/** Time adjustment on the map (SPEC F6, §3.15: a take-over step): a group's sales where they are, coloured by their
 * price per area. **Prices in a window**: the sales in the window (dragged across the chart, or the time bar's; ▶
 * steps it on a month at a time) coloured, the rest faint; no window, every sale coloured. **Change**: squares
 * coloured by how far their median price per area moved from the first year of sales to the last, beside the
 * group's own index over the same time (grey: as the index; orange: faster; blue: slower). */
import type { PickingInfo } from "@deck.gl/core";
import { PolygonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { useQuery } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import type * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import { Choice } from "../components/Form";
import { boundsOf, MapView, rgba } from "../components/MapView";
import { Seg } from "../components/Seg";
import { LoadingBar } from "../components/Waiting";
import { levelFor } from "../lib/detail";
import { day, money, num, pct } from "../lib/format";
import { setTimeWindow, useTimeWindow } from "../lib/timewindow";
import { t } from "../wording";

const s = t.sales.time;
const m = s.map;
const units = t.sales.unit;
const DAY = 86_400_000;
const MONTH = 30.44 * DAY;
const YEAR = 365.25 * DAY;
/** A square needs this many sales in both its first and last year to say how it moved. */
const MIN_SALES = 8;
const RAMP: [number, number, number][] = [
  [255, 255, 204],
  [161, 218, 180],
  [65, 182, 196],
  [44, 127, 184],
  [37, 52, 148],
];
// Diverging, around the index: blue slower, grey as it, orange faster (±20 points at the ends).
const DIVERGE: [number, number, number][] = [
  [44, 123, 182],
  [171, 217, 233],
  [233, 230, 223],
  [253, 174, 97],
  [215, 25, 28],
];
const SPREAD = 0.2;
/** How solid a square is drawn for the sales it rests on: pale at MIN_SALES, solid at 100 (log between). */
const strength = (n: number) =>
  Math.round(70 + 170 * Math.min(1, Math.max(0, Math.log(n / MIN_SALES) / Math.log(100 / MIN_SALES))));

type Group = { id: string; name: string; color: string; per: "impr" | "land" | null };
export type Sale = { key: string; t: number; per: number; lon: number; lat: number };
type Cell = {
  polygon: [number, number][];
  diff: number;
  a: number;
  b: number;
  change: number;
  index: number;
};

const time = (d: string) => new Date(`${d}T00:00:00`).getTime();
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);

function median(xs: number[]): number {
  const a = [...xs].sort((x, y) => x - y);
  const k = Math.floor(a.length / 2);
  return a.length % 2 ? (a[k] ?? 0) : ((a[k - 1] ?? 0) + (a[k] ?? 0)) / 2;
}

function along(stops: [number, number, number][], p: number, alpha = 235): [number, number, number, number] {
  const x = Math.min(Math.max(p, 0), 1) * (stops.length - 1);
  const i = Math.min(Math.floor(x), stops.length - 2);
  const f = x - i;
  const a = stops[i] ?? [0, 0, 0];
  const b = stops[i + 1] ?? a;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, alpha];
}

export function TimeMap({
  projectId,
  groups,
  group,
  setGroup,
  currency,
}: {
  projectId: string;
  /** The groups with an index to show. */
  groups: Group[];
  group: Group;
  setGroup: (id: string) => void;
  currency: string;
}) {
  const q = useQuery({
    queryKey: ["clean-time", projectId, group.id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/time/{group}", {
          params: { path: { project_id: projectId, group: group.id } },
        }),
      ),
  });
  const [mode, setMode] = useState<"prices" | "change">("prices");
  const [months, setMonths] = useState("6");
  const [playing, setPlaying] = useState(false);
  const win = useTimeWindow();
  const d = q.data;
  const sales: Sale[] = useMemo(
    () =>
      (d?.sales ?? []).flatMap((x) =>
        x.lon != null && x.lat != null
          ? [{ key: x.key_sale, t: time(x.date), per: x.per_area, lon: x.lon, lat: x.lat }]
          : [],
      ),
    [d],
  );
  const t0 = sales.length ? Math.min(...sales.map((x) => x.t)) : 0;
  const t1 = sales.length ? Math.max(...sales.map((x) => x.t)) : 0;
  const mine = win && win.group === group.id ? win : null;
  const len = Number(months) * MONTH;

  // ▶: the window steps on a month at a time, from where it is (or the start) to the end.
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      const from = mine ? mine.from + MONTH : t0;
      if (from + len > t1 + MONTH) {
        setPlaying(false);
        return;
      }
      setTimeWindow({ group: group.id, from, to: from + len });
    }, 700);
    return () => window.clearInterval(id);
  }, [playing, mine, t0, t1, len, group.id]);

  // Colour by price per area: its place between the 5th and 95th percentiles, on a log scale (prices spread so).
  const sorted = useMemo(() => sales.map((x) => x.per).sort((a, b) => a - b), [sales]);
  const lo = Math.log(sorted[Math.floor(sorted.length * 0.05)] ?? 1);
  const hi = Math.log(sorted[Math.ceil(sorted.length * 0.95) - 1] ?? 2);
  const place = (v: number) => (Math.log(v) - lo) / (hi - lo || 1);

  // The squares can get as small as the map's own at this zoom (lib/detail.ts), where the sales allow.
  const [mpp, setMpp] = useState<number | null>(null);
  const finest = levelFor(mpp ?? 200);
  const cells = useMemo(
    () => (mode === "change" ? changeCells(sales, d?.index ?? [], t0, t1, finest) : null),
    [mode, sales, d, t0, t1, finest],
  );
  const watch = (map: maplibregl.Map | null) => {
    if (!map) return;
    const look = () => {
      const lat = (map.getCenter().lat * Math.PI) / 180;
      setMpp((40_075_016.686 * Math.cos(lat)) / (512 * 2 ** map.getZoom()));
    };
    map.on("zoomend", look);
    map.once("load", look);
  };

  const shown = mine ? sales.filter((x) => x.t >= mine.from && x.t <= mine.to) : sales;
  const faint = mine ? sales.filter((x) => x.t < mine.from || x.t > mine.to) : [];
  const layers =
    mode === "change"
      ? [
          new ScatterplotLayer<Sale>({
            id: "time-all",
            data: sales,
            radiusUnits: "pixels",
            getRadius: 1.5,
            getPosition: (x) => [x.lon, x.lat],
            getFillColor: [150, 150, 150, 120],
          }),
          new PolygonLayer<Cell>({
            id: "time-change",
            data: cells?.cells ?? [],
            pickable: true,
            getPolygon: (c) => c.polygon,
            // Paler the fewer sales it rests on (its first or last year, whichever has fewer): solid from 100.
            getFillColor: (c) =>
              along(DIVERGE, (c.diff + SPREAD) / (2 * SPREAD), strength(Math.min(c.a, c.b))),
            stroked: true,
            getLineColor: [255, 255, 255, 160],
            lineWidthUnits: "pixels",
            getLineWidth: 0.5,
          }),
        ]
      : [
          new ScatterplotLayer<Sale>({
            id: "time-faint",
            data: faint,
            radiusUnits: "pixels",
            getRadius: 2,
            getPosition: (x) => [x.lon, x.lat],
            getFillColor: [160, 158, 150, 140],
          }),
          new ScatterplotLayer<Sale>({
            id: "time-shown",
            data: shown,
            pickable: true,
            radiusUnits: "pixels",
            getRadius: 4,
            stroked: true,
            lineWidthUnits: "pixels",
            getLineWidth: 1,
            getLineColor: [40, 40, 40, 200],
            getPosition: (x) => [x.lon, x.lat],
            getFillColor: (x) => along(RAMP, place(x.per)),
            updateTriggers: { getFillColor: [lo, hi] },
          }),
        ];
  const bounds = useMemo(
    () => (sales.length ? boundsOf(sales.map((x) => [x.lon, x.lat] as const)) : null),
    [sales],
  );
  const area = units[d?.unit ?? "sqft"];
  const per = group.per === "land" ? s.perLand({ unit: area }) : s.perImpr({ unit: area });
  const tooltip = (i: PickingInfo) => {
    const o = i.object as (Sale & Partial<Cell>) | undefined;
    if (!o) return null;
    if (typeof o.diff === "number")
      return m.cellTip({
        a: num(o.a ?? 0),
        b: num(o.b ?? 0),
        change: signed(o.change ?? 0),
        index: signed(o.index ?? 0),
        diff: `${signed(o.diff)} ${o.diff >= 0 ? m.faster : m.slower}`,
      });
    return `${day(iso(o.t))} · ${money(o.per, currency)} ${per}`;
  };

  if (!d) return <LoadingBar error={q.error} />;
  const startAt = mine ? mine.from : t0;
  return (
    <div className="mapwin-body tm-wrap">
      <div className="mapwin-stage tm-stage">
        <MapView
          className="mapwin-map"
          asked
          label={m.label}
          layers={layers}
          bounds={bounds}
          fitKey={`${group.id}:${sales.length}`}
          tooltip={tooltip}
          onMap={watch}
          bare
        />
        <div className="tm-panel">
          <div className="tm-line">
            <Choice
              label={m.group}
              hideLabel
              value={group.id}
              options={groups.map((g) => [g.id, g.name] as const)}
              onChange={setGroup}
            />
          </div>
          <Seg<"prices" | "change">
            label={m.mode}
            value={mode}
            options={[
              ["prices", m.prices],
              ["change", m.change],
            ]}
            onChange={(v) => {
              setPlaying(false);
              setMode(v);
            }}
          />
          {!sales.length ? (
            <small className="tm-note">{m.noPlace}</small>
          ) : mode === "prices" ? (
            <>
              <div className="tm-ramp" aria-hidden="true" />
              <div className="tm-axis">
                <span>{money(Math.exp(lo), currency)}</span>
                <span>{per}</span>
                <span>{money(Math.exp(hi), currency)}</span>
              </div>
            </>
          ) : cells && cells.cells.length ? (
            <>
              <div className="tm-diverge" aria-hidden="true" />
              <div className="tm-axis">
                <span>−20 {m.slower}</span>
                <span>{m.asIndex}</span>
                <span>+20 {m.faster}</span>
              </div>
              <small className="tm-note">
                {m.changeFrom({
                  from: new Date(t0).getFullYear().toString(),
                  to: new Date(t1).getFullYear().toString(),
                  per,
                  index: signed(cells.index),
                })}{" "}
                {m.fewer({ n: MIN_SALES })}
              </small>
            </>
          ) : (
            <small className="tm-note">{m.noChange}</small>
          )}
        </div>
      </div>
      {mode === "prices" && sales.length > 0 && (
        <div className="tm-time">
          <Button
            className="tm-play"
            aria-label={playing ? m.pause : m.play}
            onPress={() => {
              if (!playing && (!mine || mine.from + len > t1))
                setTimeWindow({ group: group.id, from: t0, to: t0 + len });
              setPlaying(!playing);
            }}
          >
            {playing ? <Pause aria-hidden="true" size="1em" /> : <Play aria-hidden="true" size="1em" />}
          </Button>
          <input
            type="range"
            className="tm-range"
            aria-label={m.label}
            min={t0}
            max={Math.max(t0, t1 - len)}
            step={MONTH}
            value={Math.min(startAt, Math.max(t0, t1 - len))}
            onChange={(e) => {
              const from = Number(e.target.value);
              setPlaying(false);
              setTimeWindow({ group: group.id, from, to: from + len });
            }}
          />
          <span className="tm-when">
            {mine
              ? m.inWindow({ from: day(iso(mine.from)), to: day(iso(mine.to)), n: num(shown.length) })
              : m.everyDate({ n: num(sales.length) })}
          </span>
          <Choice
            label={m.length}
            hideLabel
            value={months}
            options={(["3", "6", "12"] as const).map((k) => [k, m.months({ n: Number(k) })] as const)}
            onChange={(k) => {
              setMonths(k);
              if (mine)
                setTimeWindow({ group: group.id, from: mine.from, to: mine.from + Number(k) * MONTH });
            }}
          />
          {mine && (
            <Button
              className="button button-small"
              onPress={() => {
                setPlaying(false);
                setTimeWindow(null);
              }}
            >
              {m.allDates}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

const signed = (x: number) => `${x >= 0 ? "+" : "−"}${pct(Math.abs(x))}`;

/** The largest squares, metres: each splits into four while every quarter with sales keeps MIN_SALES in both years. */
const ROOT = 16_000;

type Pt = { x: number; y: number; per: number; first: boolean };

/** Squares of the sales' first and last years (a quadtree): from ROOT metres, each split into four while every
 * quarter that has sales still has MIN_SALES in its first year and in its last, down to `finest` metres (the zoom's
 * own square size). Each kept square: its median price per area then and now, how far that moved, against the
 * group's index over the same years. Dense places get small squares, sparse ones stay large. */
export function changeCells(
  sales: Sale[],
  index: { day: string; value: number }[],
  t0: number,
  t1: number,
  finest: number,
): { cells: Cell[]; index: number } | null {
  if (sales.length === 0 || t1 - t0 < 1.5 * YEAR) return null;
  const firstEnd = t0 + YEAR;
  const lastStart = t1 - YEAR;
  const at = (a: number, b: number) => {
    const v = index.filter((p) => time(p.day) >= a && time(p.day) <= b).map((p) => p.value);
    return v.length ? v.reduce((x, y) => x + y, 0) / v.length : null;
  };
  const i0 = at(t0, firstEnd);
  const i1 = at(lastStart, t1);
  const idx = i0 && i1 ? i1 / i0 - 1 : 0;
  // Metres on a flat grid anchored at 0°, 0° (at the sales' middle latitude): the same squares whatever's shown.
  const lats = sales.map((x) => x.lat);
  const lat0 = ((Math.min(...lats) + Math.max(...lats)) / 2) * (Math.PI / 180);
  const kx = 111_320 * Math.cos(lat0);
  const ky = 110_540;
  const pts: Pt[] = [];
  for (const x of sales) {
    const first = x.t <= firstEnd;
    if (!first && x.t < lastStart) continue;
    pts.push({ x: x.lon * kx, y: x.lat * ky, per: x.per, first });
    if (first && x.t >= lastStart) pts.push({ x: x.lon * kx, y: x.lat * ky, per: x.per, first: false });
  }
  const enough = (ps: Pt[]) => {
    let a = 0;
    let b = 0;
    for (const p of ps) p.first ? a++ : b++;
    return a >= MIN_SALES && b >= MIN_SALES;
  };
  const cells: Cell[] = [];
  const keep = (x0: number, y0: number, size: number, ps: Pt[]) => {
    const a = ps.filter((p) => p.first).map((p) => p.per);
    const b = ps.filter((p) => !p.first).map((p) => p.per);
    if (a.length < MIN_SALES || b.length < MIN_SALES) return;
    const change = median(b) / median(a) - 1;
    const w = x0 / kx;
    const s0 = y0 / ky;
    const e = (x0 + size) / kx;
    const n = (y0 + size) / ky;
    cells.push({
      polygon: [
        [w, s0],
        [e, s0],
        [e, n],
        [w, n],
      ],
      a: a.length,
      b: b.length,
      change,
      index: idx,
      // How much more (or less) it moved than the index, relatively: +0.1, 10% beyond what the index brings.
      diff: (1 + change) / (1 + idx) - 1,
    });
  };
  const split = (x0: number, y0: number, size: number, ps: Pt[]) => {
    const half = size / 2;
    if (half >= finest) {
      const quarters: Pt[][] = [[], [], [], []];
      for (const p of ps) quarters[(p.x >= x0 + half ? 1 : 0) + (p.y >= y0 + half ? 2 : 0)]?.push(p);
      // Every quarter with sales must still say something; an empty one (water, a park) doesn't stop it.
      if (quarters.every((q) => q.length === 0 || enough(q))) {
        quarters.forEach((q, k) => {
          if (q.length) split(x0 + (k % 2) * half, y0 + (k >= 2 ? half : 0), half, q);
        });
        return;
      }
    }
    keep(x0, y0, size, ps);
  };
  const roots = new Map<string, { x0: number; y0: number; ps: Pt[] }>();
  for (const p of pts) {
    const x0 = Math.floor(p.x / ROOT) * ROOT;
    const y0 = Math.floor(p.y / ROOT) * ROOT;
    const k = `${x0},${y0}`;
    const r = roots.get(k) ?? { x0, y0, ps: [] };
    r.ps.push(p);
    roots.set(k, r);
  }
  for (const r of roots.values()) split(r.x0, r.y0, ROOT, r.ps);
  return { cells, index: idx };
}

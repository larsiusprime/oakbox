/** The VEI's chart as openratiostudy.com draws it, with a view by price beside it. By group: each percentile group's
 * ratios as a box (quartiles, whiskers at 1.5 IQR) with every sale a dot in its column. By price: every sale at its
 * price, each group's median drawn across the prices it spans. Either way, the sample median as a red dashed line,
 * the standard's range in green and, on request, each group's 90% interval and central tendency. A slider on the
 * left sets the ratios shown; buttons on the right show or hide each part. */
import { useQuery } from "@tanstack/react-query";
import { type PointerEvent as ReactPointerEvent, useRef, useState } from "react";
import { api, unwrap } from "../api/client";
import { Seg } from "../components/Seg";
import { CHART, ORS, TRIMMED } from "../lib/colours";
import { money } from "../lib/format";
import { useWidth } from "../lib/hooks";
import { t } from "../wording";

const v = t.ratio.veiChart;

export type VeiBox = {
  n: number;
  q1: number;
  median: number;
  q3: number;
  lo: number;
  hi: number;
  outliers: number[];
  price_low: number;
  price_high: number;
  points: number[][];
};
export type VeiBand = { n?: number; median?: number | null; low?: number | null; high?: number | null };

/** Each VEI group's ratios as boxes: by each sale's price level, and by its region's (when a region is given). */
export function useVeiBoxes(projectId: string, field: string, group: string, region = "") {
  return useQuery({
    queryKey: ["ratio-boxes", projectId, field, group, region],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/ratio/boxes", {
          params: { path: { project_id: projectId }, query: { field, group, region } },
        }),
      ),
  });
}

const H = 420;
const M = { t: 30, r: 80, b: 50, l: 60 };

/** "Quartile", "Decile": what openratiostudy.com calls a group, by how many there are. */
function groupWord(n: number): string {
  return n === 2 ? v.half : n === 4 ? v.quartile : n === 10 ? v.decile : v.group;
}

/** Round, readable gridlines between lo and hi: about six. */
function ticks(lo: number, hi: number): number[] {
  const raw = (hi - lo) / 6;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) ?? 10) * mag;
  const out: number[] = [];
  for (let x = Math.ceil(lo / step) * step; x <= hi + step * 1e-9; x += step)
    out.push(Math.round(x / step) * step);
  return out;
}

/** Prices on a log scale: 1, 2 and 5 of each power of ten, fewer when they'd crowd. */
function priceTicks(lo: number, hi: number, room: number): number[] {
  const all: number[] = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
    for (const m of [1, 2, 5]) {
      const x = m * 10 ** e;
      if (x >= lo && x <= hi) all.push(x);
    }
  return all.length * 64 > room ? all.filter((x) => String(x).startsWith("1")) : all;
}

/** A dot's place across its group's column: spread, the same every time. */
const jitter = (i: number) => (((i * 2654435761) >>> 0) % 1000) / 1000 - 0.5;

const fmt = (x: number) => (Math.abs(x) >= 100 ? x.toFixed(0) : x.toFixed(2));

type Part = "dots" | "boxes" | "median" | "target" | "ci" | "ct" | "trimmed";

export function VeiChart({
  boxes,
  bands,
  median,
  label,
  target,
  trimmed = [],
  currency,
}: {
  /** Each group's ratios; empty when they weren't kept (the bands are drawn on their own then). */
  boxes: VeiBox[];
  /** Each group's median and its 90% interval, from the study. */
  bands: VeiBand[];
  /** The sample's median ratio. */
  median: number | null | undefined;
  /** What the chart shows, for screen readers. */
  label: string;
  /** The level the standard asks for, when one judges these sales. */
  target?: [number, number] | null;
  /** The sales trimmed: grey, by price. */
  trimmed?: number[][];
  /** Given: the view by price can be chosen too. */
  currency?: string;
}) {
  const [ref, W] = useWidth<SVGSVGElement>(640, 280);
  const G = Math.max(boxes.length, bands.length);
  const hasBoxes = boxes.length > 0;
  const [view, setView] = useState<"group" | "price">("group");
  const byPrice = view === "price" && hasBoxes && !!currency;
  // As openratiostudy.com: the boxes and the median shown, the intervals not; with no boxes, the intervals instead.
  const [chosen, setChosen] = useState<Partial<Record<Part, boolean>>>({});
  const show: Record<Part, boolean> = {
    dots: true,
    boxes: true,
    median: true,
    target: true,
    ci: !hasBoxes,
    ct: !hasBoxes,
    trimmed: true,
    ...chosen,
  };

  // The y range: every ratio, and by default the widest whiskers with every median, interval and the standard's
  // range in view. The slider reaches 0 below and 2 above (1 is a value at its price), further when ratios do.
  const all = [
    ...boxes.flatMap((b) => [b.lo, b.hi, ...b.outliers]),
    ...bands.flatMap((b) => [b.low, b.high, b.median]),
  ].filter((x): x is number => x != null && Number.isFinite(x));
  const fullMin = all.length ? Math.min(...all) : 0;
  const fullMax = all.length ? Math.max(...all) : 2;
  const near = [
    ...boxes.flatMap((b) => [b.lo, b.hi]),
    ...bands.flatMap((b) => [b.low, b.high]),
    ...(median != null ? [median] : []),
    ...(target ?? []),
  ].filter((x): x is number => x != null && Number.isFinite(x));
  const wLo = near.length ? Math.min(...near) : fullMin;
  const wHi = near.length ? Math.max(...near) : fullMax;
  const pad = (wHi - wLo) * 0.05 || 0.05;
  const sMin = Math.min(0, fullMin);
  const sMax = Math.max(2, fullMax);
  let defLo = Math.max(sMin, wLo - pad);
  let defHi = Math.min(sMax, wHi + pad);
  if (defHi <= defLo) {
    defLo = sMin;
    defHi = sMax;
  }
  const [range, setRange] = useState<[number, number] | null>(null);
  const [lo, hi] = range ?? [defLo, defHi];

  if (G < 2) return null;

  const x0 = M.l;
  const x1 = W - M.r;
  const y0 = M.t;
  const y1 = H - M.b;
  const slot = (x1 - x0) / G;
  const cx = (k: number) => x0 + slot * (k + 0.5);
  const y = (r: number) => y1 - ((r - lo) / (hi - lo || 1)) * (y1 - y0);
  const bw = Math.min(slot * 0.5, 120);
  const word = groupWord(G);
  const name = (k: number) => `${word} ${k + 1}`;
  const clip = `vei-clip-${label.length}-${G}`;
  const toggle = (k: Part) => setChosen((c) => ({ ...c, [k]: !show[k] }));

  // By price: a log scale across every sale, the trimmed too.
  const prices = [
    ...boxes.flatMap((b) => [b.price_low, b.price_high]),
    ...(show.trimmed ? trimmed.map((x) => x[0] ?? 0) : []),
  ].filter((x) => x > 0);
  // A margin either side, so the cheapest and dearest sales aren't cut by the edge.
  const pMin = prices.length ? Math.log10(Math.min(...prices)) : 0;
  const pMax = prices.length ? Math.log10(Math.max(...prices)) : 1;
  const pPad = (pMax - pMin) * 0.03 || 0.05;
  const pLo = pMin - pPad;
  const pHi = pMax + pPad;
  const px = (p: number) => x0 + ((x1 - x0) * (Math.log10(Math.max(p, 1)) - pLo)) / (pHi - pLo || 1);
  const spanMid = (b: VeiBox) => 10 ** ((Math.log10(b.price_low) + Math.log10(b.price_high)) / 2);
  const at = (k: number) => {
    const b = boxes[k];
    return byPrice && b ? px(spanMid(b)) : cx(k);
  };

  return (
    <div className="vei-wrap">
      {currency && hasBoxes && (
        <div className="vei-view">
          <Seg
            label={v.view}
            value={view}
            options={[
              ["group", v.byGroup],
              ["price", v.byPrice],
            ]}
            onChange={setView}
          />
        </div>
      )}
      <div className="vei">
        <YSlider
          lo={lo}
          hi={hi}
          min={sMin}
          max={sMax}
          top={M.t}
          bottom={M.b}
          onChange={(a, b) => setRange([a, b])}
          onReset={() => setRange(null)}
        />
        <svg
          ref={ref}
          className="vei-plot"
          viewBox={`0 0 ${W} ${H}`}
          height={H}
          role="img"
          aria-label={label}
        >
          <defs>
            <clipPath id={clip}>
              <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} />
            </clipPath>
          </defs>
          <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="#ffffff" />
          {ticks(lo, hi).map((tk) => (
            <g key={tk}>
              <line x1={x0} x2={x1} y1={y(tk)} y2={y(tk)} stroke={ORS.grid} />
              <text x={x0 - 6} y={y(tk) + 4} fontSize="12" textAnchor="end" fill={ORS.ink}>
                {fmt(tk)}
              </text>
            </g>
          ))}
          <text
            x={16}
            y={(y0 + y1) / 2}
            fontSize="14"
            fill={ORS.ink}
            textAnchor="middle"
            transform={`rotate(-90 16 ${(y0 + y1) / 2})`}
          >
            {v.ratio}
          </text>
          {byPrice
            ? priceTicks(10 ** pLo, 10 ** pHi, x1 - x0).map((p) => (
                <text key={p} x={px(p)} y={y1 + 18} fontSize="12" textAnchor="middle" fill={ORS.ink}>
                  {new Intl.NumberFormat(undefined, {
                    style: "currency",
                    currency: currency ?? "USD",
                    notation: "compact",
                  }).format(p)}
                </text>
              ))
            : Array.from({ length: G }, (_, k) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
                <text key={k} x={cx(k)} y={y1 + 18} fontSize="12" textAnchor="middle" fill={ORS.ink}>
                  {slot < 84 ? k + 1 : name(k)}
                </text>
              ))}
          <text x={(x0 + x1) / 2} y={H - 8} fontSize="14" textAnchor="middle" fill={ORS.ink}>
            {byPrice ? v.salePrice : word}
          </text>
          <g clipPath={`url(#${clip})`}>
            {show.target && target && (
              <rect
                x={x0}
                y={y(target[1])}
                width={x1 - x0}
                height={Math.max(0, y(target[0]) - y(target[1]))}
                fill={CHART.band}
              >
                <title>{v.targetTip({ low: target[0], high: target[1] })}</title>
              </rect>
            )}
            {byPrice &&
              show.trimmed &&
              show.dots &&
              trimmed.map(([p = 0, r = 0], i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: sales have no key here
                <circle key={i} cx={px(p)} cy={y(r)} r="2.4" fill={TRIMMED.line} opacity="0.6">
                  <title>{v.trimmedTip({ price: money(p, currency ?? "USD"), ratio: r.toFixed(3) })}</title>
                </circle>
              ))}
            {show.dots &&
              boxes.map((b, k) =>
                b.points.map(([p = 0, r = 0], i) => (
                  <circle
                    // biome-ignore lint/suspicious/noArrayIndexKey: sales have no key here
                    key={`${k}-${i}`}
                    cx={byPrice ? px(p) : cx(k) + jitter(i) * bw * 0.9}
                    cy={y(r)}
                    r={byPrice ? 2.4 : 2.2}
                    fill={ORS.boxMarker}
                    opacity={byPrice ? 0.55 : 0.45}
                  >
                    <title>
                      {v.saleTip({ group: name(k), price: money(p, currency ?? "USD"), ratio: r.toFixed(3) })}
                    </title>
                  </circle>
                )),
              )}
            {!byPrice &&
              show.boxes &&
              boxes.map((b, k) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
                <g key={k}>
                  <title>
                    {v.boxTip({
                      group: name(k),
                      n: b.n,
                      hi: b.hi.toFixed(4),
                      q3: b.q3.toFixed(4),
                      median: b.median.toFixed(4),
                      q1: b.q1.toFixed(4),
                      lo: b.lo.toFixed(4),
                    })}
                  </title>
                  <line
                    x1={cx(k)}
                    x2={cx(k)}
                    y1={y(b.q3)}
                    y2={y(b.hi)}
                    stroke={ORS.boxLine}
                    strokeWidth="2"
                  />
                  <line
                    x1={cx(k)}
                    x2={cx(k)}
                    y1={y(b.q1)}
                    y2={y(b.lo)}
                    stroke={ORS.boxLine}
                    strokeWidth="2"
                  />
                  {[b.hi, b.lo].map((e) => (
                    <line
                      key={e}
                      x1={cx(k) - bw / 4}
                      x2={cx(k) + bw / 4}
                      y1={y(e)}
                      y2={y(e)}
                      stroke={ORS.boxLine}
                      strokeWidth="2"
                    />
                  ))}
                  <rect
                    x={cx(k) - bw / 2}
                    y={y(b.q3)}
                    width={bw}
                    height={Math.max(0, y(b.q1) - y(b.q3))}
                    fill={ORS.boxFill}
                    stroke={ORS.boxLine}
                    strokeWidth="2"
                  />
                  <line
                    x1={cx(k) - bw / 2}
                    x2={cx(k) + bw / 2}
                    y1={y(b.median)}
                    y2={y(b.median)}
                    stroke={ORS.boxLine}
                    strokeWidth="2"
                  />
                  {!show.dots &&
                    b.outliers.map((o, j) => (
                      <circle
                        // biome-ignore lint/suspicious/noArrayIndexKey: ratios repeat
                        key={j}
                        cx={cx(k)}
                        cy={y(o)}
                        r="2.5"
                        fill={ORS.boxMarker}
                        opacity="0.8"
                      >
                        <title>{o.toFixed(4)}</title>
                      </circle>
                    ))}
                </g>
              ))}
            {byPrice &&
              boxes.map((b, k) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
                <g key={k}>
                  <title>
                    {v.spanTip({
                      group: name(k),
                      n: b.n,
                      low: money(b.price_low, currency ?? "USD"),
                      high: money(b.price_high, currency ?? "USD"),
                      median: b.median.toFixed(4),
                    })}
                  </title>
                  <line
                    x1={px(b.price_low)}
                    x2={px(b.price_high)}
                    y1={y(b.median)}
                    y2={y(b.median)}
                    stroke={ORS.span}
                    strokeWidth="3"
                  />
                  <text
                    x={px(b.price_low)}
                    y={y(b.median) - 5}
                    fontSize="11"
                    fill={ORS.span}
                    fontWeight="600"
                  >
                    {k + 1}
                  </text>
                </g>
              ))}
            {show.median && median != null && (
              <line
                x1={x0}
                x2={x1}
                y1={y(median)}
                y2={y(median)}
                stroke={ORS.median}
                strokeWidth="1.5"
                strokeDasharray="6 4"
              />
            )}
            {show.ci &&
              bands.map((b, k) =>
                b.median == null || b.low == null || b.high == null ? null : (
                  // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
                  <g key={k}>
                    <title>
                      {v.ciTip({
                        group: name(k),
                        median: b.median.toFixed(4),
                        low: b.low.toFixed(4),
                        high: b.high.toFixed(4),
                      })}
                    </title>
                    <line
                      x1={at(k)}
                      x2={at(k)}
                      y1={y(b.low)}
                      y2={y(b.high)}
                      stroke={ORS.ci}
                      strokeWidth="2.5"
                    />
                    {[b.low, b.high].map((e) => (
                      <line
                        key={e}
                        x1={at(k) - 10}
                        x2={at(k) + 10}
                        y1={y(e)}
                        y2={y(e)}
                        stroke={ORS.ci}
                        strokeWidth="2.5"
                      />
                    ))}
                    <line
                      x1={at(k) - 5}
                      x2={at(k) + 5}
                      y1={y(b.median)}
                      y2={y(b.median)}
                      stroke={ORS.boxLine}
                      strokeWidth="2"
                    />
                  </g>
                ),
              )}
            {show.ct &&
              bands.map((b, k) => {
                if (b.median == null) return null;
                const c = at(k);
                const m = y(b.median);
                return (
                  <polygon
                    // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
                    key={k}
                    points={`${c},${m - 6} ${c + 6},${m} ${c},${m + 6} ${c - 6},${m}`}
                    fill="#ffffff"
                    stroke={ORS.boxLine}
                    strokeWidth="1.5"
                  >
                    <title>{v.ctTip({ group: name(k), median: b.median.toFixed(4) })}</title>
                  </polygon>
                );
              })}
          </g>
          {show.median && median != null && y(median) >= y0 && y(median) <= y1 && (
            <text x={x1 + 6} y={y(median) - 12} fontSize="11" fill={ORS.median}>
              <tspan x={x1 + 6}>{v.sample}</tspan>
              <tspan x={x1 + 6} dy="13">
                {v.median}
              </tspan>
              <tspan x={x1 + 6} dy="13">
                {median.toFixed(4)}
              </tspan>
            </text>
          )}
        </svg>
        <div className="vei-keys" style={{ paddingTop: M.t }}>
          <div className="vei-keys-head">{v.toggle}</div>
          {hasBoxes && (
            <Key on={show.dots} colour={ORS.boxMarker} onPress={() => toggle("dots")}>
              {v.dots}
            </Key>
          )}
          {hasBoxes && !byPrice && (
            <Key on={show.boxes} colour={ORS.boxDot} onPress={() => toggle("boxes")}>
              {v.boxes}
            </Key>
          )}
          {byPrice && trimmed.length > 0 && (
            <Key on={show.trimmed} colour={TRIMMED.line} onPress={() => toggle("trimmed")}>
              {v.trimmed}
            </Key>
          )}
          <Key on={show.median} colour={ORS.median} onPress={() => toggle("median")}>
            {v.sampleMedian}
          </Key>
          {target && (
            <Key on={show.target} colour={ORS.target} onPress={() => toggle("target")}>
              {v.target}
            </Key>
          )}
          <Key on={show.ci} colour={ORS.ciDot} onPress={() => toggle("ci")}>
            {v.ci}
          </Key>
          <Key on={show.ct} colour={ORS.boxLine} onPress={() => toggle("ct")}>
            {v.ct}
          </Key>
          <div className="vei-keys-note">{v.rangeHint}</div>
        </div>
      </div>
    </div>
  );
}

function Key({
  on,
  colour,
  onPress,
  children,
}: {
  on: boolean;
  colour: string;
  onPress: () => void;
  children: string;
}) {
  return (
    <button type="button" className={on ? "vei-key on" : "vei-key"} aria-pressed={on} onClick={onPress}>
      <span className="vei-dot" style={{ background: colour }} aria-hidden="true" />
      {children}
    </button>
  );
}

/** The y range: a track with a handle at each end of the range shown. Drag a handle, or click it and type; a
 * double click on the track shows the default range again. */
function YSlider({
  lo,
  hi,
  min,
  max,
  top,
  bottom,
  onChange,
  onReset,
}: {
  lo: number;
  hi: number;
  min: number;
  max: number;
  top: number;
  bottom: number;
  onChange: (lo: number, hi: number) => void;
  onReset: () => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const span = max - min || 1;
  const gap = span * 0.01;
  const frac = (x: number) => (x - min) / span;
  const set = (which: "lo" | "hi", x: number) => {
    if (!Number.isFinite(x)) return;
    if (which === "hi") onChange(lo, Math.min(max, Math.max(x, lo + gap)));
    else onChange(Math.max(min, Math.min(x, hi - gap)), hi);
  };
  return (
    <div className="vei-slider" style={{ paddingTop: top, paddingBottom: bottom }}>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: a mouse shortcut; Reset is the handles' Escape and typing */}
      <div
        ref={track}
        className="vei-track"
        title={v.rangeHint}
        onDoubleClick={(e) => {
          if (e.target === e.currentTarget || (e.target as HTMLElement).classList.contains("vei-fill"))
            onReset();
        }}
      >
        <div className="vei-fill" style={{ top: `${(1 - frac(hi)) * 100}%`, bottom: `${frac(lo) * 100}%` }} />
        <Handle which="hi" at={hi} pos={1 - frac(hi)} track={track} min={min} span={span} set={set} />
        <Handle which="lo" at={lo} pos={1 - frac(lo)} track={track} min={min} span={span} set={set} />
      </div>
    </div>
  );
}

function Handle({
  which,
  at,
  pos,
  track,
  min,
  span,
  set,
}: {
  which: "lo" | "hi";
  at: number;
  pos: number;
  track: React.RefObject<HTMLDivElement | null>;
  min: number;
  span: number;
  set: (which: "lo" | "hi", x: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);
  const down = (e: ReactPointerEvent<HTMLInputElement>) => {
    if (draft != null) return; // typing: the field behaves as a field
    e.preventDefault();
    const start = e.clientY;
    let moved = false;
    const move = (m: PointerEvent) => {
      if (!moved && Math.abs(m.clientY - start) < 3) return;
      moved = true;
      const r = track.current?.getBoundingClientRect();
      if (!r) return;
      const f = Math.max(0, Math.min(1, 1 - (m.clientY - r.top) / r.height));
      set(which, min + f * span);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (!moved) {
        setDraft(fmt(at));
        requestAnimationFrame(() => input.current?.select());
      }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const commit = () => {
    if (draft != null && !cancelled.current) set(which, Number.parseFloat(draft.replace(/,/g, "")));
    cancelled.current = false;
    setDraft(null);
  };
  return (
    <input
      ref={input}
      className={`vei-handle vei-${which}`}
      style={{ top: `${pos * 100}%` }}
      type="text"
      inputMode="decimal"
      aria-label={which === "hi" ? v.top : v.bottom}
      value={draft ?? fmt(at)}
      onPointerDown={down}
      onFocus={() => draft == null && setDraft(fmt(at))}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.currentTarget.blur();
        } else if (e.key === "Escape") {
          e.preventDefault();
          cancelled.current = true;
          e.currentTarget.blur();
        }
      }}
    />
  );
}

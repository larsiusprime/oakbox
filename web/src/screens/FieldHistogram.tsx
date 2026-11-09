/** How a number field's values spread, as loaded (Big five: sizes in the project's unit, years), with the range shown
 * set live (2026-11-08): two handles under the bars and From/To boxes. It starts on the automatic range (the middle
 * half of the values and three times its width each side), so a crowd at one end (Guilford's farms) doesn't flatten
 * the rest. The bars are worked out here from the field's values at every 0.2% (sent once), so they follow a handle
 * as it's dragged. 🔗 Linked: a field's 🌐 Parcel universe and 💰 Sales record histograms share one range, bar for bar.
 * Only the view: nothing in the data changes. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Button } from "react-aria-components";
import { api, unwrap, type WizardField } from "../api/client";
import { num } from "../lib/format";
import { t } from "../wording";

const h = t.wizard.histogram;
const BINS = 24;
type Range = { lo: number; hi: number };
type Side = "pu" | "sr";
type Extent = { auto: Range; min: number; max: number };

/** A whole number or a short decimal, as a bin's edge is labelled ("1,200", "0.25"); a year as it's written. */
function edge(v: number, year: boolean): string {
  if (year) return String(Math.round(v));
  return v.toLocaleString(undefined, { maximumFractionDigits: v < 10 ? 2 : 0 });
}

// ---------- The ranges chosen, per field (shared by its two histograms while linked), for this visit ----------

// One immutable snapshot, replaced on every change: what React (and its compiler's memoizing) reads.
type Store = { chosen: Map<string, Range>; unlinked: Set<string>; extents: Map<string, Extent> };
let store: Store = { chosen: new Map(), unlinked: new Set(), extents: new Map() };
const listeners = new Set<() => void>();
const update = (f: (s: Store) => Partial<Store>) => {
  store = { ...store, ...f(store) };
  for (const l of listeners) l();
};
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
const withMap = <K, V>(m: Map<K, V>, k: K, v: V | null) => {
  const n = new Map(m);
  if (v === null) n.delete(k);
  else n.set(k, v);
  return n;
};

function useRange(key: string, side: Side, own: Extent | null) {
  const snap = useSyncExternalStore(subscribe, () => store);
  // Its extent recorded as it's drawn (the other histogram of the field is told only when it changes), and taken
  // back when it goes.
  const slot = `${key}:${side}`;
  if (own && JSON.stringify(snap.extents.get(slot)) !== JSON.stringify(own)) {
    queueMicrotask(() => update((s) => ({ extents: withMap(s.extents, slot, own) })));
  }
  useEffect(() => () => update((s) => ({ extents: withMap(s.extents, slot, null) })), [slot]);
  const linked = !snap.unlinked.has(key);
  const id = linked ? key : `${key}:${side}`;
  // Linked: the two histograms' extents together, so one range fits both.
  const mine = snap.extents.get(slot) ?? own;
  const both = linked
    ? [snap.extents.get(`${key}:pu`), snap.extents.get(`${key}:sr`)].filter((x): x is Extent => !!x)
    : mine
      ? [mine]
      : [];
  const ext: Extent | null = both.length
    ? {
        auto: { lo: Math.min(...both.map((x) => x.auto.lo)), hi: Math.max(...both.map((x) => x.auto.hi)) },
        min: Math.min(...both.map((x) => x.min)),
        max: Math.max(...both.map((x) => x.max)),
      }
    : null;
  const chosen = snap.chosen.get(id);
  return {
    ext,
    // The other dataset's histogram of this field is on the page too: linking means something.
    partner: snap.extents.has(`${key}:${side === "pu" ? "sr" : "pu"}`),
    range: chosen ?? ext?.auto ?? null,
    isAuto: chosen === undefined,
    linked,
    set: (r: Range | null) => update((s) => ({ chosen: withMap(s.chosen, id, r) })),
    // Unlinked, each keeps the range they shared; linked again, they share this one's: nothing jumps.
    setLinked: (on: boolean) =>
      update((s) => {
        const u = new Set(s.unlinked);
        let c = s.chosen;
        if (on) {
          u.delete(key);
          c = withMap(c, key, s.chosen.get(`${key}:${side}`) ?? null);
        } else {
          u.add(key);
          const shared = s.chosen.get(key) ?? null;
          c = withMap(withMap(c, `${key}:pu`, shared), `${key}:sr`, shared);
        }
        return { unlinked: u, chosen: c };
      }),
  };
}

/** The range chosen for a field's 🌐 histogram (shared while linked), or null while it's the automatic one: what
 * the map window colours by. */
export function useChosenRange(key: string): Range | null {
  const snap = useSyncExternalStore(subscribe, () => store);
  return snap.chosen.get(snap.unlinked.has(key) ? `${key}:pu` : key) ?? null;
}

/** Bars over [lo, hi] from the values at every 0.2%: each 0.2% of the values spread evenly between its two points. */
function barsFrom(
  q: number[],
  count: number,
  r: Range,
  year: boolean,
): { low: number; high: number; n: number }[] {
  const width = year ? Math.max(1, Math.ceil((r.hi - r.lo + 1) / BINS)) : (r.hi - r.lo) / BINS || 1;
  const start = year ? Math.floor(r.lo) : r.lo;
  const nb = year ? Math.max(1, Math.ceil((Math.floor(r.hi) + 1 - start) / width)) : BINS;
  const bars = Array.from({ length: nb }, (_, i) => ({
    low: start + i * width,
    high: start + (i + 1) * width,
    n: 0,
  }));
  const end = start + nb * width;
  const mass = count / Math.max(1, q.length - 1);
  const at = (v: number) => Math.min(nb - 1, Math.floor((v - start) / width));
  for (let i = 0; i + 1 < q.length; i++) {
    const a = q[i] ?? 0;
    const b = q[i + 1] ?? a;
    if (b <= a) {
      const bar = bars[at(a)];
      if (bar && a >= start && a <= (year ? end : r.hi)) bar.n += mass;
      continue;
    }
    for (let k = Math.max(0, at(a)); k <= Math.min(nb - 1, at(b)); k++) {
      const bar = bars[k];
      if (!bar) continue;
      const overlap = Math.min(b, bar.high, year ? end : r.hi) - Math.max(a, bar.low, start);
      if (overlap > 0) bar.n += (mass * overlap) / (b - a);
    }
  }
  return bars;
}

export function FieldHistogram({
  projectId,
  field,
  sale,
  sales = false,
  bare = false,
  pair = false,
}: {
  projectId: string;
  field: WizardField;
  /** Inside a dataset's capsule (🌐 or 💰): no frame or title of its own. */
  bare?: boolean;
  /** The sales record's: the sales file's column, as it's loaded there (the cache key: its column and unit). */
  sale?: { column: string; unit: string | null };
  /** Beside the other dataset's histogram of the same field: 🔗 linked offered. */
  pair?: boolean;
  /** A sales record field on its own page (Sale price): read from the sales file, in a frame of its own. */
  sales?: boolean;
}) {
  const source = sale ? { file: "sales", column: sale.column } : field.sources[0];
  const q = useQuery({
    queryKey: [
      "histogram",
      projectId,
      field.key,
      source?.file,
      source?.column,
      sale ? sale.unit : field.area_unit,
      field.number_format ?? null,
    ],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/fields/{key}/histogram", {
          params: { path: { project_id: projectId, key: field.key }, query: { sales: !!sale || sales } },
        }),
      ),
    enabled: !!source,
    placeholderData: keepPreviousData,
  });
  const v = q.data;
  if (!source || !v || (v.quantiles ?? []).length < 2) return null;
  return (
    <div className={sale || bare ? "fh-in" : "frame qc-panel"}>
      {!sale && !bare && <h3 className="wiz-group">{h.title({ name: field.name })}</h3>}
      <RangedBars
        quantiles={v.quantiles ?? []}
        count={v.total - v.empty}
        auto={v.auto ?? []}
        year={v.year}
        unit={v.unit}
        prefix={v.prefix ?? ""}
        linkKey={field.key}
        side={sale || sales ? "sr" : "pu"}
        pair={pair}
        label={h.title({ name: field.name })}
      />
    </div>
  );
}

/** A spread drawn from a column's values at every 0.2% (`quantiles`: smallest to largest), on the range shown: the
 * automatic one to start (`auto`), set live with the handles or typed. `linkKey` and `side`: which range it shares
 * (a field's 🌐 and 💰 histograms, while linked). Used by a field's capsules, Inputs' field details and Sale price. */
export function RangedBars({
  quantiles: qs,
  count,
  auto,
  year,
  unit,
  prefix = "",
  linkKey,
  side = "pu",
  pair = false,
  label,
}: {
  quantiles: number[];
  count: number;
  auto: number[];
  year: boolean;
  /** After an amount ("sq ft"); "" for none. */
  unit: string;
  /** Before an amount ("$"). */
  prefix?: string;
  linkKey: string;
  side?: Side;
  pair?: boolean;
  label: string;
}) {
  const [autoLo, autoHi] = auto;
  const own: Extent | null =
    qs.length > 1 && autoLo != null && autoHi != null
      ? { auto: { lo: autoLo, hi: autoHi }, min: qs[0] ?? autoLo, max: qs[qs.length - 1] ?? autoHi }
      : null;
  const r = useRange(linkKey, side, own);
  if (!r.range || !r.ext || qs.length < 2) return null;
  const after = unit ? ` ${unit}` : "";
  const show = (x: number) => `${prefix}${edge(x, year)}`;
  const bars = barsFrom(qs, count, r.range, year);
  const top = Math.max(1, ...bars.map((b) => b.n));
  const every = Math.max(1, Math.ceil(bars.length / 6));
  return (
    <>
      <div className="fh-chart" role="img" aria-label={label}>
        {bars.map((b) => (
          <span
            key={b.low}
            className="fh-bar"
            style={{ height: `${(100 * b.n) / top}%` }}
            title={`${show(b.low)}–${show(b.high)}${after}: ${num(Math.round(b.n))}`}
          />
        ))}
      </div>
      <div className="fh-axis" style={{ gridTemplateColumns: `repeat(${bars.length}, 1fr)` }}>
        {bars.map((b, i) => (
          <span key={b.low}>{i % every === 0 ? show(b.low) : ""}</span>
        ))}
      </div>
      <RangeControls r={r} year={year} unit={unit} prefix={prefix} pair={pair} />
    </>
  );
}

/** Two handles on a track over the field's whole range (spaced by order of magnitude for sizes spanning a hundredfold
 * or more), and the bounds typed. */
function RangeControls({
  r,
  year,
  unit,
  prefix,
  pair,
}: {
  r: ReturnType<typeof useRange>;
  year: boolean;
  unit: string;
  prefix: string;
  pair: boolean;
}) {
  const ext = r.ext as Extent;
  const range = r.range as Range;
  const log = !year && ext.min > 0 && ext.max / ext.min >= 100;
  const lmin = Math.log10(Math.max(ext.min, 1e-9));
  const lmax = Math.log10(Math.max(ext.max, 1e-9));
  const toPos = (x: number) =>
    log
      ? (1000 * (Math.log10(Math.max(x, ext.min)) - lmin)) / (lmax - lmin || 1)
      : (1000 * (x - ext.min)) / (ext.max - ext.min || 1);
  const fromPos = (p: number) =>
    log ? 10 ** (lmin + ((lmax - lmin) * p) / 1000) : ext.min + ((ext.max - ext.min) * p) / 1000;
  const round = (x: number) => (year ? Math.round(x) : Number(x.toPrecision(3)));
  const gap = year ? 1 : (range.hi - range.lo) / 1000;
  const setLo = (x: number) => r.set({ lo: Math.min(round(x), range.hi - gap), hi: range.hi });
  const setHi = (x: number) => r.set({ lo: range.lo, hi: Math.max(round(x), range.lo + gap) });
  const lo = toPos(range.lo) / 10;
  const hi = toPos(range.hi) / 10;
  return (
    <div className="fh-range">
      <div className="fh-track">
        <span className="fh-sel" style={{ left: `${lo}%`, right: `${100 - hi}%` }} />
        <input
          type="range"
          min={0}
          max={1000}
          value={Math.round(toPos(range.lo))}
          aria-label={h.lowest}
          onChange={(e) => setLo(fromPos(Number(e.target.value)))}
        />
        <input
          type="range"
          min={0}
          max={1000}
          value={Math.round(toPos(range.hi))}
          aria-label={h.highest}
          onChange={(e) => setHi(fromPos(Number(e.target.value)))}
        />
      </div>
      <div className="fh-bounds">
        <span>{h.from}</span>
        {prefix && <span>{prefix}</span>}
        <Bound value={range.lo} year={year} label={h.lowest} onCommit={setLo} />
        <span>{h.to}</span>
        {prefix && <span>{prefix}</span>}
        <Bound value={range.hi} year={year} label={h.highest} onCommit={setHi} />
        {unit && <span>{unit}</span>}
        {!r.isAuto && (
          <Button className="link-button" onPress={() => r.set(null)}>
            {h.reset}
          </Button>
        )}
        {pair && r.partner && (
          <label className="fh-linked">
            <input type="checkbox" checked={r.linked} onChange={(e) => r.setLinked(e.target.checked)} /> 🔗{" "}
            {h.linked}
          </label>
        )}
      </div>
    </div>
  );
}

/** A bound typed: thousands separated as shown; read on Enter or leaving the box. */
function Bound({
  value,
  year,
  label,
  onCommit,
}: {
  value: number;
  year: boolean;
  label: string;
  onCommit: (x: number) => void;
}) {
  const shown = edge(value, year);
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft === null) return;
    const x = Number(draft.replace(/[,\s]/g, ""));
    if (Number.isFinite(x)) onCommit(x);
    setDraft(null);
  };
  return (
    <input
      type="text"
      inputMode="decimal"
      className="fh-bound"
      aria-label={label}
      value={draft ?? shown}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") setDraft(null);
      }}
    />
  );
}

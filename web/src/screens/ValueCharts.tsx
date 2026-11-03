/** Check my values' charts: ratios by price band, and each sale's ratio against its price. */
import type { RatioStudy } from "../api/client";
import { useWidth } from "../lib/hooks";
import { t } from "../strings";

const r = t.ratio;

type Band = { median?: number | null; low?: number | null; high?: number | null };

/** Groups of sales from the cheapest to the dearest, each its median ratio with its 90% range as a bar (the VEI's
 * chart, as openratiostudy.com draws it); several series side by side in each group, the standard's level in green. */
export function BandChart({ series }: { series: { label: string; color: string; bands: Band[] }[] }) {
  const [ref, W] = useWidth<SVGSVGElement>();
  const H = 260;
  const L = 52;
  const R = 16;
  const T = 12;
  const B = 34;
  const n = Math.max(...series.map((x) => x.bands.length), 1);
  const vals = series
    .flatMap((x) => x.bands.flatMap((b) => [b.low, b.high, b.median]))
    .filter((v) => v != null);
  const rlo = Math.min(0.85, ...(vals as number[])) - 0.05;
  const rhi = Math.max(1.15, ...(vals as number[])) + 0.05;
  const slot = (W - L - R) / n;
  const y = (v: number) => T + (H - T - B) * (1 - (v - rlo) / (rhi - rlo));
  const off = (k: number) =>
    series.length === 1 ? 0 : (k - (series.length - 1) / 2) * Math.min(18, slot / 4);
  const rticks: number[] = [];
  for (let v = Math.ceil(rlo * 10) / 10; v <= rhi; v += 0.1) rticks.push(Math.round(v * 10) / 10);
  const name = (k: number) => (k === 0 ? r.regions.lowest : k === n - 1 ? r.regions.highest : String(k + 1));
  return (
    <figure className="rv-figure">
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${H}`}
        height={H}
        className="rv-chart"
        role="img"
        aria-label={series.map((x) => x.label).join("; ")}
      >
        <rect x={L} y={y(1.1)} width={W - L - R} height={y(0.9) - y(1.1)} fill="#e7f5ec" />
        {rticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#e2e4e6" />
            <text x={L - 6} y={y(v) + 4} fontSize="11" textAnchor="end" fill="#555">
              {v.toFixed(1)}
            </text>
          </g>
        ))}
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="#888" />
        {Array.from({ length: n }, (_, k) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
          <text key={k} x={L + slot * (k + 0.5)} y={H - B + 16} fontSize="11" textAnchor="middle" fill="#555">
            {name(k)}
          </text>
        ))}
        {series.map((sr, j) =>
          sr.bands.map((b, k) => {
            const cx = L + slot * (k + 0.5) + off(j);
            return b.median == null ? null : (
              // biome-ignore lint/suspicious/noArrayIndexKey: the groups are positions
              <g key={`${sr.label}-${k}`}>
                {b.low != null && b.high != null && (
                  <line x1={cx} x2={cx} y1={y(b.low)} y2={y(b.high)} stroke={sr.color} strokeWidth="2" />
                )}
                <circle cx={cx} cy={y(b.median)} r="4.5" fill={sr.color} />
              </g>
            );
          }),
        )}
      </svg>
      {series.length > 1 && (
        <figcaption className="rv-legend">
          {series.map((sr) => (
            <span key={sr.label}>
              <span className="rv-swatch" style={{ background: sr.color, borderColor: sr.color }} />
              {sr.label}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

export function Scatter({
  points,
  fifths,
  currency,
}: {
  points: [number, number, boolean][];
  fifths: RatioStudy["fifths"];
  currency: string;
}) {
  const [ref, W] = useWidth<SVGSVGElement>();
  const H = 280;
  const L = 52;
  const R = 16;
  const T = 12;
  const B = 30;
  const kept = points.filter((x) => !x[2]);
  const prices = (kept.length ? kept : points).map((x) => x[0]).filter((x) => x > 0);
  if (!prices.length) return <svg ref={ref} className="rv-chart" height={H} />;
  const lo = Math.log10(Math.min(...prices));
  const hi = Math.log10(Math.max(...prices)) + 0.01;
  const rs = kept.map((x) => x[1]).sort((a, b) => a - b);
  const rlo = Math.min(0.5, rs[Math.floor(rs.length * 0.01)] ?? 0.5) - 0.05;
  const rhi = Math.max(1.2, rs[Math.floor(rs.length * 0.99)] ?? 1.2) + 0.05;
  const x = (v: number) => L + ((W - L - R) * (Math.log10(Math.max(v, 10 ** lo)) - lo)) / (hi - lo);
  const y = (v: number) => T + (H - T - B) * (1 - (Math.min(Math.max(v, rlo), rhi) - rlo) / (rhi - rlo));
  const ticks: number[] = [];
  for (let e = Math.floor(lo); e <= Math.ceil(hi); e++)
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** e;
      if (Math.log10(v) >= lo && Math.log10(v) <= hi) ticks.push(v);
    }
  const rticks: number[] = [];
  for (let v = Math.ceil(rlo * 5) / 5; v <= rhi; v += 0.2) rticks.push(Math.round(v * 10) / 10);
  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      height={H}
      className="rv-chart"
      role="img"
      aria-label={r.prices.lede}
    >
      <rect x={L} y={y(1.1)} width={W - L - R} height={y(0.9) - y(1.1)} fill="#e7f5ec" />
      {rticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#e2e4e6" />
          <text x={L - 6} y={y(v) + 4} fontSize="11" textAnchor="end" fill="#555">
            {v.toFixed(1)}
          </text>
        </g>
      ))}
      <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="#888" />
      {ticks.map((v) => (
        <text key={v} x={x(v)} y={H - B + 16} fontSize="11" textAnchor="middle" fill="#555">
          {new Intl.NumberFormat(undefined, { style: "currency", currency, notation: "compact" }).format(v)}
        </text>
      ))}
      {points.map(([p, q, trimmed], k) => (
        <circle
          // biome-ignore lint/suspicious/noArrayIndexKey: points have no key of their own
          key={k}
          cx={x(p)}
          cy={y(q)}
          r="2.6"
          fill={trimmed ? "#9a9a9a" : "#d4566f"}
          opacity="0.55"
        />
      ))}
      {fifths.map((f) => (
        <line
          key={f.low}
          x1={x(f.low)}
          x2={x(f.high)}
          y1={y(f.median)}
          y2={y(f.median)}
          stroke="#222"
          strokeWidth="2.5"
        />
      ))}
    </svg>
  );
}

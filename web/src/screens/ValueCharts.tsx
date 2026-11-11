/** Check my values' chart of each sale's ratio against its price (the VEI's own chart is VeiChart). */
import type { RatioStudy } from "../api/client";
import { BY_SALE, CHART, TRIMMED } from "../lib/colours";
import { useWidth } from "../lib/hooks";
import { t } from "../wording";

const r = t.ratio;

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
      <rect x={L} y={y(1.1)} width={W - L - R} height={y(0.9) - y(1.1)} fill={CHART.band} />
      {rticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={CHART.grid} />
          <text x={L - 6} y={y(v) + 4} fontSize="11" textAnchor="end" fill={CHART.label}>
            {v.toFixed(1)}
          </text>
        </g>
      ))}
      <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke={CHART.axis} />
      {ticks.map((v) => (
        <text key={v} x={x(v)} y={H - B + 16} fontSize="11" textAnchor="middle" fill={CHART.label}>
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
          fill={trimmed ? TRIMMED.line : BY_SALE}
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
          stroke={CHART.ink}
          strokeWidth="2.5"
        />
      ))}
    </svg>
  );
}

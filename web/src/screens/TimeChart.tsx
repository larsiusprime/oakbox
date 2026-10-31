/** One model group's time adjustment, expanded: its index over time, drawn through the sales it's worked out from
 * (each a faint dot of its price per area, before adjustment; hover one for the sale). */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "../api/client";
import { day, money, num } from "../lib/format";
import { useWidth } from "../lib/hooks";
import { t } from "../strings";

const s = t.sales.time;
const units = t.sales.unit;
const H = 280;
const PAD = { l: 64, r: 12, t: 10, b: 26 };

export type TimeGroupLike = {
  id: string;
  name: string;
  color: string;
  per: "impr" | "land" | null;
  period: "M" | "Q" | "Y" | null;
  periods: number;
  periods_ok: number;
};

const time = (d: string) => new Date(`${d}T00:00:00`).getTime();

function median(xs: number[]): number {
  const a = [...xs].sort((x, y) => x - y);
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? (a[m] ?? 0) : ((a[m - 1] ?? 0) + (a[m] ?? 0)) / 2;
}

export function TimeChart({
  projectId,
  group,
  currency,
}: {
  projectId: string;
  group: TimeGroupLike;
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
  const [ref, width] = useWidth<HTMLDivElement>(800, 360);
  const [hover, setHover] = useState<number | null>(null);
  const d = q.data;
  // The box is always there, so its width is known before the chart is.
  if (!d || d.sales.length === 0)
    return (
      <div className="cs-tchart" ref={ref}>
        <p className="empty">{d ? s.noDots : (q.error?.message ?? t.project.loading)}</p>
      </div>
    );
  const sales = d.sales;
  // Days across, log price per area up (a few far-off sales would flatten the rest).
  const x0 = Math.min(...sales.map((x) => time(x.date)), ...d.index.map((x) => time(x.day)));
  const x1 = Math.max(...sales.map((x) => time(x.date)), ...d.index.map((x) => time(x.day)));
  // Scaled to the middle 90% of sales, with room around it: a few far-off ones would squash the rest.
  const sorted = sales.map((x) => x.per_area).sort((a, b) => a - b);
  const q5 = Math.log(sorted[Math.floor(sorted.length * 0.05)] ?? 1);
  const q95 = Math.log(sorted[Math.ceil(sorted.length * 0.95) - 1] ?? 1);
  const pad = Math.max(0.35 * (q95 - q5), 0.2);
  const lo = q5 - pad;
  const hi = q95 + pad;
  const span = hi - lo || 1;
  const w = width - PAD.l - PAD.r;
  const h = H - PAD.t - PAD.b;
  const X = (ms: number) => PAD.l + (w * (ms - x0)) / (x1 - x0 || 1);
  const Y = (v: number) => PAD.t + h - (h * (Math.log(Math.max(v, 1e-9)) - lo)) / span;
  const inside = (v: number) => Math.log(v) >= lo && Math.log(v) <= hi;
  const outside = sales.filter((x) => !inside(x.per_area)).length;
  // The index drawn through the sales: scaled so its middle sits at their median price per area.
  const scale = d.index.length
    ? median(sales.map((x) => x.per_area)) / median(d.index.map((x) => x.value))
    : 1;
  const line = d.index
    .filter((x) => inside(x.value * scale))
    .map((x) => `${X(time(x.day)).toFixed(1)},${Y(x.value * scale).toFixed(1)}`)
    .join(" ");
  const ticks = [lo, lo + span / 2, hi].map((l) => Math.exp(l));
  const years: number[] = [];
  for (let y = new Date(x0).getFullYear() + 1; y <= new Date(x1).getFullYear(); y++) years.push(y);
  const near = (mx: number, my: number) => {
    let best: number | null = null;
    let dist = 12 * 12;
    sales.forEach((x, i) => {
      if (!inside(x.per_area)) return;
      const dx = X(time(x.date)) - mx;
      const dy = Y(x.per_area) - my;
      if (dx * dx + dy * dy < dist) {
        dist = dx * dx + dy * dy;
        best = i;
      }
    });
    return best;
  };
  const h0 = hover !== null ? sales[hover] : undefined;
  const area = units[d.unit];
  const per = group.per === "land" ? s.perLand(area) : s.perImpr(area);
  const by = group.period ? s.by[group.period] : null;
  return (
    <div className="cs-tchart" ref={ref}>
      <p className="wiz-from">
        {s.chartNote(per, num(sales.length))}
        {by && ` ${s.periodsNote(by, group.periods_ok, group.periods)}`}
        {outside > 0 && ` ${s.outside(outside)}`}
      </p>
      <svg
        className="cs-tsvg"
        width={width}
        height={H}
        role="img"
        aria-label={s.chartLabel(group.name)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(near(e.clientX - r.left, e.clientY - r.top));
        }}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={width - PAD.r} y1={Y(v)} y2={Y(v)} className="cs-tgrid" />
            <text x={PAD.l - 6} y={Y(v) + 4} textAnchor="end" className="cs-taxis">
              {money(v, currency)}
            </text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={X(new Date(y, 0, 1).getTime())} y={H - 8} textAnchor="middle" className="cs-taxis">
            {y}
          </text>
        ))}
        {sales.map(
          (x, i) =>
            inside(x.per_area) && (
              <circle
                key={x.key_sale}
                cx={X(time(x.date))}
                cy={Y(x.per_area)}
                r={i === hover ? 5 : 3}
                fill={group.color}
                fillOpacity={i === hover ? 0.9 : 0.25}
              />
            ),
        )}
        {line && <polyline points={line} fill="none" stroke={group.color} strokeWidth={2.5} />}
      </svg>
      {h0 && (
        <div className="cs-ttip" role="status">
          <b>{h0.address ?? h0.key_sale}</b> · {day(h0.date)}
          <br />
          {s.tip(money(h0.price, currency), money(h0.per_area, currency), per)}
          {h0.adjusted !== null && h0.adjusted !== undefined && (
            <>
              <br />
              {s.tipAdjusted(money(h0.adjusted, currency))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

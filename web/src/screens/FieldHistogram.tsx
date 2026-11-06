import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, unwrap, type WizardField } from "../api/client";
import { num } from "../lib/format";
import { t } from "../wording";

const h = t.wizard.histogram;

/** A whole number or a short decimal, as a bin's edge is labelled ("1,200", "0.25"); a year as it's written. */
function edge(v: number, year: boolean): string {
  if (year) return String(Math.round(v));
  return v.toLocaleString(undefined, { maximumFractionDigits: v < 10 ? 2 : 0 });
}

/** How a number field's values spread, as loaded (Big five: sizes in the project's unit, years): a bar per bin,
 * its count on hover, the edges under it, and what's outside or blank said under that. */
export function FieldHistogram({ projectId, field }: { projectId: string; field: WizardField }) {
  const source = field.sources[0];
  const q = useQuery({
    queryKey: ["histogram", projectId, field.key, source?.file, source?.column, field.area_unit],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/fields/{key}/histogram", {
          params: { path: { project_id: projectId, key: field.key } },
        }),
      ),
    enabled: !!source,
    placeholderData: keepPreviousData,
  });
  const v = q.data;
  if (!source || !v || v.bins.length === 0) return null;
  const top = Math.max(1, ...v.bins.map((b) => b.count));
  // About six edge labels across, whatever the number of bins.
  const every = Math.max(1, Math.ceil(v.bins.length / 6));
  const unit = v.unit ? ` ${v.unit}` : "";
  const notes = [
    v.median != null ? h.median({ m: `${edge(v.median, v.year)}${unit}` }) : null,
    v.below ? h.below({ n: v.below, v: `${edge(v.bins[0]?.low ?? 0, v.year)}${unit}` }) : null,
    v.above
      ? h.above({ n: v.above, v: `${edge(v.bins[v.bins.length - 1]?.high ?? 0, v.year)}${unit}` })
      : null,
    v.empty ? h.empty({ n: v.empty }) : null,
  ].filter(Boolean);
  return (
    <div className="frame qc-panel">
      <h3 className="wiz-group">{h.title({ name: field.name })}</h3>
      <div className="fh-chart" role="img" aria-label={h.title({ name: field.name })}>
        {v.bins.map((b) => (
          <span
            key={b.low}
            className="fh-bar"
            style={{ height: `${(8 * b.count) / top}rem` }}
            title={`${edge(b.low, v.year)}–${edge(b.high, v.year)}${unit}: ${num(b.count)}`}
          />
        ))}
      </div>
      <div className="fh-axis" style={{ gridTemplateColumns: `repeat(${v.bins.length}, 1fr)` }}>
        {v.bins.map((b, i) => (
          <span key={b.low}>{i % every === 0 ? edge(b.low, v.year) : ""}</span>
        ))}
      </div>
      {notes.length > 0 && <p className="rc-sub">{notes.join(" · ")}</p>}
    </div>
  );
}

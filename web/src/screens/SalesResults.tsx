/** Check sales' results: the sales per model group, the patterns of those set aside, and how prices moved. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";
import { api, type CleanReceipt, type CleanView, type PatternTable, unwrap } from "../api/client";
import { POLL } from "../api/steps";
import { Choice } from "../components/Form";
import { RunProgress } from "../components/Steps";
import { InfoTip } from "../components/Tip";
import { num, when } from "../lib/format";
import { t } from "../strings";
import { TimeChart } from "./TimeChart";

const s = t.sales;

// ---------- After running ----------

function useShow(projectId: string) {
  return useMutation({
    mutationFn: async (q: { what: "output" | "schedule" | "scrutiny"; group?: string }) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/clean/show", {
          params: { path: { project_id: projectId }, query: { what: q.what, group: q.group ?? "" } },
        }),
      ),
  });
}

/** The sales from Data to modeling, per model group, and the files written. */
export function SalesResult({
  projectId,
  view,
  receipt: r,
  look,
}: {
  projectId: string;
  view: CleanView;
  receipt: CleanReceipt;
  look: (check: string) => void;
}) {
  const show = useShow(projectId);
  const few = r.groups.filter((g) => g.id !== "(none)" && g.per_year === null && g.in_window > 0);
  const orphans = r.groups.find((g) => g.id === "(none)");
  return (
    <div className={view.stale ? "cs-receipt cs-stale" : "cs-receipt"}>
      {view.stale && <p className="wiz-warn">{s.stale}</p>}
      <div className="cs-meter">
        <span className="wiz-ok">{s.meter(r.used, r.set_aside)}</span>
        <span className="wiz-from">{t.step.ran(when(r.ran_at), r.seconds, r.engine)}</span>
      </div>
      <section className="cs-step">
        <h3 className="wiz-group">{s.funnel.title}</h3>
        <div className="cs-funnel">
          {r.funnel.map((l) => (
            <div key={`${l.sign}${l.text}`} className={l.sign === "=" ? "cs-fl tot" : "cs-fl"}>
              <span className="cs-op">{l.sign === "" ? "" : l.sign === "-" ? "−" : l.sign}</span>
              <span className="cs-n">{num(l.count)}</span>
              <span>{l.text}</span>
              <span>
                {l.check && l.count > 0 && (
                  <Button className="wiz-link" onPress={() => look(l.check ?? "")}>
                    {s.funnel.see}
                  </Button>
                )}
              </span>
            </div>
          ))}
        </div>
        <p className="wiz-from cs-text">{s.funnel.once}</p>
        {r.flagged_in > 0 && (
          <p className="cs-text">
            {s.funnel.flaggedIn(r.flagged_in)}{" "}
            <Button className="wiz-link" onPress={() => look("pattern:other")}>
              {s.funnel.see}
            </Button>
          </p>
        )}
      </section>
      {r.patterns.length > 0 && <Patterns tables={r.patterns} look={look} />}
      <section className="cs-step">
        <h3 className="wiz-group">{s.groups.title}</h3>
        <table className="tbl">
          <thead>
            <tr>
              <th>{s.group}</th>
              <th className="cs-n">{s.groups.inWindow}</th>
              <th className="cs-n">{s.groups.aside}</th>
              <th className="cs-n">{s.groups.used}</th>
              <th className="cs-n">{s.groups.clusters}</th>
              <th className="cs-n">{s.groups.perYear}</th>
            </tr>
          </thead>
          <tbody>
            {r.groups.map((g) => (
              <tr key={g.id} className={g.id === "(none)" ? "cs-muted" : ""}>
                <td>
                  <span className="mg-sw ab-sw" style={{ background: g.color }} />
                  {g.name}
                </td>
                <td className="cs-n">{num(g.in_window)}</td>
                <td className="cs-n">{num(g.set_aside)}</td>
                <td className="cs-n">{num(g.used)}</td>
                <td className="cs-n">{num(g.clusters)}</td>
                <td className="cs-n">
                  {g.per_year !== null && g.per_year !== undefined ? s.time.perYear(g.per_year) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {few.length > 0 && <div className="bi-warn">{s.groups.few(few.map((g) => g.name).join(", "))}</div>}
        {orphans && <p className="wiz-from cs-text">{s.groups.orphans(orphans.used)}</p>}
      </section>
      <section className="cs-step">
        <h3 className="wiz-group">{s.written}</h3>
        <ul className="ab-files">
          {r.written.map((w) => (
            <li key={w.path}>
              <span className="mono">{w.path}</span>
              {w.what && <span className="wiz-from"> · {w.what}</span>}
            </li>
          ))}
        </ul>
        {r.notes.length > 0 && (
          <details className="bi-details">
            <summary>{t.groups.run.notes(r.notes.length)}</summary>
            <ul>
              {r.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </details>
        )}
        <div className="cs-row">
          <Button className="button" onPress={() => show.mutate({ what: "output" })}>
            <FolderOpen aria-hidden="true" size="1em" />
            {t.groups.run.show}
          </Button>
          <Button className="button" onPress={() => show.mutate({ what: "scrutiny" })}>
            {s.showScrutiny}
          </Button>
        </div>
      </section>
    </div>
  );
}

/** The sales flagged far from their group, by pattern: likely cause and what to check (the five-pattern table). */
function Patterns({ tables, look }: { tables: PatternTable[]; look: (check: string) => void }) {
  const [group, setGroup] = useState("");
  const table = tables.find((x) => x.group === group) ?? tables[0];
  if (!table) return null;
  const p = s.patterns;
  const flagged = Object.values(table.counts).reduce((a, b) => a + b, 0);
  const share = (n: number) => (table.sales ? `${((100 * n) / table.sales).toFixed(2)}%` : "—");
  return (
    <section className="cs-step">
      <h3 className="wiz-group">{p.title}</h3>
      <div className="cs-row">
        <Choice
          label={s.group}
          hideLabel
          value={group}
          options={tables.map((x) => [x.group, x.name] as [string, string])}
          onChange={setGroup}
        />
        <span className="wiz-from">{p.lede(flagged, table.sales, table.name)}</span>
      </div>
      <table className="tbl cs-patterns">
        <thead>
          <tr>
            <th>{p.pattern}</th>
            <th className="cs-n">{p.sales}</th>
            <th className="cs-n">{p.share}</th>
            <th>{p.cause}</th>
            <th>{p.action}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {Object.entries(table.counts).map(([key, n]) => {
            const d = s.review.diagnosis[key];
            return (
              <tr key={key}>
                <td>{d?.name ?? key}</td>
                <td className="cs-n">{num(n)}</td>
                <td className="cs-n">{share(n)}</td>
                <td>{d && <InfoTip label={d.short} text={d.why} />}</td>
                <td>{d && <InfoTip label={d.check} text={d.actions.join(" ")} />}</td>
                <td>
                  {n > 0 && (
                    <Button className="wiz-link" onPress={() => look(`pattern:${key}`)}>
                      {s.funnel.see}
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="cs-total">
            <td>{p.flagged}</td>
            <td className="cs-n">{num(flagged)}</td>
            <td className="cs-n">{share(flagged)}</td>
            <td colSpan={3} />
          </tr>
        </tfoot>
      </table>
    </section>
  );
}

/** Time adjustment worked out alone, before running (seconds): only when asked (Work it out, the step's action). */
export function useTimePreview(projectId: string) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["clean-time", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/time", {
          params: { path: { project_id: projectId } },
        }),
      ),
    refetchInterval: (query) => (query.state.data?.status === "running" ? POLL : false),
  });
  const run = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/clean/time/run", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["clean-time", projectId], data);
      queryClient.removeQueries({
        queryKey: ["clean-time", projectId],
        exact: false,
        predicate: (x) => x.queryKey.length > 2,
      });
    },
  });
  const v = q.data;
  const ready = !!v?.result && !v.stale && v.status !== "running";
  return { v, run, ready };
}

/** How prices moved, worked out alone: a small chart per group (one shown larger, with its sales, at a time), and
 * why a group has none. */
export function TimePreviewPanel({ projectId, currency }: { projectId: string; currency: string }) {
  const { v, run } = useTimePreview(projectId);
  const [open, setOpen] = useState<string | null>(null);
  if (!v) return null;
  const result = v.result;
  const none = result?.groups.filter((g) => g.per_year === null) ?? [];
  const curves = result?.groups.filter((g) => g.curve.length > 1) ?? [];
  return (
    <section className="cs-step">
      <h3 className="wiz-group">{s.time.preview}</h3>
      {v.status === "running" ? (
        <RunProgress job={v.job} lastSeconds={result?.seconds ?? null} />
      ) : v.status === "failed" ? (
        <p className="error" role="alert">
          {t.step.failed} <span className="mono">{v.job?.error}</span>
        </p>
      ) : result ? (
        <>
          <p className="wiz-from cs-text">
            {v.stale ? s.time.previewStale : s.time.previewNote(result.seconds)}
          </p>
          <div className="cs-charts">
            {curves.map((g) =>
              open === g.id ? (
                <figure key={g.id} className="cs-chart cs-chart-open">
                  <figcaption>
                    <span className="mg-sw ab-sw" style={{ background: g.color }} />
                    <b>{g.name}</b> {g.per_year !== null && s.time.perYear(g.per_year)}{" "}
                    <Button className="wiz-link" onPress={() => setOpen(null)}>
                      {s.time.collapse}
                    </Button>
                  </figcaption>
                  {g.per === "land" && !g.per_chosen && <p className="wiz-warn">{s.time.onLand}</p>}
                  <TimeChart projectId={projectId} group={g} currency={currency} />
                </figure>
              ) : (
                <Button key={g.id} className="cs-chart cs-chart-button" onPress={() => setOpen(g.id)}>
                  <span className="cs-chart-cap">
                    <span className="mg-sw ab-sw" style={{ background: g.color }} />
                    <b>{g.name}</b> {g.per_year !== null && s.time.perYear(g.per_year)}
                  </span>
                  <Curve points={g.curve} color={g.color} />
                  <span className="cs-chart-foot">
                    <span>{g.first?.slice(0, 7)}</span>
                    <span>×{num(g.curve.at(-1) ?? 1, 2)}</span>
                    <span>{g.last?.slice(0, 7)}</span>
                  </span>
                  <span className="sr-only">{s.time.expand}</span>
                </Button>
              ),
            )}
          </div>
          {none.length > 0 && (
            <table className="tbl cs-none">
              <thead>
                <tr>
                  <th>{s.time.none}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {none.map((g) => (
                  <tr key={g.id}>
                    <td>
                      <span className="mg-sw ab-sw" style={{ background: g.color }} />
                      {g.name}
                    </td>
                    <td>{g.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      ) : (
        <p className="wiz-from cs-text">{s.time.previewFirst}</p>
      )}
      {run.error && (
        <p className="error" role="alert">
          {run.error.message}
        </p>
      )}
    </section>
  );
}

function Curve({ points, color }: { points: number[]; color: string }) {
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const span = hi - lo || 1;
  const d = points
    .map(
      (p, i) =>
        `${((100 * i) / Math.max(1, points.length - 1)).toFixed(1)},${(38 - (34 * (p - lo)) / span).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="cs-curve" aria-hidden="true">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

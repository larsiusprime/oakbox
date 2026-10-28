import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type EnrichResult,
  type Funnel,
  type Job,
  type Receipt,
  type ReceiptField,
  unwrap,
} from "../api/client";
import { FieldDetail } from "../components/FieldDetail";
import { t } from "../strings";

const b = t.bringIn;

function useBringIn(projectId: string) {
  return useQuery({
    queryKey: ["bring-in", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/bring-in", { params: { path: { project_id: projectId } } }),
      ),
    // While it runs, ask often; otherwise only when something changes.
    refetchInterval: (q) => (q.state.data?.status === "running" ? 600 : false),
  });
}

/** Whether Looks right was pressed on an up-to-date receipt: model groups can start. */
export function useAccepted(projectId: string): boolean {
  return useBringIn(projectId).data?.accepted ?? false;
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function when(iso: string): string {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return today ? `today at ${time}` : `${d.toLocaleDateString()} at ${time}`;
}

/** Step 1, Bring in data: ready, running, or the receipt of the last run (SPEC §3.3). */
export function BringInTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const state = useBringIn(projectId);
  const act = useMutation({
    mutationFn: async (what: "run" | "stop" | "accept" | `skip:${string}`) => {
      if (what.startsWith("skip:")) {
        return unwrap(
          await api.POST("/api/projects/{project_id}/bring-in/skip/{part}", {
            params: { path: { project_id: projectId, part: what.slice(5) } },
          }),
        );
      }
      const path = `/api/projects/{project_id}/bring-in/${what as "run" | "stop" | "accept"}` as const;
      return unwrap(await api.POST(path, { params: { path: { project_id: projectId } } }));
    },
    onSuccess: (data) => queryClient.setQueryData(["bring-in", projectId], data),
  });
  const [rows, setRows] = useState<{ set: string; title: string } | null>(null);
  const v = state.data;
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  const running = v.status === "running";
  const r = v.receipt;
  const last = v.job?.steps.at(-1);
  // Enrichments say when they start, without a share of the run.
  const fraction = [...(v.job?.steps ?? [])].reverse().find((s) => s.fraction !== null)?.fraction ?? 0.05;
  // The server's clock, every answer: it moves while a step is busy (it didn't, before).
  const elapsed = v.job?.elapsed ?? (last ? last.at : 0);
  const left = r && running && elapsed < r.seconds ? r.seconds - elapsed : null;
  return (
    <div className="bi">
      <div className="bi-kicker">{b.kicker}</div>
      <h2 className="bi-title">{b.title}</h2>
      <p className="bi-lede">{b.lede}</p>

      {v.blocked.length > 0 && (
        <div className="bi-warn">
          <b>{b.blocked(v.blocked.length)}</b> {v.blocked[0]}{" "}
          <Button
            className="wiz-link"
            onPress={() => navigate({ name: "project", id: projectId, tab: "fields" })}
          >
            {b.toData}
          </Button>
        </div>
      )}
      {v.stale && !running && (
        <div className="bi-warn">
          <b>{b.stale}</b> {v.changed.join(", ")}.{" "}
          <Button className="button" isDisabled={v.blocked.length > 0} onPress={() => act.mutate("run")}>
            {b.runAgain}
          </Button>
        </div>
      )}
      {v.status === "failed" && v.job?.error && (
        <div className="bi-warn" role="alert">
          <b>{b.failed}</b> <span className="mono">{v.job.error}</span>
          <div className="wiz-from">{b.failedLog}</div>
        </div>
      )}
      {v.status === "stopped" && <p className="wiz-from">{b.stopped}</p>}

      {running ? (
        <div className="bi-card">
          <h3>{b.running(clock(elapsed), left !== null ? clock(left) : null)}</h3>
          <div className="bi-prog">
            <i style={{ width: `${Math.round(100 * fraction)}%` }} />
          </div>
          <ul className="bi-steps">
            {(v.job?.steps.length ?? 0) === 0 && (
              <li className="now">
                <span className="bi-pulse" aria-hidden="true" />
                {b.starting}
              </li>
            )}
            {v.job?.steps.map((s, i) => {
              const now = i === (v.job?.steps.length ?? 0) - 1;
              return (
                <li key={s.step} className={now ? "now" : "done"}>
                  {now ? <span className="bi-pulse" aria-hidden="true" /> : "✓ "}
                  {s.message}
                  {now && v.job && (
                    <Busy job={v.job} since={s.at} skip={(part) => act.mutate(`skip:${part}`)} />
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : !r ? (
        <div className="bi-card">
          <h3>{b.whatRuns}</h3>
          <ul className="bi-plan">
            {v.plan.files.map((f) => (
              <li key={f}>{f}</li>
            ))}
            {v.plan.layers.length > 0 && (
              <li>
                <b>{b.layers}:</b> {v.plan.layers.join("; ")}
              </li>
            )}
            {v.plan.enrichments.length > 0 && (
              <li>
                <b>{b.enrich.title}:</b> {v.plan.enrichments.join("; ")}
              </li>
            )}
            <li>{b.fields(v.plan.fields)}</li>
          </ul>
        </div>
      ) : (
        <ReceiptView
          projectId={projectId}
          receipt={r}
          stale={v.stale}
          open={(set, title) => setRows({ set, title })}
          rerun={running || v.blocked.length > 0 ? null : () => act.mutate("run")}
        />
      )}

      {act.error && (
        <p className="error" role="alert">
          {act.error.message}
        </p>
      )}
      <div className="bi-foot">
        {running ? (
          <Button className="button" onPress={() => act.mutate("stop")}>
            {b.stop}
          </Button>
        ) : (
          <>
            {!r && <span className="wiz-warn">{b.notRun}</span>}
            <Button
              className={r ? "button" : "button button-primary"}
              isDisabled={v.blocked.length > 0 || act.isPending}
              onPress={() => act.mutate("run")}
            >
              {r ? b.runAgain : b.run}
            </Button>
          </>
        )}
        <span className="bi-grow" />
        {r && !running && (
          <>
            <span className="wiz-from">{b.next}</span>
            {v.accepted ? (
              <Button
                className="button button-primary"
                onPress={() => navigate({ name: "project", id: projectId, tab: "groups" })}
              >
                {b.accepted}
              </Button>
            ) : (
              <Button
                className="button button-primary"
                isDisabled={v.stale || act.isPending}
                onPress={() =>
                  act.mutate("accept", {
                    onSuccess: () => navigate({ name: "project", id: projectId, tab: "groups" }),
                  })
                }
              >
                {b.looksRight}
              </Button>
            )}
          </>
        )}
      </div>
      {rows && (
        <RowsDialog projectId={projectId} set={rows.set} title={rows.title} close={() => setRows(null)} />
      )}
    </div>
  );
}

function ReceiptView({
  projectId,
  receipt: r,
  stale,
  open,
  rerun,
}: {
  projectId: string;
  receipt: Receipt;
  stale: boolean;
  open: (set: string, title: string) => void;
  rerun: (() => void) | null;
}) {
  return (
    <div className={stale ? "bi-receipt bi-stale" : "bi-receipt"}>
      {stale && <p className="wiz-from">{b.staleNote}</p>}
      <div className="rc-meter ok">
        <b>{b.meter(r.universe.rows, r.sales.rows)}</b>
        <span className="rc-was">{b.ran(when(r.ran_at), r.seconds, r.engine)}</span>
      </div>
      {r.enrichments.length > 0 && <EnrichCard results={r.enrichments} rerun={rerun} />}
      <Section
        title={b.universe}
        funnels={r.universe.funnels}
        fields={r.universe.fields}
        rows={r.universe.rows}
        set="universe"
        open={open}
        projectId={projectId}
      />
      <Section
        title={b.sales}
        funnels={r.sales.funnels}
        fields={r.sales.fields}
        rows={r.sales.rows}
        set="sales"
        open={open}
        projectId={projectId}
      />
      {r.checks.length > 0 && (
        <div className="bi-card">
          <h3>{b.checks}</h3>
          <table className="bi-tbl">
            <thead>
              <tr>
                <th />
                <th>{b.said}</th>
                <th>{b.got}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {r.checks.map((c) => (
                <tr key={c.what}>
                  <td>{c.what}</td>
                  <td>{c.said}</td>
                  <td>{c.got}</td>
                  <td className={c.ok ? "wiz-ok" : "wiz-warn"}>{c.ok ? "✓" : "⚠"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details className="bi-details">
        <summary>{b.engineNotes(r.notes.length, r.notices)}</summary>
        <ul>
          {r.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </details>
      <details className="bi-details">
        <summary>{b.underHood}</summary>
        <pre>
          {[b.hood, ...r.timings.map(([step, s]) => `  ${String(step).padEnd(22)} ${s} s`)].join("\n")}
          {"\nout/oakbox/bring_in/: universe.parquet, sales.parquet, rows/, sup.pickle, receipt.json"}
        </pre>
      </details>
    </div>
  );
}

/** F3e: each enrichment as it went; one that failed was skipped, and running again tries it again. */
function EnrichCard({ results, rerun }: { results: EnrichResult[]; rerun: (() => void) | null }) {
  const e = b.enrich;
  return (
    <section className="bi-card">
      <h3>{e.title}</h3>
      <table className="bi-tbl">
        <thead>
          <tr>
            <th>{e.what}</th>
            <th>{e.result}</th>
            <th>{e.fields}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {results.map((x) => (
            <tr key={x.key}>
              <td>{e.names[x.key]}</td>
              <td className={x.status === "ok" ? "wiz-ok" : x.status === "partial" ? "wiz-warn" : "wiz-bad"}>
                {x.status === "ok" ? "✓ " : x.status === "partial" ? "⚠ " : "✗ "}
                {x.text}
                <span className="wiz-from">
                  {" · "}
                  {x.reused ? e.reused : e.seconds(x.seconds)}
                </span>
                {x.status === "partial" && (
                  <ul className="bi-feats">
                    {x.features
                      .filter((f) => f.status === "failed")
                      .map((f) => (
                        <li key={f.key}>
                          {f.label}: {f.text}
                        </li>
                      ))}
                  </ul>
                )}
              </td>
              <td>
                {x.fields.slice(0, 3).map((f) => (
                  <span key={f} className="en-chip">
                    {f}
                  </span>
                ))}
                {x.fields.length > 3 && <span className="wiz-from"> {e.more(x.fields.length - 3)}</span>}
              </td>
              <td>
                {x.status !== "ok" && rerun && (
                  <Button className="wiz-link" onPress={rerun}>
                    {e.retry}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {results.some((x) => x.status !== "ok") && <p className="bi-note">{e.skippedNote}</p>}
      {results.some((x) => x.key === "distances" && x.fields.length > 0) && (
        <p className="bi-note">
          {e.osmCredit}{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
            {e.osmLicence}
          </a>
        </p>
      )}
    </section>
  );
}

function Section({
  title,
  funnels,
  fields,
  rows,
  set,
  open,
  projectId,
}: {
  projectId: string;
  title: string;
  funnels: Funnel[];
  fields: ReceiptField[];
  rows: number;
  set: string;
  open: (set: string, title: string) => void;
}) {
  const groups = ["files", "layers", "public", "engine"].map(
    (g) => [g, fields.filter((f) => f.group === g)] as const,
  );
  return (
    <section className="bi-card">
      <div className="bi-head">
        <h3>{title}</h3>
        <Button className="button" onPress={() => open(set, title)}>
          {b.viewRows(rows)}
        </Button>
      </div>
      <div className="bi-funnels">
        {funnels.map((f) => (
          <div key={f.file} className="bi-fn">
            {f.lines.map((l, i) => (
              <div
                key={`${l.op}${l.n}${l.text}`}
                className={`bi-line${l.op === "=" ? " bi-tot" : ""}${l.op === "=" && i > 0 ? " bi-rule" : ""}`}
              >
                <span className="bi-op">{l.op}</span>
                <span className="bi-n">{l.n.toLocaleString()}</span>
                <span>{l.text}</span>
                <span>
                  {l.rows && (
                    <Button
                      className="wiz-link"
                      onPress={() => open(l.rows ?? "", `${f.filename || f.file}: ${l.text}`)}
                    >
                      {b.seeThem}
                    </Button>
                  )}
                </span>
              </div>
            ))}
            {f.note && <p className="bi-note">{f.note}</p>}
          </div>
        ))}
      </div>
      <table className="bi-tbl">
        <thead>
          <tr>
            <th>{b.field}</th>
            <th>{b.has}</th>
            <th>{b.summary}</th>
            <th>{b.from}</th>
            <th>{b.notes}</th>
          </tr>
        </thead>
        {groups.map(([g, list]) =>
          list.length === 0 ? null : (
            <tbody key={g}>
              <tr className="bi-grp">
                <td colSpan={5}>{b.groups[g]}</td>
              </tr>
              {list.map((f) => (
                <tr key={f.field}>
                  <td className="mono">{f.field}</td>
                  <td className="bi-has">
                    <span className="bi-bar">
                      <i style={{ width: `${Math.round(100 * f.share)}%` }} />
                    </span>
                    {f.filled.toLocaleString()} · {pct(f.share)}
                  </td>
                  <td>
                    {f.summary}
                    <FieldDetail
                      projectId={projectId}
                      set={set === "sales" ? "sales" : "universe"}
                      field={f.field}
                    />
                  </td>
                  <td className="mono bi-src">{f.source}</td>
                  <td>{f.note}</td>
                </tr>
              ))}
            </tbody>
          ),
        )}
      </table>
    </section>
  );
}

function pct(share: number): string {
  const p = 100 * share;
  return p > 0 && p < 1 ? `${p.toFixed(1)}%` : p > 99 && p < 100 ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

const PAGE = 50;

/** Rows a page at a time: only that page is read from the file. CSV export streams the whole set. */
/** Repeated IDs: the rows of one ID share a background, and IDs alternate. */
export function band(bands: number[] | null | undefined, i: number): string | undefined {
  if (!bands) return undefined;
  return bands[i] ? "band-b" : "band-a";
}

/** The step that's running, in detail: what it's doing, how far through, how long it's taken, that the run is
 * still alive (it says so every 2 seconds), and Skip for a step that can be left out. */
function Busy({ job, since, skip }: { job: Job; since: number; skip: (part: string) => void }) {
  const skipping = job.part !== null && job.skipping.includes(job.part);
  // Two missed heartbeats and more: it may be stuck (a frozen process says nothing at all).
  const silent = job.quiet > 10;
  return (
    <div className="bi-busy">
      {job.detail && <span className="bi-detail">{job.detail}</span>}
      {job.sub !== null && (
        <span className="bi-prog bi-sub">
          <i style={{ width: `${Math.round(100 * job.sub)}%` }} />
        </span>
      )}
      <span className={silent ? "wiz-warn" : "bi-alive"}>
        {silent ? b.silent(clock(job.quiet)) : b.alive(clock(Math.max(0, job.elapsed - since)))}
      </span>
      {job.part && (
        <Button className="button bi-skip" isDisabled={skipping} onPress={() => job.part && skip(job.part)}>
          {skipping ? b.skipping : b.skip}
        </Button>
      )}
      {job.part && !skipping && <span className="bi-skip-note">{b.skipNote}</span>}
    </div>
  );
}

function RowsDialog({
  projectId,
  set,
  title,
  close,
}: {
  projectId: string;
  set: string;
  title: string;
  close: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const page = useQuery({
    queryKey: ["bring-in-rows", projectId, set, offset],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/bring-in/rows/{name}", {
          params: { path: { project_id: projectId, name: set }, query: { offset, limit: PAGE } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const p = page.data;
  const total = p?.total ?? 0;
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal rl bi-rows">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {b.rowsTitle(title)}
          </Heading>
          {p?.kept_total != null && (
            <p className="wiz-from">{b.keptNote(total - p.kept_total, p.kept_total)}</p>
          )}
          <div className="bi-pager">
            <span>{p ? b.rowsOf(total ? offset + 1 : 0, Math.min(offset + PAGE, total), total) : ""}</span>
            <span className="bi-grow" />
            <Button className="button" isDisabled={offset === 0} onPress={() => setOffset(0)}>
              {b.first}
            </Button>
            <Button
              className="button"
              isDisabled={offset === 0}
              onPress={() => setOffset(Math.max(0, offset - PAGE))}
            >
              {b.prev}
            </Button>
            <Button
              className="button"
              isDisabled={offset + PAGE >= total}
              onPress={() => setOffset(offset + PAGE)}
            >
              {b.nextPage}
            </Button>
            <a
              className="button"
              href={`/api/projects/${projectId}/bring-in/rows/${set}/csv`}
              download={`${set}.csv`}
            >
              {b.exportCsv}
            </a>
          </div>
          <div className="bi-scroll">
            {p && (
              <table className="bi-tbl bi-data" style={{ whiteSpace: "nowrap", fontSize: "0.8rem" }}>
                <thead>
                  <tr>
                    {p.columns.map((c) => (
                      <th key={c} className="mono bi-cell">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {p.rows.map((row, i) => (
                    <tr
                      // biome-ignore lint/suspicious/noArrayIndexKey: a page of rows, in file order
                      key={offset + i}
                      className={[band(p.bands, i), p.kept?.[i] ? "bi-kept" : ""].filter(Boolean).join(" ")}
                    >
                      {row.map((cell, j) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: a row's cells, by column
                        <td key={j} className="mono bi-cell">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {page.error && (
            <p className="error" role="alert">
              {page.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {b.close}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate } from "../App";
import { api, type Funnel, type Receipt, type ReceiptField, unwrap } from "../api/client";
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
    mutationFn: async (what: "run" | "stop" | "accept") => {
      const path = `/api/projects/{project_id}/bring-in/${what}` as const;
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
  const elapsed = last ? last.at : 0;
  const left = r && running ? Math.max(0, r.seconds + 4 - elapsed) : null;
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
            <i style={{ width: `${Math.round(100 * (last?.fraction ?? 0.05))}%` }} />
          </div>
          <ul className="bi-steps">
            {v.job?.steps.map((s, i) => (
              <li key={s.step} className={i === (v.job?.steps.length ?? 0) - 1 ? "now" : "done"}>
                {i === (v.job?.steps.length ?? 0) - 1 ? "● " : "✓ "}
                {s.message}
              </li>
            ))}
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
            <li>{b.fields(v.plan.fields)}</li>
          </ul>
        </div>
      ) : (
        <ReceiptView
          projectId={projectId}
          receipt={r}
          stale={v.stale}
          open={(set, title) => setRows({ set, title })}
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
}: {
  projectId: string;
  receipt: Receipt;
  stale: boolean;
  open: (set: string, title: string) => void;
}) {
  return (
    <div className={stale ? "bi-receipt bi-stale" : "bi-receipt"}>
      {stale && <p className="wiz-from">{b.staleNote}</p>}
      <div className="rc-meter ok">
        <b>{b.meter(r.universe.rows, r.sales.rows)}</b>
        <span className="rc-was">{b.ran(when(r.ran_at), r.seconds, r.engine)}</span>
      </div>
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
  const groups = ["files", "layers", "engine"].map((g) => [g, fields.filter((f) => f.group === g)] as const);
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
                    <Button className="wiz-link" onPress={() => open(l.rows ?? "", `${title}: ${l.text}`)}>
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
                    // biome-ignore lint/suspicious/noArrayIndexKey: a page of rows, in file order
                    <tr key={offset + i}>
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

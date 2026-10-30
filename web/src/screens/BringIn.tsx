import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";
import { navigate } from "../App";
import { api, type EnrichResult, type Funnel, type Receipt, type ReceiptField, unwrap } from "../api/client";
import { stepKey, useStep, useStepAct, useStepNav } from "../api/steps";
import { FieldDetail, openRow } from "../components/FieldDetail";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { InfoTip } from "../components/Tip";
import { band, pct, when } from "../lib/format";
import { t } from "../strings";

const b = t.bringIn;

/** Whether Looks right was pressed on an up-to-date receipt: model groups can start. */
export function useAccepted(projectId: string): boolean {
  return useStep("bring-in", projectId).data?.accepted ?? false;
}

type BiStep = "plan" | "run" | "universe" | "sales" | "more";
const BI_STEPS: BiStep[] = ["plan", "run", "universe", "sales", "more"];

/** Step 1, Bring in data (SPEC §3.3), one task at a time: what runs, the run, then what it brought in. */
export function BringInTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const state = useStep("bring-in", projectId);
  const act = useStepAct("bring-in", projectId);
  // Skip one part of a running run (an enrichment).
  const skip = useMutation({
    mutationFn: async (part: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/bring-in/skip/{part}", {
          params: { path: { project_id: projectId, part } },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(stepKey("bring-in", projectId), data),
  });
  const [rows, setRows] = useState<{ set: string; title: string } | null>(null);
  const nav = useStepNav<BiStep>();
  const v = state.data;
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  const running = v.status === "running";
  const r = v.receipt;
  const fresh = !!r && !v.stale;
  const fallback: BiStep = running || !r || v.stale ? (r || running ? "run" : "plan") : "universe";
  const current = nav.current(v.status, fallback, "universe");
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
  const toGroups = () => navigate({ name: "project", id: projectId, tab: "groups" });
  const steps: Step[] = BI_STEPS.map((key) => ({
    key,
    title: b.steps[key],
    status:
      key === "plan"
        ? v.blocked.length
          ? "blocked"
          : "done"
        : key === "run"
          ? r
            ? v.stale
              ? "attention"
              : "done"
            : "blank"
          : key === "more" &&
              r &&
              (r.enrichments.some((x) => x.status !== "ok") || r.checks.some((c) => !c.ok))
            ? "attention"
            : v.accepted
              ? "done"
              : "blank",
    disabled: key !== "plan" && key !== "run" && !r,
  }));
  const prev = BI_STEPS[BI_STEPS.indexOf(current) - 1];
  const back = prev ? () => go(prev) : null;
  const nextOf = (key: BiStep) => ({ label: t.wizard.next, onPress: () => go(key) });
  const staleNote = v.stale && r ? <p className="wiz-warn">{b.staleNote}</p> : null;

  return (
    <StepFrame steps={steps} current={current} go={go}>
      {current === "plan" && (
        <>
          <StepBody kicker={b.kicker} title={b.title} lede={b.lede}>
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
            {v.stale && (
              <div className="bi-warn">
                <b>{b.stale}</b> {v.changed.join(", ")}.
              </div>
            )}
            <h3 className="wiz-group">{b.whatRuns}</h3>
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
          </StepBody>
          <StepFoot next={nextOf("run")} />
        </>
      )}
      {current === "run" && (
        <>
          <StepBody kicker={b.kicker} title={b.runTitle} lede={b.runLede}>
            {running ? (
              <RunProgress job={v.job} lastSeconds={r?.seconds ?? null} skip={(part) => skip.mutate(part)} />
            ) : (
              <>
                {v.status === "failed" && v.job?.error && (
                  <div className="bi-warn" role="alert">
                    <b>{b.failed}</b> <span className="mono">{v.job.error}</span>
                    <div className="wiz-from">{b.failedLog}</div>
                  </div>
                )}
                {v.status === "stopped" && <p className="wiz-from">{b.stopped}</p>}
                {v.blocked.map((x) => (
                  <p key={x} className="wiz-warn">
                    {x}
                  </p>
                ))}
                {v.stale && r && (
                  <p className="wiz-warn">
                    {b.stale} {v.changed.join(", ")}.
                  </p>
                )}
                {fresh && r && (
                  <p className="wiz-ok">
                    {b.meter(r.universe.rows, r.sales.rows)}{" "}
                    <span className="wiz-from">{b.ran(when(r.ran_at), r.seconds, r.engine)}</span>
                  </p>
                )}
                {!r && <p className="wiz-from">{b.notRun}</p>}
              </>
            )}
            {(act.error ?? skip.error) && (
              <p className="error" role="alert">
                {(act.error ?? skip.error)?.message}
              </p>
            )}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: b.runAgain, onPress: runIt }] : []}
            next={
              running
                ? { label: b.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? nextOf("universe")
                  : {
                      label: r ? b.runAgainNext : b.run,
                      disabled: v.blocked.length > 0 || act.isPending,
                      onPress: runIt,
                    }
            }
          />
        </>
      )}
      {current === "universe" && r && (
        <>
          <StepBody kicker={b.kicker} title={b.universe}>
            {staleNote}
            <Section
              title={b.universe}
              funnels={r.universe.funnels}
              fields={r.universe.fields}
              rows={r.universe.rows}
              set="universe"
              open={(set, title) => setRows({ set, title })}
              projectId={projectId}
            />
          </StepBody>
          <StepFoot back={back} next={nextOf("sales")} />
        </>
      )}
      {current === "sales" && r && (
        <>
          <StepBody kicker={b.kicker} title={b.sales}>
            {staleNote}
            <Section
              title={b.sales}
              funnels={r.sales.funnels}
              fields={r.sales.fields}
              rows={r.sales.rows}
              set="sales"
              open={(set, title) => setRows({ set, title })}
              projectId={projectId}
            />
          </StepBody>
          <StepFoot back={back} next={nextOf("more")} />
        </>
      )}
      {current === "more" && r && (
        <>
          <StepBody kicker={b.kicker} title={b.steps.more}>
            {staleNote}
            <MoreView receipt={r} rerun={running || v.blocked.length > 0 ? null : runIt} />
          </StepBody>
          <StepFoot
            back={back}
            note={v.stale ? b.stale : null}
            next={
              v.accepted
                ? { label: b.toGroups, onPress: toGroups }
                : {
                    label: b.looksRightNext,
                    disabled: v.stale || act.isPending,
                    onPress: () => act.mutate("accept", { onSuccess: toGroups }),
                  }
            }
          />
        </>
      )}
      {rows && (
        <RowsDialog projectId={projectId} set={rows.set} title={rows.title} close={() => setRows(null)} />
      )}
    </StepFrame>
  );
}

/** Public data, the checks against Data, OpenAVMKit's notes and what ran. */
function MoreView({ receipt: r, rerun }: { receipt: Receipt; rerun: (() => void) | null }) {
  return (
    <div className="bi-receipt">
      {r.enrichments.length > 0 ? (
        <EnrichCard results={r.enrichments} rerun={rerun} />
      ) : (
        <p className="wiz-from">{b.noEnrich}</p>
      )}
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
        <h3 className="visually-hidden">{title}</h3>
        <span className="bi-grow" />
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
      <table className="bi-tbl fd-tbl">
        <thead>
          <tr>
            <th>
              <InfoTip label={b.field} text={b.fieldTip} />
            </th>
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
                <tr key={f.field} onClick={openRow}>
                  <td className="mono">
                    <FieldDetail
                      projectId={projectId}
                      set={set === "sales" ? "sales" : "universe"}
                      field={f.field}
                    />
                  </td>
                  <td className="bi-has">
                    <span className="bi-bar">
                      <i style={{ width: `${Math.round(100 * f.share)}%` }} />
                    </span>
                    {f.filled.toLocaleString()} · {pct(f.share)}
                  </td>
                  <td>{f.summary}</td>
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

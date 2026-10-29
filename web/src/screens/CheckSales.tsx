import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, Input, TextArea, TextField } from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type CleanPatch,
  type CleanReceipt,
  type CleanSetup,
  type CleanView,
  type FillRow,
  type PatternTable,
  type RelatedSale,
  type ReviewItem,
  type SaleDetail,
  unwrap,
} from "../api/client";
import { Choice, Tick } from "../components/Form";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { desktop, useCanPickFile } from "../desktop";
import { t } from "../strings";
import { when } from "./BringIn";

const s = t.sales;
type Patch = CleanPatch;
type Unit = "sqft" | "sqm";

function useClean(projectId: string) {
  return useQuery({
    queryKey: ["clean", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 600 : false),
  });
}

/** Whether Looks right was pressed on an up-to-date Check sales: step 4 can start. */
export function useSalesAccepted(projectId: string): boolean {
  return useClean(projectId).data?.accepted ?? false;
}

function money(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return "—";
  if (v !== 0 && Math.abs(v) < 1) {
    // A cent a square foot: two significant figures, not "$0.00".
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumSignificantDigits: 2,
    }).format(v);
  }
  const digits = Math.abs(v) < 100 ? 2 : 0;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v);
}

function num(v: number | null | undefined, digits = 0): string {
  return v === null || v === undefined
    ? "—"
    : v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** A price against its group's median: "16.4× the median", "0.37× the median", "1/55,000 of the median". */
function rel(r: number, of: string): string {
  if (r >= 0.1) return `${num(r, r >= 10 ? 0 : r >= 1 ? 1 : 2)}× ${of}`;
  return `1/${num(Math.round(1 / r))} of ${of}`;
}

function day(text: string | null | undefined): string {
  return text ? text.slice(0, 10) : "—";
}

/** The calls before running (Check sales, and step 5's fills and folding), and changing one. */
export function useCleanSetup(projectId: string, enabled: boolean) {
  const queryClient = useQueryClient();
  const setup = useQuery({
    queryKey: ["clean-setup", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/setup", {
          params: { path: { project_id: projectId } },
        }),
      ),
    enabled,
  });
  const change = useMutation({
    mutationFn: async (body: Patch) =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}/clean/setup", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["clean-setup", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["clean", projectId] });
      queryClient.invalidateQueries({ queryKey: ["clean-time", projectId] });
      queryClient.invalidateQueries({ queryKey: ["prepare", projectId] });
    },
  });
  return { setup, change };
}

type CsStep = "window" | "time" | "scrutiny" | "run" | "sales" | "aside";
const CS_STEPS: CsStep[] = ["window", "time", "scrutiny", "run", "sales", "aside"];

/** Step 3, Check sales (SPEC F6), one task at a time: a step per call (each with what it did last run), the run,
 * the sales it kept, and the sales set aside to keep or exclude. */
export function SalesTab({
  projectId,
  currency,
  place,
}: {
  projectId: string;
  currency: string;
  place: string;
}) {
  const queryClient = useQueryClient();
  const state = useClean(projectId);
  const v = state.data;
  const { setup, change } = useCleanSetup(projectId, !!v && v.blocked.length === 0);
  const act = useMutation({
    mutationFn: async (what: "run" | "stop" | "accept") => {
      const path = `/api/projects/{project_id}/clean/${what}` as const;
      return unwrap(await api.POST(path, { params: { path: { project_id: projectId } } }));
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["clean", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["clean-review", projectId] });
      queryClient.invalidateQueries({ queryKey: ["clean-setup", projectId] });
    },
  });
  const counts = useReviewCounts(projectId);
  // The step shown; after: a run was started here, so its results open when it's done.
  const [at, setAt] = useState<{ step: CsStep | null; after: boolean }>({ step: null, after: false });
  const [check, setCheck] = useState("");
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  if (v.blocked.length > 0)
    return (
      <div className="bi">
        <div className="bi-warn">
          <b>{s.blocked}</b> {v.blocked[0]}{" "}
          <Button
            className="wiz-link"
            onPress={() => navigate({ name: "project", id: projectId, tab: "groups" })}
          >
            {s.toGroups}
          </Button>
        </div>
      </div>
    );
  const running = v.status === "running";
  const r = v.receipt;
  const fresh = !!r && !v.stale;
  const fallback: CsStep = running ? "run" : !r ? "window" : v.stale ? "run" : "sales";
  const current: CsStep = at.after && v.status === "done" ? "sales" : (at.step ?? fallback);
  const go = (step: string) => setAt({ step: step as CsStep, after: false });
  const runIt = () => act.mutate("run", { onSuccess: () => setAt({ step: "run", after: true }) });
  const look = (c: string) => {
    setCheck(c);
    go("aside");
  };
  const u = setup.data;
  const set = (body: Patch) => change.mutate(body);
  const called = r ? (v.stale ? "attention" : "done") : "blank";
  const steps: Step[] = CS_STEPS.map((key) => ({
    key,
    title: s.steps[key],
    status:
      key === "window"
        ? u?.notices.length
          ? "attention"
          : called
        : key === "scrutiny"
          ? u && !u.location
            ? "attention"
            : called
          : key === "sales"
            ? r
              ? "done"
              : "blank"
            : key === "aside"
              ? v.accepted
                ? "done"
                : r && (counts?.undecided ?? 0) > 0
                  ? "attention"
                  : r
                    ? "done"
                    : "blank"
              : called,
    disabled: (key === "sales" || key === "aside") && !r,
  }));
  const i = CS_STEPS.indexOf(current);
  const prev = CS_STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  const onward = { label: t.wizard.next, onPress: () => go(CS_STEPS[i + 1] ?? current) };
  const kicker = s.kicker;
  const loading = <p className="empty">{setup.error?.message ?? t.project.loading}</p>;
  const errors = (
    <>
      {change.error && (
        <p className="error" role="alert">
          {change.error.message}
        </p>
      )}
      {act.error && (
        <p className="error" role="alert">
          {act.error.message}
        </p>
      )}
    </>
  );
  const callStep = (body: React.ReactNode, lede?: string) => (
    <>
      <StepBody
        kicker={kicker}
        title={s.steps[current]}
        {...(lede ? { lede: lede.charAt(0).toUpperCase() + lede.slice(1) } : {})}
      >
        {u ? body : loading}
        {errors}
      </StepBody>
      <StepFoot back={back} next={onward} />
    </>
  );

  return (
    <StepFrame steps={steps} current={current} go={go} wide={current === "aside"}>
      {current === "window" &&
        callStep(
          u && (
            <>
              <WindowCard v={u} set={set} />
              <Notices projectId={projectId} v={u} />
            </>
          ),
          s.window.sub,
        )}
      {current === "time" &&
        callStep(
          u && (
            <>
              <TimeCard v={u} set={set} projectId={projectId} />
              {u.time_adjust && <TimePreviewPanel projectId={projectId} />}
            </>
          ),
        )}
      {current === "scrutiny" &&
        callStep(u && <ScrutinyCard v={u} set={set} projectId={projectId} />, s.scrutiny.sub)}
      {current === "run" && (
        <>
          <StepBody kicker={kicker} title={s.steps.run} lede={s.runNote}>
            {running ? (
              <>
                <RunProgress job={v.job} lastSeconds={r?.seconds ?? null} />
                <p className="wiz-from">{s.noSkip}</p>
              </>
            ) : (
              <>
                {v.status === "failed" && v.job?.error && (
                  <div className="bi-warn" role="alert">
                    <b>{t.bringIn.failed}</b> <span className="mono">{v.job.error}</span>
                    <div className="wiz-from">{s.failedLog}</div>
                  </div>
                )}
                {v.status === "stopped" && <p className="wiz-from">{t.bringIn.stopped}</p>}
                {v.stale && <p className="wiz-warn">{s.stale}</p>}
                {fresh && r && (
                  <p className="wiz-ok">
                    {s.meter(r.used, r.set_aside)}{" "}
                    <span className="wiz-from">{t.bringIn.ran(when(r.ran_at), r.seconds, r.engine)}</span>
                  </p>
                )}
                {!r && <p className="wiz-from">{t.bringIn.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: s.runAgain, onPress: runIt }] : []}
            next={
              running
                ? { label: t.bringIn.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? onward
                  : { label: r ? s.runAgainNext : s.runNext, disabled: act.isPending, onPress: runIt }
            }
          />
        </>
      )}
      {current === "sales" && r && (
        <>
          <StepBody kicker={kicker} title={s.steps.sales}>
            <SalesResult projectId={projectId} view={v} receipt={r} look={look} />
          </StepBody>
          <StepFoot back={back} next={onward} note={v.stale ? s.stale : null} />
        </>
      )}
      {current === "aside" && r && (
        <>
          <StepBody kicker={kicker} title={s.steps.aside}>
            <Review
              projectId={projectId}
              currency={currency}
              place={place}
              check={check}
              setCheck={setCheck}
              view={v}
              rerun={() => go("run")}
            />
          </StepBody>
          <StepFoot
            back={back}
            note={v.stale ? s.review.apply : null}
            next={
              v.accepted
                ? { label: s.accepted, onPress: () => {}, disabled: true }
                : {
                    label: s.looksRight,
                    disabled: v.stale || act.isPending,
                    onPress: () => act.mutate("accept"),
                  }
            }
          />
        </>
      )}
    </StepFrame>
  );
}

/** What to look at before running: on the step it concerns (the sales). */
function Notices({ projectId, v }: { projectId: string; v: CleanSetup }) {
  if (v.notices.length === 0) return null;
  return (
    <div className="bi-warn">
      <b>{s.notices(v.notices.length)}</b>
      <ul className="cs-notices">
        {v.notices.map((n) => (
          <li key={n.text}>
            {n.text}{" "}
            {n.link && (
              <Button
                className="wiz-link"
                onPress={() =>
                  navigate({
                    name: "project",
                    id: projectId,
                    tab: "fields",
                    step: n.link?.split(":")[1] ?? null,
                  })
                }
              >
                {s.links[n.link?.split(":")[1] ?? ""] ?? s.toData}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export type CardProps = { v: CleanSetup; set: (body: Patch) => void };

function Card({ title, sub, children }: { title: React.ReactNode; sub: string; children: React.ReactNode }) {
  // In a step, the step says what it is: a card only shows its on/off control (a tick) and how it stands.
  return (
    <section className="cs-step">
      {typeof title !== "string" && (
        <div className="cs-head">
          <h3>{title}</h3>
          <span className="wiz-from">{sub}</span>
        </div>
      )}
      {children}
    </section>
  );
}

function WindowCard({ v, set }: CardProps) {
  const first = v.years[0]?.year ?? v.default_from;
  const options: [string, string][] = [];
  for (let y = Math.min(first, v.default_from); y <= v.valuation_year; y++) {
    options.push([String(y), y === v.default_from ? s.window.default(y) : String(y)]);
  }
  const vacantSales = v.years.some((y) => y.vacant > 0);
  const top = Math.max(1, ...v.years.map((y) => y.improved + y.vacant));
  return (
    <Card title={s.window.title} sub={s.window.sub}>
      <div className="cs-row">
        <Choice
          label={s.window.from}
          value={String(v.sales_from)}
          options={options}
          onChange={(y) => set({ sales_from: Number(y) === v.default_from ? null : Number(y) })}
        />
        {vacantSales && (
          <Choice
            label={s.window.vacantFrom}
            value={String(v.vacant_from)}
            options={options}
            onChange={(y) => set({ vacant_from: Number(y) === v.default_from ? null : Number(y) })}
          />
        )}
      </div>
      <p className="cs-text">
        {s.window.text(v.in_window, v.total, v.valuation_year - v.sales_from)}
        {vacantSales ? ` ${s.window.vacantHint}` : ` ${s.window.noVacant}`}
      </p>
      <div className="cs-bars" role="img" aria-label={s.window.chart}>
        {v.years.map((y) => {
          const n = y.improved + y.vacant;
          const inside = y.year >= Math.min(v.sales_from, v.vacant_from);
          return (
            <div key={y.year} className="cs-bar">
              <i
                className={inside ? "" : "out"}
                style={{ height: `${(100 * n) / top}%` }}
                title={s.window.bar(y.year, n)}
              />
              <span>{y.year}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function TimeCard({ v, set, projectId }: CardProps & { projectId: string }) {
  const queryClient = useQueryClient();
  const [importing, setImporting] = useState<string | null>(null);
  const borrow = useMutation({
    mutationFn: async (body: { group: string; source: string | null }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/clean/time/borrow", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["clean-setup", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["clean", projectId] });
      queryClient.invalidateQueries({ queryKey: ["clean-time", projectId] });
    },
  });
  const choose = (gid: string, from: string, now: string) => {
    if (from === "file") return setImporting(gid);
    setImporting(null);
    if (from !== now) borrow.mutate({ group: gid, source: from === "own" ? null : from });
  };
  const target = v.groups.find((g) => g.id === importing);
  return (
    <Card
      title={
        <Tick isSelected={v.time_adjust} onChange={(on) => set({ time_adjust: on })}>
          {s.time.title}
        </Tick>
      }
      sub={v.time_adjust ? s.time.on : s.time.off}
    >
      <p className="cs-text wiz-from">{s.time.what}</p>
      {v.time_adjust && (
        <>
          <div className="cs-row">
            <Choice
              label={s.time.start}
              value={v.period}
              options={[
                ["Q", s.time.quarters],
                ["M", s.time.months],
              ]}
              onChange={(period) => set({ period })}
            />
            <span className="wiz-from">{s.time.coarser}</span>
          </div>
          <table className="bi-tbl cs-tbl cs-ta">
            <thead>
              <tr>
                <th>{s.group}</th>
                <th className="cs-n">{s.time.sales}</th>
                <th>{s.time.from}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {v.groups
                .filter((g) => g.id !== "UNKNOWN")
                .map((g) => {
                  const now = g.file ? "file" : (g.borrow ?? "own");
                  const options: [string, string][] = [
                    ["own", s.time.ownSales],
                    ...v.groups
                      .filter((o) => o.id !== g.id && o.id !== "UNKNOWN")
                      .map((o) => [o.id, s.time.borrowFrom(o.name)] as [string, string]),
                    ["file", s.time.ownFile],
                  ];
                  return (
                    <tr key={g.id}>
                      <td>
                        <span className="mg-sw ab-sw" style={{ background: g.color }} />
                        {g.name}
                      </td>
                      <td className="cs-n">{num(g.sales)}</td>
                      <td>
                        <Choice
                          label={`${s.time.from}: ${g.name}`}
                          hideLabel
                          value={importing === g.id ? "file" : now}
                          options={options}
                          onChange={(from) => choose(g.id, from, now)}
                        />
                      </td>
                      <td className="wiz-from cs-ta-note">
                        {g.file ? (
                          <>
                            {s.time.fileSays(g.file.name, g.file.periods, g.file.first, g.file.last)}{" "}
                            <Button className="wiz-link" onPress={() => setImporting(g.id)}>
                              {s.time.replace}
                            </Button>
                          </>
                        ) : g.borrow ? (
                          s.time.borrowing
                        ) : g.sales < 30 ? (
                          s.time.fewSales
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {target && (
            <TimeFileImport
              projectId={projectId}
              group={target.id}
              name={target.name}
              close={() => setImporting(null)}
            />
          )}
          {borrow.error && (
            <p className="error" role="alert">
              {borrow.error.message}
            </p>
          )}
        </>
      )}
    </Card>
  );
}

/** A model group's own time adjustment: the format said exactly, the file checked by OpenAVMKit's own reader, every
 * problem listed; kept only when it can be used. */
function TimeFileImport({
  projectId,
  group,
  name,
  close,
}: {
  projectId: string;
  group: string;
  name: string;
  close: () => void;
}) {
  const queryClient = useQueryClient();
  const canPick = useCanPickFile();
  const [path, setPath] = useState("");
  const check = useMutation({
    mutationFn: async (file: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/clean/time/file/{group}", {
          params: { path: { project_id: projectId, group } },
          body: { path: file },
        }),
      ),
    onSuccess: (data) => {
      if (data.ok) {
        queryClient.invalidateQueries({ queryKey: ["clean-setup", projectId] });
        queryClient.invalidateQueries({ queryKey: ["clean", projectId] });
        queryClient.invalidateQueries({ queryKey: ["clean-time", projectId] });
        close();
      }
    },
  });
  const pick = async () => {
    const chosen = await desktop.pickFile();
    if (chosen) {
      setPath(chosen);
      check.mutate(chosen);
    }
  };
  const result = check.data;
  return (
    <section className="bi-card cs-import" aria-label={s.time.importTitle(name)}>
      <h3>{s.time.importTitle(name)}</h3>
      <p className="cs-text">{s.time.formatLede}</p>
      <ul className="cs-format">
        <li>
          <span className="mono">period</span>: {s.time.formatPeriod}
        </li>
        <li>
          <span className="mono">index</span>: {s.time.formatIndex}
        </li>
      </ul>
      <pre className="cs-example">{"period,index\n2021-Q1,100\n2021-Q2,101.8\n2021-Q3,103.1\n…"}</pre>
      <p className="wiz-from cs-text">{s.time.formatMore}</p>
      <div className="cs-row">
        {canPick ? (
          <Button className="button button-primary" isDisabled={check.isPending} onPress={() => void pick()}>
            {s.time.chooseFile}
          </Button>
        ) : (
          <>
            <TextField
              className="field field-long"
              value={path}
              onChange={setPath}
              aria-label={s.time.pathLabel}
            >
              <span className="field-label">{s.time.pathLabel}</span>
              <Input className="input" placeholder={s.time.pathPlaceholder} />
            </TextField>
            <Button
              className="button button-primary"
              isDisabled={!path.trim() || check.isPending}
              onPress={() => check.mutate(path.trim())}
            >
              {s.time.checkFile}
            </Button>
          </>
        )}
        <Button className="button" onPress={close}>
          {s.time.cancel}
        </Button>
      </div>
      {result && !result.ok && (
        <div className="bi-warn" role="alert">
          <b>{s.time.cantUse}</b>
          <ul className="cs-notices">
            {result.problems.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>
      )}
      {check.error && (
        <p className="error" role="alert">
          {check.error.message}
        </p>
      )}
    </section>
  );
}

const METHODS = ["median", "mean", "mode", "zero", "min", "max", "leave"] as const;

function putsIn(row: FillRow): string {
  const m = row.fill.method;
  if (m === "leave") return s.fill.leaveNote;
  if (m === "zero") return "0";
  const v = row.stats[m];
  return v === undefined ? "—" : s.fill.example(s.fill.methods[m], num(v, Math.abs(v) < 10 ? 1 : 0));
}

export function FillCard({ v, set }: CardProps) {
  return (
    <Card title={s.fill.title} sub={s.fill.sub}>
      <p className="cs-text wiz-from">{s.fill.what}</p>
      {v.fills.length > 0 ? (
        <table className="bi-tbl cs-tbl">
          <thead>
            <tr>
              <th>{s.fill.field}</th>
              <th className="cs-n">{s.fill.blank}</th>
              <th>{s.fill.with}</th>
              <th>{s.fill.puts}</th>
              <th>{s.fill.for}</th>
            </tr>
          </thead>
          <tbody>
            {v.fills.map((row) => (
              <tr key={row.field}>
                <td>
                  {row.name} <span className="mono wiz-from">{row.field}</span>
                  <div className="wiz-from cs-why-fill">{row.why}</div>
                </td>
                <td className="cs-n">{num(row.blanks)}</td>
                <td>
                  <Choice
                    label={s.fill.with}
                    hideLabel
                    value={row.fill.method}
                    options={METHODS.map((m) => [m, s.fill.methods[m]] as const)}
                    onChange={(method) => set({ fill: { field: row.field, method, scope: row.fill.scope } })}
                  />
                </td>
                <td className="wiz-from">{putsIn(row)}</td>
                <td>
                  <Choice
                    label={s.fill.for}
                    hideLabel
                    isDisabled={row.fill.method === "leave"}
                    value={row.fill.scope}
                    options={[
                      ["all", s.fill.scopes.all],
                      ["impr", s.fill.scopes.impr],
                      ["vacant", s.fill.scopes.vacant],
                    ]}
                    onChange={(scope) => set({ fill: { field: row.field, method: row.fill.method, scope } })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="wiz-ok">{s.fill.none}</p>
      )}
      <details className="bi-details">
        <summary>{s.fill.auto(v.auto.length)}</summary>
        <ul>
          {v.auto.map((a) => (
            <li key={a}>{a}</li>
          ))}
          <li>{s.fill.area}</li>
        </ul>
      </details>
    </Card>
  );
}

function ScrutinyCard({ v, set, projectId }: CardProps & { projectId: string }) {
  const options: [string, string][] = [
    ["", s.scrutiny.none],
    ...v.locations.map((l) => [l.value, l.label] as [string, string]),
  ];
  const checks: [string, string, string][] = [
    ["cluster", s.scrutiny.checks.cluster, s.scrutiny.checks.clusterWhy],
    ["dupe_deed_date", s.scrutiny.checks.deed, v.deed ? s.scrutiny.checks.deedWhy : s.scrutiny.checks.noDeed],
    ["dupe_date_price", s.scrutiny.checks.datePrice, ""],
    ["false_vacant", s.scrutiny.checks.vacant, v.year_built ? "" : s.scrutiny.checks.noYear],
    ["built_after_sale", s.scrutiny.checks.builtAfter, v.year_built ? "" : s.scrutiny.checks.noYear],
    ["vacant_priced_improved", s.scrutiny.checks.vacantPriced, s.scrutiny.checks.vacantPricedWhy],
    [
      "same_surname",
      s.scrutiny.checks.surname,
      v.names ? s.scrutiny.checks.surnameWhy : s.scrutiny.checks.noNames,
    ],
  ];
  const can = (key: string) =>
    !(
      (key === "dupe_deed_date" && !v.deed) ||
      (key === "same_surname" && !v.names) ||
      ((key === "false_vacant" || key === "built_after_sale") && !v.year_built)
    );
  return (
    <Card title={s.scrutiny.title} sub={s.scrutiny.sub}>
      <p className="cs-text wiz-from">{s.scrutiny.what}</p>
      <div className={v.location ? "cs-row" : "cs-row bi-warn"}>
        <Choice
          label={s.scrutiny.near}
          value={v.location ?? ""}
          options={options}
          onChange={(location) => set({ location })}
        />
        <span className={v.location ? "wiz-from" : ""}>
          {v.location ? s.scrutiny.nearHelp : s.scrutiny.noLocation}{" "}
          {v.locations.length === 0 && (
            <Button
              className="wiz-link"
              onPress={() => navigate({ name: "project", id: projectId, tab: "fields", step: "location" })}
            >
              {s.scrutiny.addLocation}
            </Button>
          )}
        </span>
      </div>
      <p className="cs-text">
        {s.scrutiny.similar} {v.similar.join(", ")}
      </p>
      <div className="cs-checks">
        <b>{s.scrutiny.checksTitle}</b>
        {checks.map(([key, label, why]) => (
          <div key={key} className="cs-check">
            <Tick
              isSelected={(v.checks[key] ?? true) && can(key)}
              isDisabled={!can(key)}
              onChange={(on) => set({ checks: { [key]: on } })}
            >
              {label}
            </Tick>
            {why && <span className="wiz-from">{why}</span>}
          </div>
        ))}
      </div>
      <p className="wiz-from cs-text">{s.scrutiny.always}</p>
    </Card>
  );
}

export function CollapseCard({ v, set }: CardProps) {
  return (
    <Card
      title={
        <Tick isSelected={v.collapse} onChange={(on) => set({ collapse: on })}>
          {s.collapse.title}
        </Tick>
      }
      sub={v.collapse ? s.collapse.on : s.collapse.off}
    >
      <p className="cs-text wiz-from">{s.collapse.what}</p>
      {v.collapse && (
        <>
          <div className="cs-row">
            <NumberBox
              key={`s${v.collapse_sales_min}`}
              label={s.collapse.salesMin}
              value={v.collapse_sales_min}
              onChange={(n) => set({ collapse_sales_min: n })}
            />
            <NumberBox
              key={`u${v.collapse_univ_min}`}
              label={s.collapse.univMin}
              value={v.collapse_univ_min}
              onChange={(n) => set({ collapse_univ_min: n })}
            />
          </div>
          {v.folds.length ? (
            <table className="bi-tbl cs-tbl">
              <thead>
                <tr>
                  <th>{s.fill.field}</th>
                  <th className="cs-n">{s.collapse.values}</th>
                  <th className="cs-n">{s.collapse.fold}</th>
                  <th className="cs-n">{s.collapse.parcels}</th>
                  <th>{s.collapse.which}</th>
                </tr>
              </thead>
              <tbody>
                {v.folds.map((f) => (
                  <tr key={f.field}>
                    <td>
                      {f.name} <span className="mono wiz-from">{f.field}</span>
                    </td>
                    <td className="cs-n">{num(f.values)}</td>
                    <td className="cs-n">{num(f.folded.length)}</td>
                    <td className="cs-n">{num(f.parcels)}</td>
                    <td className="cs-folds">
                      {f.folded.length === 0
                        ? s.collapse.none
                        : f.folded.slice(0, 8).join(", ") +
                          (f.folded.length > 8 ? s.collapse.more(f.folded.length - 8) : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="cs-text">{s.collapse.noFields}</p>
          )}
        </>
      )}
    </Card>
  );
}

function NumberBox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  // Keyed on the value by its parent: a new value starts it afresh.
  const [text, setText] = useState(String(value));
  const commit = () => {
    const n = Math.round(Number(text));
    if (Number.isFinite(n) && n >= 1 && n !== value) onChange(n);
    else setText(String(value));
  };
  return (
    <TextField
      className="field field-short"
      value={text}
      onChange={setText}
      onBlur={commit}
      aria-label={label}
    >
      <span className="field-label">{label}</span>
      <Input className="input" inputMode="numeric" onKeyDown={(e) => e.key === "Enter" && commit()} />
    </TextField>
  );
}

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
function SalesResult({
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
        <span className="wiz-from">{t.bringIn.ran(when(r.ran_at), r.seconds, r.engine)}</span>
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
        <table className="bi-tbl cs-tbl">
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
      <table className="bi-tbl cs-tbl cs-patterns">
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
                <td>{d?.title ?? key}</td>
                <td className="cs-n">{num(n)}</td>
                <td className="cs-n">{share(n)}</td>
                <td>{d?.cause}</td>
                <td>{d?.actions[0]}</td>
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
          <tr className="cs-fl tot">
            <td>
              <b>{p.flagged}</b>
            </td>
            <td className="cs-n">{num(flagged)}</td>
            <td className="cs-n">{share(flagged)}</td>
            <td colSpan={3} />
          </tr>
        </tbody>
      </table>
    </section>
  );
}

type Curved = {
  id: string;
  name: string;
  color: string;
  per_year: number | null;
  first: string | null;
  last: string | null;
  curve: number[];
};

/** How prices moved, per model group: an index line each. */
function Charts({
  groups,
  schedule,
}: {
  groups: Curved[];
  schedule?: ((group: string) => void) | undefined;
}) {
  const curves = groups.filter((g) => g.curve.length > 1);
  return (
    <div className="cs-charts">
      {curves.map((g) => (
        <figure key={g.id} className="cs-chart">
          <figcaption>
            <span className="mg-sw ab-sw" style={{ background: g.color }} />
            <b>{g.name}</b> {g.per_year !== null && s.time.perYear(g.per_year)}
          </figcaption>
          <Curve points={g.curve} color={g.color} />
          <div className="cs-chart-foot">
            <span>{g.first?.slice(0, 7)}</span>
            <span>×{num(g.curve.at(-1) ?? 1, 2)}</span>
            <span>{g.last?.slice(0, 7)}</span>
          </div>
          {schedule && (
            <Button className="wiz-link" onPress={() => schedule(g.id)}>
              {s.time.schedule}
            </Button>
          )}
        </figure>
      ))}
    </div>
  );
}

/** Time adjustment worked out alone, before running (seconds): started when the step opens, and again on asking. */
function TimePreviewPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["clean-time", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/time", {
          params: { path: { project_id: projectId } },
        }),
      ),
    refetchInterval: (x) => (x.state.data?.status === "running" ? 600 : false),
  });
  const run = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/clean/time/run", {
          params: { path: { project_id: projectId } },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(["clean-time", projectId], data),
  });
  const v = q.data;
  const needed = !!v && v.status !== "running" && v.status !== "failed" && (!v.result || v.stale);
  const asked = useRef(false);
  useEffect(() => {
    if (needed && !asked.current) {
      asked.current = true;
      run.mutate();
    }
  }, [needed, run]);
  if (!v) return null;
  const result = v.result;
  const flat = result?.groups.filter((g) => g.per_year === null && g.sales > 0) ?? [];
  return (
    <section className="cs-step">
      <h3 className="wiz-group">{s.time.preview}</h3>
      {v.status === "running" ? (
        <RunProgress job={v.job} lastSeconds={result?.seconds ?? null} />
      ) : v.status === "failed" ? (
        <p className="error" role="alert">
          {t.bringIn.failed} <span className="mono">{v.job?.error}</span>
        </p>
      ) : result ? (
        <>
          <p className="wiz-from cs-text">
            {v.stale ? s.time.previewStale : s.time.previewNote(result.seconds)}{" "}
            <Button className="wiz-link" isDisabled={run.isPending} onPress={() => run.mutate()}>
              {s.time.previewAgain}
            </Button>
          </p>
          <Charts groups={result.groups} />
          {flat.length > 0 && <p className="wiz-from">{s.groups.few(flat.map((g) => g.name).join(", "))}</p>}
        </>
      ) : null}
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

// ---------- The review: the sales set aside ----------

function useReviewCounts(projectId: string) {
  return useQuery({
    queryKey: ["clean-review", projectId, "", "", ""],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review", {
          params: { path: { project_id: projectId }, query: { limit: 1 } },
        }),
      ),
  }).data;
}

type Status = "" | "undecided" | "kept" | "excluded";

function Review({
  projectId,
  currency,
  place,
  check,
  setCheck,
  view,
  rerun,
}: {
  projectId: string;
  currency: string;
  place: string;
  check: string;
  setCheck: (c: string) => void;
  view: CleanView;
  rerun: () => void;
}) {
  const [group, setGroup] = useState("");
  const [status, setStatus] = useState<Status>("");
  const [picked, setPicked] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["clean-review", projectId, group, check, status],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review", {
          params: {
            path: { project_id: projectId },
            query: {
              group,
              status,
              limit: 500,
              ...(check.startsWith("pattern:") ? { pattern: check.slice(8) } : { check }),
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const page = list.data;
  const items = page?.items ?? [];
  const current = items.find((i) => i.key_sale === picked) ?? items[0] ?? null;
  const next = () => {
    const i = items.findIndex((x) => x.key_sale === current?.key_sale);
    const n = items[i + 1];
    if (n) setPicked(n.key_sale);
  };
  const checks: [string, string][] = [
    ["", s.review.everyCheck],
    ...Object.entries(s.review.checkNames),
    ...Object.entries(s.review.patternNames).map(([k, v]) => [`pattern:${k}`, v] as [string, string]),
  ];
  return (
    <div className="cs-review">
      <div className="cs-filters">
        <b>{s.review.title(page?.all ?? 0)}</b>
        <Choice
          label={s.group}
          hideLabel
          value={group}
          options={[
            ["", s.review.allGroups],
            ...(page?.groups ?? []).map((g) => [g.value, g.label] as [string, string]),
          ]}
          onChange={setGroup}
        />
        <Choice label={s.review.check} hideLabel value={check} options={checks} onChange={setCheck} />
        <Choice
          label={s.review.status}
          hideLabel
          value={status}
          options={[
            ["", s.review.anyStatus],
            ["undecided", s.review.undecided(page?.undecided ?? 0)],
            ["kept", s.review.kept(page?.kept ?? 0)],
            ["excluded", s.review.excluded(page?.excluded ?? 0)],
          ]}
          onChange={(v) => setStatus(v as Status)}
        />
        <span className="bi-grow" />
        {view.stale ? (
          <span className="wiz-warn">
            {s.review.apply}{" "}
            <Button className="button" onPress={rerun}>
              {s.runAgain}
            </Button>
          </span>
        ) : (
          <span className="wiz-from">{s.review.applyLater}</span>
        )}
      </div>
      {items.length === 0 ? (
        <p className="wiz-from">{s.review.empty}</p>
      ) : (
        <div className="cs-split">
          <ul className="cs-list" aria-label={s.review.listLabel}>
            {items.map((i) => (
              <li key={i.key_sale}>
                <button
                  type="button"
                  className={i.key_sale === current?.key_sale ? "cs-item sel" : "cs-item"}
                  onClick={() => setPicked(i.key_sale)}
                >
                  <b>{i.address ?? i.key}</b>
                  <span>
                    {money(i.price, currency)}
                    {i.price_per_area !== null && i.price_per_area !== undefined && (
                      <>
                        {" · "}
                        {money(i.price_per_area, currency)}/{s.unit[(page?.unit ?? "sqft") as Unit]}
                        {i.ratio ? ` · ${rel(i.ratio, s.review.itsGroupShort)}` : ""}
                      </>
                    )}
                  </span>
                  <span>
                    {pills(i)}
                    <span className="wiz-from"> {day(i.sale_date)}</span>
                  </span>
                </button>
              </li>
            ))}
            {page && page.total > items.length && (
              <li className="wiz-from cs-more">{s.review.more(page.total - items.length)}</li>
            )}
          </ul>
          {current && (
            <SaleView
              key={current.key_sale}
              projectId={projectId}
              item={current}
              unit={(page?.unit ?? "sqft") as Unit}
              currency={currency}
              place={place}
              next={next}
            />
          )}
        </div>
      )}
    </div>
  );
}

function pills(i: ReviewItem) {
  const out: React.ReactNode[] = [];
  if (i.status !== "undecided") {
    out.push(
      <span key="status" className={`cs-pill ${i.status}`}>
        {i.status === "kept" ? s.review.keptPill : s.review.excludedPill}
      </span>,
    );
  }
  if (i.ratio) {
    out.push(
      <span key="r" className={i.ratio >= 1 ? "cs-pill hi" : "cs-pill lo"}>
        {i.ratio >= 1 ? s.review.high : s.review.low}
      </span>,
    );
  }
  if (i.flag_only)
    out.push(
      <span key="only" className="cs-pill">
        {s.review.flagOnly}
      </span>,
    );
  else if (i.pattern?.split(",").includes("1"))
    out.push(
      <span key="size" className="cs-pill">
        {s.review.oddSize}
      </span>,
    );
  for (const c of i.checks.filter((c) => c !== "cluster")) {
    out.push(
      <span key={c} className="cs-pill">
        {s.review.checkNames[c as keyof typeof s.review.checkNames] ?? c}
      </span>,
    );
  }
  if (i.second_look)
    out.push(
      <span key="2" className="cs-pill">
        {s.review.secondPill}
      </span>,
    );
  return out;
}

/** Why it was set aside, in plain words, from its pattern (the five anomalies) and checks. */
function why(i: ReviewItem, d: SaleDetail | undefined, currency: string, unit: Unit): string[] {
  const out: string[] = [];
  const u = s.unit[unit];
  if (i.ratio && i.median && i.price_per_area !== null && i.price_per_area !== undefined) {
    const area = d?.area ? ` ${s.review.with(num(d.area), u, i.vacant)}` : "";
    out.push(
      s.review.sold(money(i.price, currency), area, money(i.price_per_area, currency), u) +
        s.review.vs(rel(i.ratio, s.review.theMedian), (i.count ?? 1) - 1, money(i.median, currency)),
    );
  } else if (i.price !== null && i.price !== undefined) {
    out.push(s.review.soldFor(money(i.price, currency)));
  }
  for (const c of i.checks) {
    const found = i.details[c];
    const said = found && s.review.details[c];
    const text = said ? said(found) : s.review.checkWhy[c];
    if (text) out.push(text);
  }
  if (i.seller && i.buyer) out.push(s.review.sellerBuyer(i.seller, i.buyer));
  if (i.second_look) out.push(s.review.second);
  return out;
}

function SaleView({
  projectId,
  item: i,
  unit,
  currency,
  place,
  next,
}: {
  projectId: string;
  item: ReviewItem;
  unit: Unit;
  currency: string;
  place: string;
  next: () => void;
}) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState(i.note);
  const detail = useQuery({
    queryKey: ["clean-sale", projectId, i.key_sale],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/clean/review/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: i.key_sale } },
        }),
      ),
  });
  const mark = useMutation({
    mutationFn: async (m: { key: string; action: "keep" | "exclude" | null; note: string }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/clean/marks/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: m.key } },
          body: { action: m.action, note: m.note },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(["clean", projectId], data);
      queryClient.invalidateQueries({ queryKey: ["clean-review", projectId] });
    },
  });
  const d = detail.data;
  const u = s.unit[unit];
  const decide = (action: "keep" | "exclude" | null) =>
    mark.mutate({ key: i.key_sale, action, note }, { onSuccess: () => action && next() });
  return (
    <section className="bi-card cs-detail" aria-label={i.address ?? i.key}>
      <h3>
        {i.address ?? i.key}{" "}
        <span className="wiz-from">{s.review.head(i.group_name, day(i.sale_date), i.key_sale)}</span>
      </h3>
      {why(i, d, currency, unit).map((line) => (
        <p key={line} className="cs-why">
          {line}
        </p>
      ))}
      <Readings i={i} unit={unit} currency={currency} />
      <Diagnosis i={i} />
      {d && <Look address={i.address} place={place} latitude={d.latitude} longitude={d.longitude} />}
      {d && d.members.length > 1 && (
        <>
          <Dots members={d.members} self={i.key_sale} median={i.median} currency={currency} />
          <p className="wiz-from cs-text">{s.review.dotsNote(u)}</p>
          <table className="bi-tbl cs-tbl">
            <thead>
              <tr>
                <th>{s.review.itsGroup}</th>
                <th className="cs-n">{s.review.perArea(u)}</th>
                <th className="cs-n">{i.vacant ? s.review.land(u) : s.review.finished(u)}</th>
                <th>{s.review.soldOn}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.members.map((m) => (
                <tr key={m.key_sale} className={m.key_sale === i.key_sale ? "cs-self" : ""}>
                  <td>{m.address ?? m.key_sale}</td>
                  <td className="cs-n">{money(m.price_per_area, currency)}</td>
                  <td className="cs-n">{num(m.area)}</td>
                  <td>{day(m.sale_date)}</td>
                  <td>
                    {m.key_sale === i.key_sale ? (
                      <span className="cs-pill hi">{s.review.thisSale}</span>
                    ) : m.flagged ? (
                      <span className="cs-pill">{s.review.setAside}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {d && <Related related={d.related} currency={currency} unit={unit} />}
      {d && (
        <p className="wiz-from cs-text">
          {s.review.data(num(d.area), u, i.vacant, d.year_built, money(d.raw_price, currency))}
        </p>
      )}
      <TextField className="cs-note-field" value={note} onChange={setNote} aria-label={s.review.noteLabel}>
        <TextArea className="cs-note" placeholder={s.review.notePlaceholder} />
      </TextField>
      <div className="cs-actions">
        {i.status === "undecided" ? (
          <>
            <Button
              className="button"
              isDisabled={!i.checks.length || !note.trim() || mark.isPending}
              onPress={() => decide("keep")}
            >
              {s.review.keep}
            </Button>
            <Button className="button" isDisabled={mark.isPending} onPress={() => decide("exclude")}>
              {s.review.exclude}
            </Button>
            <span className="wiz-from">{s.review.keepNote}</span>
          </>
        ) : (
          <>
            <span className="wiz-ok">{i.status === "kept" ? s.review.isKept : s.review.isExcluded}</span>
            <Button className="button" isDisabled={mark.isPending} onPress={() => decide(null)}>
              {s.review.undo}
            </Button>
          </>
        )}
        <span className="bi-grow" />
        <Button className="wiz-link" onPress={next}>
          {s.review.next}
        </Button>
      </div>
      {mark.error && (
        <p className="error" role="alert">
          {mark.error.message}
        </p>
      )}
    </section>
  );
}

/** Price, price per area and size against its group, as the five-pattern table reads them. */
function Readings({ i, unit, currency }: { i: ReviewItem; unit: Unit; currency: string }) {
  if (!i.per_area_rating) return null;
  const r = s.review.readings;
  const u = s.unit[unit];
  const rows: [string, string, string, number | null | undefined, string | null | undefined][] = [
    [r.price, money(i.price, currency), money(i.price_median, currency), i.price_dist, i.price_rating],
    [
      r.perArea(u),
      money(i.price_per_area, currency),
      money(i.median, currency),
      i.per_area_dist,
      i.per_area_rating,
    ],
    [r.size(u, i.vacant), num(i.size), num(i.size_median), i.size_dist, i.size_rating],
  ];
  return (
    <>
      <table className="bi-tbl cs-tbl cs-readings">
        <thead>
          <tr>
            <th>{r.title}</th>
            <th className="cs-n">{r.thisSale}</th>
            <th className="cs-n">{r.median}</th>
            <th className="cs-n">{r.sd}</th>
            <th>{r.reading}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, mine, median, dist, rating]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className="cs-n">{mine}</td>
              <td className="cs-n">{median}</td>
              <td className="cs-n">{dist === null || dist === undefined ? "" : dist.toFixed(2)}</td>
              <td>
                <span
                  className={rating === "in" ? "cs-pill" : rating === "high" ? "cs-pill hi" : "cs-pill lo"}
                >
                  {r[(rating ?? "in") as "low" | "in" | "high"]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="wiz-from cs-text">{r.note}</p>
    </>
  );
}

/** Its pattern: the likely causes, and what to check (the five-pattern table). */
function Diagnosis({ i }: { i: ReviewItem }) {
  const key = i.flag_only ? "other" : (i.pattern ?? "").split(",").find((p) => p in s.review.diagnosis);
  const d = key ? s.review.diagnosis[key] : undefined;
  if (!d) return null;
  return (
    <div className={i.flag_only ? "cs-diag bi-warn" : "cs-diag"}>
      <b>{d.title}</b>
      <p className="cs-text">{d.cause}</p>
      <b className="cs-small">{s.review.checkFor}</b>
      <ul className="cs-todo">
        {d.actions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </div>
  );
}

/** Street View, the aerial, Zillow and Redfin, in a viewer window beside the app (a browser tab outside it). */
function Look({
  address,
  place,
  latitude,
  longitude,
}: {
  address: string | null | undefined;
  place: string;
  latitude: number | null | undefined;
  longitude: number | null | undefined;
}) {
  const l = s.review.look;
  const where = address ? `${address}, ${place}` : "";
  const at = latitude != null && longitude != null ? `${latitude},${longitude}` : "";
  const links: [string, string][] = [];
  if (at) {
    links.push([l.streetView, `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${at}`]);
    links.push([
      l.aerial,
      `https://www.google.com/maps/@?api=1&map_action=map&center=${at}&zoom=19&basemap=satellite`,
    ]);
  }
  if (where) {
    links.push([l.zillow, `https://www.zillow.com/homes/${encodeURIComponent(where)}_rb/`]);
    // Redfin has no address link: the search's first Redfin result.
    links.push([
      l.redfin,
      `https://duckduckgo.com/?q=${encodeURIComponent(`!ducky site:redfin.com ${where}`)}`,
    ]);
  }
  if (!links.length) return null;
  return (
    <div className="cs-row cs-look">
      <b className="cs-small">{l.title}</b>
      {links.map(([label, url]) => (
        <Button
          key={label}
          className="button"
          onPress={() => desktop.view(url, `${label}: ${address ?? at}`)}
        >
          {label}
        </Button>
      ))}
      <span className="wiz-from">{l.note}</span>
    </div>
  );
}

/** Sales that may be the same transaction, or the same buyer's. */
function Related({ related, currency, unit }: { related: RelatedSale[]; currency: string; unit: Unit }) {
  const r = s.review.related;
  return (
    <section className="cs-step">
      <h4 className="wiz-group">{r.title}</h4>
      {related.length === 0 ? (
        <p className="wiz-from">{r.none}</p>
      ) : (
        <table className="bi-tbl cs-tbl">
          <thead>
            <tr>
              <th>{r.address}</th>
              <th>{r.sold}</th>
              <th className="cs-n">{r.price}</th>
              <th className="cs-n">{r.away}</th>
              <th>{r.buyer}</th>
              <th>{r.how}</th>
            </tr>
          </thead>
          <tbody>
            {related.map((x) => (
              <tr key={x.key_sale}>
                <td>
                  {x.address ?? x.key_sale}
                  {x.set_aside && <span className="cs-pill"> {s.review.setAside}</span>}
                </td>
                <td>{day(x.sale_date)}</td>
                <td className="cs-n">{money(x.price, currency)}</td>
                <td className="cs-n">
                  {x.distance == null ? "" : unit === "sqft" ? r.feet(x.distance) : r.metres(x.distance)}
                </td>
                <td>{x.buyer ?? ""}</td>
                <td>{x.why.map((w) => r.why[w] ?? w).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

/** The prices per area of the sales it was compared with, on a log scale: this sale red, others set aside orange. */
function Dots({
  members,
  self,
  median,
  currency,
}: {
  members: SaleDetail["members"];
  self: string;
  median: number | null | undefined;
  currency: string;
}) {
  const xs = members.map((m) => m.price_per_area).filter((x): x is number => !!x && x > 0);
  if (xs.length < 2) return null;
  const lo = Math.floor(Math.log10(Math.min(...xs)));
  const hi = Math.ceil(Math.log10(Math.max(...xs)));
  const span = Math.max(1, hi - lo);
  const x = (v: number) => 40 + (520 * (Math.log10(v) - lo)) / span;
  const ticks = Array.from({ length: span + 1 }, (_, k) => 10 ** (lo + k));
  return (
    <svg viewBox="0 0 600 92" className="cs-dots" role="img" aria-label={s.review.dotsLabel}>
      <line x1="40" x2="560" y1="62" y2="62" stroke="#888" />
      {ticks.map((v) => (
        <g key={v}>
          <line x1={x(v)} x2={x(v)} y1="58" y2="66" stroke="#888" />
          <text x={x(v)} y="84" textAnchor="middle" fontSize="12" fill="#555">
            {money(v, currency)}
          </text>
        </g>
      ))}
      {median && median > 0 && (
        <g>
          <line x1={x(median)} x2={x(median)} y1="18" y2="58" stroke="#333" strokeDasharray="3 3" />
          <text x={x(median)} y="13" textAnchor="middle" fontSize="12" fill="#333">
            {s.review.median(money(median, currency))}
          </text>
        </g>
      )}
      {members
        .filter((m) => m.price_per_area && m.price_per_area > 0)
        .map((m) => (
          <circle
            key={m.key_sale}
            cx={x(m.price_per_area ?? 1)}
            cy="40"
            r={m.key_sale === self ? 7 : 5}
            fill={m.key_sale === self ? "#d33" : m.flagged ? "#e8955a" : "#6f9be0"}
            opacity="0.85"
          >
            <title>{`${m.address ?? m.key_sale}: ${money(m.price_per_area, currency)}`}</title>
          </circle>
        ))}
    </svg>
  );
}

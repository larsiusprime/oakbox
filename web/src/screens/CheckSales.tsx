import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { navigate } from "../App";
import { api, type CleanPatch, type CleanSetup, unwrap } from "../api/client";
import { setupKey, stepChanged, useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { Choice, Tick } from "../components/Form";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { desktop, useCanPickFile } from "../desktop";
import { num, when } from "../lib/format";
import { t } from "../strings";
import { Card, type CardProps, NumberBox } from "./CleanCards";
import { Review, useReviewCounts } from "./SaleReview";
import { SalesResult, TimePreviewPanel } from "./SalesResults";

const s = t.sales;
type Patch = CleanPatch;

/** Whether Looks right was pressed on an up-to-date Check sales: step 4 can start. */
export function useSalesAccepted(projectId: string): boolean {
  return useStep("clean", projectId).data?.accepted ?? false;
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
  const state = useStep("clean", projectId);
  const v = state.data;
  const { setup, change } = useStepSetup("clean", projectId, !!v && v.blocked.length === 0);
  const act = useStepAct("clean", projectId);
  const counts = useReviewCounts(projectId);
  // The step shown; after: a run was started here, so its results open when it's done.
  const nav = useStepNav<CsStep>();
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
  const current = nav.current(v.status, fallback, "sales");
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
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
  const toValues = () => navigate({ name: "project", id: projectId, tab: "check" });
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
                ? { label: s.toValues, onPress: toValues }
                : {
                    label: s.looksRight,
                    disabled: v.stale || act.isPending,
                    onPress: () => act.mutate("accept", { onSuccess: toValues }),
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
      queryClient.setQueryData(setupKey("clean", projectId), data);
      stepChanged(queryClient, projectId, "clean");
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
          <table className="tbl cs-ta">
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
        void queryClient.invalidateQueries({ queryKey: setupKey("clean", projectId) });
        stepChanged(queryClient, projectId, "clean");
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

function ScrutinyCard({ v, set, projectId }: CardProps & { projectId: string }) {
  const options: [string, string][] = [
    ["", s.scrutiny.none],
    ...v.locations.map((l) => [l.value, l.label] as [string, string]),
  ];
  const checks: [string, string, string][] = [
    ["nominal_price", s.scrutiny.checks.nominal, ""],
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
            {key === "nominal_price" && (
              <NumberBox
                key={`n${v.nominal_below}`}
                label={s.scrutiny.checks.nominalBelow}
                value={v.nominal_below}
                onChange={(n) => set({ nominal_below: n })}
              />
            )}
          </div>
        ))}
      </div>
      <p className="wiz-from cs-text">{s.scrutiny.always}</p>
    </Card>
  );
}

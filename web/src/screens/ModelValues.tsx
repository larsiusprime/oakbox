import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type PrepareView, unwrap } from "../api/client";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { t } from "../strings";
import { when } from "./BringIn";
import { CollapseCard, FillCard, useCleanSetup } from "./CheckSales";

const m = t.values;
type MvStep = "fill" | "rare" | "run" | "done" | "models";
const MV_STEPS: MvStep[] = ["fill", "rare", "run", "done", "models"];

function usePrepare(projectId: string) {
  return useQuery({
    queryKey: ["prepare", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/prepare", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 600 : false),
  });
}

/** Step 5, Build model values (SPEC F7). It begins by preparing the fields for the models: fills for blanks they
 * can't take, and folding rare categories; then the models (not built yet). */
export function ValuesTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const state = usePrepare(projectId);
  const v = state.data;
  const { setup, change } = useCleanSetup(projectId, true);
  const act = useMutation({
    mutationFn: async (what: "run" | "stop" | "accept") => {
      const path = `/api/projects/{project_id}/prepare/${what}` as const;
      return unwrap(await api.POST(path, { params: { path: { project_id: projectId } } }));
    },
    onSuccess: (data) => queryClient.setQueryData(["prepare", projectId], data),
  });
  const [at, setAt] = useState<{ step: MvStep | null; after: boolean }>({ step: null, after: false });
  if (!v) return <p className="empty">{state.error?.message ?? t.project.loading}</p>;
  const running = v.status === "running";
  const r = v.receipt;
  const fresh = !!r && !v.stale;
  const fallback: MvStep = running ? "run" : fresh ? "done" : r ? "run" : "fill";
  const current: MvStep = at.after && v.status === "done" ? "done" : (at.step ?? fallback);
  const go = (step: string) => setAt({ step: step as MvStep, after: false });
  const runIt = () => act.mutate("run", { onSuccess: () => setAt({ step: "run", after: true }) });
  const called = r ? (v.stale ? "attention" : "done") : "blank";
  const steps: Step[] = MV_STEPS.map((key) => ({
    key,
    title: m.steps[key],
    status:
      key === "run"
        ? called
        : key === "done"
          ? v.accepted
            ? "done"
            : "blank"
          : key === "models"
            ? "blank"
            : called,
    disabled: (key === "done" && !r) || key === "models",
  }));
  const i = MV_STEPS.indexOf(current);
  const prev = MV_STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  const onward = { label: t.wizard.next, onPress: () => go(MV_STEPS[i + 1] ?? current) };
  const u = setup.data;
  const set = (body: Parameters<typeof change.mutate>[0]) => change.mutate(body);
  const errors = [change.error, act.error, setup.error].map(
    (e) =>
      e && (
        <p key={e.message} className="error" role="alert">
          {e.message}
        </p>
      ),
  );
  const blocked = v.blocked.length > 0 && (
    <div className="bi-warn">
      <b>{m.blocked}</b> {v.blocked[0]}
    </div>
  );

  return (
    <StepFrame steps={steps} current={current} go={go}>
      {current === "fill" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.fill} lede={m.fillLede}>
            {u ? <FillCard v={u} set={set} /> : <p className="empty">{t.project.loading}</p>}
            {errors}
          </StepBody>
          <StepFoot next={onward} />
        </>
      )}
      {current === "rare" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.rare}>
            {u ? <CollapseCard v={u} set={set} /> : <p className="empty">{t.project.loading}</p>}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "run" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.run} lede={m.runLede}>
            {blocked}
            {running ? (
              <RunProgress job={v.job} lastSeconds={r?.seconds ?? null} />
            ) : (
              <>
                {v.status === "failed" && v.job?.error && (
                  <p className="error" role="alert">
                    {t.bringIn.failed} <span className="mono">{v.job.error}</span>
                  </p>
                )}
                {v.stale && <p className="wiz-warn">{m.stale}</p>}
                {fresh && r && <p className="wiz-ok">{m.ran(when(r.ran_at), r.seconds)}</p>}
                {!r && !v.blocked.length && <p className="wiz-from">{t.bringIn.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: m.runAgain, onPress: runIt }] : []}
            next={
              running
                ? { label: t.bringIn.stop, onPress: () => act.mutate("stop"), primary: false }
                : fresh
                  ? onward
                  : {
                      label: r ? m.runAgainNext : m.runNext,
                      disabled: v.blocked.length > 0 || act.isPending,
                      onPress: runIt,
                    }
            }
          />
        </>
      )}
      {current === "done" && r && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.done}>
            <Prepared view={v} />
          </StepBody>
          <StepFoot
            back={back}
            note={v.stale ? m.stale : null}
            next={
              v.accepted
                ? { label: m.accepted, onPress: () => {}, disabled: true }
                : {
                    label: m.looksRight,
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

/** What was filled and folded, and the files written again. */
function Prepared({ view }: { view: PrepareView }) {
  const r = view.receipt;
  if (!r) return null;
  return (
    <div className="cs-receipt">
      {view.stale && <p className="wiz-warn">{m.stale}</p>}
      <p className="wiz-ok">{m.ran(when(r.ran_at), r.seconds)}</p>
      <section className="cs-step">
        <h3 className="wiz-group">{m.filled}</h3>
        {r.filled.length ? (
          <ul className="cs-list-plain">
            {r.filled.map((f) => (
              <li key={f.field}>
                {t.sales.filled.line(f.name, f.count, f.how)} <span className="mono wiz-from">{f.field}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="wiz-from">{m.noneFilled}</p>
        )}
      </section>
      <section className="cs-step">
        <h3 className="wiz-group">{m.folded}</h3>
        {r.folded.length ? (
          <ul className="cs-list-plain">
            {r.folded.map((f) => (
              <li key={f.field}>
                {m.foldLine(f.name, f.folded.length, f.parcels)}{" "}
                <span className="wiz-from">{f.folded.slice(0, 8).join(", ")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="wiz-from">{m.noneFolded}</p>
        )}
      </section>
      <section className="cs-step">
        <h3 className="wiz-group">{t.sales.written}</h3>
        <ul className="ab-files">
          {r.written.map((w) => (
            <li key={w.path}>
              <span className="mono">{w.path}</span>
              {w.what && <span className="wiz-from"> · {w.what}</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

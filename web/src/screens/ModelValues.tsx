import type { PrepareView } from "../api/client";
import { useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { when } from "../lib/format";
import { t } from "../strings";
import { CollapseCard, FillCard } from "./CleanCards";
import { HowTheyDid, ModelsCard, VariablesCard } from "./Models";
import { TestPicker, TestStep, WhatToKeep } from "./VarTests";

const m = t.values;
// The variable tests (SPEC F9): Test the variables is a major step, the tests the user picked its parts.
const TESTS = ["represented", "corr", "p_value", "vif"] as const;
type Test = (typeof TESTS)[number];
type MvStep =
  | "fill"
  | "rare"
  | "run"
  | "done"
  | "variables"
  | "test"
  | Test
  | "verdict"
  | "models"
  | "try"
  | "how";
const MV_STEPS: MvStep[] = [
  "fill",
  "rare",
  "run",
  "done",
  "variables",
  "test",
  ...TESTS,
  "verdict",
  "models",
  "try",
  "how",
];
const MODEL_STEPS: MvStep[] = ["variables", "test", ...TESTS, "verdict", "models", "try", "how"];
const TESTED: MvStep[] = [...TESTS, "verdict"];

/** Step 5, Build model values (SPEC F7, F9). It begins by preparing the fields for the models: fills for blanks they
 * can't take, and folding rare categories; then the variables and models, a try, and how they did. */
export function ValuesTab({ projectId }: { projectId: string }) {
  const state = useStep("prepare", projectId);
  const v = state.data;
  // The fills and the folding are Check sales' calls, made here.
  const { setup, change } = useStepSetup("clean", projectId);
  const act = useStepAct("prepare", projectId);
  const ms = useStep("model", projectId);
  const mv = ms.data;
  const prepared = !!v?.accepted;
  const { setup: mSetup, change: mChange } = useStepSetup("model", projectId, prepared);
  const mAct = useStepAct("model", projectId);
  const vs = useStep("vartest", projectId);
  const vv = vs.data;
  const vAct = useStepAct("vartest", projectId);
  const nav = useStepNav<MvStep>();
  const at = nav.at;
  if (!v || !mv || !vv)
    return <p className="empty">{(state.error ?? ms.error ?? vs.error)?.message ?? t.project.loading}</p>;
  const testing = vv.status === "running";
  const vr = vv.receipt;
  const vFresh = !!vr && !vv.stale;
  const running = v.status === "running";
  const trying = mv.status === "running";
  const r = v.receipt;
  const mr = mv.receipt;
  const fresh = !!r && !v.stale;
  const mFresh = !!mr && !mv.stale;
  const fallback: MvStep = testing
    ? "test"
    : trying
      ? "try"
      : prepared && mr
        ? mFresh
          ? "how"
          : "try"
        : prepared
          ? "variables"
          : running
            ? "run"
            : fresh
              ? "done"
              : r
                ? "run"
                : "fill";
  const current: MvStep =
    at.after && v.status === "done" && at.step === "run"
      ? "done"
      : at.after && mv.status === "done" && at.step === "try"
        ? "how"
        : at.after && vv.status === "done" && at.step === "test"
          ? "represented"
          : (at.step ?? fallback);
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
  const tryIt = () => mAct.mutate("run", { onSuccess: () => nav.ran("try") });
  const testIt = () => vAct.mutate("run", { onSuccess: () => nav.ran("test") });
  const tests = vr ? (vv.stale ? "attention" : "done") : "blank";
  const called = r ? (v.stale ? "attention" : "done") : "blank";
  const tried = mr ? (mv.stale ? "attention" : "done") : "blank";
  // The tests listed: those run, or before a run, those picked (Represented always runs).
  const picked: string[] = ["represented", ...(vr?.tests.length ? vr.tests : (mSetup.data?.tests ?? TESTS))];
  const shown = MV_STEPS.filter((key) => !(TESTS as readonly string[]).includes(key) || picked.includes(key));
  const steps: Step[] = shown.map((key) => ({
    key,
    title: m.steps[key],
    ...(TESTED.includes(key) ? { parent: "test" } : {}),
    status:
      key === "run"
        ? called
        : key === "done"
          ? v.accepted
            ? "done"
            : "blank"
          : key === "test"
            ? tests
            : TESTED.includes(key)
              ? vFresh
                ? "done"
                : "blank"
              : key === "try"
                ? tried
                : key === "how"
                  ? mr && !mv.stale
                    ? "done"
                    : "blank"
                  : MODEL_STEPS.includes(key)
                    ? prepared
                      ? "done"
                      : "blank"
                    : called,
    disabled:
      (key === "done" && !r) ||
      (MODEL_STEPS.includes(key) && !prepared) ||
      (key === "how" && !mr) ||
      (TESTED.includes(key) && !vr),
  }));
  const i = shown.indexOf(current);
  const prev = shown[i - 1];
  const back = prev ? () => go(prev) : null;
  const onward = { label: t.step.next, onPress: () => go(shown[i + 1] ?? current) };
  const u = setup.data;
  const set = (body: Parameters<typeof change.mutate>[0]) => change.mutate(body);
  const mu = mSetup.data;
  const mSet = (body: Parameters<typeof mChange.mutate>[0]) => mChange.mutate(body);
  const errors = [
    change.error,
    act.error,
    setup.error,
    mChange.error,
    mAct.error,
    mSetup.error,
    vAct.error,
  ].map(
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
                    {t.step.failed} <span className="mono">{v.job.error}</span>
                  </p>
                )}
                {v.stale && <p className="wiz-warn">{m.stale}</p>}
                {fresh && r && <p className="wiz-ok">{m.ran(when(r.ran_at), r.seconds)}</p>}
                {!r && !v.blocked.length && <p className="wiz-from">{t.step.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={running ? null : back}
            extra={fresh && !running ? [{ label: m.runAgain, onPress: runIt }] : []}
            next={
              running
                ? { label: t.step.stop, onPress: () => act.mutate("stop"), primary: false }
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
                ? { label: m.toVariables, onPress: () => go("variables") }
                : {
                    label: m.looksRight,
                    disabled: v.stale || act.isPending,
                    onPress: () => act.mutate("accept", { onSuccess: () => go("variables") }),
                  }
            }
          />
        </>
      )}
      {current === "variables" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.variables} lede={m.model.variablesLede}>
            {mu ? (
              <VariablesCard v={mu} set={mSet} fill={() => go("fill")} />
            ) : (
              <p className="empty">{t.project.loading}</p>
            )}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "test" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.test} lede={m.vartest.runLede}>
            {vv.blocked.length > 0 && (
              <div className="bi-warn">
                <b>{m.blocked}</b> {vv.blocked[0]}
              </div>
            )}
            {mu && <TestPicker setup={mu} set={mSet} disabled={testing} />}
            {testing ? (
              <RunProgress job={vv.job} lastSeconds={vr?.seconds ?? null} />
            ) : (
              <>
                {vv.status === "failed" && vv.job?.error && (
                  <p className="error" role="alert">
                    {t.step.failed} <span className="mono">{vv.job.error}</span>
                  </p>
                )}
                {vv.stale && <p className="wiz-warn">{m.vartest.stale}</p>}
                {vFresh && vr && <p className="wiz-ok">{m.vartest.ran(when(vr.ran_at), vr.seconds)}</p>}
                {!vr && !vv.blocked.length && <p className="wiz-from">{t.step.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={testing ? null : back}
            extra={vFresh && !testing ? [{ label: m.vartest.runAgain, onPress: testIt }] : []}
            next={
              testing
                ? { label: t.step.stop, onPress: () => vAct.mutate("stop"), primary: false }
                : vFresh
                  ? onward
                  : {
                      label: vr ? m.vartest.runAgainNext : m.vartest.runNext,
                      disabled: vv.blocked.length > 0 || vAct.isPending,
                      onPress: testIt,
                    }
            }
          />
        </>
      )}
      {(TESTS as readonly string[]).includes(current) && vr && (
        <>
          <StepBody kicker={m.kicker} title={m.steps[current]}>
            {vv.stale && <p className="wiz-warn">{m.vartest.stale}</p>}
            {mu ? (
              <TestStep
                key={current}
                test={current}
                view={vv}
                setup={mu}
                set={mSet}
                fill={() => go("fill")}
              />
            ) : (
              <p className="empty">{t.project.loading}</p>
            )}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "verdict" && vr && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.verdict}>
            {mu ? (
              <WhatToKeep view={vv} setup={mu} set={mSet} />
            ) : (
              <p className="empty">{t.project.loading}</p>
            )}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "models" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.models} lede={m.model.modelsLede}>
            {mu ? <ModelsCard v={mu} set={mSet} /> : <p className="empty">{t.project.loading}</p>}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "try" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.try} lede={m.model.tryLede}>
            {mv.blocked.length > 0 && (
              <div className="bi-warn">
                <b>{m.blocked}</b> {mv.blocked[0]}
              </div>
            )}
            {trying ? (
              <RunProgress job={mv.job} lastSeconds={mr?.seconds ?? null} />
            ) : (
              <>
                {mv.status === "failed" && mv.job?.error && (
                  <p className="error" role="alert">
                    {t.step.failed} <span className="mono">{mv.job.error}</span>
                  </p>
                )}
                {mv.stale && <p className="wiz-warn">{m.model.stale}</p>}
                {mFresh && mr && <p className="wiz-ok">{m.model.ran(when(mr.ran_at), mr.seconds)}</p>}
                {!mr && !mv.blocked.length && <p className="wiz-from">{t.step.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={trying ? null : back}
            extra={mFresh && !trying ? [{ label: m.model.tryAgain, onPress: tryIt }] : []}
            next={
              trying
                ? { label: t.step.stop, onPress: () => mAct.mutate("stop"), primary: false }
                : mFresh
                  ? onward
                  : {
                      label: mr ? m.model.tryAgainNext : m.model.tryNext,
                      disabled: mv.blocked.length > 0 || mAct.isPending,
                      onPress: tryIt,
                    }
            }
          />
        </>
      )}
      {current === "how" && mr && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.how} lede={m.model.howLede}>
            <HowTheyDid view={mv} />
          </StepBody>
          <StepFoot back={back} extra={[{ label: m.model.tryAgain, onPress: tryIt }]} />
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

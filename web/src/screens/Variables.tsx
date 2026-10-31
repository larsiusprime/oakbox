import { navigate } from "../App";
import type { PrepareView } from "../api/client";
import { useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { short, when } from "../lib/format";
import { t } from "../strings";
import { CollapseCard, FillCard } from "./CleanCards";
import { VarListsStep } from "./VarLists";
import { TestPicker, TestStep, WhatToKeep } from "./VarTests";

const m = t.values;
// The variable tests (SPEC F9): Test the variables is a major step, the tests the user picked its parts.
const TESTS = ["represented", "corr", "vif"] as const;
type Test = (typeof TESTS)[number];
type VStep = "fill" | "rare" | "run" | "done" | "test" | Test | "verdict" | "lists";
const V_STEPS: VStep[] = ["fill", "rare", "run", "done", "test", ...TESTS, "verdict", "lists"];
const TESTED: VStep[] = [...TESTS, "verdict"];

/** Step 5, Variables (SPEC F7, F9): preparing the fields for the models (fills for blanks they can't take, folding
 * rare categories), the variable tests, and the variable lists the models take their variables from. */
export function VariablesTab({ projectId }: { projectId: string }) {
  const state = useStep("prepare", projectId);
  const v = state.data;
  // The fills and the folding are Check sales' calls, made here.
  const { setup, change } = useStepSetup("clean", projectId);
  const act = useStepAct("prepare", projectId);
  const prepared = !!v?.accepted;
  const { setup: mSetup, change: mChange } = useStepSetup("model", projectId, prepared);
  const vs = useStep("vartest", projectId);
  const vv = vs.data;
  const vAct = useStepAct("vartest", projectId);
  const nav = useStepNav<VStep>();
  const at = nav.at;
  if (!v || !vv) return <p className="empty">{(state.error ?? vs.error)?.message ?? t.project.loading}</p>;
  const testing = vv.status === "running";
  const vr = vv.receipt;
  const vFresh = !!vr && !vv.stale;
  const running = v.status === "running";
  const r = v.receipt;
  const fresh = !!r && !v.stale;
  const fallback: VStep = testing
    ? "test"
    : prepared
      ? vr
        ? "lists"
        : "test"
      : running
        ? "run"
        : fresh
          ? "done"
          : r
            ? "run"
            : "fill";
  const current: VStep =
    at.after && v.status === "done" && at.step === "run"
      ? "done"
      : at.after && vv.status === "done" && at.step === "test"
        ? "represented"
        : (at.step ?? fallback);
  const go = nav.go;
  const runIt = () => act.mutate("run", { onSuccess: () => nav.ran("run") });
  const testIt = () => vAct.mutate("run", { onSuccess: () => nav.ran("test") });
  const tests = vr ? (vv.stale ? "attention" : "done") : "blank";
  const called = r ? (v.stale ? "attention" : "done") : "blank";
  // The tests listed: those run, or before a run, those picked (Represented always runs).
  const picked: string[] = ["represented", ...(vr?.tests.length ? vr.tests : (mSetup.data?.tests ?? TESTS))];
  const shown = V_STEPS.filter((key) => !(TESTS as readonly string[]).includes(key) || picked.includes(key));
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
              : key === "lists"
                ? prepared
                  ? "done"
                  : "blank"
                : called,
    disabled:
      (key === "done" && !r) ||
      ((key === "test" || key === "lists") && !prepared) ||
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
  const errors = [change.error, act.error, setup.error, mChange.error, mSetup.error, vAct.error].map(
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
                ? { label: m.toTests, onPress: () => go("test") }
                : {
                    label: m.looksRight,
                    disabled: v.stale || act.isPending,
                    onPress: () => act.mutate("accept", { onSuccess: () => go("test") }),
                  }
            }
          />
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
              <TestStep key={current} test={current} view={vv} setup={mu} fill={() => go("fill")} />
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
            {mu ? <WhatToKeep view={vv} setup={mu} /> : <p className="empty">{t.project.loading}</p>}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "lists" && (
        <>
          <StepBody kicker={m.kicker} title={m.steps.lists} lede={m.lists.lede}>
            <VarListsStep projectId={projectId} />
          </StepBody>
          <StepFoot
            back={back}
            next={{
              label: m.toModels,
              onPress: () => navigate({ name: "project", id: projectId, tab: "values" }),
            }}
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
                <span className="wiz-from">
                  {f.folded
                    .slice(0, 8)
                    .map((x) => short(x))
                    .join(", ")}
                </span>
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

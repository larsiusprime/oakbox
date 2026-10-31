import { useStep, useStepAct, useStepNav, useStepSetup } from "../api/steps";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { when } from "../lib/format";
import { t } from "../strings";
import { GroupModelsCard, HowTheyDid } from "./Models";
import { SmallGroupsStep } from "./SmallGroups";

const m = t.values;
type MvStep = "models" | "try" | "how" | "small";
const MV_STEPS: MvStep[] = ["models", "try", "how", "small"];

/** Step 6, Model values (SPEC F9): each model group's models, a try, and how they did. */
export function ValuesTab({ projectId }: { projectId: string }) {
  const ms = useStep("model", projectId);
  const mv = ms.data;
  const { setup: mSetup } = useStepSetup("model", projectId);
  const mAct = useStepAct("model", projectId);
  const nav = useStepNav<MvStep>();
  const at = nav.at;
  if (!mv) return <p className="empty">{ms.error?.message ?? t.project.loading}</p>;
  const trying = mv.status === "running";
  const mr = mv.receipt;
  const mFresh = !!mr && !mv.stale;
  const fallback: MvStep = trying ? "try" : mr ? (mFresh ? "how" : "try") : "models";
  const current: MvStep =
    at.after && mv.status === "done" && at.step === "try" ? "how" : (at.step ?? fallback);
  const go = nav.go;
  const tryIt = () => mAct.mutate("run", { onSuccess: () => nav.ran("try") });
  const tried = mr ? (mv.stale ? "attention" : "done") : "blank";
  const steps: Step[] = MV_STEPS.map((key) => ({
    key,
    title: m.steps[key],
    status:
      key === "try"
        ? tried
        : key === "how" || key === "small"
          ? mr && !mv.stale
            ? "done"
            : "blank"
          : "done",
    disabled: (key === "how" || key === "small") && !mr,
  }));
  const i = MV_STEPS.indexOf(current);
  const prev = MV_STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  const onward = { label: t.step.next, onPress: () => go(MV_STEPS[i + 1] ?? current) };
  const mu = mSetup.data;
  const errors = [mAct.error, mSetup.error].map(
    (e) =>
      e && (
        <p key={e.message} className="error" role="alert">
          {e.message}
        </p>
      ),
  );

  return (
    <StepFrame steps={steps} current={current} go={go}>
      {current === "models" && (
        <>
          <StepBody kicker={m.modelsKicker} title={m.steps.models} lede={m.model.modelsLede}>
            {mu ? (
              <GroupModelsCard projectId={projectId} v={mu} />
            ) : (
              <p className="empty">{t.project.loading}</p>
            )}
            {errors}
          </StepBody>
          <StepFoot back={back} next={onward} />
        </>
      )}
      {current === "try" && (
        <>
          <StepBody kicker={m.modelsKicker} title={m.steps.try} lede={m.model.tryLede}>
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
          <StepBody kicker={m.modelsKicker} title={m.steps.how} lede={m.model.howLede}>
            <HowTheyDid view={mv} />
          </StepBody>
          <StepFoot back={back} extra={[{ label: m.model.tryAgain, onPress: tryIt }]} next={onward} />
        </>
      )}
      {current === "small" && mr && (
        <>
          <StepBody kicker={m.modelsKicker} title={m.steps.small} lede={m.small.lede}>
            {mv.stale && <p className="wiz-warn">{m.model.stale}</p>}
            <SmallGroupsStep projectId={projectId} />
          </StepBody>
          <StepFoot back={back} />
        </>
      )}
    </StepFrame>
  );
}

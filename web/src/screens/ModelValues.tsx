import { useState } from "react";
import { useStep, useStepAct, useStepNav, useStepSetup, useStepSkip } from "../api/steps";
import { RunProgress, type Step, StepBody, StepFoot, StepFrame, type StepStatus } from "../components/Steps";
import { when } from "../lib/format";
import { say, t } from "../wording";
import { FinalValues } from "./FinalValues";
import { HowTheyDid } from "./HowTheyDid";
import { GroupModelsCard } from "./Models";
import { Outliers } from "./Outliers";
import { SmallGroupsStep } from "./SmallGroups";

const m = t.values;
type MvStep = "models" | "try" | "how" | "small" | "final" | "values" | "outliers";
const MV_STEPS: MvStep[] = ["models", "try", "how", "small", "final", "values", "outliers"];
const f = m.final;

/** Step 6, Model values (SPEC F9): each model group's models, a try, how they did, the groups left unvalued, then
 * the values made (Finalize) and checked. */
export function ValuesTab({
  projectId,
  currency,
  units,
}: {
  projectId: string;
  currency: string;
  units: string;
}) {
  const ms = useStep("model", projectId);
  const fs = useStep("final", projectId);
  const fAct = useStepAct("final", projectId);
  const mv = ms.data;
  const { setup: mSetup } = useStepSetup("model", projectId);
  const mAct = useStepAct("model", projectId);
  const skipTry = useStepSkip("model", projectId);
  const skipFinal = useStepSkip("final", projectId);
  const nav = useStepNav<MvStep>();
  // Models: one model group at a time, the footer moving between them.
  const [groupAt, setGroupAt] = useState(0);
  const at = nav.at;
  if (!mv) return <p className="empty">{ms.error?.message ?? t.project.loading}</p>;
  const trying = mv.status === "running";
  const mr = mv.receipt;
  const mFresh = !!mr && !mv.stale;
  const fallback: MvStep = trying ? "try" : mr ? (mFresh ? "how" : "try") : "models";
  const current: MvStep =
    at.after && mv.status === "done" && at.step === "try"
      ? "how"
      : at.after && fs.data?.status === "done" && at.step === "final"
        ? "values"
        : (at.step ?? fallback);
  const go = nav.go;
  const fv = fs.data;
  const finalizing = fv?.status === "running";
  const fr = fv?.receipt;
  const fFresh = !!fr && !fv?.stale;
  const finalize = () => fAct.mutate("run", { onSuccess: () => nav.ran("final") });
  // Small groups' Looks right: the try is the one to finalize.
  const keepTry = () => mAct.mutate("accept", { onSuccess: () => go("final") });
  const tryIt = () => mAct.mutate("run", { onSuccess: () => nav.ran("try") });
  const tried = mr ? (mv.stale ? "attention" : "done") : "blank";
  const modeled = (mSetup.data?.groups ?? []).filter((g) => g.modeled);
  const gi = Math.min(groupAt, Math.max(modeled.length - 1, 0));
  const group = modeled[gi];
  // Groups a model of which still has no list (or an empty one): Next waits for them.
  const unlisted = modeled.filter(
    (g) =>
      g.models.length === 0 ||
      g.models.some((e) => e.warnings.some((w) => w.code === "no_list" || w.code === "list_empty")),
  );
  const statusOf = (key: MvStep): StepStatus => {
    switch (key) {
      case "models":
        return unlisted.length ? "attention" : "done";
      case "try":
        return tried;
      case "how":
      case "small":
        return mr && !mv.stale ? "done" : "blank";
      case "final":
        if (!fr) return "blank";
        return fv?.stale || (fv?.blocked.length ?? 0) > 0 ? "attention" : "done";
      case "values":
        return fv?.accepted ? "done" : "blank";
      case "outliers":
        return fr && fv?.stale ? "attention" : "blank";
    }
  };
  const steps: Step[] = MV_STEPS.map((key) => ({
    key,
    title: m.steps[key],
    status: statusOf(key),
    disabled:
      ((key === "how" || key === "small" || key === "final") && !mr) ||
      ((key === "values" || key === "outliers") && !fr),
  }));
  const i = MV_STEPS.indexOf(current);
  const prev = MV_STEPS[i - 1];
  const back = prev ? () => go(prev) : null;
  const onward = { label: t.step.next, onPress: () => go(MV_STEPS[i + 1] ?? current) };
  const mu = mSetup.data;
  const errors = [mAct.error, mSetup.error, fAct.error].map(
    (e) =>
      e && (
        <p key={e.message} className="error" role="alert">
          {e.message}
        </p>
      ),
  );

  return (
    <StepFrame steps={steps} current={current} go={go} landing="values">
      {current === "models" && (
        <>
          <StepBody title={m.steps.models} lede={m.model.modelsLede}>
            {mu && group ? (
              <GroupModelsCard key={group.id} projectId={projectId} v={mu} gid={group.id} />
            ) : (
              <p className="empty">{t.project.loading}</p>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={gi > 0 ? () => setGroupAt(gi - 1) : back}
            note={
              gi === modeled.length - 1 && unlisted.length
                ? say.values.model.unlisted(unlisted.map((g) => g.name))
                : null
            }
            next={
              gi < modeled.length - 1
                ? {
                    label: m.model.nextGroup({ name: modeled[gi + 1]?.name ?? "" }),
                    onPress: () => setGroupAt(gi + 1),
                  }
                : { ...onward, disabled: unlisted.length > 0 }
            }
          />
        </>
      )}
      {current === "try" && (
        <>
          <StepBody title={m.steps.try} lede={m.model.tryLede}>
            {mv.blocked.length > 0 && (
              <div className="bi-warn">
                <b>{m.blocked}</b> {mv.blocked[0]}
              </div>
            )}
            {trying ? (
              <RunProgress
                job={mv.job}
                lastSeconds={mr?.seconds ?? null}
                skip={(part) => skipTry.mutate(part)}
              />
            ) : (
              <>
                {mv.status === "failed" && mv.job?.error && (
                  <p className="error" role="alert">
                    {t.step.failed} <span className="mono">{mv.job.error}</span>
                  </p>
                )}
                {mv.stale && <p className="wiz-warn">{m.model.stale}</p>}
                {mFresh && mr && (
                  <p className="wiz-ok">{m.model.ran({ when: when(mr.ran_at), seconds: mr.seconds })}</p>
                )}
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
          <StepBody title={m.steps.how} lede={m.model.howLede}>
            <HowTheyDid view={mv} />
          </StepBody>
          <StepFoot back={back} extra={[{ label: m.model.tryAgain, onPress: tryIt }]} next={onward} />
        </>
      )}
      {current === "small" && mr && (
        <>
          <StepBody title={m.steps.small} lede={m.small.lede}>
            {mv.stale && <p className="wiz-warn">{m.model.stale}</p>}
            <SmallGroupsStep projectId={projectId} />
          </StepBody>
          <StepFoot
            back={back}
            next={{ label: f.looksRight, onPress: keepTry, disabled: mv.stale || mAct.isPending }}
          />
          {errors}
        </>
      )}
      {current === "final" && (
        <>
          <StepBody title={m.steps.final} lede={f.lede}>
            {(fv?.blocked.length ?? 0) > 0 && (
              <div className="bi-warn">
                <b>{m.blocked}</b> {fv?.blocked[0]}
              </div>
            )}
            {finalizing ? (
              <RunProgress
                job={fv?.job ?? null}
                lastSeconds={fr?.seconds ?? null}
                skip={(part) => skipFinal.mutate(part)}
              />
            ) : (
              <>
                {fv?.status === "failed" && fv.job?.error && (
                  <p className="error" role="alert">
                    {t.step.failed} <span className="mono">{fv.job.error}</span>
                  </p>
                )}
                {fv?.stale && <p className="wiz-warn">{f.stale}</p>}
                {fFresh && fr && (
                  <p className="wiz-ok">{say.values.final.ran(when(fr.ran_at), fr.seconds)}</p>
                )}
                {!fr && !fv?.blocked.length && <p className="wiz-from">{t.step.notRun}</p>}
              </>
            )}
            {errors}
          </StepBody>
          <StepFoot
            back={finalizing ? null : back}
            extra={fFresh && !finalizing ? [{ label: f.again, onPress: finalize }] : []}
            next={
              finalizing
                ? { label: t.step.stop, onPress: () => fAct.mutate("stop"), primary: false }
                : fFresh
                  ? onward
                  : {
                      label: f.run,
                      disabled: (fv?.blocked.length ?? 0) > 0 || fAct.isPending,
                      onPress: finalize,
                    }
            }
          />
        </>
      )}
      {current === "values" && fr && (
        <>
          <StepBody title={m.steps.values} lede={f.valuesLede}>
            {fv?.stale && <p className="wiz-warn">{f.stale}</p>}
            <FinalValues projectId={projectId} receipt={fr} currency={currency} units={units} />
            {errors}
          </StepBody>
          <StepFoot
            back={back}
            next={{
              label: f.looksRight,
              disabled: !!fv?.stale || !!fv?.accepted || fAct.isPending,
              onPress: () => fAct.mutate("accept"),
            }}
          />
        </>
      )}
      {current === "outliers" && fr && (
        <>
          <StepBody title={m.steps.outliers} lede={m.outliers.lede}>
            {fv?.stale && <p className="wiz-warn">{f.stale}</p>}
            <Outliers projectId={projectId} currency={currency} />
          </StepBody>
          <StepFoot back={back} next={null} />
        </>
      )}
    </StepFrame>
  );
}

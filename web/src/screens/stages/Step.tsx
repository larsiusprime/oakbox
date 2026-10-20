import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, CircleX, Play, RotateCw, Square } from "lucide-react";
import { useCallback } from "react";
import { Button } from "react-aria-components";
import { type ProjectDetail, STEP_ORDER, type StepId, unwrap } from "../../api/client";
import { useJobEvents } from "../../api/events";
import { Progress } from "../../components/Progress";
import { Part, StageFrame, TechnicalDetails } from "../../components/Stage";
import { Status } from "../../components/Status";
import { ValueStudyTable } from "../../components/ValueStudyTable";
import { t } from "../../strings";
import { api } from "./common";

export function StepScreen({
  detail,
  step,
  setupDone,
}: {
  detail: ProjectDetail;
  step: StepId;
  setupDone: boolean;
}) {
  const { project, running_job } = detail;
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project", project.id] });
    void queryClient.invalidateQueries({ queryKey: ["studies", project.id] });
    void queryClient.invalidateQueries({ queryKey: ["receipt", project.id] });
  }, [queryClient, project.id]);
  const status = project.steps[step];
  const state = status.state;
  const i = STEP_ORDER.indexOf(step);
  const earlierUndone = STEP_ORDER.slice(0, i).some((s) => project.steps[s].state !== "done");
  const blocked = !setupDone || earlierUndone;
  const runningJobId = running_job?.step === step ? running_job.id : null;
  const run = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/steps/{step}/run", {
          params: { path: { project_id: project.id, step } },
        }),
      ),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: async (jobId: string) =>
      unwrap(await api.POST("/api/jobs/{job_id}/cancel", { params: { path: { job_id: jobId } } })),
  });
  const view = useJobEvents(runningJobId, refresh);
  const running = runningJobId !== null && !view.finished;
  const again = state === "done" || state === "stale";

  return (
    <StageFrame
      title={`${i + 1}. ${t.steps[step].title}`}
      what={t.steps[step].what}
      status={<Status state={running ? "running" : state} />}
    >
      <Part title={t.project.run}>
        {running ? (
          <div className="check-runner">
            <Progress
              fraction={view.fraction}
              label={view.latest?.type === "progress" ? view.latest.message : t.step.working}
            />
            <Button
              className="button"
              isDisabled={cancel.isPending}
              onPress={() => runningJobId && cancel.mutate(runningJobId)}
            >
              <Square aria-hidden="true" size="0.9em" />
              {cancel.isPending ? t.step.stopping : t.step.cancel}
            </Button>
          </div>
        ) : (
          <div className="check-runner">
            <Button
              className={again ? "button" : "button button-primary"}
              isDisabled={blocked || running_job !== null || run.isPending}
              onPress={() => run.mutate()}
            >
              {again ? <RotateCw aria-hidden="true" size="1em" /> : <Play aria-hidden="true" size="1em" />}
              {again ? t.step.runAgain : t.step.run}
            </Button>
            {blocked && (
              <span className="row-meta">{setupDone ? t.step.needsEarlier : t.step.needsSetup}</span>
            )}
          </div>
        )}
        {!running && state !== "failed" && status.message && <p className="step-result">{status.message}</p>}
        {state === "failed" && !running && <TechnicalDetails message={status.message} />}
        {run.error && (
          <p className="error" role="alert">
            {run.error.message}
          </p>
        )}
      </Part>
      {step === "bring_in_data" && (state === "done" || state === "stale") && (
        <BringInReceipt projectId={project.id} />
      )}
      {step === "check_values" && (state === "done" || state === "stale") && (
        <Results projectId={project.id} />
      )}
    </StageFrame>
  );
}

function BringInReceipt({ projectId }: { projectId: string }) {
  const r = useQuery({
    queryKey: ["receipt", projectId, "bring_in_data"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/steps/bring_in_data/receipt", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  if (!r.data) return null;
  const { report, engine } = r.data;
  // Parcels are a prediction; sales records are filtered by Sales basics in the engine, so no check mark.
  const rows = [
    [t.receipt.parcels, report.parcels, engine.parcels, true],
    [t.receipt.sales, report.sales, engine.sales, false],
  ] as const;
  return (
    <Part title={t.frame.receipt}>
      <table className="data-table receipt-table">
        <thead>
          <tr>
            <th scope="col" />
            <th scope="col" className="num">
              {t.receipt.predicted}
            </th>
            <th scope="col" className="num">
              {t.receipt.engine}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, predicted, loaded, compare]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td className="num">{t.n(predicted)}</td>
              <td className="num">
                {compare ? (
                  <span className={`mark ${predicted === loaded ? "mark-meets" : "mark-neutral"}`}>
                    {predicted === loaded ? (
                      <CircleCheck aria-hidden="true" size="1em" />
                    ) : (
                      <CircleX aria-hidden="true" size="1em" />
                    )}
                    {t.n(loaded)}
                  </span>
                ) : (
                  t.n(loaded)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.sales !== engine.sales && <p className="row-meta">{t.receipt.salesNote}</p>}
    </Part>
  );
}

function Results({ projectId }: { projectId: string }) {
  const studies = useQuery({
    queryKey: ["studies", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/results/value-studies", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  return (
    <div className="results-stack">
      {studies.data?.map((s) => (
        <ValueStudyTable key={s.field} study={s} />
      ))}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Play, RotateCw, Square } from "lucide-react";
import { useCallback } from "react";
import { Button, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import { api, type ProjectDetail, STEP_ORDER, type StepId, unwrap } from "../api/client";
import { useJobEvents } from "../api/events";
import { Progress } from "../components/Progress";
import { Status } from "../components/Status";
import { ValueStudyTable } from "../components/ValueStudyTable";
import { t } from "../strings";

export function ProjectScreen({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["studies", projectId] });
  }, [queryClient, projectId]);

  if (detail.isPending) return <p className="empty">{t.project.working}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  const { project, running_job } = detail.data;

  return (
    <div className="project">
      <header className="page-head">
        <a className="back-link" href="#/">
          <ChevronLeft aria-hidden="true" size="1.1em" />
          {t.project.back}
        </a>
        <h1>{project.name}</h1>
        <span className="page-meta">{t.project.taxYear(project.tax_year)}</span>
      </header>

      <div className="project-body">
        <section className="panel steps-panel" aria-labelledby="steps-title">
          <header className="panel-head">
            <h2 id="steps-title">{t.project.stepsTitle}</h2>
          </header>
          <ol className="rows steps">
            {STEP_ORDER.map((step, i) => (
              <StepRow
                key={step}
                index={i + 1}
                step={step}
                detail={detail.data}
                blocked={STEP_ORDER.slice(0, i).some((s) => project.steps[s]?.state !== "done")}
                runningJobId={running_job?.step === step ? running_job.id : null}
                onChange={refresh}
              />
            ))}
          </ol>
        </section>
        {project.steps.check_values?.state === "done" && <Results projectId={projectId} />}
      </div>
    </div>
  );
}

type StepRowProps = {
  index: number;
  step: StepId;
  detail: ProjectDetail;
  blocked: boolean;
  runningJobId: string | null;
  onChange: () => void;
};

function StepRow({ index, step, detail, blocked, runningJobId, onChange }: StepRowProps) {
  const status = detail.project.steps[step];
  const state = status?.state ?? "not_run";
  const anyRunning = detail.running_job !== null && detail.running_job !== undefined;
  const run = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/steps/{step}/run", {
          params: { path: { project_id: detail.project.id, step } },
        }),
      ),
    onSuccess: onChange,
  });
  const cancel = useMutation({
    mutationFn: async (jobId: string) =>
      unwrap(await api.POST("/api/jobs/{job_id}/cancel", { params: { path: { job_id: jobId } } })),
  });
  const view = useJobEvents(runningJobId, onChange);
  const running = runningJobId !== null && !view.finished;
  const info = t.steps[step];
  const again = state === "done" || state === "stale";

  return (
    <li className={`row step step-${running ? "running" : state}`}>
      <span className="step-number" aria-hidden="true">
        {index}
      </span>
      <div className="row-main">
        <div className="step-head">
          <h3 className="row-title">{info.title}</h3>
          <Status state={running ? "running" : state} />
        </div>
        <span className="row-meta">{info.what}</span>
        {running ? (
          <Progress
            fraction={view.fraction}
            label={view.latest?.type === "progress" ? view.latest.message : t.project.working}
          />
        ) : (
          <>
            {blocked && <span className="row-meta">{t.project.needsEarlier}</span>}
            {!blocked && state !== "failed" && status?.message && (
              <span className="step-result">{status.message}</span>
            )}
            {state === "failed" && <StepError message={status?.message ?? ""} />}
          </>
        )}
        {run.error && (
          <p className="error" role="alert">
            {run.error.message}
          </p>
        )}
      </div>
      {running ? (
        <Button
          className="button"
          isDisabled={cancel.isPending}
          onPress={() => runningJobId && cancel.mutate(runningJobId)}
        >
          <Square aria-hidden="true" size="0.9em" />
          {cancel.isPending ? t.project.stopping : t.project.cancel}
        </Button>
      ) : (
        <Button
          className={again ? "button" : "button button-primary"}
          isDisabled={blocked || anyRunning || run.isPending}
          onPress={() => run.mutate()}
        >
          {again ? <RotateCw aria-hidden="true" size="1em" /> : <Play aria-hidden="true" size="1em" />}
          {again ? t.project.runAgain : t.project.run}
        </Button>
      )}
    </li>
  );
}

function StepError({ message }: { message: string }) {
  return (
    <Disclosure className="disclosure">
      <Heading>
        <Button slot="trigger" className="disclosure-trigger">
          {t.project.showDetails}
        </Button>
      </Heading>
      <DisclosurePanel>
        <pre className="error-detail">{message}</pre>
      </DisclosurePanel>
    </Disclosure>
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

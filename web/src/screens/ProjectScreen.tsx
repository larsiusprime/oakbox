import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { Button, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import { api, type ProjectDetail, STEP_ORDER, type StepId, unwrap } from "../api/client";
import { useJobEvents } from "../api/events";
import { Progress } from "../components/Progress";
import { StatusChip } from "../components/StatusChip";
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

  if (detail.isPending) return <p className="muted">{t.project.working}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  const { project, running_job } = detail.data;

  return (
    <div className="project">
      <a className="back-link" href="#/">
        ← {t.project.back}
      </a>
      <h1>{project.name}</h1>
      <p className="muted">{t.project.taxYear(project.tax_year)}</p>
      <ol className="steps">
        {STEP_ORDER.map((step, i) => (
          <StepCard
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
      {project.steps.check_values?.state === "done" && <Results projectId={projectId} />}
    </div>
  );
}

type StepCardProps = {
  index: number;
  step: StepId;
  detail: ProjectDetail;
  blocked: boolean;
  runningJobId: string | null;
  onChange: () => void;
};

function StepCard({ index, step, detail, blocked, runningJobId, onChange }: StepCardProps) {
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

  return (
    <li className={`step step-${state}`}>
      <div className="step-number" aria-hidden="true">
        {index}
      </div>
      <div className="step-body">
        <div className="step-head">
          <h2>{info.title}</h2>
          <StatusChip state={running ? "running" : state} />
        </div>
        <p className="step-what">{info.what}</p>
        {running ? (
          <div className="step-running">
            <Progress
              fraction={view.fraction}
              label={view.latest?.type === "progress" ? view.latest.message : t.project.working}
            />
            <Button
              className="button"
              isDisabled={cancel.isPending}
              onPress={() => runningJobId && cancel.mutate(runningJobId)}
            >
              {cancel.isPending ? t.project.stopping : t.project.cancel}
            </Button>
          </div>
        ) : (
          <div className="step-actions">
            <Button
              className={state === "done" ? "button" : "button button-primary"}
              isDisabled={blocked || anyRunning || run.isPending}
              onPress={() => run.mutate()}
            >
              {state === "done" || state === "stale" ? t.project.runAgain : t.project.run}
            </Button>
            {blocked && <span className="muted">{t.project.needsEarlier}</span>}
            {!blocked && status?.message && <span className="step-message">{status.message}</span>}
          </div>
        )}
        {state === "failed" && !running && <StepError message={status?.message ?? ""} />}
        {run.error && (
          <p className="error" role="alert">
            {run.error.message}
          </p>
        )}
      </div>
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
    <>
      {studies.data?.map((s) => (
        <ValueStudyTable key={s.field} study={s} />
      ))}
    </>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, Search } from "lucide-react";
import { type ReactNode, useCallback } from "react";
import { Button, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import { api, type JobInfo, type StageId, type StageStatus, unwrap } from "../api/client";
import { useJobEvents } from "../api/events";
import { t } from "../strings";
import { Progress } from "./Progress";

/** The four-part frame every stage and step shares (SPEC §3.2): decide, check, run, receipt. */
export function StageFrame(props: {
  title: string;
  what: string;
  status?: ReactNode;
  note?: string | undefined;
  children: ReactNode;
}) {
  return (
    <section className="panel stage" aria-labelledby="stage-title">
      <header className="stage-head">
        <div className="stage-title-row">
          <h2 id="stage-title">{props.title}</h2>
          {props.status}
        </div>
        <p className="stage-what">{props.what}</p>
      </header>
      {props.note && (
        <aside className="walkthrough">
          <BookOpen aria-hidden="true" size="1.1em" />
          <div>
            <strong>{t.project.walkthrough}.</strong> {props.note}
          </div>
        </aside>
      )}
      {props.children}
    </section>
  );
}

export function Part(props: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="part">
      <div className="part-head">
        <h3>{props.title}</h3>
        {props.aside}
      </div>
      {props.children}
    </div>
  );
}

export function StageStatusMark({ status }: { status: StageStatus }) {
  return (
    <span className={`status status-stage-${status.state}`}>
      {status.state === "done" && <Check aria-hidden="true" size="1.1em" strokeWidth={2.5} />}
      {t.stageState[status.state]}
    </span>
  );
}

export function StaleNote({ status }: { status: StageStatus }) {
  if (status.state !== "stale") return null;
  return <p className="stale-note">{t.frame.staleBecause(status.reason)}</p>;
}

/** Runs a stage's Check as a background job, with progress, and refreshes the project when it ends. */
export function CheckRunner(props: {
  projectId: string;
  stage: StageId;
  runningJob: JobInfo | null;
  ran: boolean;
  fresh: boolean;
  disabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project", props.projectId] });
    void queryClient.invalidateQueries({ queryKey: ["check", props.projectId] });
  }, [queryClient, props.projectId]);
  const start = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/stages/{stage}/check", {
          params: { path: { project_id: props.projectId, stage: props.stage } },
        }),
      ),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: async (jobId: string) =>
      unwrap(await api.POST("/api/jobs/{job_id}/cancel", { params: { path: { job_id: jobId } } })),
  });
  const jobId = props.runningJob?.id ?? null;
  const view = useJobEvents(jobId, refresh);
  const running = jobId !== null && !view.finished;
  return (
    <div className="check-runner">
      {running ? (
        <>
          <Progress
            fraction={view.fraction}
            label={view.latest?.type === "progress" ? view.latest.message : t.project.working}
          />
          <Button
            className="button"
            isDisabled={cancel.isPending}
            onPress={() => jobId && cancel.mutate(jobId)}
          >
            {cancel.isPending ? t.frame.stopping : t.frame.stop}
          </Button>
        </>
      ) : (
        <Button
          className={props.fresh ? "button" : "button button-primary"}
          isDisabled={props.disabled || start.isPending || props.runningJob !== null}
          onPress={() => start.mutate()}
        >
          <Search aria-hidden="true" size="1em" />
          {props.ran ? t.frame.checkAgain : t.frame.runCheck}
        </Button>
      )}
      {props.ran && !props.fresh && !running && <p className="stale-note">{t.frame.checkOutdated}</p>}
      {(start.error || view.finished === "failed") && (
        <p className="error" role="alert">
          {start.error?.message ?? (view.latest?.type === "error" ? view.latest.message : "")}
        </p>
      )}
    </div>
  );
}

/** "Looks right": confirms the stage. The server says, in plain words, why it can't be yet. */
export function LooksRight(props: {
  projectId: string;
  stage: StageId;
  status: StageStatus;
  onDone?: () => void;
}) {
  const queryClient = useQueryClient();
  const confirm = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/stages/{stage}/confirm", {
          params: { path: { project_id: props.projectId, stage: props.stage } },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["project", props.projectId] });
      props.onDone?.();
    },
  });
  const done = props.status.state === "done";
  return (
    <div className="looks-right">
      <Button
        className="button button-primary"
        isDisabled={done || confirm.isPending}
        onPress={() => confirm.mutate()}
      >
        <Check aria-hidden="true" size="1.1em" strokeWidth={2.5} />
        {done ? t.frame.confirmed : t.frame.looksRight}
      </Button>
      {confirm.error && (
        <p className="error" role="alert">
          {confirm.error.message}
        </p>
      )}
    </div>
  );
}

/** The settings a stage writes, read-only (SPEC D39). Loaded only when opened. */
export function UnderTheHood({ projectId, stage }: { projectId: string; stage: StageId }) {
  return (
    <Disclosure className="hood">
      <Heading>
        <Button slot="trigger" className="hood-trigger">
          <ChevronRight aria-hidden="true" size="1em" className="hood-chevron" />
          {t.frame.underTheHood}
        </Button>
      </Heading>
      <DisclosurePanel>
        <HoodContent projectId={projectId} stage={stage} />
      </DisclosurePanel>
    </Disclosure>
  );
}

function HoodContent({ projectId, stage }: { projectId: string; stage: StageId }) {
  const items = useQuery({
    queryKey: ["hood", projectId, stage],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/stages/{stage}/under-the-hood", {
          params: { path: { project_id: projectId, stage } },
        }),
      ),
  });
  return (
    <div className="hood-body">
      <p className="row-meta">{t.frame.underTheHoodNote}</p>
      {items.data?.map((item) => (
        <div key={item.title}>
          <h4 className="hood-title">{item.title}</h4>
          <pre className="code">{JSON.stringify(item.content, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}

export function TechnicalDetails({ message }: { message: string }) {
  return (
    <Disclosure className="disclosure">
      <Heading>
        <Button slot="trigger" className="disclosure-trigger">
          {t.frame.technicalDetails}
        </Button>
      </Heading>
      <DisclosurePanel>
        <pre className="error-detail">{message}</pre>
      </DisclosurePanel>
    </Disclosure>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "react-aria-components";
import { navigate } from "../App";
import { api, type JobInfo, STEP_ORDER, unwrap } from "../api/client";
import { useJobEvents } from "../api/events";
import { Progress } from "../components/Progress";
import { t } from "../strings";

export function HomeScreen() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await api.GET("/api/projects")),
  });
  const samples = useQuery({
    queryKey: ["samples"],
    queryFn: async () => unwrap(await api.GET("/api/samples")),
  });

  return (
    <div className="home">
      <section className="panel" aria-labelledby="projects-title">
        <h2 id="projects-title">{t.home.projectsTitle}</h2>
        {projects.data?.length === 0 && <p className="muted">{t.home.noProjects}</p>}
        <ul className="project-list">
          {projects.data?.map((p) => {
            const done = STEP_ORDER.filter((s) => p.steps[s]?.state === "done").length;
            return (
              <li key={p.id} className="project-card">
                <div>
                  <div className="project-name">{p.name}</div>
                  <div className="muted">
                    {t.home.taxYear(p.tax_year)} · {t.home.stepsDone(done, STEP_ORDER.length)}
                  </div>
                </div>
                <Button className="button" onPress={() => navigate({ name: "project", id: p.id })}>
                  {t.home.open}
                </Button>
              </li>
            );
          })}
        </ul>
        <div className="soon">
          <Button className="button" isDisabled>
            {t.home.newProject}
          </Button>
          <span className="muted">{t.home.newProjectSoon}</span>
        </div>
      </section>

      <section className="panel" aria-labelledby="sample-title">
        <h2 id="sample-title">{t.home.sampleTitle}</h2>
        <p>{t.home.sampleIntro}</p>
        {samples.data?.map((s) => (
          <SampleRow key={s.id} id={s.id} name={s.name} description={s.description} />
        ))}
      </section>
    </div>
  );
}

function SampleRow({ id, name, description }: { id: string; name: string; description: string }) {
  const queryClient = useQueryClient();
  const [job, setJob] = useState<JobInfo | null>(null);
  const start = useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/samples/{sample_id}", { params: { path: { sample_id: id } } })),
    onSuccess: setJob,
  });
  const view = useJobEvents(job?.id ?? null, () => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  });

  useEffect(() => {
    if (job && view.finished === "done") navigate({ name: "project", id: job.project_id });
  }, [job, view.finished]);

  return (
    <div className="sample-row">
      <div>
        <div className="project-name">{name}</div>
        <div className="muted">{description}</div>
        <div className="notice">{t.home.sampleNotice}</div>
      </div>
      {job && !view.finished ? (
        <Progress fraction={view.fraction} label={t.home.sampleDownloading} />
      ) : (
        <Button className="button button-primary" isDisabled={start.isPending} onPress={() => start.mutate()}>
          {t.home.sampleButton}
        </Button>
      )}
      {(start.error || view.finished === "failed") && (
        <p className="error" role="alert">
          {start.error?.message ?? (view.latest?.type === "error" ? view.latest.message : "")}
        </p>
      )}
    </div>
  );
}

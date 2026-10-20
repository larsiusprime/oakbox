import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
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
        <header className="panel-head">
          <h1 id="projects-title">{t.home.projectsTitle}</h1>
        </header>
        {projects.data?.length === 0 && <p className="empty">{t.home.noProjects}</p>}
        <ul className="rows">
          {projects.data?.map((p) => {
            const done = STEP_ORDER.filter((s) => p.steps[s]?.state === "done").length;
            return (
              <li key={p.id} className="row">
                <div className="row-main">
                  <a className="row-title" href={`#/projects/${p.id}`}>
                    {p.name}
                  </a>
                  <span className="row-meta">
                    {t.home.taxYear(p.tax_year)} · {t.home.stepsDone(done, STEP_ORDER.length)}
                  </span>
                </div>
                <Button className="button" onPress={() => navigate({ name: "project", id: p.id })}>
                  {t.home.open}
                </Button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="panel" aria-labelledby="sample-title">
        <header className="panel-head">
          <h2 id="sample-title">{t.home.sampleTitle}</h2>
        </header>
        <ul className="rows">
          {samples.data?.map((s) => (
            <SampleRow key={s.id} id={s.id} name={s.name} description={s.description} />
          ))}
        </ul>
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
    <li className="row">
      <div className="row-main">
        <span className="row-title">{name}</span>
        <span className="row-meta">{description}</span>
        <span className="row-meta">{t.home.sampleNotice}</span>
        {(start.error || view.finished === "failed") && (
          <p className="error" role="alert">
            {start.error?.message ?? (view.latest?.type === "error" ? view.latest.message : "")}
          </p>
        )}
      </div>
      {job && !view.finished ? (
        <div className="row-progress">
          <Progress fraction={view.fraction} label={t.home.sampleDownloading} />
        </div>
      ) : (
        <Button className="button button-primary" isDisabled={start.isPending} onPress={() => start.mutate()}>
          <Download aria-hidden="true" size="1.1em" />
          {t.home.sampleButton}
        </Button>
      )}
    </li>
  );
}

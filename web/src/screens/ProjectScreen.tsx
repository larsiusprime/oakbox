import { useQuery } from "@tanstack/react-query";
import { Check, ChevronLeft, CircleAlert, LoaderCircle, RotateCcw } from "lucide-react";
import { api, STAGE_ORDER, STEP_ORDER, type StageId, type StepId, unwrap } from "../api/client";
import { t } from "../strings";
import { BasicsStage } from "./stages/Basics";
import { FilesStage } from "./stages/Files";
import { LaterStage } from "./stages/Later";
import { StepScreen } from "./stages/Step";
import { StitchStage } from "./stages/Stitch";

export type GuideItem = StageId | StepId;

function itemState(state: string): "done" | "stale" | "failed" | "running" | "todo" {
  if (state === "done" || state === "stale" || state === "failed" || state === "running") return state;
  return "todo";
}

function Mark({ state }: { state: ReturnType<typeof itemState> }) {
  if (state === "done")
    return <Check aria-hidden="true" size="1em" strokeWidth={2.75} className="guide-mark done" />;
  if (state === "stale") return <RotateCcw aria-hidden="true" size="1em" className="guide-mark stale" />;
  if (state === "failed") return <CircleAlert aria-hidden="true" size="1em" className="guide-mark failed" />;
  if (state === "running")
    return <LoaderCircle aria-hidden="true" size="1em" className="guide-mark running spin" />;
  return null;
}

export function ProjectScreen({ projectId, item }: { projectId: string; item: GuideItem | null }) {
  const detail = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });

  if (detail.isPending) return <p className="empty">{t.project.working}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  const { project, running_job } = detail.data;
  const setupDone = STAGE_ORDER.every((s) => project.stages[s].state === "done");
  const firstOpen: GuideItem =
    STAGE_ORDER.find((s) => project.stages[s].state !== "done") ??
    STEP_ORDER.find((s) => project.steps[s].state !== "done") ??
    "check_values";
  const current = item ?? firstOpen;
  const runningStep = running_job?.step;
  const href = (i: GuideItem) => `#/projects/${project.id}/${i}`;

  return (
    <div className="project">
      <header className="page-head">
        <a className="back-link" href="#/">
          <ChevronLeft aria-hidden="true" size="1.1em" />
          {t.project.back}
        </a>
        <h1>{project.name}</h1>
        <span className="page-meta">{t.project.taxYear(project.setup.basics.tax_year)}</span>
      </header>
      <div className="guide">
        <nav className="panel guide-nav" aria-label={project.name}>
          <h2 className="guide-group">{t.project.setUp}</h2>
          <ol className="guide-list">
            {STAGE_ORDER.map((s, i) => (
              <li key={s}>
                <a className="guide-link" href={href(s)} aria-current={current === s ? "page" : undefined}>
                  <span className="guide-num">{i + 1}</span>
                  <span className="guide-title">{t.stages[s].title}</span>
                  <Mark state={itemState(project.stages[s].state)} />
                </a>
              </li>
            ))}
          </ol>
          <h2 className="guide-group">{t.project.run}</h2>
          <ol className="guide-list">
            {STEP_ORDER.map((s, i) => (
              <li key={s}>
                <a className="guide-link" href={href(s)} aria-current={current === s ? "page" : undefined}>
                  <span className="guide-num">{i + 1}</span>
                  <span className="guide-title">{t.steps[s].title}</span>
                  <Mark state={itemState(runningStep === s ? "running" : project.steps[s].state)} />
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className="guide-main" key={current}>
          {current === "basics" && <BasicsStage detail={detail.data} />}
          {current === "files" && <FilesStage detail={detail.data} />}
          {current === "stitch" && <StitchStage detail={detail.data} />}
          {(current === "columns" || current === "sales_basics") && (
            <LaterStage detail={detail.data} stage={current} />
          )}
          {(STEP_ORDER as readonly string[]).includes(current) && (
            <StepScreen detail={detail.data} step={current as StepId} setupDone={setupDone} />
          )}
        </div>
      </div>
    </div>
  );
}

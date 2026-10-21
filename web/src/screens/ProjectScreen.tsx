import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronLeft, FolderOpen } from "lucide-react";
import { useState } from "react";
import { Button, Tab, TabList, TabPanel, Tabs } from "react-aria-components";
import { navigate } from "../App";
import { api, type ProjectDetail, unwrap } from "../api/client";
import cardFileBox from "../assets/noto/emoji_u1f5c3.svg";
import gear from "../assets/noto/emoji_u2699.svg";
import { t } from "../strings";
import { InputFilesTab } from "./InputFiles";

export const TABS = ["metadata", "files"] as const;
export type TabId = (typeof TABS)[number];
const PLACEHOLDERS = ["later-1", "later-2", "later-3"] as const;

/** F3: the project view, one tabbed panel (SPEC §3.0). */
export function ProjectScreen({ projectId, tab }: { projectId: string; tab: TabId | null }) {
  const detail = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });

  if (detail.isPending) return <p className="empty">{t.project.loading}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  return <ProjectView detail={detail.data} tab={tab} />;
}

function ProjectView({ detail, tab }: { detail: ProjectDetail; tab: TabId | null }) {
  const { project } = detail;
  const projectId = project.id;
  // Input files first while there are none: adding them is the next thing to do. Decided once,
  // when the project opens, so adding the first file doesn't switch tabs.
  const [opening] = useState<TabId>(() => (detail.files.length === 0 ? "files" : "metadata"));
  const selected = tab ?? opening;

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
      <Tabs
        className="folder-tabs"
        selectedKey={selected}
        onSelectionChange={(key) => navigate({ name: "project", id: projectId, tab: key as TabId })}
        disabledKeys={PLACEHOLDERS}
      >
        <TabList className="folder-tab-list" aria-label={project.name}>
          <Tab id="metadata" className="folder-tab">
            <img src={gear} alt="" className="tab-icon" />
            {t.tabs.metadata}
          </Tab>
          <Tab id="files" className="folder-tab">
            <img src={cardFileBox} alt="" className="tab-icon" />
            {t.tabs.inputFiles}
          </Tab>
          {PLACEHOLDERS.map((id) => (
            <Tab key={id} id={id} className="folder-tab" aria-label={t.tabs.later}>
              <span aria-hidden="true">· · ·</span>
            </Tab>
          ))}
        </TabList>
        <TabPanel id="metadata" className="folder-panel">
          <MetadataTab detail={detail} />
        </TabPanel>
        <TabPanel id="files" className="folder-panel">
          <InputFilesTab detail={detail} />
        </TabPanel>
      </Tabs>
    </div>
  );
}

function MetadataTab({ detail }: { detail: ProjectDetail }) {
  const { project } = detail;
  const m = t.metadata;
  const show = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/show-in-folder", {
          params: { path: { project_id: project.id } },
        }),
      ),
  });
  const rows = [
    [m.jurisdiction, project.jurisdiction],
    [m.region, `${project.region}, ${project.country}`],
    [m.taxYear, String(project.tax_year)],
    [m.valuationDate, project.valuation_date ?? ""],
    [m.units, project.units === "imperial" ? t.newProject.imperial : t.newProject.metric],
  ] as const;
  return (
    <dl className="facts">
      {rows.map(([k, v]) => (
        <div key={k} className="fact">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
      <div className="fact">
        <dt>{m.folder}</dt>
        <dd>
          <span className="mono folder-path">{detail.folder}</span>
          <Button className="button" isDisabled={show.isPending} onPress={() => show.mutate()}>
            <FolderOpen aria-hidden="true" size="1em" />
            {m.showInFolder}
          </Button>
          {show.error && (
            <span className="error" role="alert">
              {show.error.message}
            </span>
          )}
        </dd>
      </div>
    </dl>
  );
}

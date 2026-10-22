import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronLeft, FolderOpen } from "lucide-react";
import { useEffect } from "react";
import { Button, Tab, TabList, TabPanel, Tabs } from "react-aria-components";
import { navigate } from "../App";
import { api, type ProjectDetail, unwrap } from "../api/client";
import clipboard from "../assets/noto/emoji_u1f4cb.svg";
import cardFileBox from "../assets/noto/emoji_u1f5c3.svg";
import gear from "../assets/noto/emoji_u2699.svg";
import { desktop } from "../desktop";
import { t } from "../strings";
import { FieldsTab } from "./FieldsWizard";
import { FieldView } from "./FieldView";
import { InputFilesTab } from "./InputFiles";

export const TABS = ["metadata", "files", "fields"] as const;
export type TabId = (typeof TABS)[number];
const PLACEHOLDERS = ["later-1", "later-2"] as const;

/** F3: the project view, one tabbed panel (SPEC §3.0). */
export function ProjectScreen({
  projectId,
  tab,
  file,
  step,
}: {
  projectId: string;
  tab: TabId | null;
  file: string | null;
  step: string | null;
}) {
  const detail = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });

  if (detail.isPending) return <p className="empty">{t.project.loading}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  return <ProjectView detail={detail.data} tab={tab} file={file} step={step} />;
}

function ProjectView({
  detail,
  tab,
  file,
  step,
}: {
  detail: ProjectDetail;
  tab: TabId | null;
  file: string | null;
  step: string | null;
}) {
  const { project } = detail;
  const projectId = project.id;
  // A project opens on the Data wizard, where its files are added and described (SPEC F3d).
  useEffect(() => desktop.setContext(t.project.title(project.name), project.id), [project.name, project.id]);
  const selected = tab ?? "fields";

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
          <Tab id="fields" className="folder-tab">
            <img src={clipboard} alt="" className="tab-icon" />
            {t.tabs.fields}
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
          {file ? <FieldView detail={detail} name={file} /> : <InputFilesTab detail={detail} />}
        </TabPanel>
        <TabPanel id="fields" className="folder-panel">
          <FieldsTab detail={detail} step={step} />
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

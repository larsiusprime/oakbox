import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useEffect } from "react";
import { Button, Tab, TabList, TabPanel, Tabs } from "react-aria-components";
import { api, type ProjectDetail, unwrap } from "../api/client";
import { useAccepted, useStep } from "../api/steps";
import { LocaleFields, type LocaleValue } from "../components/Locale";
import { MapWindow } from "../components/MapWindow";
import { OakBand } from "../components/OakBand";
import { Opening } from "../components/Opening";
import { StepBody, StepFoot, StepFrame } from "../components/Steps";
import { TabStrip } from "../components/TabStrip";
import { desktop } from "../desktop";
import { lastTab, record, rememberTab, setTabs, setWhere } from "../lib/place";
import { setReturn } from "../lib/returnto";
import { navigate, TABS, type TabId } from "../lib/route";
import { lockedTabs } from "../lib/tabs";
import { say, t } from "../wording";
import { BringInTab } from "./BringIn";
import { SalesTab } from "./CheckSales";
import { CheckValuesTab } from "./CheckValues";
import { FieldsTab } from "./FieldsWizard";
import { ModelGroupsTab } from "./ModelGroups";
import { ValuesTab } from "./ModelValues";
import { ReportTab } from "./ReportTab";
import { VariablesTab } from "./Variables";

/** F3: the project view, one tabbed panel (SPEC §3.0). */
export function ProjectScreen({
  projectId,
  tab,
  step,
}: {
  projectId: string;
  tab: TabId | null;
  step: string | null;
}) {
  const detail = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      unwrap(await api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } })),
  });

  // Its files, as the Data wizard reads them (the sidebar's, the map's): read before anything of the project is
  // shown, so nothing can be pressed while it opens (the same query the Data tab uses).
  const wizard = useQuery({
    queryKey: ["wizard", projectId],
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
  });
  if (detail.error) return <p className="error">{detail.error.message}</p>;
  if (detail.isPending || wizard.isPending)
    return <Opening projectId={projectId} name={detail.data?.project.name ?? null} />;
  return <ProjectView detail={detail.data} tab={tab} step={step} />;
}

function ProjectView({
  detail,
  tab,
  step,
}: {
  detail: ProjectDetail;
  tab: TabId | null;
  step: string | null;
}) {
  const { project } = detail;
  const projectId = project.id;
  // A project opens on the Data wizard, where its files are added and described (SPEC F3d).
  useEffect(
    () => desktop.setContext(t.project.title({ name: project.name }), project.id),
    [project.name, project.id],
  );
  const accepted = useAccepted("bring-in", projectId);
  const grouped = useAccepted("assemble", projectId);
  const checked = useAccepted("clean", projectId);
  // Check my values only with existing values to check (the roll, a vendor's AVM: Data › Existing values).
  const hasValues = useStep("ratio", projectId).data?.has_values ?? true;
  // Model values once the fields are prepared and Looks right pressed (Variables › What changed).
  const prepared = useAccepted("prepare", projectId);
  // Report once the model values have had Looks right (Model values › Model values).
  const finalized = useAccepted("final", projectId);
  // Asked for a tab that waits on an earlier step: shown that step's tab instead, and why, never silently.
  const views = {
    bring: useStep("bring-in", projectId).data,
    groups: useStep("assemble", projectId).data,
    sales: useStep("clean", projectId).data,
    variables: useStep("prepare", projectId).data,
  };
  // The first step, in order, that isn't accepted on an up-to-date run: what the tab asked for waits on.
  const order = ["bring", "groups", "sales", "variables"] as const;
  const name = (k: string) => t.tabs[k as keyof typeof t.tabs] as string;
  const first = order.find((k) => !views[k]?.accepted);
  // A tab that waits on an earlier step shows the first step, in order, not accepted on an up-to-date run: where
  // something needs doing, the tab bar greys what waits (no notice: the user asked for none, 2026-11-10).
  const locked = lockedTabs({ accepted, grouped, checked, hasValues, prepared, finalized });
  const loaded = order.every((k) => views[k] !== undefined);
  // Opened without a tab: the one last open in this project here (if it's open to you), else Data.
  const last = lastTab(projectId) as TabId | null;
  const resume = last && (TABS as readonly string[]).includes(last) ? last : null;
  // Never moved off the tab asked for (2026-11-11): a tab that waits shows what it has, dimmed, under a bar that
  // says what it waits on and goes there; that step's Looks right brings you back (lib/returnto).
  const selected = !tab ? (resume ?? "fields") : tab;
  // What a tab waits on: the first step, in order, not accepted on an up-to-date run (Report: the model values).
  const waitsOn = (id: TabId): { on: string; stale: boolean } | "no-values" | null => {
    if (!loaded || !locked.has(id)) return null;
    if (id === "check" && checked && !hasValues) return "no-values";
    const at = (TABS as readonly string[]).indexOf(id);
    const before = order.find((k) => (TABS as readonly string[]).indexOf(k) < at && !views[k]?.accepted);
    if (before) return { on: before, stale: !!views[before]?.stale };
    return id === "report" ? { on: "values", stale: false } : null;
  };
  const bar = (id: TabId) => {
    const w = waitsOn(id);
    if (!w) return null;
    if (w === "no-values")
      return (
        <div className="wait-bar" role="status">
          <span>{t.tabs.noValues}</span>
        </div>
      );
    return (
      <div className="wait-bar" role="status">
        <span>
          {t.tabs.waitsOn({ step: name(w.on) })} {w.stale ? t.tabs.waitsStale : t.tabs.waitsNotYet}
        </span>
        <Button
          className="button button-small button-primary"
          onPress={() => {
            setReturn(projectId, id);
            navigate({ name: "project", id: projectId, tab: w.on as TabId });
          }}
        >
          {t.tabs.goTo({ step: name(w.on) })}
        </Button>
      </div>
    );
  };
  const panel = (id: TabId) => (waitsOn(id) ? "folder-panel waits" : "folder-panel");
  // The plate: where you are, and the tabs it lists (each one's name, whether it waits, whether it's done).
  setWhere({ projectId, tab: selected });
  const done: Record<string, boolean> = {
    bring: !!views.bring?.accepted,
    groups: !!views.groups?.accepted,
    sales: !!views.sales?.accepted,
    variables: !!views.variables?.accepted,
    values: finalized,
  };
  const tabList = TABS.map((id) => ({
    id,
    title: name(id),
    locked: locked.has(id),
    done: !!done[id],
  }));
  useEffect(() => {
    rememberTab(projectId, selected);
    setTabs(tabList);
    // A tab with no steps (Metadata) is a stop on the path too.
    if (selected === "metadata") record({ projectId, tab: selected, step: "" });
  });
  useEffect(() => () => setWhere(null), []);

  return (
    <div className="project">
      <h1 className="visually-hidden">{project.name}</h1>
      <OakBand page={{ kind: "project", id: projectId, name: project.name, year: project.tax_year }} />
      <MapWindow projectId={projectId} tab={tab} step={step} />
      <Tabs
        className="folder-tabs"
        selectedKey={selected}
        onSelectionChange={(key) => navigate({ name: "project", id: projectId, tab: key as TabId })}
      >
        <TabStrip selected={selected}>
          <TabList className="folder-tab-list" aria-label={project.name}>
            <Tab
              id="metadata"
              className={locked.has("metadata") ? "folder-tab folder-tab-waits" : "folder-tab"}
            >
              {t.tabs.metadata}
            </Tab>
            <Tab id="fields" className={locked.has("fields") ? "folder-tab folder-tab-waits" : "folder-tab"}>
              {t.tabs.fields}
            </Tab>
            <Tab id="bring" className={locked.has("bring") ? "folder-tab folder-tab-waits" : "folder-tab"}>
              {t.tabs.bring}
            </Tab>
            <Tab
              id="groups"
              className={locked.has("groups") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={accepted ? undefined : t.tabs.groupsLocked}
            >
              {t.tabs.groups}
            </Tab>
            <Tab
              id="sales"
              className={locked.has("sales") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={grouped ? undefined : t.tabs.salesLocked}
            >
              {t.tabs.sales}
            </Tab>
            <Tab
              id="check"
              className={locked.has("check") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={!hasValues ? t.tabs.noValues : checked ? undefined : t.tabs.valuesLocked}
              {...(!hasValues ? { "aria-label": `${t.tabs.check}: ${t.tabs.noValues}` } : {})}
            >
              {t.tabs.check}
            </Tab>
            <Tab
              id="variables"
              className={locked.has("variables") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={checked ? undefined : t.tabs.valuesLocked}
            >
              {t.tabs.variables}
            </Tab>
            <Tab
              id="values"
              className={locked.has("values") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={!checked ? t.tabs.valuesLocked : prepared ? undefined : t.tabs.modelsLocked}
            >
              {t.tabs.values}
            </Tab>
            <Tab
              id="report"
              className={locked.has("report") ? "folder-tab folder-tab-waits" : "folder-tab"}
              aria-description={finalized ? undefined : t.tabs.reportLocked}
            >
              {t.tabs.report}
            </Tab>
          </TabList>
        </TabStrip>
        <TabPanel id="metadata" className="folder-panel">
          <MetadataTab detail={detail} />
        </TabPanel>
        <TabPanel id="fields" className="folder-panel">
          <FieldsTab detail={detail} step={step} />
        </TabPanel>
        <TabPanel id="bring" className={panel("bring")}>
          {bar("bring")}
          <BringInTab projectId={projectId} />
        </TabPanel>
        <TabPanel id="groups" className={panel("groups")}>
          {bar("groups")}
          <ModelGroupsTab projectId={projectId} currency={project.currency} />
        </TabPanel>
        <TabPanel id="sales" className={panel("sales")}>
          {bar("sales")}
          <SalesTab
            projectId={projectId}
            currency={project.currency}
            place={`${project.jurisdiction}, ${project.region}`}
          />
        </TabPanel>
        <TabPanel id="check" className={panel("check")}>
          {bar("check")}
          <CheckValuesTab projectId={projectId} currency={project.currency} />
        </TabPanel>
        <TabPanel id="variables" className={panel("variables")}>
          {bar("variables")}
          <VariablesTab projectId={projectId} />
        </TabPanel>
        <TabPanel id="values" className={panel("values")}>
          {bar("values")}
          <ValuesTab projectId={projectId} currency={project.currency} units={project.units} />
        </TabPanel>
        <TabPanel id="report" className={panel("report")}>
          {bar("report")}
          <ReportTab projectId={projectId} />
        </TabPanel>
      </Tabs>
    </div>
  );
}

function MetadataTab({ detail }: { detail: ProjectDetail }) {
  const { project } = detail;
  const m = t.metadata;
  const queryClient = useQueryClient();
  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: async () => unwrap(await api.GET("/api/regions")),
  });
  const locale = useMutation({
    mutationFn: async (patch: Partial<LocaleValue>) =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}/locale", {
          params: { path: { project_id: project.id } },
          body: patch,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project", project.id] }),
  });
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
  ] as const;
  return (
    <StepFrame
      steps={[{ key: "details", title: m.details, status: "blank" }]}
      current="details"
      go={() => {}}
    >
      <StepBody title={m.details}>
        <div className="meta-sheet">
          <dl className="facts">
            {rows.map(([k, v]) => (
              <div key={k} className="fact">
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
            <div className="fact">
              <dt>{m.locale}</dt>
              <dd className="facts-locale">
                <LocaleFields
                  regions={regions.data}
                  value={{ units: project.units, currency: project.currency, numbers: project.numbers }}
                  onChange={(patch) => locale.mutate(patch)}
                />
                {locale.error && (
                  <span className="error" role="alert">
                    {locale.error.message}
                  </span>
                )}
              </dd>
            </div>
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
        </div>
      </StepBody>
      <StepFoot
        next={{
          label: t.step.next,
          onPress: () => navigate({ name: "project", id: project.id, tab: "fields" }),
        }}
      />
    </StepFrame>
  );
}

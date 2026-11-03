import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { useEffect } from "react";
import { Button, Tab, TabList, TabPanel, Tabs } from "react-aria-components";
import { navigate } from "../App";
import { api, type ProjectDetail, unwrap } from "../api/client";
import { useStep } from "../api/steps";
import { LocaleFields, type LocaleValue } from "../components/Locale";
import { OakBand } from "../components/OakBand";
import { StepBody, StepFrame } from "../components/Steps";
import { TabStrip } from "../components/TabStrip";
import { say, t } from "../copy";
import { desktop } from "../desktop";
import { lastTab, record, rememberTab, setTabs, setWhere } from "../lib/place";
import { BringInTab, useAccepted } from "./BringIn";
import { SalesTab, useSalesAccepted } from "./CheckSales";
import { CheckValuesTab } from "./CheckValues";
import { FieldsTab } from "./FieldsWizard";
import { ModelGroupsTab } from "./ModelGroups";
import { ValuesTab } from "./ModelValues";
import { ReportTab } from "./ReportTab";
import { VariablesTab } from "./Variables";

export const TABS = [
  "metadata",
  "fields",
  "bring",
  "groups",
  "sales",
  "check",
  "variables",
  "values",
  "report",
] as const;
export type TabId = (typeof TABS)[number];

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

  if (detail.isPending) return <p className="empty">{t.project.loading}</p>;
  if (detail.error) return <p className="error">{detail.error.message}</p>;
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
  const accepted = useAccepted(projectId);
  const grouped = useStep("assemble", projectId).data?.accepted ?? false;
  const checked = useSalesAccepted(projectId);
  // Check my values only with existing values to check (the roll, a vendor's AVM: Data › Existing values).
  const hasValues = useStep("ratio", projectId).data?.has_values ?? true;
  // Model values once the fields are prepared and Looks right pressed (Variables › What changed).
  const prepared = useStep("prepare", projectId).data?.accepted ?? false;
  // Report once the model values have had Looks right (Model values › Model values).
  const finalized = useStep("final", projectId).data?.accepted ?? false;
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
  // something needs doing, with a notice saying why (never silently somewhere else).
  const tabLocked =
    (tab === "groups" && !accepted) ||
    (tab === "sales" && !grouped) ||
    ((tab === "values" || tab === "variables" || tab === "check") && !checked) ||
    (tab === "check" && !hasValues) ||
    (tab === "values" && !prepared) ||
    (tab === "report" && !finalized);
  const loaded = order.every((k) => views[k] !== undefined);
  // Opened without a tab: the one last open in this project here (if it's open to you), else Data.
  const last = lastTab(projectId) as TabId | null;
  const resume = last && (TABS as readonly string[]).includes(last) ? last : null;
  const selected = !tab
    ? (resume ?? "fields")
    : !tabLocked || !loaded
      ? tab
      : tab === "check" && checked && !hasValues
        ? "variables"
        : (first ?? "bring");
  const changed = views.bring?.stale ? (views.bring.changed ?? []) : [];
  const why =
    tab && tab !== selected
      ? [
          say.tabs.waits(name(tab), name(selected)),
          first
            ? views[first]?.stale
              ? say.tabs.runAgain(name(first))
              : say.tabs.pressLooksRight(name(first))
            : "",
          first === "bring" && changed.length ? t.tabs.bringChanged({ what: changed.join(", ") }) : "",
        ]
          .filter(Boolean)
          .join(" ")
      : null;
  const locked = [
    ...(accepted ? [] : ["groups"]),
    ...(grouped ? [] : ["sales"]),
    ...(checked ? [] : ["check", "variables", "values"]),
    ...(hasValues ? [] : ["check"]),
    ...(prepared ? [] : ["values"]),
    ...(finalized ? [] : ["report"]),
  ];

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
    locked: locked.includes(id),
    done: !!done[id],
  }));
  useEffect(() => {
    rememberTab(projectId, selected);
    setTabs(tabList);
    // A tab with no steps (Metadata) is a stop on the path too.
    if (selected === "metadata") record({ projectId, tab: selected, step: "" });
  });
  useEffect(() => () => setWhere(null), []);

  // Why the tab asked for isn't the one shown: at the top of the page, under the tabs.
  const notice = why && (
    <p className="bi-warn tab-waits" role="status">
      {why}
    </p>
  );

  return (
    <div className="project">
      <h1 className="visually-hidden">{project.name}</h1>
      <OakBand page={{ kind: "project", id: projectId, name: project.name, year: project.tax_year }} />
      <Tabs
        className="folder-tabs"
        selectedKey={selected}
        onSelectionChange={(key) => navigate({ name: "project", id: projectId, tab: key as TabId })}
        disabledKeys={locked}
      >
        <TabStrip selected={selected}>
          <TabList className="folder-tab-list" aria-label={project.name}>
            <Tab id="metadata" className="folder-tab">
              {t.tabs.metadata}
            </Tab>
            <Tab id="fields" className="folder-tab">
              {t.tabs.fields}
            </Tab>
            <Tab id="bring" className="folder-tab">
              {t.tabs.bring}
            </Tab>
            <Tab
              id="groups"
              className="folder-tab"
              aria-description={accepted ? undefined : t.tabs.groupsLocked}
            >
              {t.tabs.groups}
            </Tab>
            <Tab
              id="sales"
              className="folder-tab"
              aria-description={grouped ? undefined : t.tabs.salesLocked}
            >
              {t.tabs.sales}
            </Tab>
            <Tab
              id="check"
              className="folder-tab"
              aria-description={!hasValues ? t.tabs.noValues : checked ? undefined : t.tabs.valuesLocked}
              {...(!hasValues ? { "aria-label": `${t.tabs.check}: ${t.tabs.noValues}` } : {})}
            >
              {t.tabs.check}
            </Tab>
            <Tab
              id="variables"
              className="folder-tab"
              aria-description={checked ? undefined : t.tabs.valuesLocked}
            >
              {t.tabs.variables}
            </Tab>
            <Tab
              id="values"
              className="folder-tab"
              aria-description={!checked ? t.tabs.valuesLocked : prepared ? undefined : t.tabs.modelsLocked}
            >
              {t.tabs.values}
            </Tab>
            <Tab
              id="report"
              className="folder-tab"
              aria-description={finalized ? undefined : t.tabs.reportLocked}
            >
              {t.tabs.report}
            </Tab>
          </TabList>
        </TabStrip>
        <TabPanel id="metadata" className="folder-panel">
          {notice}
          <MetadataTab detail={detail} />
        </TabPanel>
        <TabPanel id="fields" className="folder-panel">
          {notice}
          <FieldsTab detail={detail} step={step} />
        </TabPanel>
        <TabPanel id="bring" className="folder-panel">
          {notice}
          <BringInTab projectId={projectId} />
        </TabPanel>
        <TabPanel id="groups" className="folder-panel">
          {notice}
          <ModelGroupsTab projectId={projectId} currency={project.currency} />
        </TabPanel>
        <TabPanel id="sales" className="folder-panel">
          {notice}
          <SalesTab
            projectId={projectId}
            currency={project.currency}
            place={`${project.jurisdiction}, ${project.region}`}
          />
        </TabPanel>
        <TabPanel id="check" className="folder-panel">
          {notice}
          <CheckValuesTab projectId={projectId} currency={project.currency} />
        </TabPanel>
        <TabPanel id="variables" className="folder-panel">
          {notice}
          <VariablesTab projectId={projectId} />
        </TabPanel>
        <TabPanel id="values" className="folder-panel">
          {notice}
          <ValuesTab projectId={projectId} currency={project.currency} units={project.units} />
        </TabPanel>
        <TabPanel id="report" className="folder-panel">
          {notice}
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
      landing="metadata"
    >
      <StepBody kicker={m.kicker} title={m.details}>
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
    </StepFrame>
  );
}

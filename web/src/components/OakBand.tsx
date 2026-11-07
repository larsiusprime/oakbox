/** The top of every screen (SPEC D21): the box's lid, polished oak with the brass plate on it. The plate is the
 * app's main navigation: a trail of where you are, Projects › project › tab › step, each crumb above you a link,
 * the one you're on in bold; each crumb in a project opens a list of the others at its level (projects, tabs,
 * steps), each saying where it will open. No text sits on the bare wood: what's said is on the plate. */
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings } from "lucide-react";
import { useState } from "react";
import { Button, Menu, MenuItem, MenuTrigger, Popover, Separator } from "react-aria-components";
import { useAppSettings } from "../api/app";
import { api, unwrap } from "../api/client";
import { openSettings } from "../lib/machine";
import { lastStep, lastTab, usePlace } from "../lib/place";
import { navigate } from "../lib/route";
import { t } from "../wording";
import { StorageLocationDialog } from "./StorageLocation";

const n = t.nav;

export type Page =
  | { kind: "projects" }
  | { kind: "check" }
  | { kind: "new" }
  | { kind: "project"; id: string; name: string; year: number };

export function OakBand({ page }: { page: Page }) {
  return (
    <header className="oak-nav">
      <nav className="plate" aria-label={n.label}>
        <span className="wordmark">
          <span className="wordmark-strong">OAK</span>
          <span className="wordmark-light">box</span>
        </span>
        <span className="plate-rule" aria-hidden="true" />
        <ol className="crumbs">
          {page.kind === "check" ? null : page.kind === "projects" ? (
            <ProjectsHere />
          ) : (
            <Crumb>
              <a className="crumb" href="#/">
                {n.projects}
              </a>
            </Crumb>
          )}
          {page.kind === "new" && <Here>{n.newProject}</Here>}
          {page.kind === "check" && <Here>{t.machine.title}</Here>}
          {page.kind === "project" && <ProjectCrumbs page={page} />}
        </ol>
        {page.kind !== "check" && (
          <Button className="plate-gear" aria-label={n.settings} onPress={() => openSettings()}>
            <Settings aria-hidden="true" size="1em" />
          </Button>
        )}
      </nav>
    </header>
  );
}

/** On the projects page, Projects holds the setting for where they're kept. */
function ProjectsHere() {
  const [open, setOpen] = useState(false);
  const settings = useAppSettings();
  return (
    <Crumb>
      <Jump label={n.projects} current title={n.projectsSettings}>
        <Menu className="crumb-list" onAction={() => setOpen(true)}>
          <MenuItem id="where" className="crumb-item" textValue={n.whereKept}>
            <span className="crumb-item-t">
              {n.whereKept}
              {settings.data && <small className="mono">{settings.data.storage_location}</small>}
            </span>
          </MenuItem>
        </Menu>
      </Jump>
      <StorageLocationDialog isOpen={open} onClose={() => setOpen(false)} />
    </Crumb>
  );
}

function Crumb({ children }: { children: React.ReactNode }) {
  return <li className="crumb-li">{children}</li>;
}

function Here({ children }: { children: React.ReactNode }) {
  return (
    <li className="crumb-li">
      <span className="crumb here" aria-current="page">
        {children}
      </span>
    </li>
  );
}

/** Where a tab will open: the step last open in it here, by name. */
function opensAt(projectId: string, tab: string): string | null {
  return lastStep(projectId, tab)?.title ?? null;
}

function ProjectCrumbs({ page }: { page: Extract<Page, { kind: "project" }> }) {
  // Reads the remembered places (localStorage) as it draws: not memoized, or a list would show where things were.
  "use no memo";
  const { where, frame, tabs } = usePlace();
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: async () => unwrap(await api.GET("/api/projects")),
  });
  const running = useQuery({
    queryKey: ["running"],
    queryFn: async () => unwrap(await api.GET("/api/running")),
    meta: { quiet: true }, // its own progress
    refetchInterval: 5000,
  });
  const tabId = where?.projectId === page.id ? where.tab : null;
  const tab = tabs.find((x) => x.id === tabId);
  const step = frame?.steps.find((s) => s.key === frame.current);
  const tabName = (id: string) => tabs.find((x) => x.id === id)?.title ?? id;
  const busy = new Set(running.data ?? []);
  return (
    <>
      <Crumb>
        <Jump label={`${page.name} · ${page.year}`} current={!tab} title={n.projectsHere}>
          <Menu
            className="crumb-list"
            onAction={(k) =>
              k === "*" ? navigate({ name: "home" }) : navigate({ name: "project", id: String(k) })
            }
          >
            {(projects.data ?? []).map((p) => {
              const at = lastTab(p.id);
              const where = at ? [tabName(at), opensAt(p.id, at)].filter(Boolean).join(" › ") : n.notOpened;
              return (
                <MenuItem
                  key={p.id}
                  id={p.id}
                  className={p.id === page.id ? "crumb-item on" : "crumb-item"}
                  textValue={p.name}
                >
                  <span className="crumb-item-t">
                    {p.name} · {p.tax_year}
                    <small>{where}</small>
                  </span>
                  <span className={busy.has(p.id) ? "crumb-item-s run" : "crumb-item-s"}>
                    {p.id === page.id ? n.here : busy.has(p.id) ? n.running : ""}
                  </span>
                </MenuItem>
              );
            })}
            <Separator className="crumb-sep" />
            <MenuItem id="*" className="crumb-item" textValue={n.allProjects}>
              {n.allProjects}
            </MenuItem>
          </Menu>
          <p className="crumb-foot">{n.projectsFoot}</p>
        </Jump>
      </Crumb>
      {tab && (
        <Crumb>
          <Jump label={tab.title} current={!step} title={n.tabsHere}>
            <Menu
              className="crumb-list"
              disabledKeys={tabs.filter((x) => x.locked).map((x) => x.id)}
              onAction={(k) => navigate({ name: "project", id: page.id, tab: String(k) as never })}
            >
              {tabs.map((x) => (
                <MenuItem
                  key={x.id}
                  id={x.id}
                  className={["crumb-item", x.id === tab.id ? "on" : "", x.locked ? "off" : ""].join(" ")}
                  textValue={x.title}
                >
                  <span className="crumb-item-t">
                    {x.title}
                    {(x.locked || opensAt(page.id, x.id)) && (
                      <small>{x.locked ? n.waits : opensAt(page.id, x.id)}</small>
                    )}
                  </span>
                  <span className="crumb-item-s">
                    {x.id === tab.id ? n.here : x.locked ? n.waitsShort : x.done ? "✓" : ""}
                  </span>
                </MenuItem>
              ))}
            </Menu>
            <p className="crumb-foot">{n.tabsFoot}</p>
          </Jump>
        </Crumb>
      )}
      {tab && step && frame && (
        <Crumb>
          <Jump label={step.title} current title={n.stepsHere}>
            <Menu
              className="crumb-list"
              disabledKeys={frame.steps.filter((s) => s.disabled).map((s) => s.key)}
              onAction={(k) => frame.go(String(k))}
            >
              {frame.steps.map((s) => (
                <MenuItem
                  key={s.key}
                  id={s.key}
                  className={[
                    "crumb-item",
                    s.parent ? "sub" : "",
                    s.key === frame.current ? "on" : "",
                    s.disabled ? "off" : "",
                  ].join(" ")}
                  textValue={s.title}
                >
                  <span className="crumb-item-t">{s.title}</span>
                  <span className="crumb-item-s">
                    {s.key === frame.current
                      ? n.here
                      : s.status === "done"
                        ? "✓"
                        : s.status === "attention"
                          ? "!"
                          : ""}
                  </span>
                </MenuItem>
              ))}
            </Menu>
          </Jump>
        </Crumb>
      )}
    </>
  );
}

/** A crumb that opens the list of the others at its level. The one you're on is in bold. */
function Jump({
  label,
  current,
  title,
  children,
}: {
  label: string;
  current: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <MenuTrigger>
      <Button className={current ? "crumb here jump" : "crumb jump"} aria-label={`${label}: ${title}`}>
        {label}
        <ChevronDown aria-hidden="true" size="0.75em" />
      </Button>
      <Popover className="popover crumb-pop" placement="bottom start" offset={0}>
        {children}
      </Popover>
    </MenuTrigger>
  );
}

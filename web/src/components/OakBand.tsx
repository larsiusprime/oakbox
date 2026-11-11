/** The top of every screen (SPEC D21): the box's lid, polished oak with brass on it: at its left, ⚙ Settings and 🗺
 * Map (in a project), each a brass button of its own; then the plate, the app's main navigation: a trail of where you are, Projects › project › tab › step, each crumb above you a link,
 * the one you're on in bold; each crumb in a project opens a list of the others at its level (projects, tabs,
 * steps), each saying where it will open. No text sits on the bare wood: what's said is on the plate. */
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Menu, MenuItem, MenuTrigger, Popover, Separator } from "react-aria-components";
import { useAppSettings } from "../api/app";
import { api, unwrap } from "../api/client";
import { openSettings } from "../lib/machine";
import { toggleMap, useDock } from "../lib/mapdock";
import { lastStep, lastTab, usePlace } from "../lib/place";
import { navigate } from "../lib/route";
import { t } from "../wording";
import { StorageLocationDialog } from "./StorageLocation";
import { Tip } from "./Tip";

const n = t.nav;

export type Page =
  | { kind: "projects" }
  | { kind: "check" }
  | { kind: "new" }
  | { kind: "project"; id: string; name: string; year: number }
  /** A project opening: its name alone, nothing to press until it's open. */
  | { kind: "opening"; name: string };

export function OakBand({ page }: { page: Page }) {
  return (
    <header className="oak-nav">
      {page.kind !== "check" && page.kind !== "opening" && (
        <div className="oak-tools">
          <Button className="oak-btn oak-btn-gear" aria-label={n.settings} onPress={() => openSettings()}>
            <Settings aria-hidden="true" size="1.05em" />
          </Button>
          {page.kind === "project" && <MapButton />}
        </div>
      )}
      <nav className="plate" aria-label={n.label}>
        <ol className="crumbs">
          {page.kind === "check" || page.kind === "opening" ? null : page.kind === "projects" ? (
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
          {page.kind === "opening" && <Here>{page.name || "…"}</Here>}
          {page.kind === "project" && <ProjectCrumbs page={page} />}
        </ol>
      </nav>
      {page.kind === "project" && <PlateNav />}
    </header>
  );
}

type NavTarget = { label: string; disabled: boolean } | null;

/** The step on screen's Back and Next, as its foot has them (data-nav): read again as the page changes. */
function useNavTargets(): { back: NavTarget; next: NavTarget } {
  const [targets, setTargets] = useState<{ back: NavTarget; next: NavTarget }>({ back: null, next: null });
  useEffect(() => {
    let frame = 0;
    const read = (which: "back" | "next"): NavTarget => {
      const el = [...document.querySelectorAll<HTMLElement>(`.folder-panel [data-nav="${which}"]`)].find(
        (x) => x.offsetParent !== null,
      );
      if (!el) return null;
      const disabled =
        el.hasAttribute("disabled") ||
        el.getAttribute("aria-disabled") === "true" ||
        el.hasAttribute("data-disabled");
      const label = (el.textContent ?? "").replace(/[‹›]/g, "").trim();
      // A plain Back or Next: named by the step before or after the one open in the step list.
      if (
        label === t.wizard.back.replace(/[‹›]/g, "").trim() ||
        label === t.step.next.replace(/[‹›]/g, "").trim()
      ) {
        const items = [
          ...document.querySelectorAll<HTMLElement>(".folder-panel .wiz-steps .wiz-step"),
        ].filter((x) => x.offsetParent !== null);
        const at = items.findIndex((x) => x.classList.contains("now"));
        const near = items[which === "back" ? at - 1 : at + 1]
          ?.querySelector("button")
          ?.getAttribute("title");
        if (at >= 0 && near) return { label: near, disabled };
      }
      return { label, disabled };
    };
    const check = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const back = read("back");
        const next = read("next");
        setTargets((t) => (JSON.stringify(t) === JSON.stringify({ back, next }) ? t : { back, next }));
      });
    };
    check();
    const mo = new MutationObserver(check);
    mo.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["disabled", "aria-disabled", "data-disabled", "hidden"],
    });
    return () => {
      mo.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);
  return targets;
}

/** ‹ › on the plate (SPEC D, 2026-11-11): the step's Back and Next, always in view however far the page is scrolled;
 * pressing one presses the step's own, so they do exactly what it does (and are disabled when it is). */
function PlateNav() {
  const { back, next } = useNavTargets();
  const press = (which: "back" | "next") =>
    [...document.querySelectorAll<HTMLElement>(`.folder-panel [data-nav="${which}"]`)]
      .find((x) => x.offsetParent !== null)
      ?.click();
  if (!back && !next) return null;
  return (
    <div className="plate-nav">
      <Tip text={back ? n.backTo({ step: back.label }) : n.noBack}>
        <Button
          className="oak-btn"
          aria-label={back ? n.backTo({ step: back.label }) : n.noBack}
          isDisabled={!back || back.disabled}
          onPress={() => press("back")}
        >
          ‹
        </Button>
      </Tip>
      <Tip text={next ? n.nextTo({ step: next.label }) : n.noNext}>
        <Button
          className="oak-btn oak-btn-next"
          aria-label={next ? n.nextTo({ step: next.label }) : n.noNext}
          isDisabled={!next || next.disabled}
          onPress={() => press("next")}
        >
          ›
        </Button>
      </Tip>
    </div>
  );
}

/** 🗺 Map: shows or hides the map window (SPEC §3.15); Ctrl+M too. */
function MapButton() {
  const d = useDock();
  return (
    <Tip text={n.mapTip}>
      <Button
        className={`oak-btn oak-btn-map ${d.open && !d.out ? "on" : ""}`}
        aria-pressed={d.open}
        onPress={toggleMap}
      >
        <span aria-hidden="true">🗺</span> {d.out ? n.mapOut : n.map}
      </Button>
    </Tip>
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

import { useEffect, useState } from "react";
import { AppMenus } from "./AppMenus";
import { OakFrame } from "./components/OakFrame";
import { SettingsDialog } from "./components/SettingsDialog";
import { UndoToast } from "./components/UndoToast";
import { onOpenSettings, type SettingsSection, useMachine } from "./lib/machine";
import { back, record } from "./lib/place";
import { HomeScreen } from "./screens/HomeScreen";
import { MachineCheck } from "./screens/MachineCheck";
import { NewProjectScreen } from "./screens/NewProjectScreen";
import { ProjectScreen, TABS, type TabId } from "./screens/ProjectScreen";

export type Route =
  | { name: "home" }
  | { name: "new" }
  | { name: "project"; id: string; tab?: TabId | null; step?: string | null };

function parseHash(hash: string): Route {
  if (hash === "#/new") return { name: "new" };
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z]+)(?:\/([^/]+))?)?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const wanted = match[2];
  const tab = TABS.find((x) => x === wanted) ?? null;
  // #/projects/<id>/fields/<step>: a step of the Data wizard (F3d); a file's own part is "more:<its name>".
  const step = tab === "fields" && match[3] ? decodeURIComponent(match[3]) : null;
  return { name: "project", id: match[1], tab, step };
}

export function navigate(route: Route): void {
  if (route.name === "project") {
    const step = route.tab === "fields" && route.step ? `/${encodeURIComponent(route.step)}` : "";
    window.location.hash = `#/projects/${route.id}${route.tab ? `/${route.tab}` : ""}${step}`;
  } else {
    window.location.hash = route.name === "new" ? "#/new" : "#/";
  }
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  // The computer check (SPEC §5): first run, its memory or cores changed, or asked for in Settings.
  const machine = useMachine();
  const [check, setCheck] = useState<"first" | "changed" | "asked" | null>(null);
  // Not checked yet, or changed since: the check starts (state adjusted as the answer comes in; once it's on screen,
  // it stays until it's done, though the answer changes as it saves).
  const needed = !machine.data
    ? null
    : !machine.data.machine
      ? "first"
      : machine.data.changed
        ? "changed"
        : null;
  const [seen, setSeen] = useState<typeof machine.data>(undefined);
  if (machine.data !== seen) {
    setSeen(machine.data);
    if (needed && check === null) setCheck(needed);
  }
  const [settings, setSettings] = useState<SettingsSection | null>(null);
  useEffect(() => onOpenSettings(setSettings), []);

  // Back (Alt+←, or the mouse's back button): one stop back along the path you took, steps included.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "ArrowLeft") {
        e.preventDefault();
        back();
      }
    };
    const onMouse = (e: MouseEvent) => {
      if (e.button === 3) {
        e.preventDefault();
        back();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mouseup", onMouse);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mouseup", onMouse);
    };
  }, []);
  useEffect(() => {
    if (route.name === "home") record({ home: true });
  }, [route]);

  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return (
    <div className="app">
      <main className="content">
        {check ? (
          <MachineCheck again={check} onDone={() => setCheck(null)} />
        ) : machine.isPending ? null : (
          <>
            {route.name === "home" && <HomeScreen />}
            {route.name === "new" && <NewProjectScreen />}
            {route.name === "project" && (
              <ProjectScreen projectId={route.id} tab={route.tab ?? null} step={route.step ?? null} />
            )}
          </>
        )}
      </main>
      <SettingsDialog
        section={settings}
        onSection={setSettings}
        onClose={() => setSettings(null)}
        onCheck={() => {
          setSettings(null);
          setCheck("asked");
        }}
      />
      <UndoToast />
      <OakFrame />
      <AppMenus route={route} />
    </div>
  );
}

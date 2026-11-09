import { useEffect, useState } from "react";
import { AppMenus } from "./AppMenus";
import { Activity } from "./components/Activity";
import { MapAlone } from "./components/MapWindow";
import { OakFrame } from "./components/OakFrame";
import { SettingsDialog } from "./components/SettingsDialog";
import { UndoToast } from "./components/UndoToast";
import { onOpenSettings, type SettingsSection, useMachine } from "./lib/machine";
import { back, record } from "./lib/place";
import { parseHash, type Route } from "./lib/route";
import { HomeScreen } from "./screens/HomeScreen";
import { MachineCheck } from "./screens/MachineCheck";
import { NewProjectScreen } from "./screens/NewProjectScreen";
import { ProjectScreen } from "./screens/ProjectScreen";

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
            {route.name === "map" && <MapAlone projectId={route.id} />}
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
      <Activity />
      {route.name !== "map" && <OakFrame />}
      {route.name !== "map" && <AppMenus route={route} />}
    </div>
  );
}

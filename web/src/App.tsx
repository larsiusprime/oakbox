import { useEffect, useState } from "react";
import { AppMenus } from "./AppMenus";
import { OakFrame } from "./components/OakFrame";
import { UndoToast } from "./components/UndoToast";
import { back, record } from "./lib/place";
import { parseHash, type Route } from "./lib/route";
import { HomeScreen } from "./screens/HomeScreen";
import { NewProjectScreen } from "./screens/NewProjectScreen";
import { ProjectScreen } from "./screens/ProjectScreen";

export function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

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
        {route.name === "home" && <HomeScreen />}
        {route.name === "new" && <NewProjectScreen />}
        {route.name === "project" && (
          <ProjectScreen projectId={route.id} tab={route.tab ?? null} step={route.step ?? null} />
        )}
      </main>
      <UndoToast />
      <OakFrame />
      <AppMenus route={route} />
    </div>
  );
}

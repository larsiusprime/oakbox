import { useEffect, useState } from "react";
import { HomeScreen } from "./screens/HomeScreen";
import { NewProjectScreen } from "./screens/NewProjectScreen";
import { ProjectScreen, TABS, type TabId } from "./screens/ProjectScreen";
import { t } from "./strings";

type Route = { name: "home" } | { name: "new" } | { name: "project"; id: string; tab?: TabId | null };

function parseHash(hash: string): Route {
  if (hash === "#/new") return { name: "new" };
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z]+))?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const wanted = match[2];
  const tab = TABS.find((x) => x === wanted) ?? null;
  return { name: "project", id: match[1], tab };
}

export function navigate(route: Route): void {
  if (route.name === "project") {
    window.location.hash = `#/projects/${route.id}${route.tab ? `/${route.tab}` : ""}`;
  } else {
    window.location.hash = route.name === "new" ? "#/new" : "#/";
  }
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return (
    <div className="app">
      <header className="titlebar">
        <a className="plate" href="#/">
          <span className="wordmark">
            <span className="wordmark-strong">{t.appName.strong}</span>
            <span className="wordmark-light">{t.appName.light}</span>
          </span>
          <span className="plate-rule" aria-hidden="true" />
          <span className="tagline">{t.tagline}</span>
        </a>
      </header>
      <main className="content">
        {route.name === "home" && <HomeScreen />}
        {route.name === "new" && <NewProjectScreen />}
        {route.name === "project" && <ProjectScreen projectId={route.id} tab={route.tab ?? null} />}
      </main>
    </div>
  );
}

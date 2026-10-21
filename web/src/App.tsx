import { useEffect, useState } from "react";
import { HomeScreen } from "./screens/HomeScreen";
import { NewProjectScreen } from "./screens/NewProjectScreen";
import { ProjectScreen, TABS, type TabId } from "./screens/ProjectScreen";
import { t } from "./strings";

type Route =
  | { name: "home" }
  | { name: "new" }
  | { name: "project"; id: string; tab?: TabId | null; file?: string | null };

function parseHash(hash: string): Route {
  if (hash === "#/new") return { name: "new" };
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z]+)(?:\/([a-z0-9_]+))?)?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const wanted = match[2];
  const tab = TABS.find((x) => x === wanted) ?? null;
  // #/projects/<id>/files/<name>: one input file's fields (SPEC F3c).
  return { name: "project", id: match[1], tab, file: tab === "files" ? (match[3] ?? null) : null };
}

export function navigate(route: Route): void {
  if (route.name === "project") {
    const file = route.tab === "files" && route.file ? `/${route.file}` : "";
    window.location.hash = `#/projects/${route.id}${route.tab ? `/${route.tab}` : ""}${file}`;
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
        {route.name === "project" && (
          <ProjectScreen projectId={route.id} tab={route.tab ?? null} file={route.file ?? null} />
        )}
      </main>
    </div>
  );
}

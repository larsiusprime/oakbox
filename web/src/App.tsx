import { useEffect, useState } from "react";
import { HomeScreen } from "./screens/HomeScreen";
import { ProjectScreen } from "./screens/ProjectScreen";
import { t } from "./strings";

type Route = { name: "home" } | { name: "project"; id: string };

function parseHash(hash: string): Route {
  const match = /^#\/projects\/([a-z0-9-]+)$/.exec(hash);
  return match?.[1] ? { name: "project", id: match[1] } : { name: "home" };
}

export function navigate(route: Route): void {
  window.location.hash = route.name === "home" ? "#/" : `#/projects/${route.id}`;
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
        <a className="wordmark" href="#/" aria-label={t.appTitle}>
          <span className="wordmark-strong">{t.appName.strong}</span>
          <span className="wordmark-light">{t.appName.light}</span>
        </a>
        <span className="titlebar-groove" aria-hidden="true" />
        <span className="tagline">{t.tagline}</span>
      </header>
      <main className="content">
        {route.name === "home" ? <HomeScreen /> : <ProjectScreen projectId={route.id} />}
      </main>
    </div>
  );
}

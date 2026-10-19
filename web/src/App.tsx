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
        <a className="brand" href="#/">
          <span className="brand-mark" aria-hidden="true">
            ◆
          </span>
          {t.appName}
        </a>
        <span className="titlebar-tagline">{t.tagline}</span>
      </header>
      <main className="content">
        {route.name === "home" ? <HomeScreen /> : <ProjectScreen projectId={route.id} />}
      </main>
    </div>
  );
}

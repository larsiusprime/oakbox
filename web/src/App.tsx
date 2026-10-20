import { useEffect, useState } from "react";
import { STAGE_ORDER, STEP_ORDER } from "./api/client";
import { HomeScreen } from "./screens/HomeScreen";
import { type GuideItem, ProjectScreen } from "./screens/ProjectScreen";
import { t } from "./strings";

type Route = { name: "home" } | { name: "project"; id: string; item: GuideItem | null };

const ITEMS: readonly string[] = [...STAGE_ORDER, ...STEP_ORDER];

function parseHash(hash: string): Route {
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z_]+))?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const item = match[2] && ITEMS.includes(match[2]) ? (match[2] as GuideItem) : null;
  return { name: "project", id: match[1], item };
}

export function navigate(route: { name: "home" } | { name: "project"; id: string; item?: GuideItem }): void {
  window.location.hash =
    route.name === "home" ? "#/" : `#/projects/${route.id}${route.item ? `/${route.item}` : ""}`;
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
        {route.name === "home" ? <HomeScreen /> : <ProjectScreen projectId={route.id} item={route.item} />}
      </main>
    </div>
  );
}

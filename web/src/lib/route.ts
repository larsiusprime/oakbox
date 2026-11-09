/** Where the app is: the address after # (#/, #/new, #/projects/<id>/<tab>[/<Data step>]), read and written here
 * only. Screens move with navigate; App follows the address (parseHash). */

/** The project's tabs, in order: their ids in the address. */
export const TABS = [
  "metadata",
  "fields",
  "bring",
  "groups",
  "sales",
  "check",
  "variables",
  "values",
  "report",
] as const;
export type TabId = (typeof TABS)[number];

export type Route =
  | { name: "home" }
  | { name: "new" }
  | { name: "project"; id: string; tab?: TabId | null; step?: string | null }
  /** The map window popped out (SPEC §3.15): a window showing only a project's map. */
  | { name: "map"; id: string };

export function parseHash(hash: string): Route {
  if (hash === "#/new") return { name: "new" };
  const map = /^#\/map\/([a-z0-9-]+)$/.exec(hash);
  if (map?.[1]) return { name: "map", id: map[1] };
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z]+)(?:\/([^/]+))?)?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const wanted = match[2];
  const tab = TABS.find((x) => x === wanted) ?? null;
  // #/projects/<id>/fields/<step>: a step of the Data wizard (F3d); a file's own part is "more:<its name>", encoded.
  const step = tab === "fields" && match[3] ? decodeURIComponent(match[3]) : null;
  return { name: "project", id: match[1], tab, step };
}

/** The address of a place: only the Data tab's steps are in it (the other tabs remember theirs, lib/place.ts). */
export function hashOf(route: Route): string {
  if (route.name === "project") {
    const step = route.tab === "fields" && route.step ? `/${encodeURIComponent(route.step)}` : "";
    return `#/projects/${route.id}${route.tab ? `/${route.tab}` : ""}${step}`;
  }
  if (route.name === "map") return `#/map/${route.id}`;
  return route.name === "new" ? "#/new" : "#/";
}

export function navigate(route: Route): void {
  window.location.hash = hashOf(route);
}

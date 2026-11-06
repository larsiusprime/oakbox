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
  | { name: "project"; id: string; tab?: TabId | null; step?: string | null };

export function parseHash(hash: string): Route {
  if (hash === "#/new") return { name: "new" };
  const match = /^#\/projects\/([a-z0-9-]+)(?:\/([a-z]+)(?:\/([a-z0-9_]+))?)?$/.exec(hash);
  if (!match?.[1]) return { name: "home" };
  const wanted = match[2];
  const tab = TABS.find((x) => x === wanted) ?? null;
  // #/projects/<id>/fields/<step>: a step of the Data wizard (F3d).
  return { name: "project", id: match[1], tab, step: tab === "fields" ? (match[3] ?? null) : null };
}

/** The address of a place: only the Data tab's steps are in it (the other tabs remember theirs, lib/place.ts). */
export function hashOf(route: Route): string {
  if (route.name === "project") {
    const step = route.tab === "fields" && route.step ? `/${route.step}` : "";
    return `#/projects/${route.id}${route.tab ? `/${route.tab}` : ""}${step}`;
  }
  return route.name === "new" ? "#/new" : "#/";
}

export function navigate(route: Route): void {
  window.location.hash = hashOf(route);
}

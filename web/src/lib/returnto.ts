/** Where to come back to (SPEC D, 2026-11-11): a tab that waits on an earlier step sends you there with "Go to …";
 * that step's Looks right (or Next on to the following tab) brings you back to the tab you came from, never somewhere
 * new. This window only, until used. */
import type { TabId } from "./route";
import { navigate } from "./route";

const KEY = "oakbox.returnTo";
type Back = { projectId: string; tab: TabId };

export function setReturn(projectId: string, tab: TabId) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ projectId, tab }));
  } catch {
    // nowhere to keep it: the step goes on as usual
  }
}

function takeReturn(projectId: string): TabId | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const b = JSON.parse(raw) as Back;
    return b.projectId === projectId ? b.tab : null;
  } catch {
    return null;
  }
}

/** On from a step that's done: back to the tab that sent you here, else to the next one. */
export function onward(projectId: string, next: TabId) {
  navigate({ name: "project", id: projectId, tab: takeReturn(projectId) ?? next });
}

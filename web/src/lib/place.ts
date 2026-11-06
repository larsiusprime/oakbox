/** Where you are and where you were (SPEC D21, the plate): the step list on screen now, for the plate's crumbs; the
 * last place in each project and tab, so going back to one opens where you left it; and the path you took, for
 * Back (Alt+←). The places are kept on this computer (localStorage); losing them only means starting a project or
 * tab at its own pick. */
import { useSyncExternalStore } from "react";
import { navigate, type TabId } from "./route";

/** The key of a major step's landing page in its step list (SPEC D21). */
export const OVERVIEW = "overview";

export type FrameStep = { key: string; title: string; status: string; disabled?: boolean; parent?: string };
export type Frame = { steps: FrameStep[]; current: string; go: (key: string) => void };
export type TabInfo = { id: string; title: string; locked: boolean; done: boolean };
export type Where = { projectId: string; tab: string } | null;

type State = { where: Where; frame: Frame | null; tabs: TabInfo[] };
let state: State = { where: null, frame: null, tabs: [] };
// Which step list put the frame up: a list going away clears only its own (a tab's list can leave after the next
// tab's has arrived).
let owner: object | null = null;
const listeners = new Set<() => void>();
const emit = () => {
  for (const l of listeners) l();
};
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function usePlace(): State {
  return useSyncExternalStore(subscribe, () => state);
}

/** The project and tab on screen (set as the project screen renders, before its tab mounts). */
export function setWhere(where: Where): void {
  if (where?.projectId === state.where?.projectId && where?.tab === state.where?.tab) return;
  state = { ...state, where, frame: where?.tab === state.where?.tab ? state.frame : null };
  queueMicrotask(emit);
}

/** The step list on the plate now. */
export function currentFrame(): Frame | null {
  return state.frame;
}

export function currentWhere(): Where {
  return state.where;
}

export function setTabs(tabs: TabInfo[]): void {
  if (JSON.stringify(tabs) === JSON.stringify(state.tabs)) return;
  state = { ...state, tabs };
  emit();
}

/** A step list on screen: its steps and the open one. Remembered as the tab's place; recorded on the path. */
export function publishFrame(frame: Frame | null, by: object): void {
  if (!frame) {
    if (owner !== by) return;
    owner = null;
  } else {
    owner = by;
  }
  state = { ...state, frame };
  emit();
  const w = state.where;
  const now = frame?.steps.find((s) => s.key === frame.current);
  if (!w || !frame || !now) return;
  record({ projectId: w.projectId, tab: w.tab, step: now.key });
  // A tab opens on its landing page only the first time: the place kept is the step under it.
  if (now.key === OVERVIEW) return;
  remember(w.projectId, w.tab, now.key, now.title);
}

// ---------- Last places, per project and per tab ----------

type Place = { tab?: string; steps?: Record<string, { key: string; title: string }>; seen?: string[] };
const KEY = (projectId: string) => `oakbox.place.${projectId}`;

function read(projectId: string): Place {
  try {
    return JSON.parse(localStorage.getItem(KEY(projectId)) ?? "{}") as Place;
  } catch {
    return {};
  }
}

function write(projectId: string, p: Place): void {
  try {
    localStorage.setItem(KEY(projectId), JSON.stringify(p));
  } catch {
    // Not remembered: the project opens at its own pick next time.
  }
}

export function rememberTab(projectId: string, tab: string): void {
  const p = read(projectId);
  if (p.tab !== tab) write(projectId, { ...p, tab });
}

export function remember(projectId: string, tab: string, key: string, title: string): void {
  const p = read(projectId);
  if (p.tab === tab && p.steps?.[tab]?.key === key && p.steps[tab]?.title === title) return;
  write(projectId, { ...p, tab, steps: { ...p.steps, [tab]: { key, title } } });
}

/** The tab a project was last on; null: never opened here. */
export function lastTab(projectId: string): string | null {
  return read(projectId).tab ?? null;
}

/** The step a tab was last on (its key and name); null: never opened here. */
export function lastStep(projectId: string, tab: string): { key: string; title: string } | null {
  return read(projectId).steps?.[tab] ?? null;
}

/** Whether a landing page (a tab's, or a major step's) has been shown in this project here. */
export function seen(projectId: string, landing: string): boolean {
  return read(projectId).seen?.includes(landing) ?? false;
}

export function markSeen(projectId: string, landing: string): void {
  const p = read(projectId);
  if (!p.seen?.includes(landing)) write(projectId, { ...p, seen: [...(p.seen ?? []), landing] });
}

// ---------- The path, for Back ----------

type Stop = { projectId: string; tab: string; step: string } | { home: true };
const path: Stop[] = [];
let goingBack = false;

const same = (a: Stop | undefined, b: Stop) => JSON.stringify(a) === JSON.stringify(b);

export function record(stop: Stop): void {
  if (goingBack) return;
  if (!same(path[path.length - 1], stop)) path.push(stop);
  if (path.length > 100) path.shift();
}

/** One stop back along the path: the step in this tab, or the tab or project it came from (opened at that step). */
export function back(): void {
  if (path.length < 2) return;
  path.pop();
  const to = path[path.length - 1];
  if (!to) return;
  goingBack = true;
  setTimeout(() => {
    goingBack = false;
  }, 400);
  if ("home" in to) {
    navigate({ name: "home" });
    return;
  }
  const w = state.where;
  if (w && w.projectId === to.projectId && w.tab === to.tab && state.frame) {
    state.frame.go(to.step);
    return;
  }
  const title = lastStep(to.projectId, to.tab)?.title ?? "";
  if (to.step !== OVERVIEW) remember(to.projectId, to.tab, to.step, title);
  navigate({ name: "project", id: to.projectId, tab: to.tab as TabId, step: to.step });
}

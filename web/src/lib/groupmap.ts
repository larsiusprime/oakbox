/** Build the groups on the map window (SPEC §3.15): the groups as they're being edited, and what the map shows of
 * them, shared by the step (which writes them) and the map window (which draws them), in this window and a
 * popped-out one (localStorage, as the dock is). Null while the step isn't open. */
import { useSyncExternalStore } from "react";
import type { ModelGroup } from "../api/client";

export type ColourBy = "group" | "changes";
export type GroupMap = {
  projectId: string;
  /** The groups as edited (the preview's), in order. */
  groups: ModelGroup[];
  unassigned: string;
  currency: string;
  colourBy: ColourBy;
  /** Legend entries switched off: group ids ("" unassigned), or "__same" (unchanged, by changes). */
  hidden: string[];
  /** Parcels picked out (a move, a condition's "show them"), or null. */
  highlight: number[] | null;
};

const KEY = "oakbox.mapGroups";

function load(): GroupMap | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null") as GroupMap | null;
  } catch {
    return null;
  }
}

let state: GroupMap | null = typeof window === "undefined" ? null : load();
const listeners = new Set<() => void>();
const tell = () => {
  for (const l of listeners) l();
};

if (typeof window !== "undefined")
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY) return;
    state = load();
    tell();
  });

function write(next: GroupMap | null) {
  state = next;
  try {
    if (next) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {
    // this window only
  }
  tell();
}

/** The step opened (or its groups edited): what the map window draws; what's shown of them is kept. */
export function publishGroups(g: Omit<GroupMap, "colourBy" | "hidden" | "highlight">) {
  const kept = state && state.projectId === g.projectId ? state : null;
  write({
    colourBy: kept?.colourBy ?? "group",
    hidden: kept?.hidden ?? [],
    highlight: kept?.highlight ?? null,
    ...g,
  });
}

/** A change to what's shown (from the step or the map window): colouring, the legend, the highlight. */
export function setGroupMap(patch: Partial<Pick<GroupMap, "colourBy" | "hidden" | "highlight">>) {
  if (state) write({ ...state, ...patch });
}

/** The step closed: the map window goes back to following fields. */
export function clearGroups() {
  if (state) write(null);
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useGroupMap(): GroupMap | null {
  return useSyncExternalStore(subscribe, () => state);
}

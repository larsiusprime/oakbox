/** A step that takes the map over (SPEC §3.15): which one, what it asks to be done on the map (the map's banner), and
 * the map as it was before (given back on leaving). Shared with a popped-out map through localStorage, as the dock
 * is. Changes made on the map are announced, so a screen in the other window reads them again. */
import { useEffect, useSyncExternalStore } from "react";
import { type Dock, dockNow, setDock } from "./mapdock";

/** What the map window draws for the step. */
export type StepView = "groups" | "centre";
export type MapStep = {
  projectId: string;
  view: StepView;
  /** The step's name, on the banner and the Follow button. */
  title: string;
  /** What to do on the map: one imperative sentence. */
  instruction: string;
  /** When the screen's card was last hovered: the banner flashes. */
  flash: number;
};

const KEY = "oakbox.mapStep";
const TOUCHED = "oakbox.mapTouched";

function load(): MapStep | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "null") as MapStep | null;
  } catch {
    return null;
  }
}

let state: MapStep | null = typeof window === "undefined" ? null : load();
const listeners = new Set<() => void>();
const touchers = new Set<(projectId: string) => void>();
const tell = () => {
  for (const l of listeners) l();
};

if (typeof window !== "undefined")
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) {
      state = load();
      tell();
    } else if (e.key === TOUCHED && e.newValue) {
      try {
        const { projectId } = JSON.parse(e.newValue) as { projectId: string };
        for (const t of touchers) t(projectId);
      } catch {
        // not ours
      }
    }
  });

function write(next: MapStep | null) {
  state = next;
  try {
    if (next) localStorage.setItem(KEY, JSON.stringify(next));
    else localStorage.removeItem(KEY);
  } catch {
    // this window only
  }
  tell();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useMapStep(): MapStep | null {
  return useSyncExternalStore(subscribe, () => state);
}

/** The screen's card hovered: the map's banner flashes, so the two read as one. */
export function flashBanner() {
  if (state) write({ ...state, flash: Date.now() });
}

/** Something changed on the map (the centre moved): a screen in the other window reads it again. */
export function announceTouched(projectId: string) {
  try {
    localStorage.setItem(TOUCHED, JSON.stringify({ projectId, at: Date.now() }));
  } catch {
    // one window
  }
}

/** Something was changed on the map in the other window. */
export function onTouched(f: (projectId: string) => void): () => void {
  touchers.add(f);
  return () => {
    touchers.delete(f);
  };
}

/** The step takes the map over while it's open: the map opens where it last was (a popped-out one stays out), shows the
 * step's view and its instruction; leaving, the map is given back as it was (open or closed, its field, Follow). Its
 * size and side are never changed. Closed by the user on the step, it isn't opened again here. */
export function useTakeOver(projectId: string, view: StepView, title: string, instruction: string) {
  useEffect(() => {
    const before: Dock = dockNow();
    write({ projectId, view, title, instruction, flash: 0 });
    setDock(before.out ? { follow: true } : { open: true, follow: true });
    return () => {
      if (state?.projectId === projectId && state.view === view) write(null);
      const now = dockNow();
      setDock({ ...(now.out ? {} : { open: before.open }), follow: before.follow, field: before.field });
    };
  }, [projectId, view, title, instruction]);
}

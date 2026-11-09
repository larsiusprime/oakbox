/** Where the map window is (SPEC §3.15): docked on a side of the main window, at a size, or closed; remembered on this
 * computer. One immutable snapshot, replaced on every change (read through useSyncExternalStore). */
import { useSyncExternalStore } from "react";

export type Side = "right" | "bottom" | "left" | "top";
export type Dock = {
  open: boolean;
  side: Side;
  size: number;
  /** The field chosen by hand (when not following, or the step shows none). */
  field: string | null;
  /** Follow: the map takes the step's colouring (SPEC §3.15); on until a field is chosen by hand. */
  follow: boolean;
};

const KEY = "oakbox.mapDock";
export const MIN = 0.25;
export const MAX = 0.7;
const START: Dock = { open: false, side: "right", size: 0.4, field: null, follow: true };

function read(): Dock {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null") as Partial<Dock> | null;
    if (v && typeof v === "object") return { ...START, ...v };
  } catch {
    // no storage here: the default
  }
  return START;
}

let dock: Dock = read();
const listeners = new Set<() => void>();

export function setDock(patch: Partial<Dock>) {
  dock = { ...dock, ...patch, size: Math.min(MAX, Math.max(MIN, patch.size ?? dock.size)) };
  try {
    localStorage.setItem(KEY, JSON.stringify(dock));
  } catch {
    // remembered for this visit only
  }
  for (const l of listeners) l();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useDock(): Dock {
  return useSyncExternalStore(subscribe, () => dock);
}

export const toggleMap = () => setDock({ open: !dock.open });

/** Narrow windows dock it at the bottom only. */
export const NARROW = 900;
export const sideFor = (side: Side, width: number): Side => (width < NARROW ? "bottom" : side);

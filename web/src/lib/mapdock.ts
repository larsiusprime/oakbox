/** Where the map window is (SPEC §3.15): docked on a side of the main window, at a size, full size, popped out into a
 * window of its own, or closed; remembered on this computer. One immutable snapshot, replaced on every change (read
 * through useSyncExternalStore).
 *
 * The main window and the popped-out one keep in step through this computer's storage (its `storage` event reaches
 * every other window of the app): the dock itself, where the main window is (what the popped-out map follows), and a
 * link the card asks the main window to go to. */
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
  /** Full size: the whole of the main window inside the frame, the page behind it. */
  full: boolean;
  /** Popped out: in a window of its own; the main window shows none. */
  out: boolean;
  /** The parcel's card pinned to the map's left side (📌), or floating over it, where it was dragged. */
  cardPinned: boolean;
  /** The colour picker's sections folded away (pu, sr, problems, differences, columns). */
  folded: string[];
  /** The parcels (or sales) outside the histogram's range not drawn, rather than drawn at its ends. */
  hideOut: boolean;
};

const KEY = "oakbox.mapDock";
const ROUTE = "oakbox.mapRoute";
const GO = "oakbox.mapGo";
export const MIN = 0.25;
export const MAX = 0.7;
const START: Dock = {
  open: false,
  side: "right",
  size: 0.4,
  field: null,
  follow: true,
  full: false,
  out: false,
  cardPinned: true,
  folded: ["columns"],
  hideOut: false,
};

function load<T>(key: string, fallback: T): T {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? "null") as T | null;
    return v ?? fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // remembered for this visit only
  }
}

let dock: Dock = { ...START, ...load<Partial<Dock>>(KEY, {}) };
export type Where = { projectId: string; tab: string | null; step: string | null };
let where: Where | null = load<Where | null>(ROUTE, null);
const listeners = new Set<() => void>();
const goers = new Set<(w: Where) => void>();
const tell = () => {
  for (const l of listeners) l();
};

// Another window of the app changed one: taken in here.
if (typeof window !== "undefined")
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) {
      dock = { ...START, ...load<Partial<Dock>>(KEY, {}) };
      tell();
    } else if (e.key === ROUTE) {
      where = load<Where | null>(ROUTE, null);
      tell();
    } else if (e.key === GO && e.newValue) {
      const asked = load<Where | null>(GO, null);
      if (asked) for (const g of goers) g(asked);
    }
  });

export function setDock(patch: Partial<Dock>) {
  dock = { ...dock, ...patch, size: Math.min(MAX, Math.max(MIN, patch.size ?? dock.size)) };
  save(KEY, dock);
  tell();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useDock(): Dock {
  return useSyncExternalStore(subscribe, () => dock);
}

/** Ctrl+M and 🗺 Map: open or close it; popped out, back into the main window. */
export const toggleMap = () => setDock(dock.out ? { out: false, open: true } : { open: !dock.open });

/** Narrow windows dock it at the bottom only. */
export const NARROW = 900;
export const sideFor = (side: Side, width: number): Side => (width < NARROW ? "bottom" : side);

/** The main window says where it is (the popped-out map follows it). */
export function publishWhere(w: Where) {
  if (where && where.projectId === w.projectId && where.tab === w.tab && where.step === w.step) return;
  where = w;
  save(ROUTE, w);
}

/** Where the main window is, seen from the popped-out one. */
export function useWhere(): Where | null {
  return useSyncExternalStore(subscribe, () => where);
}

/** The popped-out map's card asks the main window to go to a step. */
export function askGo(w: Where) {
  save(GO, { ...w, at: Date.now() });
}

/** The main window going where the popped-out map asks. */
export function onGo(g: (w: Where) => void): () => void {
  goers.add(g);
  return () => {
    goers.delete(g);
  };
}

/** The dock as it is now, read outside React (an effect deciding whether to open the map). */
export const dockNow = (): Dock => dock;

/** 🗺 Show on map from a screen that doesn't take the map over (SPEC §3.15, summon): the map opens (a popped-out one
 * stays out) on exactly that layer, Follow off, so the next step doesn't wipe it; Back to following in its header. */
export function summonMap(field: string) {
  setDock(dock.out ? { follow: false, field } : { open: true, follow: false, field });
}

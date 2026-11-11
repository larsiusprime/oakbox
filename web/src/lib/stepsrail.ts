/** The step list's width (SPEC D): the full list, a thin rail of numbers and marks, or (auto) thin only when the
 * folder is too narrow for the full list beside the sheet. Remembered for this viewer. */
import { useSyncExternalStore } from "react";

export type RailMode = "auto" | "thin" | "wide";
const KEY = "oakbox.stepsRail";

function load(): RailMode {
  try {
    const v = localStorage.getItem(KEY);
    return v === "thin" || v === "wide" ? v : "auto";
  } catch {
    return "auto";
  }
}

let mode: RailMode = typeof window === "undefined" ? "auto" : load();
const listeners = new Set<() => void>();

export function setRail(next: RailMode) {
  mode = next;
  try {
    if (next === "auto") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, next);
  } catch {
    // this window only
  }
  for (const l of listeners) l();
}

export function useRail(): RailMode {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => mode,
  );
}

/** The list's class: thin or wide as chosen; auto, the stylesheet decides by the folder's width. */
export const railClass = (m: RailMode) => (m === "auto" ? "wiz-steps" : `wiz-steps rail-${m}`);

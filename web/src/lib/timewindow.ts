/** The time adjustment step's window in time (SPEC F6): a group's sales between two days, chosen by dragging across
 * its chart or with the map's time bar (▶ steps it on). The step's map shows the sales in it; none: every date. */
import { useSyncExternalStore } from "react";

export type TimeWindow = { group: string; from: number; to: number } | null;

let state: TimeWindow = null;
const listeners = new Set<() => void>();

export function setTimeWindow(next: TimeWindow) {
  state = next;
  for (const l of listeners) l();
}

export function useTimeWindow(): TimeWindow {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}

/** One thing in a step's list picked to look at on the map (SPEC §3.15): a sale in a group of sales compared, say.
 * The step's map rings it and moves to it. Kept with what it belongs to (the sale picked), so picking another sale
 * clears it. This window only: a step that takes the map over draws its map here. */
import { useSyncExternalStore } from "react";

type Focus = { within: string; key: string } | null;
let focus: Focus = null;
const listeners = new Set<() => void>();

export function setFocus(within: string, key: string | null) {
  focus = key ? { within, key } : null;
  for (const l of listeners) l();
}

/** The key picked within this (the sale whose group it is), or null. */
export function useFocus(within: string | null): string | null {
  const f = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => focus,
  );
  return f && within && f.within === within ? f.key : null;
}

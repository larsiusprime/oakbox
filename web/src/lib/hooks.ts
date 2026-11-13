import { useEffect, useRef, useState } from "react";

/** A value once it has stopped changing for `ms`: waits for typing to stop before asking the server again. */
export function useSettled<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return settled;
}

/** An element's width in pixels, kept up to date, for a chart drawn at its own width so its text keeps its size
 * (AGENTS.md); at least `min`. */
export function useWidth<T extends Element>(fallback = 800, min = 320) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const seen = new ResizeObserver(([e]) => e && setW(Math.max(min, Math.round(e.contentRect.width))));
    seen.observe(el);
    return () => seen.disconnect();
  }, [min]);
  return [ref, w] as const;
}

/** Runs `run` with the value once it has stopped changing for `ms` (a change saved as it settles, on a page with no
 * Save button). The value is compared by its content, so a new object with the same content doesn't count. */
export function useOnSettled<T>(value: T, run: (v: T) => void, ms = 600): void {
  const settled = useSettled(JSON.stringify(value), ms);
  const latest = useRef(run);
  useEffect(() => {
    latest.current = run;
  });
  useEffect(() => {
    latest.current(JSON.parse(settled) as T);
  }, [settled]);
}

/** A control's value shown at once (AGENTS.md: instant feedback): what was just pressed shows until the value it was
 * pressed over changes (saved and read back, or changed elsewhere), however long the save takes. A save that fails
 * leaves it showing the press; the failure is said where the save is. */
export function useAtOnce<T>(value: T): [T, (v: T) => void] {
  const [mine, setMine] = useState<{ v: T; over: string } | null>(null);
  const now = JSON.stringify(value ?? null);
  const shown = mine && mine.over === now ? mine.v : value;
  return [shown, (v: T) => setMine({ v, over: now })];
}

/** After the browser has painted what's on screen now (two frames): a choice shown chosen, its list closed, before
 * the work it starts (AGENTS.md: instant feedback first). */
export function afterPaint(f: () => void) {
  requestAnimationFrame(() => requestAnimationFrame(f));
}

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

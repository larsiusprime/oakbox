/** A row of folder tabs that never wraps (SPEC D21): when the tabs are wider than the folder, the row scrolls, with
 * ‹ › buttons at its ends (each greyed at its end), as sheet tabs and browser tab strips do. The open tab is kept in
 * view; the mouse wheel over the row scrolls it sideways. */
import { ChevronLeft, ChevronRight } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { t } from "../wording";
import { Tip } from "./Tip";

export function TabStrip({ selected, children }: { selected: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const [ends, setEnds] = useState({ over: false, start: true, end: true });

  const measure = useCallback(() => {
    const el = box.current;
    if (!el) return;
    const over = el.scrollWidth > el.clientWidth + 1;
    const start = el.scrollLeft <= 1;
    const end = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1;
    setEnds((was) =>
      was.over === over && was.start === start && was.end === end ? was : { over, start, end },
    );
  }, []);

  // Measure as the window, the zoom or the tabs change.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    measure();
    const seen = new ResizeObserver(measure);
    seen.observe(el);
    for (const child of Array.from(el.children)) seen.observe(child);
    return () => seen.disconnect();
  }, [measure]);

  // The open tab is always in view: again whenever another tab opens.
  // biome-ignore lint/correctness/useExhaustiveDependencies: `selected` is the trigger; the tab is found in the DOM.
  useEffect(() => {
    const el = box.current;
    const tab = el?.querySelector<HTMLElement>("[data-selected]");
    if (!el || !tab) return;
    const left = tab.offsetLeft - el.offsetLeft;
    if (left < el.scrollLeft) el.scrollLeft = left - 24;
    else if (left + tab.offsetWidth > el.scrollLeft + el.clientWidth)
      el.scrollLeft = left + tab.offsetWidth - el.clientWidth + 24;
    measure();
  }, [selected, measure]);

  // The wheel over the row scrolls it sideways (Ctrl+wheel is the app's zoom, left alone).
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || el.scrollWidth <= el.clientWidth) return;
      const by = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      if (!by) return;
      e.preventDefault();
      el.scrollLeft += by;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const scroll = (dir: -1 | 1) => {
    const el = box.current;
    if (el) el.scrollBy({ left: dir * Math.max(120, el.clientWidth * 0.6), behavior: "smooth" });
  };

  return (
    <div className={ends.over ? "tab-strip over" : "tab-strip"}>
      {ends.over && (
        <Tip text={t.tabs.scrollLeft}>
          <Button
            className="tab-scroll"
            aria-label={t.tabs.scrollLeft}
            isDisabled={ends.start}
            onPress={() => scroll(-1)}
          >
            <ChevronLeft aria-hidden="true" size="1em" />
          </Button>
        </Tip>
      )}
      <div className="tab-strip-box" ref={box} onScroll={measure}>
        {children}
      </div>
      {ends.over && (
        <Tip text={t.tabs.scrollRight}>
          <Button
            className="tab-scroll"
            aria-label={t.tabs.scrollRight}
            isDisabled={ends.end}
            onPress={() => scroll(1)}
          >
            <ChevronRight aria-hidden="true" size="1em" />
          </Button>
        </Tip>
      )}
    </div>
  );
}

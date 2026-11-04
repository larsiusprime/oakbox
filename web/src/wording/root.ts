import { createElement, Fragment, type ReactNode, useEffect, useState } from "react";

/** Around the app. In live wording editing (`npm run dev:wording`), it draws the app again when a formatted message
 * changes (catalog.ts), keeping the page it's on; everywhere else it's just its children. */
export function WordingRoot({ children }: { children: ReactNode }) {
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    if (!__WORDING_EDIT__) return;
    const redraw = () => setDrawn((n) => n + 1);
    window.addEventListener("oakbox-wording-redraw", redraw);
    return () => window.removeEventListener("oakbox-wording-redraw", redraw);
  }, []);
  return createElement(Fragment, { key: drawn }, children);
}

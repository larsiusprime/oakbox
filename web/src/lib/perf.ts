/** How long a click takes to settle, written to OAK box's log when it's slow (app.py's /api/log/slow-click), so a
 * slow click can be diagnosed from the log: what was clicked, every request it made (when it went out, how long its
 * answer took), the time the window itself was busy, and the time it was doing neither (waiting between them).
 *
 * A click (or Enter or Space) starts it; it settles once no request is out for a moment and the screen is drawn with
 * the last answer. A click that comes while one is still waiting for answers starts its own; the one before still
 * settles when its answers come (and its record says another click came meanwhile).
 *
 * Imported first in main.tsx: it wraps window.fetch before anything keeps a reference to it (openapi-fetch does, when
 * its client is made). */

export const SLOW_CLICK = 2000; // ms: a click taking longer to settle is written to the log
const QUIET = 300; // ms with no request out before a click is taken as settled
const LONGEST = 900_000; // ms: one still open after this is let go, unreported

/** SLOW_CLICK, or what localStorage's oakbox.slowClickMs says instead (to see what quicker clicks spend time on). */
function slowClick(): number {
  try {
    return Number(localStorage.getItem("oakbox.slowClickMs")) || SLOW_CLICK;
  } catch {
    return SLOW_CLICK;
  }
}

export type Sent = { method: string; path: string; at: number; took: number; status: number };

type Click = {
  what: string;
  page: string;
  t0: number;
  requests: Sent[];
  spans: [number, number][]; // when a request was out, ms from the page's start
  out: number;
  lastPaint: number;
  done: boolean;
  overlapped: boolean; // another click came while it was still waiting for answers
  quiet?: ReturnType<typeof setTimeout>;
};

const fetch0: typeof fetch = typeof window === "undefined" ? fetch : window.fetch.bind(window);
let supportsLongTasks = false;
let click: Click | null = null;
const longTasks: [number, number][] = [];

/** The union of spans' length within [a, b]. */
export function covered(spans: [number, number][], a: number, b: number): number {
  const s = spans
    .map(([x, y]): [number, number] => [Math.max(a, x), Math.min(b, y)])
    .filter(([x, y]) => y > x)
    .sort((p, q) => p[0] - q[0]);
  let total = 0;
  let end = a;
  for (const [x, y] of s) {
    if (y > end) {
      total += y - Math.max(x, end);
      end = y;
    }
  }
  return total;
}

/** A path for the log: a project's id shortened, the query string left off (it can carry what's typed). */
export function shortPath(url: string): string {
  const path = new URL(url, "http://x").pathname;
  return path.replace(/^\/api\/projects\/[^/]+/, "/api/projects/…");
}

/** What was clicked, in a few words: its label, or its text. */
export function whatWas(target: EventTarget | null): string {
  if (!(target instanceof Element)) return "?";
  const el =
    target.closest(
      "[role=option],[role=menuitem],[role=tab],[role=checkbox],[role=switch],[role=radio],[role=button],button,a,label,input,select,[aria-label]",
    ) ?? target;
  // Its label, or the first line of its text (an option's name, not the sample values under it).
  const text = (el as HTMLElement).innerText || el.textContent || "";
  const first = text
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l);
  const what = (el.getAttribute("aria-label") || first || "").replace(/\s+/g, " ").trim();
  return what.length > 60 ? `${what.slice(0, 59)}…` : what || el.tagName.toLowerCase();
}

function paint(f: () => void) {
  requestAnimationFrame(() => requestAnimationFrame(f));
}

function finish(c: Click) {
  if (c.done) return;
  c.done = true;
  if (c.quiet) clearTimeout(c.quiet);
  if (click === c) click = null;
  const end = c.lastPaint;
  const took = end - c.t0;
  if (took < slowClick() || took > LONGEST) return;
  const busy = supportsLongTasks ? covered(longTasks, c.t0, end) : null;
  const either = covered([...c.spans, ...(busy === null ? [] : longTasks)], c.t0, end);
  const body = {
    what: c.what,
    page: c.page,
    took: took / 1000,
    requests: c.requests,
    busy: busy === null ? null : busy / 1000,
    neither: (took - either) / 1000,
    cut_short: c.overlapped,
  };
  void fetch0("/api/log/slow-click", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => undefined);
}

function settleLater(c: Click) {
  if (c.done) return;
  if (c.quiet) clearTimeout(c.quiet);
  c.quiet = setTimeout(() => {
    if (c.out === 0) finish(c);
  }, QUIET);
}

function start(e: Event) {
  if (!e.isTrusted) return; // a click the page made itself (a button opening its list) is part of the one before
  // One still waiting for answers stays open, and settles when they come; one only waiting the quiet moment out
  // has settled.
  if (click) {
    if (click.out > 0) click.overlapped = true;
    else finish(click);
  }
  const c: Click = {
    what: whatWas(e.target),
    page: location.pathname + location.hash,
    t0: performance.now(),
    requests: [],
    spans: [],
    out: 0,
    lastPaint: 0,
    done: false,
    overlapped: false,
  };
  click = c;
  paint(() => {
    c.lastPaint = performance.now();
    settleLater(c);
  });
}

function install() {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : String(input);
    const c = click;
    if (!c || !shortPath(url).startsWith("/api/")) return fetch0(input, init);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const a = performance.now();
    c.out += 1;
    if (c.quiet) clearTimeout(c.quiet);
    let status = 0;
    try {
      const r = await fetch0(input, init);
      status = r.status;
      return r;
    } finally {
      const b = performance.now();
      c.out -= 1;
      c.spans.push([a, b]);
      c.requests.push({ method, path: shortPath(url), at: (a - c.t0) / 1000, took: (b - a) / 1000, status });
      if (c.out === 0)
        paint(() => {
          c.lastPaint = performance.now();
          settleLater(c);
        });
    }
  };
  document.addEventListener("click", start, true);
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.key === "Enter" || (e.key === " " && !(e.target instanceof HTMLInputElement))) start(e);
    },
    true,
  );
  try {
    new PerformanceObserver((list) => {
      for (const t of list.getEntries()) longTasks.push([t.startTime, t.startTime + t.duration]);
      const old = performance.now() - LONGEST;
      while ((longTasks[0]?.[1] ?? old) < old) longTasks.shift();
    }).observe({ type: "longtask", buffered: false });
    supportsLongTasks = true;
  } catch {
    // This browser can't say when the page was busy (Safari's WebKit): the log says so.
  }
}

if (typeof window !== "undefined" && typeof document !== "undefined" && import.meta.env.MODE !== "test")
  install();

/** Every action acknowledged at once (AGENTS.md, 2026-11-07), for the whole app in one place:
 *
 * - the control pressed shows busy (`data-busy`: a pulsing dot, the progress cursor) while the change it started is
 *   being saved;
 * - a pill in the corner, from the first moment anything is saved or read: what, how long it's been, and Stop for a
 *   read (a save isn't stopped half way: it finishes, and says so).
 *
 * A query or mutation with `meta: { quiet: true }` is left out: it shows its own progress where its result appears
 * (a run's steps, a file's quick-read copy, polling). */
import { type Mutation, type Query, type QueryClient, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Button } from "react-aria-components";
import { clock } from "../lib/format";
import { t } from "../wording";

const a = t.activity;
/** A mutation starting this soon after a press is that press's. */
const PRESS_MS = 600;
const CONTROL =
  "button, [role=button], [role=radio], [role=checkbox], [role=switch], [role=option], a, select, input";

/** Queries a screen is showing its own Loading line for (components/Waiting.tsx): not in the pill too. */
const shown = new Map<string, number>();
const listeners = new Set<() => void>();
export function showHere(hash: string): () => void {
  shown.set(hash, (shown.get(hash) ?? 0) + 1);
  for (const l of listeners) l();
  return () => {
    const n = (shown.get(hash) ?? 1) - 1;
    if (n > 0) shown.set(hash, n);
    else shown.delete(hash);
    for (const l of listeners) l();
  };
}

type Item = { id: string; kind: "save" | "read"; doing: string; since: number };

const quiet = (meta: Record<string, unknown> | undefined) => meta?.quiet === true;
const text = (meta: Record<string, unknown> | undefined) =>
  typeof meta?.doing === "string" ? meta.doing : null;

function pending(qc: QueryClient, seen: Map<string, number>): Item[] {
  const now = Date.now();
  const items: Item[] = [];
  for (const m of qc.getMutationCache().getAll() as Mutation<unknown, unknown, unknown, unknown>[]) {
    if (m.state.status !== "pending" || quiet(m.meta)) continue;
    items.push({
      id: `m${m.mutationId}`,
      kind: "save",
      doing: text(m.meta) ?? a.saving,
      since: m.state.submittedAt,
    });
  }
  for (const q of qc.getQueryCache().getAll() as Query[]) {
    // A first load (nothing to show yet) is shown where it will appear (a step's loading bar, a Loading): not here.
    if (
      q.state.fetchStatus !== "fetching" ||
      q.state.status === "pending" ||
      quiet(q.meta) ||
      shown.has(q.queryHash)
    )
      continue;
    const id = `q${q.queryHash}`;
    if (!seen.has(id)) seen.set(id, now);
    items.push({ id, kind: "read", doing: text(q.meta) ?? a.reading, since: seen.get(id) ?? now });
  }
  for (const id of [...seen.keys()]) if (!items.some((i) => i.id === id)) seen.delete(id);
  return items.sort((x, y) => x.since - y.since);
}

export function Activity() {
  const qc = useQueryClient();
  const seen = useRef(new Map<string, number>());
  const [{ items, now }, setState] = useState<{ items: Item[]; now: number }>({ items: [], now: 0 });

  // The pill: from the caches, as they change.
  useEffect(() => {
    const update = () => setState({ items: pending(qc, seen.current), now: Date.now() });
    const a = qc.getQueryCache().subscribe(update);
    const b = qc.getMutationCache().subscribe(update);
    listeners.add(update);
    update();
    return () => {
      a();
      b();
      listeners.delete(update);
    };
  }, [qc]);
  useEffect(() => {
    if (items.length === 0) return;
    const id = window.setInterval(() => setState((s) => ({ ...s, now: Date.now() })), 1000);
    return () => window.clearInterval(id);
  }, [items.length]);
  // The control pressed: busy while the change it started is pending.
  useEffect(() => {
    let last: { el: Element; at: number } | null = null;
    const press = (e: Event) => {
      const el = e.target instanceof Element ? e.target.closest(CONTROL) : null;
      if (el) last = { el, at: Date.now() };
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") press(e);
    };
    const busy = new Map<number, Element>();
    const off = qc.getMutationCache().subscribe((ev) => {
      const m = ev.mutation;
      if (!m || quiet(m.meta)) return;
      if (ev.type === "added" && last && Date.now() - last.at < PRESS_MS && last.el.isConnected) {
        busy.set(m.mutationId, last.el);
        last.el.setAttribute("data-busy", "");
      } else if (ev.type === "updated" && m.state.status !== "pending" && busy.has(m.mutationId)) {
        const el = busy.get(m.mutationId);
        busy.delete(m.mutationId);
        if (el && ![...busy.values()].includes(el)) el.removeAttribute("data-busy");
      }
    });
    document.addEventListener("pointerdown", press, true);
    document.addEventListener("keydown", key, true);
    return () => {
      off();
      document.removeEventListener("pointerdown", press, true);
      document.removeEventListener("keydown", key, true);
      for (const el of busy.values()) el.removeAttribute("data-busy");
    };
  }, [qc]);

  if (items.length === 0) return null;
  const first = items[0];
  if (!first) return null;
  const reads = items.filter((i) => i.kind === "read");
  const stop = () =>
    void qc.cancelQueries({
      predicate: (q) => q.state.fetchStatus === "fetching" && !quiet(q.meta),
    });
  return (
    <div className="activity" role="status" aria-live="polite">
      <span className="bi-pulse" aria-hidden="true" />
      <span>
        {first.doing}
        {items.length > 1 && ` ${a.more({ n: items.length - 1 })}`} ·{" "}
        {clock(Math.max(0, now - first.since) / 1000)}
      </span>
      {reads.length > 0 && reads.length === items.length && (
        <Button className="button button-small" onPress={stop}>
          {a.stop}
        </Button>
      )}
    </div>
  );
}

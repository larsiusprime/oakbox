/** Steps that only show results, ticked once they've been looked at: per project and tab, and per run. A new run
 * starts them unticked again (what they show has changed); while a run is stale they show no tick at all. Kept on
 * this computer (localStorage): a convenience, not part of the project. */
import { useEffect, useState } from "react";

type Seen = { run: string; steps: string[] };

const key = (projectId: string, tab: string) => `oakbox.visited.${projectId}.${tab}`;

function read(projectId: string, tab: string): Seen | null {
  try {
    return JSON.parse(localStorage.getItem(key(projectId, tab)) ?? "null");
  } catch {
    return null;
  }
}

export function useVisited(projectId: string, tab: string, run: string | null | undefined) {
  const [seen, setSeen] = useState<Seen | null>(() => read(projectId, tab));
  const steps = run && seen?.run === run ? seen.steps : [];
  return {
    has: (step: string) => steps.includes(step),
    mark: (step: string) => {
      if (!run || steps.includes(step)) return;
      const next = { run, steps: [...steps, step] };
      setSeen(next);
      try {
        localStorage.setItem(key(projectId, tab), JSON.stringify(next));
      } catch {
        // Not remembered: the tick still shows until the page is left.
      }
    },
  };
}

/** Marks a step visited once it's on screen (an effect: never while rendering). */
export function MarkVisited({ step, mark }: { step: string | null; mark: (step: string) => void }) {
  useEffect(() => {
    if (step) mark(step);
  }, [step, mark]);
  return null;
}

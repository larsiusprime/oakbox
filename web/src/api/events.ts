import { useEffect, useState } from "react";

export type JobEvent =
  | { type: "progress"; step: string; fraction: number | null; message: string }
  | { type: "done"; message: string }
  | { type: "error"; message: string; detail?: string }
  | { type: "cancelled"; message: string };

export type JobView = {
  latest: JobEvent | null;
  fraction: number | null;
  finished: "done" | "failed" | "cancelled" | null;
};

const EMPTY: JobView = { latest: null, fraction: null, finished: null };

/** Follow a job's server-sent event stream. Reconnecting replays all events, so state is rebuilt. */
export function useJobEvents(jobId: string | null, onEnd?: () => void): JobView {
  // State is keyed by job, so switching jobs shows a fresh view without resetting state in an effect.
  const [state, setState] = useState<{ jobId: string | null; view: JobView }>({ jobId: null, view: EMPTY });

  useEffect(() => {
    if (jobId === null) return;
    const update = (fn: (prev: JobView) => JobView) =>
      setState((prev) => ({ jobId, view: fn(prev.jobId === jobId ? prev.view : EMPTY) }));
    const source = new EventSource(`/api/jobs/${jobId}/events`);
    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as JobEvent;
      update((prev) => ({
        latest: event,
        fraction: event.type === "progress" && event.fraction !== null ? event.fraction : prev.fraction,
        finished: prev.finished,
      }));
    };
    source.addEventListener("end", (msg) => {
      const { state: finished } = JSON.parse((msg as MessageEvent).data) as { state: JobView["finished"] };
      update((prev) => ({ ...prev, finished }));
      source.close();
      onEnd?.();
    });
    return () => source.close();
  }, [jobId, onEnd]);

  return state.jobId === jobId && jobId !== null ? state.view : EMPTY;
}

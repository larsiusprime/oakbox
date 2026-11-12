/** Requests OAK box failed with a bug (a 500): what the page was told, to copy and send. The server writes each one,
 * with its traceback, to its log (src/oakbox/applog.py); the page keeps the latest here for the failure bar
 * (components/FailureBar). */
import { useSyncExternalStore } from "react";

export type Failure = { ref: string; at: string; request: string; what: string; log: string };

let latest: Failure | null = null;
let count = 0;
const listeners = new Set<() => void>();

export function noteFailure(f: Failure): void {
  latest = f;
  count += 1;
  for (const l of listeners) l();
}

export function dismissFailure(): void {
  latest = null;
  for (const l of listeners) l();
}

/** The latest failure (null once dismissed), and how many there have been. */
export function useFailure(): { failure: Failure | null; count: number } {
  const failure = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => latest,
  );
  return { failure, count };
}

/** The details to paste into a message: what failed, when, and where the log is. */
export function failureText(f: Failure): string {
  return [
    `OAK box error ${f.ref} at ${f.at}`,
    `Request: ${f.request}`,
    `Error: ${f.what}`,
    `The full traceback is in ${f.log} (search for [${f.ref}]).`,
  ].join("\n");
}

export function isFailure(x: unknown): x is Failure {
  return !!x && typeof x === "object" && typeof (x as Failure).ref === "string";
}

import { CircleAlert, CircleCheck, CircleDashed, LoaderCircle, RotateCcw } from "lucide-react";
import type { StepStatus } from "../api/client";
import { t } from "../strings";

const ICON = {
  not_run: CircleDashed,
  running: LoaderCircle,
  done: CircleCheck,
  failed: CircleAlert,
  stale: RotateCcw,
} as const;

/** Status as icon + words, never colour alone (SPEC §3.4). */
export function Status({ state }: { state: StepStatus["state"] }) {
  const Icon = ICON[state];
  return (
    <span className={`status status-${state}`}>
      <Icon
        aria-hidden="true"
        size="1.1em"
        strokeWidth={2.25}
        className={state === "running" ? "spin" : undefined}
      />
      {t.state[state]}
    </span>
  );
}

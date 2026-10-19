import type { StepStatus } from "../api/client";
import { t } from "../strings";

const ICON: Record<StepStatus["state"], string> = {
  not_run: "○",
  running: "◐",
  done: "✓",
  failed: "!",
  stale: "↻",
};

/** Status as icon + words, never colour alone (SPEC §3.4). */
export function StatusChip({ state }: { state: StepStatus["state"] }) {
  return (
    <span className={`chip chip-${state}`}>
      <span aria-hidden="true">{ICON[state]}</span> {t.state[state]}
    </span>
  );
}

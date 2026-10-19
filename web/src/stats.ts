import type { Stat } from "./api/client";

export type Verdict = "meets" | "outside" | "unknown";

/** IAAO default targets (SPEC §4.2). Replaced by editable standards profiles in M1d. */
const TARGETS = {
  medianRatio: [0.9, 1.1],
  cod: [0, 15],
  prd: [0.98, 1.03],
  prb: [-0.05, 0.05],
} as const;

export function verdict(stat: Stat | null | undefined, target: keyof typeof TARGETS): Verdict {
  const value = stat?.value;
  if (value === null || value === undefined) return "unknown";
  const [lo, hi] = TARGETS[target];
  return value >= lo && value <= hi ? "meets" : "outside";
}

export function fmt(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

export function fmtRange(stat: Stat | null | undefined, digits = 2): string {
  if (!stat || stat.low === null || stat.low === undefined || stat.high === null || stat.high === undefined) {
    return "";
  }
  return `${fmt(stat.low, digits)} to ${fmt(stat.high, digits)}`;
}

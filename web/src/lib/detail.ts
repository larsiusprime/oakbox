/** Map detail (SPEC §5, §3.15): how far out parcel shapes are still drawn; zoomed out past that, squares. Zoomed in
 * enough, every level draws the parcels. One setting for every parcel map: Settings › Performance, or the Parcels
 * dropdown on a map. */
import { useQueryClient } from "@tanstack/react-query";
import type { MachineView } from "../api/client";
import { useMachine, useResolved, useSetPerformance } from "./machine";

export type Detail = "max" | "high" | "medium" | "low" | "verylow";

/** The levels, most parcels first. */
export const DETAILS: readonly Detail[] = ["max", "high", "medium", "low", "verylow"];

/** A quarter-acre lot's side, metres. */
export const LOT_M = Math.sqrt(4046.8564224 / 4);

/** How many pixels across a quarter-acre lot must be for parcel shapes; smaller, squares. Max: any size. High: until
 * it's about a pixel, barely seen (1 px). Medium: while it's still a bit bigger than the hand pointer's fingertip (8 px), so
 * still easy to click. Low and Very low: half as far out each time. */
export const LOT_PX: Record<Detail, number> = { max: 0, high: 1, medium: 8, low: 16, verylow: 32 };

/** Parcel shapes at this zoom (metres a pixel covers)? */
export function shapesAt(detail: Detail, mpp: number): boolean {
  return LOT_M / mpp >= LOT_PX[detail];
}

/** Square sizes in metres, coarsest first: the finest at least CELL_PX pixels across is drawn. */
export const LEVELS = [8000, 4000, 2000, 1000, 500, 250, 125, 60, 30];
export const CELL_PX = 16;

/** The square size for a zoom, as metres a pixel covers. */
export function levelFor(mpp: number): number {
  return [...LEVELS].reverse().find((s) => s / mpp >= CELL_PX) ?? LEVELS[0] ?? 8000;
}

/** Parcels shown as shapes from a Parcels choice: more than this, and the switch says it may be slow (once). */
export const MANY_SHAPES = 50_000;

/** The detail in force, and a setter that shows at once on every map, then saves (AGENTS.md). */
export function useDetail(): [Detail, (d: Detail) => void] {
  const detail = useResolved().map_detail;
  const machine = useMachine().data;
  const save = useSetPerformance();
  const queryClient = useQueryClient();
  const set = (d: Detail) => {
    if (!machine) return;
    queryClient.setQueryData<MachineView>(["machine"], {
      ...machine,
      performance: { ...machine.performance, map_detail: d },
      resolved: { ...machine.resolved, map_detail: d },
    });
    save.mutate({ ...machine.performance, map_detail: d });
  };
  return [detail, set];
}

/** How strongly to draw parcels' outlines (0–1) when a typical parcel (its side in metres) is this many metres a pixel:
 * none while parcels are a few pixels across, so zoomed out each is its colour and not a tangle of edges; full once
 * they're EDGE_FULL_PX across. */
export const EDGE_NONE_PX = 5;
export const EDGE_FULL_PX = 20;
export function edgeShare(metres: number | null | undefined, mpp: number | null | undefined): number {
  if (!metres || !mpp) return 1;
  const px = metres / mpp;
  return Math.min(1, Math.max(0, (px - EDGE_NONE_PX) / (EDGE_FULL_PX - EDGE_NONE_PX)));
}

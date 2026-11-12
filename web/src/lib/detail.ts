/** Map detail (SPEC §5, §3.15): squares zoomed out and parcel shapes zoomed in (Auto), squares always, or parcel
 * shapes always. One setting for every parcel map: Settings › Performance, or the Detail switch on a map. */
import { useQueryClient } from "@tanstack/react-query";
import type { MachineView } from "../api/client";
import { useMachine, useResolved, useSetPerformance } from "./machine";

export type Detail = "auto" | "squares" | "parcels";

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

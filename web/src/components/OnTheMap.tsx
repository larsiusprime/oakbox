/** A take-over step that draws its own map (SPEC §3.15): the map, with its own controls, shown in the map window
 * (the step keeps its state; a click there is the step's), the step's instruction card on the step. Popped out,
 * the map is drawn on the step itself; closed, only the card, which offers to show it. */
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { useDock } from "../lib/mapdock";
import { useSlot, useTakeOver } from "../lib/mapstep";
import { MapInstruction } from "./MapInstruction";

export function OnTheMap({
  projectId,
  step,
  title,
  sub,
  children,
}: {
  projectId: string;
  /** The step's name, on the map's banner and Follow. */
  step: string;
  /** What to do on the map: one imperative sentence. */
  title: string;
  sub?: string;
  children: ReactNode;
}) {
  useTakeOver(projectId, "portal", step, title);
  const dock = useDock();
  const slot = useSlot();
  return (
    <>
      <MapInstruction title={title} {...(sub ? { sub } : {})} />
      {dock.out ? children : dock.open && dock.follow && slot ? createPortal(children, slot) : null}
    </>
  );
}

/** Which of a project's tabs wait on an earlier step: the one place the rules are written. */
import type { TabId } from "./route";

/** What the tabs wait on: each step accepted (Looks right, on an up-to-date run), and existing values to check. */
export type Gates = {
  /** Inputs (Bring in data). */
  accepted: boolean;
  /** Model groups. */
  grouped: boolean;
  /** Sales (Check sales). */
  checked: boolean;
  /** Existing values to check (the roll, a vendor's AVM: Data › Existing values). */
  hasValues: boolean;
  /** Variables › What changed (Prepare the fields). */
  prepared: boolean;
  /** Models › Model values (Finalize). */
  finalized: boolean;
};

/** The tabs that wait: Model groups on Inputs, Sales on Model groups, Evaluate, Variables and Models on Sales,
 * Evaluate on existing values too, Models on Variables, Report on Models. */
export function lockedTabs(g: Gates): Set<TabId> {
  const out = new Set<TabId>();
  if (!g.accepted) out.add("groups");
  if (!g.grouped) out.add("sales");
  if (!g.checked) for (const t of ["check", "variables", "values"] as const) out.add(t);
  if (!g.hasValues) out.add("check");
  if (!g.prepared) out.add("values");
  if (!g.finalized) out.add("report");
  return out;
}

/** Check sales' calls on single sales, from whichever screen makes them. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { type StepId, stepChanged, stepKey } from "./steps";

export type SaleMark = { key: string; action: "keep" | "exclude" | null; note: string };

/** Keep a sale set aside (with a note), exclude a sale, or undo either: it applies on Check sales' next run, so
 * Check sales and every step after it are asked again, but those in `leave` (Check my values, whose results stay on
 * screen while several of its sales are excluded in turn). */
export function useMarkSale(projectId: string, leave: readonly StepId[] = []) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (m: SaleMark) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/clean/marks/{key_sale}", {
          params: { path: { project_id: projectId, key_sale: m.key } },
          body: { action: m.action, note: m.note },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(stepKey("clean", projectId), data);
      stepChanged(queryClient, projectId, "clean", false, leave);
    },
  });
}

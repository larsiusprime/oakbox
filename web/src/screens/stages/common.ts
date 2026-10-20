import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Project, type ProjectDetail, unwrap } from "../../api/client";

export type StageProps = { detail: ProjectDetail };

/** Wraps a decision-saving call: the server answers with the updated project. */
export function useSave<A>(projectId: string, fn: (arg: A) => Promise<{ data?: Project; error?: unknown }>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (arg: A) => unwrap(await fn(arg)),
    onSuccess: (project) => {
      queryClient.setQueryData<ProjectDetail>(["project", projectId], (old) =>
        old ? { ...old, project } : old,
      );
      void queryClient.invalidateQueries({ queryKey: ["check", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["hood", projectId] });
    },
  });
}

export { api };

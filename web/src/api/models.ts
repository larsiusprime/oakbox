/** The variable lists, each model group's models, and a location stack's preview (SPEC F9). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ModelEntry, type ModelSetup, unwrap, type VarList } from "./client";
import { setupKey, stepChanged } from "./steps";

export const listsKey = (projectId: string) => ["varlists", projectId] as const;

export function useVarLists(projectId: string, enabled = true) {
  return useQuery({
    queryKey: listsKey(projectId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/varlists", { params: { path: { project_id: projectId } } }),
      ),
    enabled,
  });
}

/** Every list at once (null: back to the proposed ones): the models' setup and the try are asked again. */
export function useSetVarLists(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lists: VarList[] | null) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/varlists", {
          params: { path: { project_id: projectId } },
          body: { lists },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(listsKey(projectId), data);
      void queryClient.invalidateQueries({ queryKey: setupKey("model", projectId) });
      stepChanged(queryClient, projectId, "model");
    },
  });
}

/** A model group's models (null: back to the default ones). */
export function useSetGroupModels(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ group, models }: { group: string; models: ModelEntry[] | null }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/model/groups/{group}", {
          params: { path: { project_id: projectId, group } },
          body: { models },
        }),
      ) as ModelSetup,
    onSuccess: (data) => {
      queryClient.setQueryData(setupKey("model", projectId), data);
      stepChanged(queryClient, projectId, "model");
    },
  });
}

/** A location stack in a model group, broadest first: each level's areas and sales, and whether it nests. */
export function useStack(projectId: string, group: string, broadestFirst: string[]) {
  return useQuery({
    queryKey: ["model-stack", projectId, group, ...broadestFirst],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/model/stack/{group}", {
          params: { path: { project_id: projectId, group }, query: { fields: broadestFirst } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

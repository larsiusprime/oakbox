/** Model engines OAK box downloads when first asked for: XGBoost and CatBoost (oakbox/engines.py). */
import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type EngineState, unwrap } from "./client";

export const enginesKey = ["engines"] as const;
const fetchEngines = async () => unwrap(await api.GET("/api/engines"));

/** Each optional engine's state; asked again twice a second while one downloads. */
export function useEngines() {
  return useQuery({
    queryKey: enginesKey,
    queryFn: fetchEngines,
    refetchInterval: (q) => (q.state.data?.some((e) => e.install?.status === "running") ? 500 : false),
  });
}

type Key = "xgboost" | "catboost";
const path = (key: string) => ({ params: { path: { key: key as Key } } });

/** Install (start the download), stop it, say its outcome was seen, or remove the engine. */
export function useEngineAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ key, action }: { key: string; action: "install" | "stop" | "seen" | "remove" }) =>
      unwrap(
        action === "install"
          ? await api.POST("/api/engines/{key}/install", path(key))
          : action === "stop"
            ? await api.POST("/api/engines/{key}/stop", path(key))
            : action === "seen"
              ? await api.POST("/api/engines/{key}/seen", path(key))
              : await api.DELETE("/api/engines/{key}", path(key)),
      ),
    onSuccess: (data: EngineState[]) => {
      queryClient.setQueryData(enginesKey, data);
      // A run's "isn't installed" notice changes with it.
      void queryClient.invalidateQueries({
        predicate: (q) => q.queryKey[0] === "model" || q.queryKey[0] === "final",
      });
    },
  });
}

export const mb = (bytes: number | null | undefined) => Math.round((bytes ?? 0) / 1e6);

/** Wait for an engine's download to end (it's installed, or it failed or was stopped): its state then. */
export async function downloadEnded(queryClient: QueryClient, key: string): Promise<EngineState | undefined> {
  for (;;) {
    const list = await queryClient.fetchQuery({ queryKey: enginesKey, queryFn: fetchEngines, staleTime: 0 });
    const e = list.find((x) => x.key === key);
    if (!e || e.installed || e.install?.status !== "running") return e;
    await new Promise((r) => setTimeout(r, 500));
  }
}

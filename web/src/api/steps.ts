import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, unwrap } from "./client";
import type { components } from "./schema";

type S = components["schemas"];

/** Each step that runs the engine, and what its state route answers (app.py's _step_routes: the same routes for
 * every step). */
export type StepViews = {
  "bring-in": S["View"];
  assemble: S["AssembleView"];
  clean: S["CleanView"];
  prepare: S["PrepareView"];
  ratio: S["RatioView"];
  vartest: S["VarTestView"];
  model: S["ModelView"];
};
export type StepId = keyof StepViews;
export type StepAct = "run" | "stop" | "accept";

/** The steps that start from each step's output. When a step runs again, is accepted, or one of its calls
 * changes, the steps after it may become out of date or blocked, so they're asked again. */
const NEXT: Record<StepId, StepId[]> = {
  "bring-in": ["assemble"],
  assemble: ["clean"],
  clean: ["prepare", "ratio"],
  prepare: ["vartest", "model"],
  ratio: [],
  vartest: [],
  model: [],
};

/** Every step after this one, however far down. */
export function stepsAfter(id: StepId): StepId[] {
  const out: StepId[] = [];
  const visit = (x: StepId) => {
    for (const n of NEXT[x]) {
      if (!out.includes(n)) {
        out.push(n);
        visit(n);
      }
    }
  };
  visit(id);
  return out;
}

export const stepKey = (id: StepId, projectId: string) => [id, projectId] as const;
export const setupKey = (id: SetupId, projectId: string) => [`${id}-setup`, projectId] as const;

/** What else a step's screen shows from its run or its calls: asked again with it. */
const ALSO: Partial<Record<StepId, string[]>> = {
  clean: ["clean-time", "clean-review"],
  prepare: ["varlists"],
  vartest: ["varlists"],
  model: ["vartest", "varlists", "model-small"],
};

/** Something about a step changed (a call, a mark, a run): ask it again (unless `self` is false: the caller has
 * its new state), what else its screen shows, and every step after it. */
export function stepChanged(queryClient: QueryClient, projectId: string, id: StepId, self = true): void {
  const keys = [...(self ? [id] : []), ...(ALSO[id] ?? []), ...stepsAfter(id)];
  for (const k of keys) void queryClient.invalidateQueries({ queryKey: [k, projectId] });
}

/** While a step runs it's asked this often (ms); otherwise only when something changes. */
export const POLL = 700;

/** A step's state: ready, running (asked often), or its last run's receipt, out of date or not. */
export function useStep<K extends StepId>(id: K, projectId: string) {
  return useQuery({
    queryKey: stepKey(id, projectId),
    queryFn: async () => {
      // The routes are typed one path at a time; every step's has the same shape, so one stands for all.
      const path = `/api/projects/{project_id}/${id}` as "/api/projects/{project_id}/clean";
      const view = unwrap(await api.GET(path, { params: { path: { project_id: projectId } } }));
      return view as unknown as StepViews[K];
    },
    refetchInterval: (q) => (q.state.data?.status === "running" ? POLL : false),
  });
}

/** Run, stop, or Looks right: the answer is the step's new state, and the steps after it are asked again. */
export function useStepAct<K extends StepId>(id: K, projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (what: StepAct) => {
      const path = `/api/projects/{project_id}/${id}/${what}` as "/api/projects/{project_id}/clean/run";
      const view = unwrap(await api.POST(path, { params: { path: { project_id: projectId } } }));
      return view as unknown as StepViews[K];
    },
    onSuccess: (data) => {
      queryClient.setQueryData(stepKey(id, projectId), data);
      stepChanged(queryClient, projectId, id, false);
      if (id in SETUP) void queryClient.invalidateQueries({ queryKey: setupKey(id as SetupId, projectId) });
    },
  });
}

/** The steps whose calls are made before they run, and what their setup routes answer and take. */
type Setups = {
  clean: [S["CleanSetup"], S["CleanPatch"]];
  ratio: [S["RatioSetup"], S["RatioPatch"]];
  model: [S["ModelSetup"], S["ModelPatch"]];
};
export type SetupId = keyof Setups;
const SETUP: Record<SetupId, true> = { clean: true, ratio: true, model: true };

/** A step's calls before it runs, and changing one: the step and the steps after it are asked again. */
export function useStepSetup<K extends SetupId>(id: K, projectId: string, enabled = true) {
  const queryClient = useQueryClient();
  const path = `/api/projects/{project_id}/${id}/setup` as "/api/projects/{project_id}/clean/setup";
  const setup = useQuery({
    queryKey: setupKey(id, projectId),
    queryFn: async () => {
      const view = unwrap(await api.GET(path, { params: { path: { project_id: projectId } } }));
      return view as unknown as Setups[K][0];
    },
    enabled,
  });
  const change = useMutation({
    mutationFn: async (body: Setups[K][1]) => {
      const params = { params: { path: { project_id: projectId } }, body: body as S["CleanPatch"] };
      return unwrap(await api.PATCH(path, params)) as unknown as Setups[K][0];
    },
    onSuccess: (data) => {
      queryClient.setQueryData(setupKey(id, projectId), data);
      stepChanged(queryClient, projectId, id);
    },
  });
  return { setup, change };
}

/** Which task a step's tab shows: the one chosen, else the tab's own pick; and once a run started here is done,
 * its results. */
export function useStepNav<T extends string>() {
  const [at, setAt] = useState<{ step: T | null; after: boolean }>({ step: null, after: false });
  return {
    /** The task chosen (null: the tab's own pick), and whether a run was started from it. */
    at,
    current: (status: string, fallback: T, done: T): T =>
      at.after && status === "done" ? done : (at.step ?? fallback),
    go: (step: string) => setAt({ step: step as T, after: false }),
    /** A run was started from `step`: stay there while it runs, then show its results. */
    ran: (step: T) => setAt({ step, after: true }),
  };
}

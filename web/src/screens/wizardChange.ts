/** The Fields wizard's changes: every change a step can make, and the hook that sends one. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type CleanStep,
  type NumberFormat,
  type Rule,
  type Scale,
  unwrap,
  type Wizard,
  type WizardField,
} from "../api/client";
import type { CustomChange } from "./CustomFields";
import type { PermitsChange } from "./Permits";
import type { LayerChange } from "./Shapefiles";
import type { UnitsChange } from "./Units";
import type { ValuesChange } from "./ValueSets";

export type AreaUnit = NonNullable<WizardField["area_unit"]>;
export type CombineHow = "max" | "min" | "sum" | "mean" | "count";

type Holds = "parcels" | "sales" | "sale_rows" | "parcel_rows" | "unused" | "permits";

// ---------- Changes ----------

export type Change =
  | { kind: "visit"; step: string }
  | { kind: "confirm"; step: string }
  | { kind: "skip"; step: string }
  | {
      kind: "file";
      name: string;
      holds?: Holds;
      universe?: boolean;
      match?: "key" | "key2" | "key3" | "key_sale";
      id_column?: string;
      dupes?: "first" | "all";
      dupes_sort?: string;
      dupes_desc?: boolean;
      /** Keeping the first row of each ID: the file's columns to sort by, in order. */
      dupes_by?: { column: string; desc: boolean; numeric: boolean }[];
      blank_ok?: boolean;
      extra_field?: "key2" | "key3";
      extra_column?: string | null;
      /** Added on More files: one of its files, not said yet what it holds. */
      added?: boolean;
    }
  | { kind: "saleId"; column: string | null; make: boolean }
  | {
      kind: "combine";
      name: string;
      about: string;
      groups: { name: string; values: string[]; makes: ("has" | "count" | "total")[] }[];
      measures: Record<string, CombineHow>;
      main: string[] | null;
      measure: string | null;
      rows: boolean;
    }
  | { kind: "reconcile"; name: string; file_steps: CleanStep[]; base_steps: CleanStep[] }
  | {
      kind: "field";
      key: string;
      file?: string | null;
      column?: string | null;
      assume?: boolean;
      date_format?: string;
      area_unit?: AreaUnit;
      number_format?: NumberFormat;
      scale?: Scale;
      absent?: boolean;
    }
  | { kind: "rule"; key: string; rule: Rule }
  | { kind: "rowField"; name: string; key: string; column: string | null }
  | { kind: "location"; name: string; file: string | null; column: string | null }
  | CustomChange
  | UnitsChange
  | ValuesChange
  | LayerChange
  | PermitsChange;

/** The file choice being read for its step, if one is: what Stop stops. */
let reading: { projectId: string; name: string; request: string; abort: AbortController } | null = null;

/** Stop on a file being read for its step: stop waiting at once (the wizard as it is stands), and have the server
 * undo the choice when its reading ends. */
export function stopFileChoice() {
  const r = reading;
  if (!r) return;
  reading = null;
  void api.POST("/api/projects/{project_id}/wizard/files/{name}/stop", {
    params: { path: { project_id: r.projectId, name: r.name }, query: { request: r.request } },
  });
  r.abort.abort();
}

/** `quiet`: left out of the corner's Activity pill. A step's visit is: moving between steps records where you are
 * (and fills in a guess or two, shown on the step itself), nothing to say "Saving" about. */
export function useChange(projectId: string, { quiet = false }: { quiet?: boolean } = {}) {
  const queryClient = useQueryClient();
  return useMutation({
    ...(quiet ? { meta: { quiet: true } } : {}),
    mutationFn: async (c: Change): Promise<Wizard> => {
      const project_id = projectId;
      if (c.kind === "visit" || c.kind === "skip" || c.kind === "confirm") {
        const path = `/api/projects/{project_id}/wizard/steps/{step}/${c.kind}` as const;
        return unwrap(await api.POST(path, { params: { path: { project_id, step: c.step } } }));
      }
      if (c.kind === "file") {
        const { kind: _, name, ...body } = c;
        // Reading a big file for its step takes a while: Stop (stopFileChoice) gives up waiting, and the server
        // undoes the choice once its reading ends. The wizard as it is then stands for the answer.
        const request = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const abort = new AbortController();
        reading = { projectId: project_id, name, request, abort };
        try {
          const r = await api.PUT("/api/projects/{project_id}/wizard/files/{name}", {
            params: { path: { project_id, name }, query: { request } },
            signal: abort.signal,
            body: {
              holds: null,
              universe: false,
              match: null,
              id_column: null,
              extra_field: null,
              extra_column: null,
              dupes: null,
              dupes_sort: null,
              dupes_desc: false,
              dupes_by: null,
              blank_ok: null,
              added: false,
              ...body,
            },
          });
          return unwrap(r);
        } catch (e) {
          if (abort.signal.aborted)
            return unwrap(
              await api.GET("/api/projects/{project_id}/wizard", { params: { path: { project_id } } }),
            );
          throw e;
        } finally {
          if (reading?.request === request) reading = null;
        }
      }
      if (c.kind === "rowField") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/rows/{key}", {
            params: { path: { project_id, name: c.name, key: c.key } },
            body: { column: c.column, date_format: null },
          }),
        );
      }
      if (c.kind === "reconcile") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/reconcile", {
            params: { path: { project_id, name: c.name } },
            body: { file_steps: c.file_steps, base_steps: c.base_steps },
          }),
        );
      }
      if (c.kind === "combine") {
        const { kind: _, name, ...body } = c;
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/combine", {
            params: { path: { project_id, name } },
            body,
          }),
        );
      }
      if (c.kind === "saleId") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/sale-id", {
            params: { path: { project_id } },
            body: { column: c.column, make: c.make },
          }),
        );
      }
      if (c.kind === "layer") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/layers/{name}", {
            params: { path: { project_id, name: c.name } },
            ...(c.overlay ? { body: c.overlay } : {}),
          }),
        );
      }
      if (c.kind === "location") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/locations/{name}", {
            params: { path: { project_id, name: c.name } },
            body: { file: c.file, column: c.column },
          }),
        );
      }
      if (c.kind === "permits") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/permits", {
            params: { path: { project_id, name: c.name } },
            body: { permits: c.permits, guess: c.guess ?? false },
          }),
        );
      }
      if (c.kind === "addSet") {
        return unwrap(
          await api.POST("/api/projects/{project_id}/wizard/value-sets", {
            params: { path: { project_id } },
            body: { name: c.name },
          }),
        );
      }
      if (c.kind === "setChange") {
        return unwrap(
          await api.PATCH("/api/projects/{project_id}/wizard/value-sets/{set_id}", {
            params: { path: { project_id, set_id: c.id } },
            body: {
              ...(c.name !== undefined ? { name: c.name } : {}),
              ...(c.roll !== undefined ? { roll: c.roll } : {}),
            },
          }),
        );
      }
      if (c.kind === "removeSet") {
        return unwrap(
          await api.DELETE("/api/projects/{project_id}/wizard/value-sets/{set_id}", {
            params: { path: { project_id, set_id: c.id } },
          }),
        );
      }
      if (c.kind === "condos") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/condos", {
            params: { path: { project_id } },
            body: { has: c.has },
          }),
        );
      }
      if (c.kind === "units") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/units", {
            params: { path: { project_id, name: c.name } },
            body: { units: c.units, guess: c.guess ?? false },
          }),
        );
      }
      if (c.kind === "unitFields") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/units/fields", {
            params: { path: { project_id, name: c.name } },
            body: { fields: c.fields },
          }),
        );
      }
      if (c.kind === "unitField") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/units/fields/{field}", {
            params: { path: { project_id, name: c.name, field: c.field } },
            body: { column: c.column },
          }),
        );
      }
      if (c.kind === "custom") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/custom/{name}", {
            params: { path: { project_id, name: c.name } },
            body: { file: c.file, column: c.column, group: c.group, type: c.type },
          }),
        );
      }
      if (c.kind === "rule") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/fields/{key}/rule", {
            params: { path: { project_id, key: c.key } },
            body: c.rule,
          }),
        );
      }
      return unwrap(
        await api.PUT("/api/projects/{project_id}/wizard/fields/{key}", {
          params: { path: { project_id, key: c.key } },
          body: {
            file: c.file ?? null,
            column: c.column ?? null,
            assume: c.assume ?? false,
            date_format: c.date_format ?? null,
            area_unit: c.area_unit ?? null,
            number_format: c.number_format ?? null,
            scale: c.scale ?? null,
            absent: c.absent ?? false,
          },
        }),
      );
    },
    onSuccess: async (data, c) => {
      // Each answer is the whole wizard as it stood when it was worked out. Two at once (a step's visit, and a
      // choice made on it straight away) can answer out of order, and in any order: the server works on them side
      // by side. The project's revision (its saves so far) says which is newer; an older one would put back the
      // choice's "before" (the rows under a choice missing until you came back).
      const before = queryClient.getQueryData<Wizard>(["wizard", projectId]);
      if (before && data.revision < before.revision) return;
      queryClient.setQueryData(["wizard", projectId], data);
      // Showing or moving on from a step that changed nothing but the steps (where you've been, which are done):
      // nothing else to ask again.
      if ((c.kind === "visit" || c.kind === "confirm") && before && beyondSteps(before) === beyondSteps(data))
        return;
      // Sales record fields compares the sales file with the parcel fields: either changing asks it again.
      void queryClient.invalidateQueries({ queryKey: ["as-sold", projectId] });
      // Renaming the base to geo_parcels, and the field counts, show on the other tabs.
      if (c.kind !== "visit" || c.step === "files") {
        await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      }
    },
  });
}

/** The wizard without its steps (their statuses, which a visit changes): what a visit changing something shows in. */
const beyondSteps = (w: Wizard) => JSON.stringify({ ...w, steps: undefined });

export type Mutate = (
  c: Change,
  options?: { onSuccess?: () => void; onError?: () => void; onSettled?: () => void },
) => void;
export type MutateAsync = (c: Change) => Promise<Wizard>;

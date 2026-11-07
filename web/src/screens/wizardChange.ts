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
      blank_ok?: boolean;
      extra_field?: "key2" | "key3";
      extra_column?: string | null;
      /** Added on More files: one of its files, not said yet what it holds. */
      added?: boolean;
    }
  | { kind: "saleId"; column: string | null; make: boolean }
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

export function useChange(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (c: Change): Promise<Wizard> => {
      const project_id = projectId;
      if (c.kind === "visit" || c.kind === "skip" || c.kind === "confirm") {
        const path = `/api/projects/{project_id}/wizard/steps/{step}/${c.kind}` as const;
        return unwrap(await api.POST(path, { params: { path: { project_id, step: c.step } } }));
      }
      if (c.kind === "file") {
        const { kind: _, name, ...body } = c;
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}", {
            params: { path: { project_id, name } },
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
              blank_ok: null,
              added: false,
              ...body,
            },
          }),
        );
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
      queryClient.setQueryData(["wizard", projectId], data);
      // Sales as sold compares the sales file with the parcel fields: either changing asks it again.
      void queryClient.invalidateQueries({ queryKey: ["as-sold", projectId] });
      // Renaming the base to geo_parcels, and the field counts, show on the other tabs.
      if (c.kind !== "visit" || c.step === "files") {
        await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      }
    },
  });
}

export type Mutate = (c: Change, options?: { onSuccess?: () => void }) => void;
export type MutateAsync = (c: Change) => Promise<Wizard>;

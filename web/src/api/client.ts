import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type Project = components["schemas"]["Project"];
export type ProjectDetail = components["schemas"]["ProjectDetail"];
export type InputFile = components["schemas"]["InputFile"];
export type NewProject = components["schemas"]["NewProject"];
export type Regions = components["schemas"]["Regions"];
export type AppSettingsView = components["schemas"]["AppSettingsView"];
export type FileCheck = components["schemas"]["FileCheck"];

/** Unwrap an openapi-fetch result, turning API errors into thrown Errors with the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new Error(typeof detail === "string" ? detail : "Something went wrong talking to OAK box.");
  }
  return result.data;
}
export type FileColumns = components["schemas"]["FileColumns"];
export type FileColumn = components["schemas"]["Column"];
export type DictionaryField = components["schemas"]["DictionaryField"];

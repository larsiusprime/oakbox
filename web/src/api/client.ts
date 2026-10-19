import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type Project = components["schemas"]["Project"];
export type ProjectDetail = components["schemas"]["ProjectDetail"];
export type StepId =
  paths["/api/projects/{project_id}/steps/{step}/run"]["post"]["parameters"]["path"]["step"];
export type StepStatus = components["schemas"]["StepStatus"];
export type JobInfo = components["schemas"]["JobInfo"];
export type SampleInfo = components["schemas"]["SampleInfo"];
export type ValueStudy = components["schemas"]["ValueStudy"];
export type GroupStudy = components["schemas"]["GroupStudy"];
export type Stat = components["schemas"]["Stat"];

export const STEP_ORDER: readonly StepId[] = ["bring_in_data", "model_groups", "check_sales", "check_values"];

/** Unwrap an openapi-fetch result, turning API errors into thrown Errors with the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new Error(typeof detail === "string" ? detail : "Something went wrong talking to Oakbox.");
  }
  return result.data;
}

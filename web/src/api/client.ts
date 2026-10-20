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
export type StageId =
  paths["/api/projects/{project_id}/stages/{stage}/confirm"]["post"]["parameters"]["path"]["stage"];
export type StageStatus = components["schemas"]["StageStatus"];
export type Setup = components["schemas"]["Setup"];
export type Basics = components["schemas"]["Basics-Output"];
export type SourceFile = components["schemas"]["SourceFile"];
export type FileUse = SourceFile["uses"][number];
export type Stitch = components["schemas"]["Stitch-Output"];
export type IdFix = components["schemas"]["IdFix-Output"];
export type Collapse = components["schemas"]["Collapse-Output"];
export type Inspection = components["schemas"]["Inspection"];
export type StitchReport = components["schemas"]["StitchReport"];
export type FileReport = components["schemas"]["FileReport"];
export type StageCheck = components["schemas"]["StageCheck"];
export type HoodItem = components["schemas"]["HoodItem"];
export type BringInReceipt = components["schemas"]["BringInReceipt"];

export const STEP_ORDER: readonly StepId[] = ["bring_in_data", "model_groups", "check_sales", "check_values"];
export const STAGE_ORDER: readonly StageId[] = ["basics", "files", "stitch", "columns", "sales_basics"];

/** Unwrap an openapi-fetch result, turning API errors into thrown Errors with the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new Error(typeof detail === "string" ? detail : "Something went wrong talking to OAK box.");
  }
  return result.data;
}

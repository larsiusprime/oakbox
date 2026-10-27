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
export type Wizard = components["schemas"]["Wizard"];
export type WizardField = components["schemas"]["WizardField"];
export type WizardFile = components["schemas"]["WizardFile"];
export type WizardStep = components["schemas"]["StepView"];
export type WizardCheck = components["schemas"]["Check"];
export type WizardIssue = components["schemas"]["Issue"];
export type Reconcile = components["schemas"]["Reconcile"];
export type CleanStep = components["schemas"]["CleanStep-Output"];
export type ReconcileSample = components["schemas"]["Sample"];
export type RulePreview = components["schemas"]["RulePreview"];
export type DatePreview = components["schemas"]["DatePreview"];
export type Rule = components["schemas"]["Rule-Output"];
export type Condition = components["schemas"]["Condition-Output"];
export type Overlay = components["schemas"]["Overlay-Output"];
export type LayerView = components["schemas"]["LayerView"];
export type NumberPreview = components["schemas"]["NumberPreview"];
export type NumberFormat = components["schemas"]["NumberFormat-Output"];

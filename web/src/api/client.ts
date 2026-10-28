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
export type EnrichView = components["schemas"]["EnrichView"];
export type Enrichments = components["schemas"]["Enrichments-Output"];
export type EnrichResult = components["schemas"]["EnrichResult"];
export type EnrichAddField = components["schemas"]["AddField"];
export type Permits = components["schemas"]["Permits-Output"];
export type PermitsView = components["schemas"]["PermitsView"];
export type NumberPreview = components["schemas"]["NumberPreview"];
export type NumberFormat = components["schemas"]["NumberFormat-Output"];
export type Scale = components["schemas"]["Scale-Output"];
export type Candidate = components["schemas"]["Candidate"];
export type ScalePreview = components["schemas"]["ScalePreview"];
export type TiersPreview = components["schemas"]["TiersPreview"];
export type Source = components["schemas"]["Source"];
export type BringIn = components["schemas"]["View"];
export type Receipt = components["schemas"]["Receipt"];
export type Funnel = components["schemas"]["Funnel"];
export type ReceiptField = components["schemas"]["FieldRow"];
export type Rows = components["schemas"]["Rows"];
export type ModelGroup = components["schemas"]["ModelGroup-Output"];
export type GroupsView = components["schemas"]["GroupsView"];
export type GroupsPreview = components["schemas"]["GroupsPreview"];
export type GroupStats = components["schemas"]["GroupStats"];
export type GroupField = components["schemas"]["GroupField"];
export type GroupValues = components["schemas"]["GroupValues"];
export type ParcelInspect = components["schemas"]["ParcelInspect"];
export type AssembleView = components["schemas"]["AssembleView"];
export type AssembleReceipt = components["schemas"]["AssembleReceipt"];
export type Units = components["schemas"]["Units-Output"];
export type UnitsView = components["schemas"]["UnitsView"];

import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const api = createClient<paths>({ baseUrl: "" });

export type Project = components["schemas"]["Project"];
export type NamesView = components["schemas"]["NamesView"];
export type RatioView = components["schemas"]["RatioView"];
export type RatioSetup = components["schemas"]["RatioSetup"];
export type RatioPatch = components["schemas"]["RatioPatch"];
export type RatioStudy = components["schemas"]["Study"];
export type FieldResult = components["schemas"]["FieldResult"];
export type ModelView = components["schemas"]["ModelView"];
export type ModelSetup = components["schemas"]["ModelSetup"];
export type EngineState = components["schemas"]["EngineState"];
export type ModelPatch = components["schemas"]["ModelPatch"];
export type ModelEntry = components["schemas"]["ModelEntry-Input"];
export type EntryView = components["schemas"]["EntryView"];
export type GroupModels = components["schemas"]["GroupModels"];
export type VarList = components["schemas"]["VarList-Input"];
export type VarListsView = components["schemas"]["VarListsView"];
export type ListView = components["schemas"]["ListView"];
export type StackPreview = components["schemas"]["StackPreview"];
export type SmallGroupsView = components["schemas"]["SmallGroupsView"];
export type ModelRow = components["schemas"]["ModelRow"];
export type SalesSet = components["schemas"]["SalesSet"];
export type VarTestView = components["schemas"]["VarTestView"];
export type TestRow = components["schemas"]["TestRow"];
export type CorrDetail = components["schemas"]["CorrDetail"];
export type ProjectDetail = components["schemas"]["ProjectDetail"];
export type NewProject = components["schemas"]["NewProject"];
export type Regions = components["schemas"]["Regions"];
export type FileCheck = components["schemas"]["FileCheck"];

/** Unwrap an openapi-fetch result, turning API errors into thrown Errors with the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new Error(typeof detail === "string" ? detail : "Something went wrong talking to OAK box.");
  }
  return result.data;
}
export type Wizard = components["schemas"]["Wizard"];
export type WizardField = components["schemas"]["WizardField"];
export type WizardFile = components["schemas"]["WizardFile"];
export type WizardStep = components["schemas"]["StepView"];
export type WizardCheck = components["schemas"]["Check"];
export type WizardIssue = components["schemas"]["Issue"];
export type Reconcile = components["schemas"]["Reconcile"];
export type CleanStep = components["schemas"]["CleanStep-Output"];
export type ReconcileSample = components["schemas"]["Sample"];
export type Rule = components["schemas"]["Rule-Output"];
export type Condition = components["schemas"]["Condition-Output"];
export type Overlay = components["schemas"]["Overlay-Output"];
export type LayerView = components["schemas"]["LayerView"];
export type EnrichView = components["schemas"]["EnrichView"];
export type Enrichments = components["schemas"]["Enrichments-Output"];
export type EnrichResult = components["schemas"]["EnrichResult"];
export type EnrichAddField = components["schemas"]["AddField"];
export type Permits = components["schemas"]["Permits-Output"];
export type NumberFormat = components["schemas"]["NumberFormat-Output"];
export type Scale = components["schemas"]["Scale-Output"];
export type Source = components["schemas"]["Source"];
export type BringIn = components["schemas"]["View"];
export type Job = components["schemas"]["Job"];
export type Histogram = components["schemas"]["Histogram"];
export type Receipt = components["schemas"]["Receipt"];
export type Funnel = components["schemas"]["Funnel"];
export type ReceiptField = components["schemas"]["FieldRow"];
export type Rows = components["schemas"]["Rows"];
export type ModelGroup = components["schemas"]["ModelGroup-Output"];
export type GroupsView = components["schemas"]["GroupsView"];
export type GroupsPreview = components["schemas"]["GroupsPreview"];
export type GroupField = components["schemas"]["GroupField"];
export type ParcelInspect = components["schemas"]["ParcelInspect"];
export type AssembleView = components["schemas"]["AssembleView"];
export type Units = components["schemas"]["Units-Output"];
export type UnitsView = components["schemas"]["UnitsView"];
export type CleanView = components["schemas"]["CleanView"];
export type CleanSetup = components["schemas"]["CleanSetup"];
export type CleanReceipt = components["schemas"]["CleanReceipt"];
export type FillRow = components["schemas"]["FillRow"];
export type ReviewItem = components["schemas"]["ReviewItem"];
export type SaleDetail = components["schemas"]["SaleDetail"];
export type RelatedSale = components["schemas"]["RelatedSale"];
export type PatternTable = components["schemas"]["PatternTable"];
export type CleanPatch = components["schemas"]["CleanPatch"];
export type PrepareView = components["schemas"]["PrepareView"];

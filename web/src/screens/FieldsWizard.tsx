import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Plus } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import {
  Button,
  Dialog,
  Header,
  Heading,
  Label,
  ListBox,
  ListBoxItem,
  ListBoxSection,
  Modal,
  ModalOverlay,
  Popover,
  Radio,
  RadioGroup,
  Select,
  SelectValue,
} from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type CleanStep,
  type NumberFormat,
  type Project,
  type ProjectDetail,
  type Rule,
  type Scale,
  unwrap,
  type Wizard,
  type WizardCheck,
  type WizardField,
  type WizardFile,
  type WizardIssue,
  type WizardStep,
} from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import blockingIcon from "../assets/noto/emoji_u274c.svg";
import resolvedIcon from "../assets/noto/emoji_u2705.svg";
import { Choice, Tick } from "../components/Form";
import { Tip, TipOn } from "../components/Tip";
import { ValuesButton } from "../components/ValuesButton";
import { desktop, useCanPickFile } from "../desktop";
import { t } from "../strings";
import { type CustomChange, CustomFields } from "./CustomFields";
import { EnrichStep } from "./Enrich";
import { DateDialog, NumberDialog, RuleDialog, ruleComplete } from "./FieldRules";
import { AddFile } from "./InputFiles";
import { LocationExtras } from "./Location";
import { type PermitsChange, PermitsStep } from "./Permits";
import { ABSENT, CompareDialog, PAIRS, SCALED, ScaleChoice, ScaleDialog, TiersDialog } from "./Quality";
import { describeSteps, ReconcileDialog } from "./Reconcile";
import { type LayerChange, ShapefilesStep } from "./Shapefiles";
import { type UnitsChange, UnitsPanel } from "./Units";

const w = t.wizard;
type AreaUnit = NonNullable<WizardField["area_unit"]>;
type Holds = "parcels" | "sales" | "unused" | "permits";
// Fields with no column that can instead be assumed, after a warning (SPEC F3d).
const ASSUMABLE = ["valid_sale", "vacant_sale"];
const NONE = "__none";
const ASSUME = "__assume";
const MAKE = "__make";
const ELSEWHERE = "__elsewhere";

/** F3d: the Fields tab, a guided wizard over all of the project's files (SPEC §3.0). */
export function FieldsTab({ detail, step }: { detail: ProjectDetail; step: string | null }) {
  const projectId = detail.project.id;
  const wizard = useQuery({
    queryKey: ["wizard", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard", { params: { path: { project_id: projectId } } }),
      ),
  });
  if (wizard.isPending) return <p className="empty">{w.loading}</p>;
  if (wizard.error) return <p className="error">{wizard.error.message}</p>;
  return <WizardView project={detail.project} data={wizard.data} step={step} />;
}

/** Steps in the order Next goes through them: the parts of More details, not More details itself. */
function order(steps: WizardStep[]): WizardStep[] {
  return steps.filter((s) => s.key !== "details");
}

function WizardView({ project, data, step }: { project: Project; data: Wizard; step: string | null }) {
  const projectId = project.id;
  const flat = order(data.steps);
  // Opens at the first step not done yet, or at Review (SPEC F3d).
  const [opening] = useState(() => flat.find((s) => s.status !== "done")?.key ?? "review");
  const wanted = step === "details" ? "big_five" : step;
  const current = flat.find((s) => s.key === wanted) ?? flat.find((s) => s.key === opening) ?? flat[0];
  const change = useChange(projectId);
  const [unfinished, setUnfinished] = useState(false);
  const go = (key: string) => navigate({ name: "project", id: projectId, tab: "fields", step: key });

  // Showing a step fills in its guesses, once (the server keeps track).
  const key = current?.key;
  const visit = change.mutate;
  useEffect(() => {
    if (key) visit({ kind: "visit", step: key });
  }, [key, visit]);

  if (!current) return null;
  const index = flat.indexOf(current);
  const prev = flat[index - 1];
  const next = flat[index + 1];
  const tops = data.steps.filter((s) => !s.parent);
  const top = current.parent ?? current.key;
  const copy = w.steps[current.key] ?? { title: current.key, question: "", lede: "" };
  const kicker = [
    w.stepOf(tops.findIndex((s) => s.key === top) + 1, tops.length),
    current.parent ? `${w.steps[current.parent]?.title} › ${copy.title}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  // Sales must have their fields; a step of optional fields (deeds, too) can be answered "I don't have these".
  const skippable = current.fields.length > 0 && current.key !== "sales";
  // Next is greyed until the step is ✅, but still answers a click: it says what's left (SPEC F3d).
  const gated = current.status === "blocked" || current.status === "attention";
  const onward = () =>
    // Moving on confirms the step: an optional step is then complete (SPEC F3d).
    next && change.mutate({ kind: "confirm", step: current.key }, { onSuccess: () => go(next.key) });

  return (
    <div className="wiz">
      <StepList steps={data.steps} current={current.key} go={go} />
      <div className="wiz-main">
        <div className="wiz-body">
          <p className="wiz-kicker">{kicker}</p>
          <h2 className="wiz-q">{copy.question}</h2>
          {copy.lede && <p className="wiz-lede">{copy.lede}</p>}
          {current.key === "welcome" && <WelcomeStep />}
          {current.key === "universe" && (
            <UniverseStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "sales" && <SalesStep project={project} data={data} change={change.mutate} />}
          {current.key === "more_files" && (
            <MoreFilesStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "review" && (
            <ReviewStep projectId={projectId} data={data} go={go} change={change.mutate} />
          )}
          {current.fields.length > 0 && (current.key !== "sales" || data.sale_id.file) && (
            <FieldsStep project={project} data={data} step={current} change={change.mutateAsync} />
          )}
          {current.key === "location" && (
            <LocationExtras project={project} data={data} change={change.mutate} />
          )}
          {current.key === "property_type" && (
            <CustomFields projectId={projectId} data={data} change={change.mutate} />
          )}
          {current.key === "shapefiles" && (
            <ShapefilesStep project={project} data={data} change={change.mutate} />
          )}
          {current.key === "deeds" && data.deeds && (
            <p className={data.deeds.ok ? "wiz-note" : "wiz-note wiz-warn"}>{data.deeds.text}</p>
          )}
          {current.key === "enrich" && <EnrichStep projectId={projectId} />}
          {current.key === "permits" && <PermitsStep project={project} data={data} change={change.mutate} />}
          {change.error && (
            <p className="error" role="alert">
              {change.error.message}
            </p>
          )}
        </div>
        {next && gated && current.left.length > 0 && (
          <p className="wiz-left">{w.left(current.left.length)}</p>
        )}
        <div className="wiz-foot">
          <span className="wiz-grow" />
          {prev && (
            <Button className="button" onPress={() => go(prev.key)}>
              {w.back}
            </Button>
          )}
          {skippable && (
            <Button
              className="button"
              onPress={() =>
                change.mutate({ kind: "skip", step: current.key }, { onSuccess: () => next && go(next.key) })
              }
            >
              {w.skip}
            </Button>
          )}
          {next && (
            <Button
              className={gated ? "button button-primary is-gated" : "button button-primary"}
              aria-disabled={gated}
              onPress={() => (gated ? setUnfinished(true) : onward())}
            >
              {current.key === "welcome" ? w.start : w.next}
            </Button>
          )}
        </div>
      </div>
      {unfinished && next && (
        <UnfinishedDialog
          left={current.left}
          close={() => setUnfinished(false)}
          skip={() => {
            setUnfinished(false);
            go(next.key);
          }}
        />
      )}
    </div>
  );
}

/** Clicking the greyed Next: what's left on the step, and the choice to move on anyway. */
function UnfinishedDialog({
  left,
  close,
  skip,
}: {
  left: WizardStep["left"];
  close: () => void;
  skip: () => void;
}) {
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal wiz-unfinished">
        <Dialog className="modal-body" role="alertdialog">
          <Heading slot="title" className="modal-title">
            {w.unfinished.title}
          </Heading>
          <ul className="wiz-left-list">
            {left.map((item) => (
              <li key={item.text} className={item.blocking ? "wiz-blocking" : "wiz-caution"}>
                <img src={item.blocking ? blockingIcon : warningIcon} alt="" className="wiz-inline-icon" />
                {item.text}
              </li>
            ))}
          </ul>
          <p className="wiz-from">{w.unfinished.body}</p>
          <div className="form-actions wiz-unfinished-actions">
            <Button className="button" onPress={skip}>
              {w.unfinished.skip}
            </Button>
            <Button className="button button-primary" onPress={close} autoFocus>
              {w.unfinished.finish}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

// A step's mark (SPEC F3d): ✅ complete, ⚠ to decide, ❌ blocks a run; blank shows its number.
const STATUS_ICONS: Record<string, string | null> = {
  done: resolvedIcon,
  attention: warningIcon,
  blocked: blockingIcon,
  blank: null,
};

function StepList({ steps, current, go }: { steps: WizardStep[]; current: string; go: (k: string) => void }) {
  const tops = steps.filter((s) => !s.parent);
  return (
    <ol className="wiz-steps">
      {steps.map((s) => {
        const n = tops.indexOf(s) + 1;
        const icon = STATUS_ICONS[s.status];
        const classes = ["wiz-step", s.parent ? "sub" : "", s.key === current ? "now" : "", s.status].join(
          " ",
        );
        return (
          <li key={s.key} className={classes}>
            <button
              type="button"
              onClick={() => go(s.key === "details" ? "big_five" : s.key)}
              aria-current={s.key === current ? "step" : undefined}
            >
              <span className="n" aria-hidden="true">
                {icon ? <img src={icon} alt="" className="wiz-step-icon" /> : s.parent ? "" : String(n)}
              </span>
              {w.steps[s.key]?.title ?? s.key}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

// ---------- Changes ----------

type Change =
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
  | { kind: "location"; name: string; file: string | null; column: string | null }
  | CustomChange
  | UnitsChange
  | LayerChange
  | PermitsChange;

function useChange(projectId: string) {
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
              ...body,
            },
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
      if (c.kind === "units") {
        return unwrap(
          await api.PUT("/api/projects/{project_id}/wizard/files/{name}/units", {
            params: { path: { project_id, name: c.name } },
            body: { units: c.units, guess: c.guess ?? false },
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
      // Renaming the base to geo_parcels, and the field counts, show on the other tabs.
      if (c.kind !== "visit" || c.step === "files") {
        await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      }
    },
  });
}

export type Mutate = (c: Change, options?: { onSuccess?: () => void }) => void;
type MutateAsync = (c: Change) => Promise<Wizard>;

// ---------- Welcome, parcel universe, sales ----------

function CheckText({ check }: { check: WizardCheck | null | undefined }) {
  if (!check) return null;
  if (check.ok && !check.warn) return <span className="wiz-ok">{check.text}</span>;
  // A warning of its own (a unit that looks wrong, a date that reads two ways) shows as one; a result
  // whose warnings are listed as issues beside it stays plain.
  const own = check.warn && check.issues.length === 0;
  return <span className={check.ok && !own ? "wiz-result" : "wiz-warn"}>{check.text}</span>;
}

/** The second line of a check: each issue (✅ decided, ⚠ to decide, ❌ blocks a run), then the action. */
function Issues({ issues, action }: { issues: WizardIssue[]; action?: ReactNode }) {
  if (issues.length === 0 && !action) return null;
  return (
    <span className="wiz-issues">
      {issues.map((issue, i) => (
        <span
          key={issue.text}
          className={issue.resolved ? "wiz-resolved" : issue.blocking ? "wiz-blocking" : "wiz-caution"}
        >
          {i > 0 && <span className="wiz-sep"> · </span>}
          <img
            src={issue.resolved ? resolvedIcon : issue.blocking ? blockingIcon : warningIcon}
            alt=""
            className="wiz-inline-icon"
          />
          {issue.text}
        </span>
      ))}
      {action}
    </span>
  );
}

/** A file's ID check, and "Resolve…" when its IDs repeat: the duplicates dialog (SPEC F3d). */
function IdCheck({
  projectId,
  data,
  file,
  change,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: Mutate;
}) {
  const [open, setOpen] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const r = file.repeats;
  const resolvable =
    (((file.holds === "parcels" || file.match === "key_sale") && (r?.extra ?? 0) > 0) ||
      (r?.blank ?? 0) > 0) &&
    (file.holds === "parcels" || file.holds === "sales");
  // The ID it joins on: the universe's own is its parcel ID.
  const field = file.base ? "key" : file.match;
  const steps = file.clean[field] ?? [];
  // What it joins to: the main sales file for more sales details, else the parcel universe.
  const base =
    file.match === "key_sale" ? data.files.find((f) => isMainSales(f)) : data.files.find((f) => f.base);
  const share = file.id_check?.share;
  // Reconcile: whenever some rows don't find their parcel (or sale), or to change the clean-up (SPEC F3d).
  const reconcilable =
    !file.base &&
    base !== undefined &&
    share !== null &&
    share !== undefined &&
    (share < 1 || steps.length > 0 || (base.clean[field] ?? []).length > 0);
  const reconcile = reconcilable && (
    <Button className="wiz-link wiz-resolve" onPress={() => setReconciling(true)}>
      {w.reconcile.open}
    </Button>
  );
  return (
    <div className="wiz-samples wiz-check-lines">
      <span>
        <CheckText check={file.id_check} />
        {(file.id_check?.issues ?? []).length === 0 && reconcile}
      </span>
      <Issues
        issues={file.id_check?.issues ?? []}
        action={
          <>
            {resolvable && (
              <Button className="wiz-link wiz-resolve" onPress={() => setOpen(true)}>
                {w.dupes.resolve}
              </Button>
            )}
            {(file.id_check?.issues ?? []).length > 0 && reconcile}
          </>
        }
      />
      {steps.length > 0 && <span className="wiz-cleaned">{w.reconcile.cleaned(describeSteps(steps))}</span>}
      {reconciling && base && (
        <ReconcileDialog
          projectId={projectId}
          file={file}
          base={base}
          close={() => setReconciling(false)}
          save={(file_steps, base_steps) =>
            change(
              { kind: "reconcile", name: file.name, file_steps, base_steps },
              { onSuccess: () => setReconciling(false) },
            )
          }
        />
      )}
      {open && (
        <DupesDialog
          projectId={projectId}
          data={data}
          file={file}
          change={change}
          close={() => setOpen(false)}
        />
      )}
    </div>
  );
}

function DupesDialog({
  projectId,
  data,
  file,
  change,
  close,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: Mutate;
  close: () => void;
}) {
  const d = w.dupes;
  const r = file.repeats;
  const examples = useQuery({
    queryKey: ["repeats", projectId, file.name, file.id_column],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/files/{name}/repeats", {
          params: { path: { project_id: projectId, name: file.name } },
        }),
      ),
  });
  const id = file.base ? "key" : file.match;
  const [policy, setPolicy] = useState<"first" | "all" | null>(r?.policy ?? null);
  const [sort, setSort] = useState<string>(r?.sort ?? id);
  const [desc, setDesc] = useState<boolean>(r?.descending ?? false);
  const [blankOk, setBlankOk] = useState<boolean>(r?.blank_ok ?? false);
  if (!r) return null;
  const hasRepeats = r.extra > 0;
  const hasBlanks = r.blank > 0;
  const fieldsHere = Object.values(data.used[file.name] ?? {});
  const kept = policy === "all" ? r.singles : policy === "first" ? r.distinct : null;
  const nameOf = (key: string) => w.idNames[key] ?? data.fields.find((f) => f.key === key)?.name ?? key;
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal wiz-modal wiz-modal-wide">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {d.title(file.name, file.id_column ?? "")}
          </Heading>
          {hasRepeats && (
            <div className="wiz-section-head-row">
              <h3 className="wiz-sub">{d.repeatsTitle(r.repeated)}</h3>
              <span className="wiz-from">{r.few ? d.fewMeans : d.manyMeans}</span>
            </div>
          )}
          {hasRepeats && examples.data && (
            <div className="wiz-dupes-table">
              <table className="wiz-table">
                <thead>
                  <tr>
                    {examples.data.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {examples.data.rows.map((row, i) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: example rows have no identity of their own
                    <tr key={i}>
                      {row.map((v, j) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: cells by position
                        <td key={j} className="mono">
                          {v}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {hasRepeats && (
            <RadioGroup
              className="field radios wiz-act"
              value={policy}
              onChange={(v) => setPolicy(v as "first" | "all")}
            >
              <Label className="wiz-act-label">{d.what}</Label>
              <Radio value="first" className="radio">
                <span className="radio-dot" aria-hidden="true" />
                {d.first}
              </Radio>
              {policy === "first" && (
                <div className="wiz-pair wiz-indent">
                  <Choice
                    label={d.sortBy}
                    value={sort}
                    options={fieldsHere.map((k) => [k, nameOf(k)] as const)}
                    onChange={setSort}
                  />
                  <Choice
                    label={d.order}
                    value={desc ? "desc" : "asc"}
                    options={[
                      ["asc", d.asc],
                      ["desc", d.desc],
                    ]}
                    onChange={(v) => setDesc(v === "desc")}
                  />
                </div>
              )}
              <Radio value="all" className="radio">
                <span className="radio-dot" aria-hidden="true" />
                {d.all}
              </Radio>
            </RadioGroup>
          )}
          {hasRepeats && hasBlanks && <hr className="wiz-rule" />}
          {hasBlanks && (
            <>
              <div className="wiz-section-head-row">
                <h3 className="wiz-sub">{d.blanksTitle(r.blank)}</h3>
                <span className="wiz-from">{d.blankMeans(file.holds === "sales")}</span>
              </div>
              <div className="wiz-act">
                <span className="wiz-act-label">{d.confirm}</span>
                <Tick isSelected={blankOk} onChange={setBlankOk}>
                  {d.blankOk(r.blank, file.holds === "sales")}
                </Tick>
              </div>
            </>
          )}
          <hr className="wiz-rule" />
          {kept !== null && (
            <p>
              <strong>{d.result(r.rows, kept)}</strong>
            </p>
          )}
          <div className="form-actions">
            <Button
              className="button button-primary"
              isDisabled={!((hasRepeats && policy !== null) || (hasBlanks && blankOk !== r.blank_ok))}
              onPress={() =>
                change(
                  {
                    kind: "file",
                    name: file.name,
                    ...(hasRepeats && policy ? { dupes: policy } : {}),
                    ...(hasRepeats && policy === "first" ? { dupes_sort: sort, dupes_desc: desc } : {}),
                    ...(hasBlanks ? { blank_ok: blankOk } : {}),
                  },
                  { onSuccess: close },
                )
              }
            >
              {w.save}
            </Button>
            <Button className="button" onPress={close}>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function WelcomeStep() {
  return (
    <div className="wiz-welcome">
      {w.welcome.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </div>
  );
}

/** Add a file with the picker (SPEC F2), or take one already in the project. */
export function FilePicker({
  project,
  data,
  exclude,
  onChosen,
}: {
  project: Project;
  data: Wizard;
  exclude: string[];
  onChosen: (name: string) => void;
}) {
  const canPick = useCanPickFile();
  const queryClient = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const pick = async () => {
    const path = await desktop.pickFile();
    if (path) setPicked(path);
  };
  const existing = data.files.filter((f) => !exclude.includes(f.name) && !f.problem);
  if (picked !== null) {
    return (
      <AddFile
        project={project}
        path={picked}
        onBrowse={() => void pick()}
        onDone={() => setPicked(null)}
        onAdded={async (name) => {
          await queryClient.invalidateQueries({ queryKey: ["wizard", project.id] });
          onChosen(name);
        }}
      />
    );
  }
  return (
    <div className="wiz-pick">
      {canPick ? (
        <Button className="button button-primary" onPress={() => void pick()}>
          {w.addFile}
        </Button>
      ) : (
        <TipOn text={w.noPicker}>
          <Button className="button" isDisabled>
            {w.addFile}
          </Button>
        </TipOn>
      )}
      {existing.length > 0 && (
        <Choice
          label={w.orExisting}
          value={null}
          placeholder={w.choose}
          options={existing.map((f) => [f.name, w.fileLabel(f.name, f.filename)] as const)}
          onChange={onChosen}
        />
      )}
    </div>
  );
}

export function FileHeader({ file, onReplace }: { file: WizardFile; onReplace: () => void }) {
  return (
    <div className="wiz-file">
      <span className="mono">{file.name}</span>
      <span className="wiz-from">{file.filename}</span>
      {file.rows !== null && <span className="wiz-from">· {file.rows.toLocaleString()} rows</span>}
      <Button className="wiz-link" onPress={onReplace}>
        {w.addOther}
      </Button>
    </div>
  );
}

function UniverseStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const [replacing, setReplacing] = useState(false);
  const [adding, setAdding] = useState(false);
  if (!base || replacing) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={base ? [base.name] : []}
        onChosen={(name) =>
          change({ kind: "file", name, universe: true }, { onSuccess: () => setReplacing(false) })
        }
      />
    );
  }
  const columns = base.columns.map((c) => [c.name, c.name] as const);
  return (
    <>
      <FileHeader file={base} onReplace={() => setReplacing(true)} />
      <p className="wiz-ok">{w.geometryFound}</p>
      <div className="wiz-grid">
        <div className="wiz-label">
          <TipOn text={w.parcelIdTip}>
            <span>{w.parcelId}</span>
          </TipOn>
        </div>
        <Choice
          label={w.parcelId}
          hideLabel
          value={base.id_column}
          placeholder={w.choose}
          options={columns}
          onChange={(id_column) => change({ kind: "file", name: base.name, id_column })}
        />
        <IdCheck projectId={project.id} data={data} file={base} change={change} />
        {base.extra_ids.map((e) => (
          <ExtraIdRow key={e.field} file={base} extra={e} change={change} />
        ))}
        {adding && <NewExtraIdRow file={base} change={change} done={() => setAdding(false)} />}
      </div>
      {!adding && base.extra_ids.length < EXTRA_IDS.length && (
        <Tip text={w.extraIdTip}>
          <Button className="button wiz-add-id" onPress={() => setAdding(true)}>
            <Plus aria-hidden="true" size="1em" />
            {w.addId(w.idOrdinal[EXTRA_IDS[base.extra_ids.length] ?? "key2"] ?? "")}
          </Button>
        </Tip>
      )}
    </>
  );
}

const EXTRA_IDS = ["key2", "key3"] as const;

/** The IDs a file can match the universe on: its parcel ID, then its extra IDs. */
function matchOptions(base: WizardFile | undefined): (readonly ["key" | "key2" | "key3", string])[] {
  return [
    ["key", w.parcelId] as const,
    ...(base?.extra_ids ?? []).map((e) => [e.field, `${w.idOrdinal[e.field]} (${e.column})`] as const),
  ];
}

function ExtraIdRow({
  file,
  extra,
  change,
}: {
  file: WizardFile;
  extra: WizardFile["extra_ids"][number];
  change: Mutate;
}) {
  const ordinal = w.idOrdinal[extra.field] ?? extra.field;
  return (
    <>
      <div className="wiz-label">
        <TipOn text={w.extraIdTip}>
          <span>{ordinal}</span>
        </TipOn>
        <small>{w.optional}</small>
      </div>
      <Choice
        label={ordinal}
        hideLabel
        value={extra.column}
        options={[[NONE, w.removeId] as const, ...file.columns.map((c) => [c.name, c.name] as const)]}
        onChange={(v) =>
          change({
            kind: "file",
            name: file.name,
            extra_field: extra.field,
            extra_column: v === NONE ? null : v,
          })
        }
      />
      <div />
    </>
  );
}

function NewExtraIdRow({ file, change, done }: { file: WizardFile; change: Mutate; done: () => void }) {
  const field = EXTRA_IDS[file.extra_ids.length] ?? "key2";
  const ordinal = w.idOrdinal[field] ?? field;
  return (
    <>
      <div className="wiz-label">
        <TipOn text={w.extraIdTip}>
          <span>{ordinal}</span>
        </TipOn>
        <small>{w.optional}</small>
      </div>
      <Choice
        label={ordinal}
        hideLabel
        value={null}
        placeholder={w.choose}
        options={file.columns.map((c) => [c.name, c.name] as const)}
        onChange={(v) =>
          change({ kind: "file", name: file.name, extra_field: field, extra_column: v }, { onSuccess: done })
        }
      />
      <div className="wiz-samples">
        <Button className="wiz-link" onPress={done}>
          {w.cancel}
        </Button>
      </div>
    </>
  );
}

/** The sales file the Sales step is about; more sales details join it on the sale ID. */
function isMainSales(f: WizardFile): boolean {
  return f.holds === "sales" && f.match !== "key_sale";
}

function SalesStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find(isMainSales);
  const base = data.files.find((f) => f.base);
  const [replacing, setReplacing] = useState(false);
  if (!sales || replacing) {
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={[...(base ? [base.name] : []), ...(sales ? [sales.name] : [])]}
        onChosen={(name) =>
          change({ kind: "file", name, holds: "sales" }, { onSuccess: () => setReplacing(false) })
        }
      />
    );
  }
  return (
    <>
      <FileHeader file={sales} onReplace={() => setReplacing(true)} />
      <IdRow projectId={project.id} data={data} file={sales} base={base} change={change} />
      <div className="wiz-grid">
        <div className="wiz-label">
          <TipOn text={w.saleIdTip}>
            <span>{w.saleIdColumn}</span>
          </TipOn>
        </div>
        <Choice
          label={w.saleIdColumn}
          hideLabel
          value={data.sale_id.made ? MAKE : data.sale_id.column}
          placeholder={w.choose}
          options={[[MAKE, w.makeSaleId] as const, ...sales.columns.map((c) => [c.name, c.name] as const)]}
          onChange={(v) => change({ kind: "saleId", column: v === MAKE ? null : v, make: v === MAKE })}
        />
        <div className="wiz-samples">
          <CheckText check={data.sale_id.check} />
        </div>
      </div>
      <hr className="wiz-rule" />
    </>
  );
}

/** F3d: more files, one by one: what each joins to (parcels or sales), the ID it joins on, and its checks. */
function MoreFilesStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const base = data.files.find((f) => f.base);
  const main = data.files.find(isMainSales);
  // Picked here this visit: shown even before it's said what it holds.
  const [chosen, setChosen] = useState<string[]>([]);
  const extras = data.files.filter(
    (f) =>
      !f.base &&
      f !== main &&
      (f.holds === "parcels" || f.holds === "sales" || f.holds === null || chosen.includes(f.name)),
  );
  const [adding, setAdding] = useState(extras.length === 0);
  return (
    <>
      {extras.map((f) => (
        <ExtraFile
          key={f.name}
          project={project}
          data={data}
          file={f}
          base={base}
          main={main}
          change={change}
          drop={() => {
            setChosen((c) => c.filter((n) => n !== f.name));
            change({ kind: "file", name: f.name, holds: "unused" });
          }}
        />
      ))}
      {adding ? (
        <div className="wiz-extra">
          <FilePicker
            project={project}
            data={data}
            exclude={[
              ...(base ? [base.name] : []),
              ...(main ? [main.name] : []),
              ...extras.map((f) => f.name),
            ]}
            onChosen={(name) => {
              setChosen((c) => [...c, name]);
              setAdding(false);
            }}
          />
          {extras.length > 0 && (
            <Button className="wiz-link" onPress={() => setAdding(false)}>
              {w.cancel}
            </Button>
          )}
        </div>
      ) : (
        <Button className="button wiz-add-id" onPress={() => setAdding(true)}>
          <Plus aria-hidden="true" size="1em" />
          {extras.length ? w.extraFiles.another : w.extraFiles.first}
        </Button>
      )}
    </>
  );
}

function ExtraFile({
  project,
  data,
  file,
  base,
  main,
  change,
  drop,
}: {
  project: Project;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  main: WizardFile | undefined;
  change: Mutate;
  drop: () => void;
}) {
  const m = w.extraFiles;
  const holds = file.holds === "parcels" || file.holds === "sales" ? file.holds : null;
  // More sales details join on the sale ID, so the main sales file needs one in a column.
  const salesOk = main !== undefined && main.id_column !== null && !data.sale_id.made;
  return (
    <section className="wiz-extra">
      <div className="wiz-file">
        <span className="mono">{file.name}</span>
        <span className="wiz-from">{file.filename}</span>
        {file.rows !== null && <span className="wiz-from">· {file.rows.toLocaleString()} rows</span>}
        <Button className="wiz-link" onPress={drop}>
          {m.drop}
        </Button>
      </div>
      <RadioGroup
        className="field radios wiz-holds"
        value={holds}
        onChange={(v) =>
          change(
            v === "sales"
              ? { kind: "file", name: file.name, holds: "sales", match: "key_sale" }
              : { kind: "file", name: file.name, holds: "parcels" },
          )
        }
      >
        <Label className="field-label">{m.what}</Label>
        <Radio value="parcels" className="radio">
          <span className="radio-dot" aria-hidden="true" />
          {m.parcels}
        </Radio>
        <Radio value="sales" className="radio" isDisabled={!salesOk && holds !== "sales"}>
          <span className="radio-dot" aria-hidden="true" />
          {m.sales}
          {!salesOk && <small className="wiz-from"> {m.salesNeedsId}</small>}
        </Radio>
      </RadioGroup>
      {holds && <IdRow projectId={project.id} data={data} file={file} base={base} change={change} />}
      {holds === "parcels" && <UnitsPanel projectId={project.id} data={data} file={file} change={change} />}
    </section>
  );
}

/** A file's ID column, and whether it matches the universe's parcel ID or its second ID. */
export function IdRow({
  projectId,
  data,
  file,
  base,
  change,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  base: WizardFile | undefined;
  change: Mutate;
}) {
  const options = matchOptions(base);
  // More sales details join on the sale ID; anything else on the parcel ID or an extra ID.
  const several = options.length > 1 && file.match !== "key_sale";
  return (
    <div className="wiz-grid">
      <div className="wiz-label">
        {file.match === "key_sale" ? w.saleIdLabel : several ? w.matchBy : w.parcelId}
      </div>
      <div className="wiz-pair">
        {several && (
          <Choice
            label={w.matchBy}
            hideLabel
            value={file.match}
            options={options}
            onChange={(match) => change({ kind: "file", name: file.name, match })}
          />
        )}
        <Choice
          label={w.idColumnIn(file.name)}
          hideLabel
          value={file.id_column}
          placeholder={w.choose}
          options={file.columns.map((c) => [c.name, c.name] as const)}
          onChange={(id_column) => change({ kind: "file", name: file.name, id_column })}
        />
      </div>
      <IdCheck projectId={projectId} data={data} file={file} change={change} />
    </div>
  );
}

// ---------- The fields, a few at a time ----------

function FieldsStep({
  project,
  data,
  step,
  change,
}: {
  project: Project;
  data: Wizard;
  step: WizardStep;
  change: MutateAsync;
}) {
  const [more, setMore] = useState(false);
  const mine = data.fields.filter((f) => f.step === step.key && !f.hidden);
  // Only the universe so far: building details are often in a separate file (a CAMA export).
  const onlyBase = step.key === "big_five" && data.files.filter((f) => f.holds === "parcels").length <= 1;
  // A field under More that's loaded (guessed or chosen) always shows: nothing loaded is ever out of sight.
  const inUse = (f: WizardField) => f.sources.length > 0 || f.assumed || f.absent;
  const shown = mine.filter((f) => !f.more || more || inUse(f));
  const hidden = mine.filter((f) => f.more && !inUse(f)).length;
  return (
    <>
      {onlyBase && <p className="wiz-note wiz-another">{w.anotherFileHint}</p>}
      <div className="wiz-grid">
        {groupsFor(step.key, shown).map(([title, fields]) =>
          // A section of one field is that row, numbered; a section of several gets a heading.
          title && fields.length === 1 && fields[0]
            ? [
                <FieldRow
                  key={fields[0].key}
                  project={project}
                  data={data}
                  field={fields[0]}
                  sales={step.sales}
                  change={change}
                  label={title}
                />,
              ]
            : [
                title && (
                  <h3 key={`group-${title}`} className="wiz-group">
                    {title}
                  </h3>
                ),
                ...fields.map((f) => (
                  <FieldRow
                    key={f.key}
                    project={project}
                    data={data}
                    field={f}
                    sales={step.sales}
                    change={change}
                    inGroup={Boolean(title)}
                  />
                )),
              ],
        )}
      </div>
      {hidden > 0 && (
        <Button className="wiz-more" onPress={() => setMore(!more)}>
          {more ? w.fewer : w.more(hidden)}
        </Button>
      )}
    </>
  );
}

/** The Big five step's numbered sections (year built and effective year built are one: age). */
function groupsFor(step: string, fields: WizardField[]): [string | null, WizardField[]][] {
  if (step !== "big_five") return [[null, fields]];
  return w.bigFive
    .map(([title, keys], i) => [`${i + 1}. ${title}`, fields.filter((f) => keys.includes(f.key))] as const)
    .filter(([, group]) => group.length > 0)
    .map(([title, group]) => [title, [...group]]);
}

/** Amounts of money: read with a format when written as text, and checked for scale (SPEC F3d). */
function isMoney(key: string): boolean {
  return key === "sale_price" || (key.startsWith("assr_") && key.endsWith("_value"));
}

function FieldRow({
  project,
  data,
  field,
  sales,
  change,
  label,
  inGroup,
}: {
  project: Project;
  data: Wizard;
  field: WizardField;
  sales: boolean;
  change: MutateAsync;
  /** A numbered section's title, shown instead of the field's name (which moves underneath). */
  label?: string;
  inGroup?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [elsewhere, setElsewhere] = useState(false);
  const [ruling, setRuling] = useState(false);
  const [dating, setDating] = useState(false);
  const [reading, setReading] = useState(false);
  // Quality and condition: compare the columns, say what a number means, or rank a category's tiers.
  const [qc, setQc] = useState<"compare" | "scale" | "tiers" | null>(null);
  const scaled = SCALED.includes(field.key);
  const paired = field.key in PAIRS;
  const money = isMoney(field.key);
  // Under a numbered title, the field's own name only when it says more ("4. Quality" needs no "Quality").
  const name = shortName(field);
  const same = label?.replace(/^\d+\.\s*/, "").toLowerCase() === name.toLowerCase();
  const sub = [label && !same ? name : null, w.hints[field.key]].filter(Boolean).join(" · ");
  const files = data.files.filter((f) => f.holds === (sales ? "sales" : "parcels"));
  const source = field.sources[0];
  const value = field.assumed
    ? ASSUME
    : field.absent
      ? ABSENT
      : source
        ? `${source.file}\u0000${source.column}`
        : NONE;
  const sourceFile = source ? files.find((f) => f.name === source.file) : undefined;
  const column = source && sourceFile?.columns.find((c) => c.name === source.column);
  const pick = (v: string) => {
    if (v === ASSUME) setConfirming(true);
    else if (v === ABSENT) void change({ kind: "field", key: field.key, absent: true }).catch(() => {});
    else if (v === ELSEWHERE) setElsewhere(true);
    else if (v === NONE) void change({ kind: "field", key: field.key }).catch(() => {});
    else {
      const [file, col] = v.split("\u0000");
      void change({ kind: "field", key: field.key, file: file ?? null, column: col ?? null })
        .then((next) => {
          // Not yes/no (Q/U, a deed code): straight on to choosing which values mean yes (SPEC F3d).
          const now = next.fields.find((f) => f.key === field.key);
          if (now?.rule && !ruleComplete(now.rule)) setRuling(true);
          // A sale price that needs reading, or whose amounts look wrong: straight to how it's read.
          if (field.key === "sale_price" && now?.check && (!now.check.ok || now.check.warn)) setReading(true);
          // A category for a number: straight to ranking its tiers; a condition number: to what it means.
          if (now?.scale?.kind === "tiers" && Object.keys(now.scale.tiers).length === 0) setQc("tiers");
          else if (field.key === "bldg_condition_num" && now?.scale && !now.scale.kind) setQc("scale");
        })
        .catch(() => {});
    }
  };
  return (
    <>
      <div className={inGroup ? "wiz-label wiz-in-group" : "wiz-label"}>
        <TipOn text={field.description || field.name}>
          <span>{label ?? w.rowNames[field.key] ?? shortName(field)}</span>
        </TipOn>
        {sub && <small>{sub}</small>}
      </div>
      <div
        className={
          field.area_unit || (scaled && source && field.scale && field.scale.kind !== "tiers")
            ? "wiz-pair"
            : undefined
        }
      >
        <ColumnChoice
          field={field}
          files={files}
          used={data.used}
          names={Object.fromEntries(data.fields.map((f) => [f.key, shortName(f)]))}
          value={value}
          many={files.length > 1}
          elsewhere={!sales}
          onChange={pick}
        />
        {scaled && source && (
          <ScaleChoice
            field={field}
            source={source}
            change={(c) => void change({ kind: "field", ...c }).catch(() => {})}
          />
        )}
        {field.area_unit && source && (
          // The unit the column is in: OAK box converts it to the project's (SPEC F3d).
          <div className="wiz-unit">
            <Choice
              label={w.areaUnitFor(shortName(field))}
              hideLabel
              value={field.area_unit}
              options={Object.entries(w.areaUnits) as [AreaUnit, string][]}
              onChange={(area_unit) =>
                void change({
                  kind: "field",
                  key: field.key,
                  file: source.file,
                  column: source.column,
                  area_unit,
                }).catch(() => {})
              }
            />
          </div>
        )}
      </div>
      <div className="wiz-samples">
        {field.assumed ? (
          <span className="wiz-warn">
            {w.assumed}: {w.assumedValue[field.key]}
          </span>
        ) : (
          <>
            <CheckText check={field.check} />
            {field.absent && <span className="wiz-from">{w.quality.absentNote}</span>}
            {paired &&
            !source &&
            !field.absent &&
            data.fields.find((f) => f.key === PAIRS[field.key])?.sources.length
              ? !scaled && <span className="wiz-from">{w.numberUsed}</span>
              : null}
            {scaled && source && field.scale && (
              <Button
                className="wiz-link wiz-resolve"
                onPress={() => setQc(field.scale?.kind === "tiers" ? "tiers" : "scale")}
              >
                {field.scale.kind === "tiers"
                  ? Object.keys(field.scale.tiers).length
                    ? w.quality.reRank
                    : w.quality.rank
                  : field.key === "bldg_quality_num"
                    ? w.quality.checkDirection
                    : w.quality.checkMeaning}
              </Button>
            )}
            {paired && !scaled && (
              // One per section, on the category row: its text is short, so the link always shows.
              <Button className="wiz-link wiz-resolve" onPress={() => setQc("compare")}>
                {w.quality.compare}
              </Button>
            )}
            {sourceFile && column && field.type === "boolean" && sales && (
              <Button className="wiz-link wiz-resolve" onPress={() => setRuling(true)}>
                {!field.rule ? w.rule.make : ruleComplete(field.rule) ? w.rule.edit : w.rule.choose}
              </Button>
            )}
            {sourceFile && column && field.type === "date" && column.type !== "date" && (
              <Button className="wiz-link wiz-resolve" onPress={() => setDating(true)}>
                {field.check?.warn || !field.check?.ok ? w.dates.check : w.dates.change}
              </Button>
            )}
            {sourceFile && column && money && (
              <Button className="wiz-link wiz-resolve" onPress={() => setReading(true)}>
                {field.check?.warn || !field.check?.ok ? w.numbers.check : w.numbers.change}
              </Button>
            )}
            {sourceFile && column && !field.rule && (
              <ValuesButton
                projectId={project.id}
                file={sourceFile.name}
                column={column.name}
                distinct={field.distinct}
              />
            )}
          </>
        )}
      </div>
      {ruling && sourceFile && (
        <RuleDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          price={data.fields.find((f) => f.key === "sale_price")}
          close={() => setRuling(false)}
          save={(rule) =>
            void change({ kind: "rule", key: field.key, rule })
              .then(() => setRuling(false))
              .catch(() => {})
          }
        />
      )}
      {dating && sourceFile && source && (
        <DateDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          column={source.column}
          close={() => setDating(false)}
          save={(date_format) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              date_format,
            })
              .then(() => setDating(false))
              .catch(() => {})
          }
        />
      )}
      {reading && sourceFile && source && (
        <NumberDialog
          projectId={project.id}
          field={field}
          file={sourceFile}
          column={source.column}
          close={() => setReading(false)}
          save={(number_format) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              number_format,
            })
              .then(() => setReading(false))
              .catch(() => {})
          }
        />
      )}
      {qc === "compare" && (
        <CompareDialog
          projectId={project.id}
          data={data}
          numKey={scaled ? field.key : (PAIRS[field.key] ?? field.key)}
          close={() => setQc(null)}
          save={(num, txt) =>
            void change({ kind: "field", ...num })
              .then(() => change({ kind: "field", ...txt }))
              .then((next) => {
                const now = next.fields.find((f) => f.key === num.key);
                setQc(null);
                if (
                  num.key === field.key &&
                  now?.scale?.kind === "tiers" &&
                  !Object.keys(now.scale.tiers).length
                )
                  setQc("tiers");
              })
              .catch(() => {})
          }
        />
      )}
      {qc === "scale" && source && (
        <ScaleDialog
          projectId={project.id}
          field={field}
          source={source}
          close={() => setQc(null)}
          save={(scale) =>
            void change({ kind: "field", key: field.key, file: source.file, column: source.column, scale })
              .then(() => setQc(null))
              .catch(() => {})
          }
        />
      )}
      {qc === "tiers" && source && (
        <TiersDialog
          projectId={project.id}
          field={field}
          source={source}
          close={() => setQc(null)}
          save={(tiers) =>
            void change({
              kind: "field",
              key: field.key,
              file: source.file,
              column: source.column,
              scale: { kind: "tiers", fraction: false, low: null, high: null, tiers },
            })
              .then(() => setQc(null))
              .catch(() => {})
          }
        />
      )}
      {confirming && (
        <AssumeDialog
          field={field.key}
          close={() => setConfirming(false)}
          confirm={() => {
            setConfirming(false);
            void change({ kind: "field", key: field.key, assume: true }).catch(() => {});
          }}
        />
      )}
      {elsewhere && (
        <OtherFileDialog
          project={project}
          data={data}
          field={field}
          change={change}
          close={() => setElsewhere(false)}
        />
      )}
    </>
  );
}

/** The dictionary's name, without "Building" for building fields ("Year built"), except where "Building type"
 * sits beside "Land use". */
function shortName(field: WizardField): string {
  if (!field.key.startsWith("bldg_") || field.step === "property_type") return field.name;
  const rest = field.name.replace(/^Building /, "");
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** Quality and condition fields can take the same column. */
function shares(a: string, b: string): boolean {
  return a in PAIRS && b in PAIRS;
}

/** A column dropdown grouped by file, with used columns shown but not pickable. */
function ColumnChoice({
  field,
  files,
  used,
  names,
  value,
  many,
  elsewhere,
  onChange,
}: {
  field: WizardField;
  files: WizardFile[];
  used: Wizard["used"];
  names: Record<string, string>;
  value: string;
  many: boolean;
  elsewhere: boolean;
  onChange: (v: string) => void;
}) {
  const disabled: string[] = [];
  const nameOf = (key: string) => w.idNames[key] ?? names[key] ?? key;
  for (const f of files) {
    for (const c of f.columns) {
      const as = used[f.name]?.[c.name];
      // Quality and condition can share a column: a category is the text and, ranked, the number.
      if (as && as !== field.key && !shares(field.key, as)) disabled.push(`${f.name}\u0000${c.name}`);
    }
  }
  return (
    <Select
      className="field choice wiz-choice"
      selectedKey={value}
      onSelectionChange={(k) => k !== null && onChange(String(k))}
      disabledKeys={disabled}
      aria-label={w.columnFor(field.name)}
    >
      <Button className="choice-button">
        <SelectValue className="choice-value">
          {({ selectedText }) => selectedValue(value, selectedText, many)}
        </SelectValue>
        <span className="combo-arrow" aria-hidden="true">
          <ChevronDown size="0.9em" />
        </span>
      </Button>
      <Popover className="popover choice-popover wiz-popover">
        <ListBox className="choice-list">
          <ListBoxItem id={NONE} className="choice-item" textValue={w.none}>
            {w.none}
          </ListBoxItem>
          {files.map((f) => (
            <ListBoxSection key={f.name} className="wiz-section">
              <Header className="wiz-section-head">{f.name}</Header>
              {f.columns.map((c) => {
                const as = used[f.name]?.[c.name];
                const taken = as && as !== field.key && !shares(field.key, as);
                return (
                  <ListBoxItem
                    key={c.name}
                    id={`${f.name}\u0000${c.name}`}
                    className="choice-item wiz-item"
                    textValue={c.name}
                  >
                    <span className="mono">{c.name}</span>
                    <span className="wiz-item-note">
                      {taken ? w.used(nameOf(as)) : c.samples.slice(0, 3).join(", ")}
                    </span>
                  </ListBoxItem>
                );
              })}
            </ListBoxSection>
          ))}
          {elsewhere && (
            <ListBoxItem id={ELSEWHERE} className="choice-item wiz-elsewhere" textValue={w.elsewhere}>
              {w.elsewhere}
            </ListBoxItem>
          )}
          {field.key === "bldg_condition_num" && (
            <ListBoxItem id={ABSENT} className="choice-item" textValue={w.quality.absent}>
              {w.quality.absent}
            </ListBoxItem>
          )}
          {ASSUMABLE.includes(field.key) && (
            <ListBoxItem id={ASSUME} className="choice-item" textValue={w.assume[field.key] ?? ""}>
              {w.assume[field.key]}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </Select>
  );
}

function selectedValue(value: string, text: string, many: boolean): ReactNode {
  if (value === NONE) return <span className="wiz-none">{w.none}</span>;
  if (value === ASSUME) return w.assumed;
  if (value === ABSENT) return w.quality.absent;
  const [file, column] = value.split("\u0000");
  return (
    <>
      <span className="mono">{column ?? text}</span>
      {many && <span className="wiz-from"> · {file}</span>}
    </>
  );
}

/** "It's in another file": the file (added here if need be), its ID column, and the field's column. */
function OtherFileDialog({
  project,
  data,
  field,
  change,
  close,
}: {
  project: Project;
  data: Wizard;
  field: WizardField;
  change: MutateAsync;
  close: () => void;
}) {
  const base = data.files.find((f) => f.base);
  const taken = data.files.filter((f) => f.base || f.holds === "sales").map((f) => f.name);
  const [file, setFile] = useState<string | null>(null);
  const [match, setMatch] = useState<"key" | "key2" | "key3">("key");
  const [idColumn, setIdColumn] = useState<string | null>(null);
  const [column, setColumn] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chosen = data.files.find((f) => f.name === file);
  const columns = (chosen?.columns ?? []).map((c) => [c.name, c.name] as const);
  const save = async () => {
    if (!file || !idColumn || !column) return;
    try {
      await change({ kind: "file", name: file, holds: "parcels", match, id_column: idColumn });
      await change({ kind: "field", key: field.key, file, column });
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal wiz-modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            {w.otherTitle(shortName(field))}
          </Heading>
          {chosen ? (
            <div className="wiz-grid wiz-grid-dialog">
              <div className="wiz-label">{w.otherFile}</div>
              <div className="mono">{w.fileLabel(chosen.name, chosen.filename)}</div>
              <div />
              {matchOptions(base).length > 1 && (
                <>
                  <div className="wiz-label">{w.matchBy}</div>
                  <Choice
                    label={w.matchBy}
                    hideLabel
                    value={match}
                    options={matchOptions(base)}
                    onChange={setMatch}
                  />
                  <div />
                </>
              )}
              <div className="wiz-label">{w.otherKey}</div>
              <Choice
                label={w.otherKey}
                hideLabel
                value={idColumn}
                placeholder={w.choose}
                options={columns}
                onChange={setIdColumn}
              />
              <div />
              <div className="wiz-label">{shortName(field)}</div>
              <Choice
                label={w.otherColumn(shortName(field))}
                hideLabel
                value={column}
                placeholder={w.choose}
                options={columns}
                onChange={setColumn}
              />
              <div />
            </div>
          ) : (
            <FilePicker project={project} data={data} exclude={taken} onChosen={setFile} />
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions">
            <Button
              className="button button-primary"
              isDisabled={!file || !idColumn || !column}
              onPress={() => void save()}
            >
              {w.save}
            </Button>
            <Button className="button" onPress={close}>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function AssumeDialog({ field, close, confirm }: { field: string; close: () => void; confirm: () => void }) {
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal">
        <Dialog className="modal-body" role="alertdialog">
          <Heading slot="title" className="modal-title wiz-warn-title">
            <img src={warningIcon} alt="" className="wiz-warn-icon" />
            {w.warnTitle[field]}
          </Heading>
          <p>{w.warnBody[field]}</p>
          <div className="form-actions">
            <Button className="button button-danger" onPress={confirm}>
              {w.warnConfirm}
            </Button>
            <Button className="button" onPress={close} autoFocus>
              {w.cancel}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

// ---------- Step 9: Review ----------

function ReviewStep({
  projectId,
  data,
  go,
  change,
}: {
  projectId: string;
  data: Wizard;
  go: (k: string) => void;
  change: Mutate;
}) {
  const loaded = data.fields.filter((f) => f.sources.length > 0 || f.assumed);
  const columns = loaded.reduce((n, f) => n + f.sources.length, 0);
  const required = new Set(["sale_price", "sale_date", ...ASSUMABLE]);
  const groups = order(data.steps).filter((s) => s.fields.length > 0);
  return (
    <>
      <p className="wiz-lede">
        {w.summary(loaded.length, columns)}{" "}
        {data.not_loaded.map((n) => w.notLoaded(n.file, n.columns)).join(" ")}
      </p>
      {data.files
        .filter((f) => f.holds === "parcels" && (f.repeats?.extra ?? 0) > 0)
        .map((f) => (
          <div key={f.name} className="wiz-grid wiz-review-ids">
            <div className="wiz-label mono">{f.name}</div>
            <div className="mono">{f.id_column}</div>
            <IdCheck projectId={projectId} data={data} file={f} change={change} />
          </div>
        ))}
      <h3 className="wiz-sub">{w.problems}</h3>
      {data.problems.length ? (
        <ul className="wiz-problems">
          {data.problems.map((p) => (
            <li key={p} className="wiz-warn">
              {p}
            </li>
          ))}
        </ul>
      ) : (
        <p className="wiz-ok">✓ {w.noProblems}</p>
      )}
      {data.warnings.length > 0 && (
        <>
          <h3 className="wiz-sub">{w.warnings}</h3>
          <ul className="wiz-problems">
            {data.warnings.map((p) => (
              <li key={p} className="wiz-warn">
                {p}
              </li>
            ))}
          </ul>
        </>
      )}
      <table className="wiz-review">
        <tbody>
          {groups.map((s) => {
            const rows = data.fields.filter(
              (f) => f.step === s.key && (f.sources.length > 0 || f.assumed || required.has(f.key)),
            );
            if (rows.length === 0) return null;
            return [
              <tr key={s.key} className="wiz-review-head">
                <th colSpan={3}>
                  {s.parent ? `${w.steps[s.parent]?.title} › ` : ""}
                  {w.steps[s.key]?.title}
                </th>
              </tr>,
              ...rows.map((f) => (
                <tr key={f.key}>
                  <td>{shortName(f)}</td>
                  <td className={f.sources.length ? "mono" : "wiz-none"}>
                    {f.assumed
                      ? `${w.assumed}: ${w.assumedValue[f.key]}`
                      : f.sources.map((x) => w.from(x.column, x.file)).join("; ") || w.nothing}
                  </td>
                  <td>
                    <Button className="wiz-link" onPress={() => go(s.key)}>
                      {w.change}
                    </Button>
                  </td>
                </tr>
              )),
            ];
          })}
        </tbody>
      </table>
    </>
  );
}

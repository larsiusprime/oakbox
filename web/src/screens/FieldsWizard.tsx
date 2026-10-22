import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import {
  Button,
  Dialog,
  Header,
  Heading,
  ListBox,
  ListBoxItem,
  ListBoxSection,
  Modal,
  ModalOverlay,
  Popover,
  Select,
  SelectValue,
} from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type Project,
  type ProjectDetail,
  unwrap,
  type Wizard,
  type WizardCheck,
  type WizardField,
  type WizardFile,
  type WizardStep,
} from "../api/client";
import warningIcon from "../assets/noto/emoji_u26a0.svg";
import { Choice } from "../components/Form";
import { TipOn } from "../components/Tip";
import { desktop, useCanPickFile } from "../desktop";
import { t } from "../strings";
import { AddFile } from "./InputFiles";

const w = t.wizard;
type Holds = "parcels" | "sales" | "unused";
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
  const [opening] = useState(() => flat.find((s) => s.status === "todo")?.key ?? "review");
  const wanted = step === "details" ? "big_five" : step;
  const current = flat.find((s) => s.key === wanted) ?? flat.find((s) => s.key === opening) ?? flat[0];
  const change = useChange(projectId);
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
  const skippable = current.fields.length > 0 && !current.sales;

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
          {current.key === "review" && <ReviewStep data={data} go={go} />}
          {current.fields.length > 0 && (current.key !== "sales" || data.sale_id.file) && (
            <FieldsStep project={project} data={data} step={current} change={change.mutateAsync} />
          )}
          {change.error && (
            <p className="error" role="alert">
              {change.error.message}
            </p>
          )}
        </div>
        <div className="wiz-foot">
          <TipOn text={w.advancedTip}>
            <a className="wiz-link" href={`#/projects/${projectId}/files`}>
              {w.advanced}
            </a>
          </TipOn>
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
            <Button className="button button-primary" onPress={() => go(next.key)}>
              {current.key === "welcome" ? w.start : w.next}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function StepList({ steps, current, go }: { steps: WizardStep[]; current: string; go: (k: string) => void }) {
  const tops = steps.filter((s) => !s.parent);
  return (
    <ol className="wiz-steps">
      {steps.map((s) => {
        const n = tops.indexOf(s) + 1;
        const mark = s.status === "done" ? "✓" : s.status === "skipped" ? "–" : s.parent ? "" : String(n);
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
                {mark}
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
  | { kind: "skip"; step: string }
  | {
      kind: "file";
      name: string;
      holds?: Holds;
      universe?: boolean;
      match?: "key" | "key2";
      id_column?: string;
      key2_column?: string | null;
      key2_set?: boolean;
    }
  | { kind: "saleId"; column: string | null; make: boolean }
  | { kind: "field"; key: string; file?: string | null; column?: string | null; assume?: boolean };

function useChange(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (c: Change): Promise<Wizard> => {
      const project_id = projectId;
      if (c.kind === "visit" || c.kind === "skip") {
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
              key2_column: null,
              key2_set: false,
              ...body,
            },
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
      return unwrap(
        await api.PUT("/api/projects/{project_id}/wizard/fields/{key}", {
          params: { path: { project_id, key: c.key } },
          body: { file: c.file ?? null, column: c.column ?? null, assume: c.assume ?? false },
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

type Mutate = (c: Change, options?: { onSuccess?: () => void }) => void;
type MutateAsync = (c: Change) => Promise<Wizard>;

// ---------- Welcome, parcel universe, sales ----------

function CheckText({ check }: { check: WizardCheck | null | undefined }) {
  if (!check) return null;
  return <span className={check.ok ? "wiz-ok" : "wiz-warn"}>{check.text}</span>;
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
function FilePicker({
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

function FileHeader({ file, onReplace }: { file: WizardFile; onReplace: () => void }) {
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
        <div className="wiz-samples">
          <CheckText check={base.id_check} />
        </div>
        <div className="wiz-label">
          <TipOn text={w.secondIdTip}>
            <span>{w.secondId}</span>
          </TipOn>
        </div>
        <Choice
          label={w.secondId}
          hideLabel
          value={base.key2_column ?? NONE}
          options={[[NONE, w.none] as const, ...columns]}
          onChange={(v) =>
            change({ kind: "file", name: base.name, key2_column: v === NONE ? null : v, key2_set: true })
          }
        />
        <div />
      </div>
    </>
  );
}

function SalesStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const sales = data.files.find((f) => f.holds === "sales");
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
      <IdRow file={sales} base={base} change={change} />
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

/** A file's ID column, and whether it matches the universe's parcel ID or its second ID. */
function IdRow({ file, base, change }: { file: WizardFile; base: WizardFile | undefined; change: Mutate }) {
  const canKey2 = Boolean(base?.key2_column);
  return (
    <div className="wiz-grid">
      <div className="wiz-label">{canKey2 ? w.matchBy : w.parcelId}</div>
      <div className="wiz-pair">
        {canKey2 && (
          <Choice
            label={w.matchBy}
            hideLabel
            value={file.match}
            options={[
              ["key", w.matchKey],
              ["key2", w.matchKey2],
            ]}
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
      <div className="wiz-samples">
        <CheckText check={file.id_check} />
      </div>
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
  const shown = mine.filter((f) => !f.more || more);
  const hasMore = mine.some((f) => f.more);
  return (
    <>
      <div className="wiz-grid">
        {groupsFor(step.key, shown).map(([title, fields]) => [
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
            />
          )),
        ])}
      </div>
      {hasMore && (
        <Button className="wiz-more" onPress={() => setMore(!more)}>
          {more ? w.fewer : w.more}
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

function FieldRow({
  project,
  data,
  field,
  sales,
  change,
}: {
  project: Project;
  data: Wizard;
  field: WizardField;
  sales: boolean;
  change: MutateAsync;
}) {
  const [confirming, setConfirming] = useState(false);
  const [elsewhere, setElsewhere] = useState(false);
  const files = data.files.filter((f) => f.holds === (sales ? "sales" : "parcels"));
  const source = field.sources[0];
  const value = field.assumed ? ASSUME : source ? `${source.file}\u0000${source.column}` : NONE;
  const column =
    source && files.find((f) => f.name === source.file)?.columns.find((c) => c.name === source.column);
  const pick = (v: string) => {
    if (v === ASSUME) setConfirming(true);
    else if (v === ELSEWHERE) setElsewhere(true);
    else if (v === NONE) void change({ kind: "field", key: field.key }).catch(() => {});
    else {
      const [file, col] = v.split("\u0000");
      void change({ kind: "field", key: field.key, file: file ?? null, column: col ?? null }).catch(() => {});
    }
  };
  return (
    <>
      <div className="wiz-label">
        <TipOn text={field.description || field.name}>
          <span>{shortName(field)}</span>
        </TipOn>
        {w.hints[field.key] && <small>{w.hints[field.key]}</small>}
      </div>
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
      <div className="wiz-samples">
        {field.assumed ? (
          <span className="wiz-warn">
            {w.assumed}: {w.assumedValue[field.key]}
          </span>
        ) : (
          <>
            <CheckText check={field.check} />
            {column && column.samples.length > 0 && (
              <span className="wiz-sample-values">
                {field.check ? " · " : ""}
                {column.samples.join(", ")}
              </span>
            )}
          </>
        )}
      </div>
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

/** The dictionary's name, without "Building" for building fields ("Year built"). */
function shortName(field: WizardField): string {
  if (!field.key.startsWith("bldg_")) return field.name;
  const rest = field.name.replace(/^Building /, "");
  return rest.charAt(0).toUpperCase() + rest.slice(1);
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
      if (as && as !== field.key) disabled.push(`${f.name}\u0000${c.name}`);
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
                const taken = as && as !== field.key;
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
  const [match, setMatch] = useState<"key" | "key2">("key");
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
              {base?.key2_column && (
                <>
                  <div className="wiz-label">{w.matchBy}</div>
                  <Choice
                    label={w.matchBy}
                    hideLabel
                    value={match}
                    options={[
                      ["key", w.matchKey],
                      ["key2", w.matchKey2],
                    ]}
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

function ReviewStep({ data, go }: { data: Wizard; go: (k: string) => void }) {
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

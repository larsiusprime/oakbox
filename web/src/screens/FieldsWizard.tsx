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
import { t } from "../strings";

const w = t.wizard;
type Holds = "parcels" | "sales" | "unused";
// Fields with no column that can instead be assumed, after a warning (SPEC F3d).
const ASSUMABLE = ["valid_sale", "vacant_sale"];
const NONE = "__none";
const ASSUME = "__assume";
const MAKE = "__make";

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
  if (detail.files.length === 0) return <p className="empty">{w.noFiles}</p>;
  if (wizard.isPending) return <p className="empty">{w.loading}</p>;
  if (wizard.error) return <p className="error">{wizard.error.message}</p>;
  return <WizardView projectId={projectId} data={wizard.data} step={step} />;
}

/** Steps in the order Next goes through them: Building's parts, not Building itself. */
function order(steps: WizardStep[]): WizardStep[] {
  return steps.filter((s) => s.key !== "building");
}

function WizardView({ projectId, data, step }: { projectId: string; data: Wizard; step: string | null }) {
  const flat = order(data.steps);
  // Opens at the first step not done yet, or at Review (SPEC F3d).
  const [opening] = useState(() => flat.find((s) => s.status === "todo")?.key ?? "review");
  const wanted = step === "building" ? "building_basics" : step;
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
          {current.key === "files" && <FilesStep data={data} change={change.mutate} />}
          {current.key === "shapes" && <ShapesStep data={data} />}
          {current.key === "review" && <ReviewStep data={data} go={go} />}
          {current.fields.length > 0 && <FieldsStep data={data} step={current} change={change.mutate} />}
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
              {w.next}
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
              onClick={() => go(s.key === "building" ? "building_basics" : s.key)}
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
            body: { holds: null, id_column: null, key2_column: null, key2_set: false, ...body },
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

// ---------- Step 1: Your files ----------

function CheckText({ check }: { check: WizardCheck | null | undefined }) {
  if (!check) return null;
  return <span className={check.ok ? "wiz-ok" : "wiz-warn"}>{check.text}</span>;
}

function FilesStep({ data, change }: { data: Wizard; change: Mutate }) {
  const holdsOptions = Object.entries(w.holdsOptions) as [Holds, string][];
  return (
    <>
      <table className="wiz-table">
        <thead>
          <tr>
            <th>{w.file}</th>
            <th>{w.rows}</th>
            <th>{w.holds}</th>
            <th>{w.idColumn}</th>
            <th>
              <TipOn text={w.key2Tip}>
                <span>{w.key2}</span>
              </TipOn>
            </th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data.files.map((f) => (
            <tr key={f.name}>
              <td className="mono">
                {f.name}
                {f.base && <span className="wiz-base"> {w.base}</span>}
              </td>
              <td className="num">{f.rows?.toLocaleString() ?? ""}</td>
              {f.problem ? (
                <td colSpan={4} className="wiz-warn">
                  {w.unreadable(f.problem)}
                </td>
              ) : (
                <>
                  <td>
                    <Choice
                      label={w.holdsFor(f.name)}
                      hideLabel
                      value={f.holds}
                      placeholder={w.choose}
                      options={holdsOptions}
                      onChange={(holds) => change({ kind: "file", name: f.name, holds })}
                    />
                  </td>
                  <td>
                    <Choice
                      label={w.idFor(f.name)}
                      hideLabel
                      value={f.id_column}
                      placeholder={w.choose}
                      options={f.columns.map((c) => [c.name, c.name] as const)}
                      onChange={(id_column) => change({ kind: "file", name: f.name, id_column })}
                    />
                  </td>
                  <td>{f.holds === "parcels" && <Key2 file={f} change={change} />}</td>
                  <td className="wiz-check">
                    <CheckText check={f.id_check} />
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {data.sale_id.file && <SaleIdRow data={data} change={change} />}
      <p className="wiz-note">{w.baseNote}</p>
    </>
  );
}

function Key2({ file, change }: { file: WizardFile; change: Mutate }) {
  const options = [[NONE, w.none] as const, ...file.columns.map((c) => [c.name, c.name] as const)];
  return (
    <Choice
      label={w.key2For(file.name)}
      hideLabel
      value={file.key2_column ?? NONE}
      options={options}
      onChange={(v) =>
        change({ kind: "file", name: file.name, key2_column: v === NONE ? null : v, key2_set: true })
      }
    />
  );
}

function SaleIdRow({ data, change }: { data: Wizard; change: Mutate }) {
  const sales = data.files.find((f) => f.name === data.sale_id.file);
  const options = [
    [MAKE, w.makeSaleId] as const,
    ...(sales?.columns ?? []).map((c) => [c.name, c.name] as const),
  ];
  const value = data.sale_id.made ? MAKE : data.sale_id.column;
  return (
    <>
      <h3 className="wiz-sub">{w.saleIdTitle}</h3>
      <div className="wiz-grid">
        <div className="wiz-label">
          <span className="mono">{data.sale_id.file}</span>
          <small>{w.saleIdColumn}</small>
        </div>
        <Choice
          label={w.saleIdColumn}
          hideLabel
          value={value}
          placeholder={w.choose}
          options={options}
          onChange={(v) => change({ kind: "saleId", column: v === MAKE ? null : v, make: v === MAKE })}
        />
        <div className="wiz-samples">
          <CheckText check={data.sale_id.check} />
        </div>
      </div>
    </>
  );
}

// ---------- Step 2: Shapes ----------

function ShapesStep({ data }: { data: Wizard }) {
  const base = data.files.find((f) => f.base);
  return base ? (
    <p className="wiz-ok">✓ {w.shapesFrom(base.name, base.filename)}</p>
  ) : (
    <p className="wiz-warn">{w.noShapes}</p>
  );
}

// ---------- Steps 3 to 8: one topic at a time ----------

function FieldsStep({ data, step, change }: { data: Wizard; step: WizardStep; change: Mutate }) {
  const [more, setMore] = useState(false);
  const mine = data.fields.filter((f) => f.step === step.key && !f.hidden);
  const shown = mine.filter((f) => !f.more || more);
  const hasMore = mine.some((f) => f.more);
  return (
    <>
      <div className="wiz-grid">
        {shown.map((f) => (
          <FieldRow key={f.key} data={data} field={f} sales={step.sales} change={change} />
        ))}
      </div>
      {hasMore && (
        <Button className="wiz-more" onPress={() => setMore(!more)}>
          {more ? w.fewer : w.more}
        </Button>
      )}
    </>
  );
}

function FieldRow({
  data,
  field,
  sales,
  change,
}: {
  data: Wizard;
  field: WizardField;
  sales: boolean;
  change: Mutate;
}) {
  const [confirming, setConfirming] = useState(false);
  const files = data.files.filter((f) => f.holds === (sales ? "sales" : "parcels"));
  const source = field.sources[0];
  const value = field.assumed ? ASSUME : source ? `${source.file}\u0000${source.column}` : NONE;
  const column =
    source && files.find((f) => f.name === source.file)?.columns.find((c) => c.name === source.column);
  const pick = (v: string) => {
    if (v === ASSUME) setConfirming(true);
    else if (v === NONE) change({ kind: "field", key: field.key });
    else {
      const [file, col] = v.split("\u0000");
      change({ kind: "field", key: field.key, file: file ?? null, column: col ?? null });
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
            change({ kind: "field", key: field.key, assume: true });
          }}
        />
      )}
    </>
  );
}

/** The dictionary's name, without "Building" inside the Building steps ("Year built"). */
function shortName(field: WizardField): string {
  if (!field.step.startsWith("building_")) return field.name;
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
  onChange,
}: {
  field: WizardField;
  files: WizardFile[];
  used: Wizard["used"];
  names: Record<string, string>;
  value: string;
  many: boolean;
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

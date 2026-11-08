import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import {
  api,
  type Condition,
  type NumberFormat,
  type Project,
  type Rule,
  unwrap,
  type Wizard,
  type WizardField,
  type WizardFile,
  type WizardStep,
} from "../api/client";
import { AddButton } from "../components/AddButton";
import { Choice, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { RemoveButton } from "../components/RemoveButton";
import { Val } from "../components/Val";
import { amount, num, pct } from "../lib/format";
import { useOnSettled, useSettled } from "../lib/hooks";
import { say, t } from "../wording";
import { FieldHistogram } from "./FieldHistogram";
import { FieldRow } from "./FieldRow";
import { ruleComplete } from "./FieldRules";
import type { MutateAsync } from "./wizardChange";

/* Sales' field parts (SPEC F3d, revised 2026-11-05): each field on a page of its own, how it's read and checked
   laid out under it, live, and saved as it's changed: no dialogs, no Save or Cancel. */

const r = t.wizard.rule;
const d = t.wizard.dates;
const n = t.wizard.numbers;
const sp = t.wizard.salesParts;
type Op = Condition["op"];
const LISTS: Op[] = ["isin", "notin"];
const NO_VALUE: Op[] = ["isempty", "notempty"];
const SCALES = [1, 1000, 1_000_000, 0.01];
const CUSTOM = "__custom";

function mainSales(data: Wizard): WizardFile | undefined {
  return data.files.find((f) => f.holds === "sales" && f.match !== "key_sale");
}

export function SalesFieldPage({
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
  const field = data.fields.find((f) => f.step === step.key && !f.hidden);
  const sales = mainSales(data);
  if (!field) return null;
  if (!sales) return <p className="wiz-note">{sp.noFile}</p>;
  const source = field.sources[0];
  const file = source ? data.files.find((f) => f.name === source.file) : undefined;
  const column = file && source ? file.columns.find((c) => c.name === source.column) : undefined;
  const save = (patch: { number_format?: NumberFormat; date_format?: string }) =>
    source &&
    void change({ kind: "field", key: field.key, file: source.file, column: source.column, ...patch }).catch(
      () => {},
    );
  const dated = field.key === "sale_date" && !!file && !!column && column.type !== "date";
  return (
    <>
      <div className="wiz-grid wiz-capsules">
        <div className="frame wiz-capsule">
          <FieldRow project={project} data={data} field={field} sales change={change} bare paged />
          {field.key === "sale_price" && file && column && (
            <NumberOptions
              projectId={project.id}
              field={field}
              file={file}
              column={column.name}
              save={save}
            />
          )}
          {dated && file && column && (
            <DateOptions projectId={project.id} field={field} file={file} column={column.name} save={save} />
          )}
        </div>
      </div>
      {field.key === "sale_price" && file && column && (
        <NumberPreview projectId={project.id} field={field} file={file} column={column.name} save={save} />
      )}
      {dated && file && column && (
        <DatePreview projectId={project.id} field={field} file={file} column={column.name} save={save} />
      )}
      {field.rule && file && (
        <RulePanel
          // A new column starts a new rule: the page starts again from it.
          key={`${source?.column}`}
          projectId={project.id}
          field={field}
          file={file}
          price={data.fields.find((f) => f.key === "sale_price")}
          change={change}
        />
      )}
    </>
  );
}

// ---------- Sale price ----------

function useNumbers(projectId: string, field: WizardField, file: WizardFile, column: string) {
  const format = field.number_format ?? null;
  return useQuery({
    queryKey: ["numbers", projectId, file.name, field.key, column, format],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/files/{name}/numbers", {
          params: { path: { project_id: projectId, name: file.name } },
          body: { key: field.key, column, format },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

type Save = (patch: { number_format?: NumberFormat; date_format?: string }) => void;

/** How the amounts are read, as rows of the field's capsule: the decimal mark, the scale, K and M. */
function NumberOptions({
  projectId,
  field,
  file,
  column,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  column: string;
  save: Save;
}) {
  const v = useNumbers(projectId, field, file, column).data;
  const shown = field.number_format ?? v?.format ?? null;
  if (!shown) return null;
  const set = (patch: Partial<NumberFormat>) => save({ number_format: { ...shown, ...patch } });
  const scales = SCALES.includes(shown.scale) ? SCALES : [...SCALES, shown.scale];
  return (
    <>
      <div className="wiz-label">{n.decimal}</div>
      <Choice
        label={n.decimal}
        hideLabel
        value={shown.decimal}
        options={(Object.entries(n.decimals) as [NumberFormat["decimal"], string][]).map(
          ([k, x]) => [k, cap(x)] as const,
        )}
        onChange={(decimal) => set({ decimal })}
      />
      <span />
      <div className="wiz-label">{n.scale}</div>
      <Choice
        label={n.scale}
        hideLabel
        value={String(shown.scale)}
        options={scales.map((s) => [String(s), cap(say.wizard.numbers.scales(s))] as const)}
        onChange={(s) => set({ scale: Number(s) })}
      />
      <span />
      <span />
      <Tick isSelected={shown.suffixes} onChange={(suffixes) => set({ suffixes })}>
        {n.suffixes}
      </Tick>
      <span />
    </>
  );
}

/** The amounts as read: how many, their spread, a scale that looks wrong, and samples. */
function NumberPreview({
  projectId,
  field,
  file,
  column,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  column: string;
  save: Save;
}) {
  const q = useNumbers(projectId, field, file, column);
  const v = q.data;
  if (!v) return null;
  const shown = field.number_format ?? v.format;
  const good = v.read > 0 && v.failed === 0 && !v.hint;
  return (
    <div className="frame qc-panel">
      <h3 className="wiz-group">{sp.asRead}</h3>
      <div className={`rc-meter ${good ? "ok" : "bad"}`}>
        <b>
          {good ? "✓ " : "⚠ "}
          {v.median != null && v.low != null && v.high != null
            ? n.spread({
                median: amount(v.symbol, v.median),
                low: amount(v.symbol, v.low),
                high: amount(v.symbol, v.high),
              })
            : n.read({ read: v.read, total: v.total - v.blank })}
        </b>
      </div>
      <p className="rc-sub">
        {[
          n.read({ read: v.read, total: v.total - v.blank }),
          v.blank ? n.blank({ n: v.blank }) : null,
          v.failed ? n.failed({ n: v.failed }) : null,
        ]
          .filter(Boolean)
          .join(" · ")}
        {!v.hint && v.assessed != null && v.assessed_field
          ? ` · ${say.wizard.numbers.assessed(v.assessed, v.assessed_field)}`
          : ""}
      </p>
      {v.guessed && <p className="rc-sub">{n.guessed}</p>}
      {v.hint && shown && (
        <p className="rc-suggest">
          <b>{v.hint.reason}</b>{" "}
          <Button
            className="button button-small"
            onPress={() => save({ number_format: { ...shown, scale: v.hint?.scale ?? 1 } })}
          >
            {n.readAs({ s: say.wizard.numbers.scales(v.hint.scale) })}
          </Button>
        </p>
      )}
      {v.excel > 0 && <p className="rc-suggest nm-warn">{n.excel({ n: v.excel })}</p>}
      <table className="tbl">
        <thead>
          <tr>
            <th>{n.asIs}</th>
            <th>{n.asRead}</th>
          </tr>
        </thead>
        <tbody>
          {v.samples.map((s) => (
            <tr key={s.raw}>
              <td className="mono">{s.raw}</td>
              <td className="mono">
                {s.read != null ? (
                  s.read.toLocaleString(undefined, { maximumFractionDigits: 2 })
                ) : (
                  <span className="rc-miss">{n.notRead}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {/* How the prices spread, as read: in this box, under the samples ($10 deeds and portfolio sales at the ends,
          the range set live). */}
      <FieldHistogram projectId={projectId} field={field} sales bare />
    </div>
  );
}

// ---------- Sale date ----------

function useDates(projectId: string, field: WizardField, file: WizardFile, column: string) {
  const guessed = file.columns.find((c) => c.name === column)?.date_format ?? "%Y-%m-%d";
  const format = field.date_format ?? guessed;
  return {
    format,
    query: useQuery({
      queryKey: ["dates", projectId, file.name, column, format],
      queryFn: async () =>
        unwrap(
          await api.POST("/api/projects/{project_id}/wizard/files/{name}/dates", {
            params: { path: { project_id: projectId, name: file.name } },
            body: { column, format },
          }),
        ),
      placeholderData: keepPreviousData,
    }),
  };
}

/** The format the dates are written in: a row of the field's capsule, every format in its list. */
function DateOptions({
  projectId,
  field,
  file,
  column,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  column: string;
  save: Save;
}) {
  const { format, query } = useDates(projectId, field, file, column);
  const formats = query.data?.formats ?? [];
  const known = formats.length === 0 || formats.some((f) => f.format === format);
  const [custom, setCustom] = useState(!known);
  const [typed, setTyped] = useState(format);
  useOnSettled(typed, (x) => {
    if (custom && x && x !== format) save({ date_format: x });
  });
  return (
    <>
      <div className="wiz-label">{sp.writtenAs}</div>
      <Choice
        label={sp.writtenAs}
        hideLabel
        value={custom ? CUSTOM : format}
        options={[
          ...formats.map((f) => [f.format, `${f.words} (${f.format})`] as const),
          [CUSTOM, d.custom] as const,
        ]}
        onChange={(x) => {
          setCustom(x === CUSTOM);
          if (x !== CUSTOM) save({ date_format: x });
        }}
      />
      <span />
      {custom && (
        <>
          <div className="wiz-label">{d.customLabel}</div>
          <TextField aria-label={d.customLabel} value={typed} onChange={setTyped}>
            <Input className="input" />
          </TextField>
          <span />
        </>
      )}
    </>
  );
}

/** The dates as read: how many, their range, other formats that also read, samples, and sales by year. */
function DatePreview({
  projectId,
  field,
  file,
  column,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  column: string;
  save: Save;
}) {
  const v = useDates(projectId, field, file, column).query.data;
  if (!v) return null;
  const good = v.read > 0 && v.failed === 0;
  const top = Math.max(1, ...v.by_year.map((y) => y.count));
  return (
    <div className="frame qc-panel">
      <h3 className="wiz-group">{sp.asRead}</h3>
      <div className={`rc-meter ${good ? "ok" : "bad"}`}>
        <b>
          {good ? "✓ " : "⚠ "}
          {d.read({ read: v.read, total: v.total - v.blank })}
          {v.first && v.last ? ` · ${d.range({ a: v.first, b: v.last })}` : ""}
        </b>
        <span className="rc-was">
          {[v.failed ? d.failed({ n: v.failed }) : null, v.blank ? d.blank({ n: v.blank }) : null]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>
      {v.also.length > 0 && (
        <p className="rc-suggest">
          <b>{d.also}</b>{" "}
          {v.also.map((a, i) => (
            <span key={a.format}>
              {i > 0 && ", "}
              {a.words}{" "}
              <Button className="button button-small" onPress={() => save({ date_format: a.format })}>
                {d.useIt}
              </Button>
            </span>
          ))}
        </p>
      )}
      <table className="tbl">
        <thead>
          <tr>
            <th>{d.asIs}</th>
            <th>{d.asRead}</th>
          </tr>
        </thead>
        <tbody>
          {v.samples.map((s) => (
            <tr key={s.raw}>
              <td className="mono">{s.raw}</td>
              <td className="mono">{s.read ?? <span className="rc-miss">{d.notRead}</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {v.by_year.length > 0 && (
        <>
          <h3 className="wiz-group">{sp.byYear}</h3>
          {/* A bar per year, its count on top, the most recent first: how the sales spread over time. */}
          <div className="yr-hist" role="img" aria-label={sp.byYear}>
            {[...v.by_year].reverse().map((y) => (
              <div key={y.year} className="yr-col">
                <span className="yr-n">{num(y.count)}</span>
                <span className="yr-bar" style={{ height: `${(8 * y.count) / top}rem` }} />
                <span className="yr-x">{y.year}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------- Valid sale, vacant sale ----------

function Mini({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <TextField aria-label={label} value={value} onChange={onChange} className="rl-mini">
      <Input className="input rl-input" />
    </TextField>
  );
}

/** Which values mean yes: "A sale is valid if [All of these] are true", its conditions, and what it picks. */
function RulePanel({
  projectId,
  field,
  file,
  price,
  change,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  price?: WizardField | undefined;
  change: MutateAsync;
}) {
  const start = field.sources[0]?.column ?? file.columns[0]?.name ?? "";
  const [rule, setRule] = useState<Rule>(
    field.rule ?? { join: "all", conditions: [{ column: start, op: "isin", values: [] }] },
  );
  const asked = useSettled(rule);
  // Saved once it settles, even left without values (cleared): the page then says what's missing.
  useOnSettled(rule, (x) => {
    if (JSON.stringify(x) !== JSON.stringify(field.rule ?? null))
      void change({ kind: "rule", key: field.key, rule: x }).catch(() => {});
  });
  const preview = useQuery({
    queryKey: ["rule", projectId, field.key, asked],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/fields/{key}/rule", {
          params: { path: { project_id: projectId, key: field.key } },
          body: asked,
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = preview.data;
  const complete = ruleComplete(rule);
  const word = r.word[field.key] ?? r.yes;
  const set = (i: number, patch: Partial<Condition>) =>
    setRule({ ...rule, conditions: rule.conditions.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const columns = file.columns.map((c) => [c.name, c.name] as const);
  const priceColumn =
    field.key === "valid_sale" ? price?.sources.find((s) => s.file === file.name)?.column : undefined;
  const prices = useQuery({
    queryKey: ["numbers", projectId, file.name, "sale_price", priceColumn, price?.number_format ?? null],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/files/{name}/numbers", {
          params: { path: { project_id: projectId, name: file.name } },
          body: { key: "sale_price", column: priceColumn ?? "" },
        }),
      ),
    enabled: !!priceColumn,
  });
  const p = prices.data;
  const priced = !!priceColumn && rule.conditions.some((c) => c.column === priceColumn);
  const ops = Object.entries(r.ops) as [Op, string][];
  return (
    <>
      {/* The logic, in a box of its own: its head says how the conditions combine; each condition a white row. */}
      <div className="entry rl-env">
        <div className="entry-head rl-env-head">
          <span>{sp.ruleIf({ word })}</span>
          <Choice
            label={sp.ruleIf({ word })}
            hideLabel
            value={rule.join}
            options={[
              ["all", sp.allOf],
              ["any", sp.anyOf],
            ]}
            onChange={(join) => setRule({ ...rule, join })}
          />
          <span>{sp.areTrue}</span>
        </div>
        <div className="entry-body">
          <ol className="rl-conds">
            {rule.conditions.map((c, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: conditions have no id; their place is what they are
              <li key={i} className="rl-cond">
                <Choice
                  label={r.column}
                  hideLabel
                  value={c.column}
                  options={columns}
                  onChange={(column) => set(i, { column, values: [] })}
                />
                <Choice
                  label={r.op}
                  hideLabel
                  value={c.op}
                  options={ops}
                  onChange={(op) =>
                    set(i, { op, values: LISTS.includes(op) === LISTS.includes(c.op) ? c.values : [] })
                  }
                />
                {LISTS.includes(c.op) ? (
                  <MultiPick
                    label={r.value}
                    values={v?.values[c.column] ?? []}
                    more={v?.more[c.column] ?? 0}
                    chosen={c.values}
                    onChange={(values) => set(i, { values })}
                    countNoun={r.countRows}
                  />
                ) : NO_VALUE.includes(c.op) ? (
                  <span />
                ) : (
                  <Mini
                    label={r.value}
                    value={c.values[0] ?? ""}
                    onChange={(x) => set(i, { values: x ? [x] : [] })}
                  />
                )}
                {rule.conditions.length > 1 ? (
                  <RemoveButton
                    what={t.buttons.theTest}
                    label={sp.removeCondition}
                    onPress={() =>
                      setRule({ ...rule, conditions: rule.conditions.filter((_, j) => j !== i) })
                    }
                    undo={() => setRule(rule)}
                  />
                ) : (
                  <span />
                )}
              </li>
            ))}
          </ol>
          <div className="form-actions">
            {field.key === "valid_sale" && !priced && (
              <AddButton
                isDisabled={!priceColumn}
                onPress={() =>
                  priceColumn &&
                  setRule({
                    ...rule,
                    conditions: [...rule.conditions, { column: priceColumn, op: ">=", values: ["1000"] }],
                  })
                }
              >
                {r.addPrice({ amount: p ? amount(p.symbol, 1000) : "1,000" })}
              </AddButton>
            )}
            <AddButton
              onPress={() =>
                setRule({
                  ...rule,
                  conditions: [...rule.conditions, { column: start, op: "isin", values: [] }],
                })
              }
            >
              {sp.addCondition}
            </AddButton>
          </div>
        </div>
      </div>
      <div className="frame qc-panel">
        <h3 className="wiz-group">{sp.picks}</h3>
        <div className={`rc-meter ${complete && v && v.yes > 0 && v.yes < v.total ? "ok" : "bad"}`}>
          <b>
            {complete && v
              ? `✓ ${r.meter({ yes: v.yes, total: v.total, word, pct: v.total ? pct(v.yes / v.total) : "0%" })}`
              : `⚠ ${r.incomplete}`}
          </b>
        </div>
        {field.key === "valid_sale" && (
          <p className="rc-sub">
            {!priceColumn
              ? r.noPrice
              : p && p.zero + p.nominal + p.negative > 0
                ? r.priceCounts({
                    column: priceColumn,
                    counts: [
                      p.zero ? r.zero({ n: p.zero }) : null,
                      p.nominal ? r.nominal({ n: p.nominal, amount: amount(p.symbol, 1000) }) : null,
                      p.negative ? r.negative({ n: p.negative }) : null,
                    ]
                      .filter(Boolean)
                      .join(", "),
                  })
                : null}
          </p>
        )}
        {complete && v && v.rows.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                {v.columns.map((c) => (
                  <th key={c}>{v.as_read.includes(c) ? r.asRead({ column: c }) : c}</th>
                ))}
                <th>{r.result}</th>
              </tr>
            </thead>
            <tbody>
              {v.rows.map((row, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: sample rows, shown once
                <tr key={i}>
                  {row.cells.map((cell, j) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: a row's cells, by column
                    <td key={j} className="mono">
                      {cell.trim() ? <Val v={cell} /> : <span className="rc-dim">{r.blank}</span>}
                    </td>
                  ))}
                  <td>
                    {row.yes ? (
                      <span className="rc-hit">✓ {word}</span>
                    ) : (
                      <span className="rc-dim">{r.no}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {preview.error && (
          <p className="error" role="alert">
            {preview.error.message}
          </p>
        )}
      </div>
    </>
  );
}

/** "in thousands (× 1,000)" as an option: its first letter capital. */
function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

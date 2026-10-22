import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Dialog, Heading, Input, Modal, ModalOverlay, TextField } from "react-aria-components";
import { api, type Condition, type Rule, unwrap, type WizardField, type WizardFile } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { t } from "../strings";

const r = t.wizard.rule;
const d = t.wizard.dates;
type Op = Condition["op"];
const LISTS: Op[] = ["isin", "notin"];
const NO_VALUE: Op[] = ["isempty", "notempty"];

/** Every test has what it needs: a value, or (lists) at least one. */
export function ruleComplete(rule: Rule): boolean {
  return (
    rule.conditions.length > 0 && rule.conditions.every((c) => NO_VALUE.includes(c.op) || c.values.length > 0)
  );
}

/** Waits for typing to stop before asking the server again. */
function useSettled<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return settled;
}

function pct(n: number, total: number): string {
  if (!total) return "0%";
  const p = (100 * n) / total;
  return (p > 0 && p < 1) || (p > 99 && p < 100) ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

function Mini({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <TextField aria-label={label} value={value} onChange={onChange} className="rl-mini">
      <Input className="input rl-input" />
    </TextField>
  );
}

/** F3d: a yes/no field (valid sale, vacant sale) from the sales file's columns, as OpenAVMKit's ["?", filter]. */
export function RuleDialog({
  projectId,
  field,
  file,
  close,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  close: () => void;
  save: (rule: Rule) => void;
}) {
  const start = field.sources[0]?.column ?? file.columns[0]?.name ?? "";
  const [rule, setRule] = useState<Rule>(
    field.rule ?? { join: "all", conditions: [{ column: start, op: "isin", values: [] }] },
  );
  const asked = useSettled(rule);
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
  const ops = Object.entries(r.ops) as [Op, string][];

  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rl">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {r.title[field.key] ?? r.titleFor(field.name)}
          </Heading>
          <p className="rc-sub">{r.lede}</p>
          <div className={`rc-meter ${complete && v && v.yes > 0 && v.yes < v.total ? "ok" : "bad"}`}>
            <b>{complete && v ? r.meter(v.yes, v.total, word, pct(v.yes, v.total)) : r.incomplete}</b>
          </div>
          {rule.conditions.length > 1 && (
            <div className="rl-join">
              <span>{r.where}</span>
              <Choice
                label={r.where}
                hideLabel
                value={rule.join}
                options={[
                  ["all", r.all],
                  ["any", r.any],
                ]}
                onChange={(join) => setRule({ ...rule, join })}
              />
            </div>
          )}
          <ol className="rl-tests">
            {rule.conditions.map((c, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: tests have no id; their place is what they are
              <li key={i} className="rc-card">
                <div className="rl-head">
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
                  {rule.conditions.length > 1 && (
                    <Button
                      className="rc-x"
                      aria-label={r.removeTest}
                      onPress={() =>
                        setRule({ ...rule, conditions: rule.conditions.filter((_, j) => j !== i) })
                      }
                    >
                      <X size="0.9em" />
                    </Button>
                  )}
                </div>
                {LISTS.includes(c.op) ? (
                  <ValuePicker
                    values={v?.values[c.column] ?? []}
                    more={v?.more[c.column] ?? 0}
                    chosen={c.values}
                    onChange={(values) => set(i, { values })}
                  />
                ) : NO_VALUE.includes(c.op) ? null : (
                  <Mini
                    label={r.value}
                    value={c.values[0] ?? ""}
                    onChange={(x) => set(i, { values: x ? [x] : [] })}
                  />
                )}
              </li>
            ))}
          </ol>
          <Button
            className="button rc-add"
            onPress={() =>
              setRule({
                ...rule,
                conditions: [...rule.conditions, { column: start, op: "isin", values: [] }],
              })
            }
          >
            {r.addTest}
          </Button>
          {complete && v && v.rows.length > 0 && (
            <table className="rc-tbl rl-rows">
              <thead>
                <tr>
                  {v.columns.map((c) => (
                    <th key={c} className="rc-th">
                      {c}
                    </th>
                  ))}
                  <th className="rc-th">{r.result}</th>
                </tr>
              </thead>
              <tbody>
                {v.rows.map((row, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: sample rows, shown once
                  <tr key={i}>
                    {row.cells.map((cell, j) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: a row's cells, by column
                      <td key={j} className="rc-td">
                        {cell.trim() ? cell : <span className="rc-dim">{r.blank}</span>}
                      </td>
                    ))}
                    <td className="rc-td rc-m">
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
          <details className="rc-writes">
            <summary>{r.writes}</summary>
            <pre>
              {v && v.calc.length > 0
                ? [
                    ...Object.entries(v.load).map(
                      ([f, spec]) => `"load": { "${f}": ${JSON.stringify(spec)} }`,
                    ),
                    `"calc": { "${field.key}": ${JSON.stringify(v.calc)} }`,
                  ].join("\n")
                : r.incomplete}
            </pre>
          </details>
          {preview.error && (
            <p className="error" role="alert">
              {preview.error.message}
            </p>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {r.cancel}
            </Button>
            <Button className="button button-primary" isDisabled={!complete} onPress={() => save(rule)}>
              {r.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** A column's values with how many sales have each: tick the ones the test means. */
function ValuePicker({
  values,
  more,
  chosen,
  onChange,
}: {
  values: { value: string; count: number }[];
  more: number;
  chosen: string[];
  onChange: (v: string[]) => void;
}) {
  const [typed, setTyped] = useState("");
  const listed = new Set(values.map((x) => x.value));
  const extra = chosen.filter((c) => !listed.has(c));
  const toggle = (value: string, on: boolean) =>
    onChange(on ? [...chosen, value] : chosen.filter((c) => c !== value));
  return (
    <div className="rl-values">
      {[...values, ...extra.map((value) => ({ value, count: -1 }))].map((x) => (
        <Tick key={x.value} isSelected={chosen.includes(x.value)} onChange={(on) => toggle(x.value, on)}>
          <span className="rl-value">{x.value || r.blank}</span>
          {x.count >= 0 && <span className="rl-count">{x.count.toLocaleString()}</span>}
        </Tick>
      ))}
      {more > 0 && (
        <form
          className="rl-other"
          onSubmit={(e) => {
            e.preventDefault();
            if (typed.trim() && !chosen.includes(typed)) onChange([...chosen, typed]);
            setTyped("");
          }}
        >
          <small>{r.more(more)}</small>
          <Mini label={r.addValue} value={typed} onChange={setTyped} />
        </form>
      )}
    </div>
  );
}

const CUSTOM = "__custom";

/** F3d: the format a date column is read with, previewed on every row as OpenAVMKit reads it. */
export function DateDialog({
  projectId,
  field,
  file,
  column,
  close,
  save,
}: {
  projectId: string;
  field: WizardField;
  file: WizardFile;
  column: string;
  close: () => void;
  save: (format: string) => void;
}) {
  const guessed = file.columns.find((c) => c.name === column)?.date_format ?? "%Y-%m-%d";
  const [format, setFormat] = useState(field.date_format ?? guessed);
  const asked = useSettled(format);
  const preview = useQuery({
    queryKey: ["dates", projectId, file.name, column, asked],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/wizard/files/{name}/dates", {
          params: { path: { project_id: projectId, name: file.name } },
          body: { column, format: asked },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const v = preview.data;
  const known = v?.formats.some((f) => f.format === format) ?? true;
  const [custom, setCustom] = useState(!known);
  const good = v ? v.read > 0 && v.failed === 0 : false;
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(open) => !open && close()}>
      <Modal className="modal rl">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {d.title(column)}
          </Heading>
          <p className="rc-sub">{d.lede}</p>
          <div className="rl-join">
            <span>{d.format}</span>
            <Choice
              label={d.format}
              hideLabel
              value={custom ? CUSTOM : format}
              options={[
                ...(v?.formats ?? []).map((f) => [f.format, `${f.words}  (${f.format})`] as const),
                [CUSTOM, d.custom] as const,
              ]}
              onChange={(x) => {
                setCustom(x === CUSTOM);
                if (x !== CUSTOM) setFormat(x);
              }}
            />
            {custom && <Mini label={d.customLabel} value={format} onChange={setFormat} />}
          </div>
          {v && (
            <div className={`rc-meter ${good ? "ok" : "bad"}`}>
              <b>
                {good && "✓ "}
                {d.read(v.read, v.total - v.blank)}
              </b>
              <span className="rc-was">
                {[
                  v.first && v.last ? d.range(v.first, v.last) : null,
                  v.failed ? d.failed(v.failed) : null,
                  v.blank ? d.blank(v.blank) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </div>
          )}
          {v && v.also.length > 0 && (
            <p className="rc-suggest">
              <b>{d.also}</b>{" "}
              {v.also.map((a, i) => (
                <span key={a.format}>
                  {i > 0 && ", "}
                  {a.words}{" "}
                  <Button
                    className="wiz-link"
                    onPress={() => {
                      setCustom(false);
                      setFormat(a.format);
                    }}
                  >
                    ({d.useIt})
                  </Button>
                </span>
              ))}
            </p>
          )}
          {v && (
            <table className="rc-tbl">
              <thead>
                <tr>
                  <th className="rc-th">{d.asIs}</th>
                  <th className="rc-th" />
                  <th className="rc-th">{d.asRead}</th>
                </tr>
              </thead>
              <tbody>
                {v.samples.map((s) => (
                  <tr key={s.raw}>
                    <td className="rc-td">{s.raw}</td>
                    <td className="rc-td rc-arrow">→</td>
                    <td className="rc-td">{s.read ?? <span className="rc-miss">✗ {d.notRead}</span>}</td>
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
          <div className="form-actions rc-actions">
            <Button className="button" onPress={close}>
              {d.cancel}
            </Button>
            <Button
              className="button button-primary"
              isDisabled={!v || v.read === 0}
              onPress={() => save(format)}
            >
              {d.save}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

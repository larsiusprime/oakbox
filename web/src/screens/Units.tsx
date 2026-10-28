import { useQuery } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Dialog, DialogTrigger, Input, Popover, TextField } from "react-aria-components";
import { api, type Condition, type Units, unwrap, type Wizard, type WizardFile } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { Seg } from "../components/Seg";
import { t } from "../strings";

const u = t.wizard.units;

export type UnitsChange =
  | { kind: "units"; name: string; units: Units | null; guess?: boolean }
  | { kind: "unitField"; name: string; field: string; column: string | null };

const DEFAULT: Units = {
  rule: null,
  link: "prefix",
  column: null,
  base_column: null,
  prefix_len: 10,
  land: "field",
  location: true,
};

/** F3d, on a parcel file of More files: its rows without a shape, as units of a shared parcel (condos). Off: a
 * line offering it when some rows have no shape. On: which rows are units, how each finds its building, the land
 * share and the fields it gives them (OpenAVMKit's data.process.condos). */
export function UnitsPanel({
  projectId,
  data,
  file,
  change,
}: {
  projectId: string;
  data: Wizard;
  file: WizardFile;
  change: (c: UnitsChange) => void;
}) {
  const v = file.units;
  const base = data.files.find((f) => f.base);
  if (!v) {
    // Offered where most rows have no shape, and while no other file holds the units (OpenAVMKit takes one).
    const mostly = file.unshaped > 0 && file.unshaped >= 0.5 * (file.rows ?? 0);
    if (!mostly || data.files.some((f) => f.units)) return null;
    return (
      <div className="un-offer">
        <span>{u.offer(file.unshaped)}</span>
        <Button className="button" onPress={() => change({ kind: "units", name: file.name, units: DEFAULT })}>
          {u.setUp}
        </Button>
      </div>
    );
  }
  const s = v.settings;
  const set = (patch: Partial<Units>) =>
    change({ kind: "units", name: file.name, units: { ...s, ...patch } });
  const cols = file.columns.map((c) => [c.name, c.name] as const);
  const baseCols = (base?.columns ?? []).map((c) => [c.name, c.name] as const);
  return (
    <section className="un">
      <div className="un-head">
        <b>{u.title}</b>
        <span className={v.check.ok && !v.check.warn ? "wiz-ok" : "wiz-warn"}>{v.check.text}</span>
        <span className="un-grow" />
        <Button className="wiz-link" onPress={() => change({ kind: "units", name: file.name, units: null })}>
          {u.stop}
        </Button>
      </div>

      <div className="un-row">
        <span className="un-label">{u.which}</span>
        <Seg
          label={u.which}
          value={s.rule ? "where" : "every"}
          options={[
            ["every", u.every],
            ["where", u.where],
          ]}
          onChange={(k) =>
            set({
              rule:
                k === "every"
                  ? null
                  : {
                      join: "all",
                      conditions: [{ column: file.columns[0]?.name ?? "", op: "isin", values: [] }],
                    },
            })
          }
        />
      </div>
      {s.rule && (
        <RuleLines
          projectId={projectId}
          file={file.name}
          columns={cols}
          conditions={s.rule.conditions}
          onChange={(conditions) => set({ rule: { join: "all", conditions } })}
        />
      )}

      <div className="un-row">
        <span className="un-label">{u.finds}</span>
        <Seg
          label={u.finds}
          value={s.link}
          options={[
            ["prefix", u.byPrefix],
            ["parent", u.byParent],
          ]}
          onChange={(link) => set({ link, column: null })}
        />
        <Button
          className="wiz-link"
          onPress={() => change({ kind: "units", name: file.name, units: s, guess: true })}
        >
          {u.guess}
        </Button>
      </div>
      <div className="un-row un-indent">
        {s.link === "prefix" ? (
          <>
            <span>{u.first}</span>
            <Prefix value={s.prefix_len} onChange={(prefix_len) => set({ prefix_len })} />
            <span>{u.characters}</span>
            <Choice
              label={u.column}
              hideLabel
              value={s.column}
              options={cols}
              onChange={(column) => set({ column })}
            />
            <span>{u.match}</span>
            <Choice
              label={u.inUniverse}
              hideLabel
              value={s.base_column}
              options={baseCols}
              onChange={(base_column) => set({ base_column })}
            />
            <span>{u.inUniverse}</span>
          </>
        ) : (
          <>
            <Choice
              label={u.column}
              hideLabel
              value={s.column}
              options={cols}
              onChange={(column) => set({ column })}
            />
            <span>{u.holds}</span>
          </>
        )}
      </div>
      {v.examples.length > 0 && (
        <ul className="un-examples">
          {v.examples.map((x) => (
            <li key={x.unit} className={x.building ? "" : "wiz-warn"}>
              <span className="mono">{x.unit}</span>{" "}
              {x.building ? `${u.building} ${x.building}` : u.noBuilding}
              {x.address && <span className="wiz-from"> · {x.address}</span>}
            </li>
          ))}
        </ul>
      )}

      <div className="un-row">
        <span className="un-label">{u.land}</span>
        <Seg
          label={u.land}
          value={s.land}
          options={[
            ["field", u.ownLand],
            ["floor_area", u.sharedLand],
          ]}
          onChange={(land) => set({ land })}
        />
        <span className={v.land.ok ? "wiz-ok" : "wiz-warn"}>{v.land.text}</span>
      </div>

      <div className="un-row">
        <span className="un-label">{u.gives}</span>
        {v.fields.map((f) => (
          <span key={f.field} className="ly-chip">
            <span>{f.name}</span>
            <span className="wiz-from mono">← {f.column}</span>
            <Button
              className="ly-x"
              aria-label={`${u.remove} ${f.name}`}
              onPress={() => change({ kind: "unitField", name: file.name, field: f.field, column: null })}
            >
              <X size="0.85em" />
            </Button>
          </span>
        ))}
        <AddField
          data={data}
          file={file}
          given={v.fields.map((f) => f.field)}
          add={(field, column) => change({ kind: "unitField", name: file.name, field, column })}
        />
      </div>
      <Tick isSelected={s.location} onChange={(location) => set({ location })}>
        {u.location}
      </Tick>
    </section>
  );
}

function Prefix({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  // What's typed, until it's saved; otherwise the value as it is.
  const [draft, setDraft] = useState<string | null>(null);
  const text = draft ?? String(value);
  const save = () => {
    const n = Number.parseInt(text, 10);
    if (n >= 1 && n <= 64 && n !== value) onChange(n);
    setDraft(null);
  };
  return (
    <TextField aria-label={u.characters} value={text} onChange={setDraft} onBlur={save} className="ly-max">
      <Input
        className="input ly-input wiz-num"
        inputMode="numeric"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

/** "Rows where" tests, one line each: a column, is one of, its values. */
function RuleLines({
  projectId,
  file,
  columns,
  conditions,
  onChange,
}: {
  projectId: string;
  file: string;
  columns: readonly (readonly [string, string])[];
  conditions: Condition[];
  onChange: (c: Condition[]) => void;
}) {
  const set = (i: number, patch: Partial<Condition>) =>
    onChange(conditions.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  return (
    <div className="un-rules">
      {conditions.map((c, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: tests have no id; their place is what they are
        <div key={i} className="un-rule">
          <Choice
            label={u.column}
            hideLabel
            value={c.column}
            options={columns}
            onChange={(column) => set(i, { column, values: [] })}
          />
          <span>{t.wizard.rule.ops.isin}</span>
          <ColumnValues
            projectId={projectId}
            file={file}
            column={c.column}
            chosen={c.values}
            onChange={(values) => set(i, { values })}
          />
          {conditions.length > 1 && (
            <Button
              className="rc-x"
              aria-label={u.remove}
              onPress={() => onChange(conditions.filter((_, j) => j !== i))}
            >
              <X size="0.9em" />
            </Button>
          )}
        </div>
      ))}
      <Button
        className="ly-add"
        onPress={() => onChange([...conditions, { column: columns[0]?.[0] ?? "", op: "isin", values: [] }])}
      >
        {u.addCondition}
      </Button>
    </div>
  );
}

function ColumnValues({
  projectId,
  file,
  column,
  chosen,
  onChange,
}: {
  projectId: string;
  file: string;
  column: string;
  chosen: string[];
  onChange: (v: string[]) => void;
}) {
  const q = useQuery({
    queryKey: ["column-values", projectId, file, column, ""],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/files/{name}/values", {
          params: { path: { project_id: projectId, name: file }, query: { column } },
        }),
      ),
    enabled: !!column,
  });
  return (
    <MultiPick
      label={u.which}
      values={q.data?.values ?? []}
      more={q.data?.more ?? 0}
      chosen={chosen}
      onChange={onChange}
      countNoun={t.wizard.rule.countRows}
    />
  );
}

/** Give the units another of the parcel universe's fields, from a column of their file. */
function AddField({
  data,
  file,
  given,
  add,
}: {
  data: Wizard;
  file: WizardFile;
  given: string[];
  add: (field: string, column: string) => void;
}) {
  const base = data.files.find((f) => f.base);
  const fields = data.fields.filter(
    (f) => f.sources.some((s) => s.file === base?.name) && !given.includes(f.key) && f.key !== "key",
  );
  const [field, setField] = useState<string | null>(null);
  const [column, setColumn] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  if (fields.length === 0) return null;
  return (
    <DialogTrigger isOpen={open} onOpenChange={setOpen}>
      <Button className="ly-add">
        <Plus aria-hidden="true" size="0.9em" />
        {u.addField}
      </Button>
      <Popover className="popover" placement="bottom start">
        <Dialog className="popover-body ly-pop" aria-label={u.addField}>
          <div className="ly-form">
            <Choice
              label={u.fieldPick}
              value={field}
              options={fields.map((f) => [f.key, f.name] as const)}
              onChange={setField}
            />
            <Choice
              label={u.columnPick}
              value={column}
              options={file.columns.map((c) => [c.name, c.name] as const)}
              onChange={setColumn}
            />
            <Button
              className="button button-primary"
              isDisabled={!field || !column}
              onPress={() => {
                if (field && column) add(field, column);
                setField(null);
                setColumn(null);
                setOpen(false);
              }}
            >
              {u.add}
            </Button>
          </div>
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

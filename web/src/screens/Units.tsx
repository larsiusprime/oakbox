import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";
import { Button, Input, Radio, RadioGroup, TextField } from "react-aria-components";
import { navigate } from "../App";
import {
  api,
  type Condition,
  type Units,
  type UnitsView as Units_View,
  unwrap,
  type Wizard,
  type WizardFile,
} from "../api/client";
import { AddButton } from "../components/AddButton";
import { Choice, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { Seg } from "../components/Seg";
import { short } from "../lib/format";
import { say, t } from "../wording";

const u = t.wizard.units;

export type UnitsChange =
  | { kind: "condos"; has: boolean | null }
  | { kind: "units"; name: string; units: Units | null; guess?: boolean }
  | { kind: "unitField"; name: string; field: string; column: string | null }
  | { kind: "unitFields"; name: string; fields: Record<string, string> };

const DEFAULT: Units = {
  rule: null,
  link: "prefix",
  column: null,
  base_column: null,
  prefix_len: 10,
  land: "equal",
  location: true,
  guessed: false,
  inherit: [],
};

type Props = { projectId: string; data: Wizard; change: (c: UnitsChange) => void };

/** F3d, Condo units: units on the roll but not on the map, on a parcel they share (condos of any kind, timeshares,
 * homes in a mobile-home park, buildings on leased land). Asked first; then one decision per part, each worked out
 * on the units as OpenAVMKit's data.process.condos will. */
export function CondoStep({ step, ...props }: Props & { step: string }) {
  const file = props.data.files.find((f) => f.units);
  if (step === "condo_ask") return <Ask {...props} />;
  if (step === "condo_file") return <FileChoice {...props} />;
  if (!file?.units)
    return (
      <p className="cu-row">
        <span className="wiz-from">{u.pickFirst}</span>
        <Button
          className="wiz-link"
          onPress={() =>
            navigate({ name: "project", id: props.projectId, tab: "fields", step: "condo_file" })
          }
        >
          {u.toFile}
        </Button>
      </p>
    );
  const parts: Record<string, ReactNode> = {
    condo_rows: <Rows {...props} file={file} v={file.units} />,
    condo_link: <Link {...props} file={file} v={file.units} />,
    condo_land: <Land {...props} file={file} v={file.units} />,
    condo_fields: <Fields {...props} file={file} v={file.units} />,
    condo_location: <Location {...props} file={file} v={file.units} />,
    condo_summary: <Summary {...props} file={file} v={file.units} />,
  };
  return <div className="cu">{parts[step]}</div>;
}

type Part = Props & { file: WizardFile; v: Units_View };

function setter(file: WizardFile, v: Units_View, change: Props["change"]) {
  return (patch: Partial<Units>) =>
    change({ kind: "units", name: file.name, units: { ...v.settings, ...patch } });
}

/** A choice as a card: a radio with a title and a line saying what it means. */
function Card({
  value,
  title,
  sub,
  children,
}: {
  value: string;
  title: string;
  sub: string;
  children?: ReactNode;
}) {
  return (
    <Radio value={value} className="radio cu-choice">
      <span className="radio-dot" aria-hidden="true" />
      <span className="cu-text">
        <b>{title}</b>
        <span className="cu-sub">{sub}</span>
        {children}
      </span>
    </Radio>
  );
}

function Ask({ data, change }: Props) {
  const c = data.condos;
  if (!c) return null;
  const value = c.answer === null ? null : c.answer ? "yes" : "no";
  return (
    <div className="cu">
      <div className="cu-kinds">
        <span>{u.kindsTitle}</span>
        <ul>
          {u.kinds.map((k) => (
            <li key={k}>{k}</li>
          ))}
        </ul>
        <span className="wiz-from">{u.notThese}</span>
      </div>
      <div className="cu-ev">
        <b>{u.evidence}</b>
        {c.evidence.length ? (
          <ul>
            {c.evidence.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        ) : (
          <p>{u.noEvidence}</p>
        )}
      </div>
      <RadioGroup
        aria-label={u.answer}
        className="cu-choices cu-big"
        value={value}
        onChange={(v) => change({ kind: "condos", has: v === "yes" })}
      >
        <Card value="yes" title={u.yes} sub={u.yesSub} />
        <Card value="no" title={u.no} sub={u.noSub} />
      </RadioGroup>
      {c.answer === false && c.evidence.length > 0 && <p className="wiz-from">{u.noLeft}</p>}
    </div>
  );
}

function FileChoice({ projectId, data, change }: Props) {
  const c = data.condos;
  if (!c) return null;
  return (
    <div className="cu">
      <RadioGroup
        aria-label={u.fileLabel}
        className="cu-choices"
        value={c.file}
        onChange={(name) => change({ kind: "units", name, units: DEFAULT })}
      >
        {c.files.map((f) => {
          const rows = f.rows ?? 0;
          const sub =
            f.unshaped === 0
              ? u.fileNone
              : f.unshaped >= 0.5 * rows
                ? say.wizard.units.fileMostly(f.unshaped, rows)
                : u.fileSome({ n: f.unshaped, rows });
          return (
            <Card
              key={f.name}
              value={f.name}
              title={`${f.filename}${u.rowsOf({ rows: f.rows })}`}
              sub={sub}
            />
          );
        })}
      </RadioGroup>
      <p className="cu-row">
        <span className="wiz-from">{u.notListed}</span>
        <Button
          className="wiz-link"
          onPress={() => navigate({ name: "project", id: projectId, tab: "fields", step: "more_files" })}
        >
          {u.toMoreFiles}
        </Button>
      </p>
      <p className="wiz-from">{u.oneFile}</p>
    </div>
  );
}

function Rows({ projectId, file, v, change }: Part) {
  const set = setter(file, v, change);
  const s = v.settings;
  const cols = file.columns.map((c) => [c.name, c.name] as const);
  return (
    <>
      <RadioGroup
        aria-label={u.which}
        className="cu-choices"
        value={s.rule ? "where" : "every"}
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
      >
        <Card value="every" title={u.every} sub={u.everySub} />
        <Card value="where" title={u.where} sub={u.whereSub} />
      </RadioGroup>
      {s.rule && (
        <RuleLines
          projectId={projectId}
          file={file.name}
          columns={cols}
          conditions={s.rule.conditions}
          onChange={(conditions) => set({ rule: { join: "all", conditions } })}
        />
      )}
      <p className={v.units ? "wiz-ok" : "wiz-bad"}>
        {v.units ? `✓ ${u.units({ n: v.units })}` : v.check.text}
      </p>
    </>
  );
}

function Examples({ v, show }: { v: Units_View; show: "link" | "land" | "location" }) {
  if (!v.examples.length) return null;
  const column = v.settings.link === "prefix" ? v.settings.base_column : null;
  return (
    <ul className="cu-ex">
      {v.examples.map((x) => (
        <li key={x.unit} className={x.building ? "" : "wiz-warn"}>
          <span className="mono">{short(x.unit)}</span>{" "}
          {x.building ? `${u.onParcel} ${short(x.building)}` : u.noParcel}
          {show === "link" && x.building_value && (
            <span className="wiz-from"> {say.wizard.units.matched(column, short(x.building_value))}</span>
          )}
          {show === "land" && x.share && (
            <span className="wiz-from">
              {" "}
              · {u.share} {x.share}
            </span>
          )}
          {x.address && <span className="wiz-from"> · {x.address}</span>}
        </li>
      ))}
    </ul>
  );
}

function Link({ data, file, v, change }: Part) {
  const set = setter(file, v, change);
  const s = v.settings;
  const base = data.files.find((f) => f.base);
  const cols = file.columns.map((c) => [c.name, c.name] as const);
  const baseCols = (base?.columns ?? []).map((c) => [c.name, c.name] as const);
  return (
    <>
      {v.basis && <p className="cu-guess">{v.basis}</p>}
      <div className="cu-row">
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
      <div className="cu-row">
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
      <p className={v.check.ok ? (v.check.warn ? "wiz-warn" : "wiz-ok") : "wiz-bad"}>{v.check.text}</p>
      <Examples v={v} show="link" />
    </>
  );
}

function Land({ data, file, v, change }: Part) {
  const set = setter(file, v, change);
  const s = v.settings;
  const landField = data.fields.find((f) => f.key === "land_area_sqft" || f.key === "land_area_sqm");
  const own = landField ? v.fields.find((f) => f.field === landField.key) : undefined;
  return (
    <>
      <RadioGroup
        aria-label={u.land}
        className="cu-choices"
        value={s.land}
        onChange={(land) => set({ land: land as Units["land"] })}
      >
        {(["equal", "floor_area", "field", "none"] as const).map((k) => {
          const [title, sub] = u.landChoices[k] ?? [k, ""];
          return (
            <Card key={k} value={k} title={title} sub={sub}>
              {k === "field" && s.land === "field" && landField && (
                <span className="cu-row">
                  <Choice
                    label={u.landColumn}
                    value={own?.column ?? null}
                    options={file.columns.map((c) => [c.name, c.name] as const)}
                    onChange={(column) =>
                      change({ kind: "unitField", name: file.name, field: landField.key, column })
                    }
                  />
                </span>
              )}
            </Card>
          );
        })}
      </RadioGroup>
      <p className={v.land.ok ? (v.land.warn ? "wiz-warn" : "wiz-ok") : "wiz-bad"}>{v.land.text}</p>
      <Examples v={v} show="land" />
    </>
  );
}

function Fields({ data, file, v, change }: Part) {
  const set = setter(file, v, change);
  const base = data.files.find((f) => f.base);
  // Fields ticked that have no same-named column yet: a row each, waiting for its column.
  const [waiting, setWaiting] = useState<string[]>([]);
  const offered = new Map(v.offers.map((o) => [o.field, o.column]));
  const named = new Map(data.fields.map((f) => [f.key, f.name]));
  const given = v.fields.map((f) => f.field);
  const rows = [
    ...v.fields.map((f) => ({ ...f, name: named.get(f.field) ?? f.name })),
    ...waiting
      .filter((k) => !given.includes(k))
      .map((k) => ({ field: k, name: named.get(k) ?? k, column: null })),
  ];
  // Not the land size: the Land part sets it (a share of the parcel's, or the unit's own).
  const candidates = data.fields.filter(
    (f) =>
      f.sources.some((s) => s.file === base?.name) &&
      !["key", "land_area_sqft", "land_area_sqm"].includes(f.key),
  );
  const unit = (field: string, column: string | null) =>
    change({ kind: "unitField", name: file.name, field, column });
  const pick = (next: string[]) => {
    const now = rows.map((r) => r.field);
    const added = next.filter((k) => !now.includes(k));
    const withColumn: Record<string, string> = {};
    for (const k of added) {
      const column = offered.get(k);
      if (column) withColumn[k] = column;
    }
    if (Object.keys(withColumn).length) change({ kind: "unitFields", name: file.name, fields: withColumn });
    const removed = now.filter((k) => !next.includes(k));
    for (const k of removed) if (given.includes(k)) unit(k, null);
    setWaiting((w) => [...w.filter((k) => !removed.includes(k)), ...added.filter((k) => !offered.has(k))]);
  };
  const columns = file.columns.map((c) => [c.name, c.name] as const);
  return (
    <>
      <h3 className="cu-h">{u.fromFile}</h3>
      <MultiPick
        label={u.fieldsPick}
        placeholder={u.chooseFields}
        values={candidates.map((f) => {
          const note = offered.get(f.key);
          return note ? { value: f.key, label: f.name, note } : { value: f.key, label: f.name };
        })}
        chosen={rows.map((r) => r.field)}
        onChange={pick}
      />
      {rows.length > 0 && (
        <div className="wiz-grid cu-fields">
          {rows.map((r) => (
            <Fragment key={r.field}>
              <span className="wiz-label">{r.name}</span>
              <Choice
                label={r.name}
                hideLabel
                value={r.column}
                placeholder={u.pickColumn}
                options={columns}
                onChange={(column) => {
                  unit(r.field, column);
                  setWaiting((w) => w.filter((k) => k !== r.field));
                }}
              />
              <Button
                className="ly-x"
                aria-label={`${u.remove} ${r.name}`}
                onPress={() => pick(rows.map((x) => x.field).filter((k) => k !== r.field))}
              >
                <X size="0.9em" />
              </Button>
            </Fragment>
          ))}
        </div>
      )}
      <h3 className="cu-h">{u.fromParcelTitle}</h3>
      {v.inheritable.length > 0 ? (
        <>
          <MultiPick
            label={u.inheritPick}
            placeholder={u.chooseFields}
            values={v.inheritable.map((f) => ({ value: f.field, label: f.name, note: f.column }))}
            chosen={v.settings.inherit}
            onChange={(inherit) => set({ inherit })}
          />
          <p className="wiz-from">{u.inheritNote}</p>
        </>
      ) : (
        <p className="wiz-from">{u.inheritNone}</p>
      )}
      {v.from_shape.length > 0 && (
        <>
          <p className="cu-sub-h">{u.shapeTitle}</p>
          <ul className="cu-shape">
            {v.from_shape.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function Location({ file, v, change }: Part) {
  const set = setter(file, v, change);
  // One example per parcel the examples are on.
  const seen = new Set<string>();
  const parcels = v.examples.filter((x) => x.building && !seen.has(x.building) && seen.add(x.building));
  return (
    <>
      <Tick isSelected={v.settings.location} onChange={(location) => set({ location })}>
        {u.location}
      </Tick>
      {v.settings.location ? (
        parcels.length > 0 && (
          <>
            <span className="wiz-from">{u.locationEg}</span>
            <ul className="cu-ex">
              {parcels.map((x) => (
                <li key={x.building}>
                  <span className="mono">condo_group {short(x.building ?? "")}</span>
                  {x.address && <span className="wiz-from"> · {x.address}</span>}
                </li>
              ))}
            </ul>
          </>
        )
      ) : (
        <p className="wiz-from">{u.locationOff}</p>
      )}
    </>
  );
}

function Summary({ data, file, v }: Part) {
  const s = v.settings;
  const sm = u.summary;
  const sales = data.files.find((f) => f.holds === "sales" && f.match === "key");
  const how =
    s.link === "prefix"
      ? sm.prefix({ n: s.prefix_len, column: s.column ?? "?" })
      : sm.parent({ column: s.column ?? "?" });
  return (
    <>
      <ol className="cu-sum">
        <li>{sm.rows({ n: v.units, file: file.filename, every: !s.rule })}</li>
        <li>{sm.link({ how, linked: v.linked, units: v.units, parcels: v.buildings })}</li>
        <li>{sm.shape({ linked: v.linked })}</li>
        <li>{sm.land[s.land]}</li>
        <li>
          {say.wizard.units.summary.carries(
            v.fields.map((f) => f.name.toLowerCase()),
            file.filename,
          )}
        </li>
        <li>{sm.location({ on: s.location })}</li>
      </ol>
      {sales?.id_check && (
        <p className="wiz-from">{sm.sales({ text: sales.id_check.text.replace(/^✓ /, "") })}</p>
      )}
    </>
  );
}

/** On More files: a parcel file whose rows have no shape of their own is set up on Condo units, not here. */
export function UnitsPointer({ projectId, file }: { projectId: string; file: WizardFile }) {
  const mostly = file.unshaped > 0 && file.unshaped >= 0.5 * (file.rows ?? 0);
  // Rows for parcels the parcel universe lacks already say so, with the way there.
  if (!file.units && (!mostly || file.not_in_universe?.units)) return null;
  return (
    <p className="un-offer">
      <span>{file.units ? u.pointerUnits : u.pointer({ n: file.unshaped })}</span>
      <CondosLink projectId={projectId} />
    </p>
  );
}

export function CondosLink({ projectId }: { projectId: string }) {
  return (
    <Button
      className="wiz-link"
      onPress={() => navigate({ name: "project", id: projectId, tab: "fields", step: "condo_ask" })}
    >
      {u.toCondos}
    </Button>
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
      <AddButton
        onPress={() => onChange([...conditions, { column: columns[0]?.[0] ?? "", op: "isin", values: [] }])}
      >
        {u.addCondition}
      </AddButton>
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

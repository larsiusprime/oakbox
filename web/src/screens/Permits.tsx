import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { Permits, Project, Wizard } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { Val } from "../components/Val";
import { t } from "../wording";
import { FilePicker, IdRow, StepFile } from "./WizardFiles";
import type { Mutate } from "./wizardChange";

const w = t.wizard;
const p = t.wizard.permits;
type Meaning = Permits["means"][string];
export type PermitsChange = { kind: "permits"; name: string; permits: Permits | null; guess?: boolean };

const MEANINGS: readonly (readonly [Meaning, string])[] = [
  ["teardown", p.teardown],
  ["major", p.major],
  ["minor", p.minor],
  ["none", p.none],
];

/** F3g, Permits: the permits file, joined on the parcel ID; the date each was issued, what each kind of permit
 * means, and what OpenAVMKit does with them (teardown sales, the effective year built). */
export function PermitsStep({ project, data, change }: { project: Project; data: Wizard; change: Mutate }) {
  const v = data.permits;
  const file = v ? data.files.find((f) => f.name === v.file) : undefined;
  const base = data.files.find((f) => f.base);
  if (!v || !file) {
    const taken = data.files.filter((f) => f.base || f.holds === "sales").map((f) => f.name);
    return (
      <FilePicker
        project={project}
        data={data}
        exclude={taken}
        onChosen={(name) => change({ kind: "file", name, holds: "permits" })}
      />
    );
  }
  const s = v.settings;
  const set = (patch: Partial<Permits>) =>
    change({ kind: "permits", name: v.file, permits: { ...s, ...patch } });
  const columns = file.columns.map((c) => [c.name, c.name] as const);
  // What each kind means, guesses included: saying one says them all, as shown.
  const means = Object.fromEntries(v.kinds.map((k) => [k.value, k.means]));
  return (
    <StepFile file={file} onRemove={() => change({ kind: "permits", name: v.file, permits: null })}>
      <IdRow projectId={project.id} data={data} file={file} base={base} change={change} />
      <div className="wiz-grid">
        <div className="wiz-label">{p.date}</div>
        <Choice
          label={p.date}
          hideLabel
          value={s.date}
          placeholder={w.choose}
          options={columns}
          onChange={(date) => {
            const fmt = file.columns.find((c) => c.name === date)?.date_format ?? s.date_format;
            set({ date, date_format: fmt });
          }}
        />
        <div className="wiz-samples">
          {v.date && (
            <span className={v.date.ok && !v.date.warn ? "wiz-ok" : "wiz-warn"}>
              {v.date.text}
              {v.span && ` · ${v.span}`}
            </span>
          )}
          {s.date && !s.date_format && <span className="wiz-warn">{p.noFormat}</span>}
        </div>
        <div className="wiz-label">{p.type}</div>
        <Choice
          label={p.type}
          hideLabel
          value={s.type}
          placeholder={w.choose}
          options={columns}
          onChange={(type) => set({ type, means: {} })}
        />
        <div className="wiz-samples">
          {v.kinds.length > 0 && <span>{p.kinds({ n: v.kinds.length + v.more })}</span>}
        </div>
      </div>
      {v.kinds.length > 0 && (
        <table className="pm-tbl">
          <thead>
            <tr>
              <th className="pm-head">{s.type}</th>
              <th className="pm-head pm-n">{p.permits}</th>
              <th className="pm-head">{p.means}</th>
            </tr>
          </thead>
          <tbody>
            {v.kinds.map((k) => (
              <tr key={k.value}>
                <td className="pm-cell mono">
                  <Val v={k.value} />
                </td>
                <td className="pm-cell pm-n">{k.count.toLocaleString()}</td>
                <td className="pm-cell">
                  <Choice
                    label={`${p.means}: ${k.value}`}
                    hideLabel
                    value={k.means}
                    options={MEANINGS}
                    onChange={(m) => set({ means: { ...means, [k.value]: m } })}
                  />
                  {k.guessed && <span className="wiz-from"> {p.guessed}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {v.more > 0 && <p className="wiz-from">{p.more({ n: v.more })}</p>}
      <div className="pm-row">
        <span>{p.teardownSale}</span>
        <Days value={s.max_days} onChange={(max_days) => set({ max_days })} />
        <span>{p.teardownSaleEnd}</span>
      </div>
      <div className="pm-row">
        <Tick
          isSelected={s.effective_age && v.year_built}
          onChange={(effective_age) => set({ effective_age })}
        >
          {p.effectiveAge}
        </Tick>
        {!v.year_built && <span className="wiz-warn">{p.needsYearBuilt}</span>}
      </div>
      <p className="wiz-note">{p.gives}</p>
    </StepFile>
  );
}

function Days({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  // What's typed, until it's saved; otherwise the value as it is.
  const [draft, setDraft] = useState<string | null>(null);
  const text = draft ?? String(value);
  const commit = () => {
    const n = Number.parseInt(text, 10);
    if (n >= 1 && n <= 3650 && n !== value) onChange(n);
    setDraft(null);
  };
  return (
    <TextField aria-label={p.days} value={text} onChange={setDraft} onBlur={commit} className="ly-max">
      <Input
        className="input ly-input wiz-num"
        inputMode="numeric"
        onKeyDown={(k) => {
          if (k.key === "Enter") commit();
        }}
      />
    </TextField>
  );
}

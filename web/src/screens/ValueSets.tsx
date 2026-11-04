import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { Project, Wizard } from "../api/client";
import { AddButton } from "../components/AddButton";
import { Tick } from "../components/Form";
import { RemoveButton } from "../components/RemoveButton";
import { t } from "../wording";
import { FieldRow } from "./FieldRow";
import type { MutateAsync } from "./wizardChange";

const v = t.wizard.valueSets;
const PARTS = [
  ["market", v.market],
  ["land", v.land],
  ["impr", v.impr],
] as const;

export type ValuesChange =
  | { kind: "addSet"; name: string }
  | { kind: "setChange"; id: string; name?: string; roll?: boolean }
  | { kind: "removeSet"; id: string };

export function ValueSetsStep({
  project,
  data,
  change,
}: {
  project: Project;
  data: Wizard;
  change: MutateAsync;
}) {
  return (
    <div className="vs">
      {data.value_sets.map((s) => (
        <section key={s.id} className="vs-set" aria-label={s.name}>
          <div className="vs-head">
            <SetName name={s.name} rename={(name) => change({ kind: "setChange", id: s.id, name })} />
            <Tick isSelected={s.roll} onChange={(roll) => change({ kind: "setChange", id: s.id, roll })}>
              {v.roll}
            </Tick>
            <span className="wiz-from">{s.roll ? v.rollNote : v.otherNote}</span>
            <span className="vs-grow" />
            <RemoveButton label={v.remove} onPress={() => change({ kind: "removeSet", id: s.id })} />
          </div>
          <div className="wiz-grid">
            {PARTS.map(([part, label]) => {
              const field = data.fields.find((f) => f.key === `${s.id}_${part}_value`);
              return (
                field && (
                  <FieldRow
                    key={field.key}
                    project={project}
                    data={data}
                    field={field}
                    sales={false}
                    change={change}
                    label={label}
                  />
                )
              );
            })}
          </div>
        </section>
      ))}
      {data.value_sets.length === 0 && <p className="wiz-from">{v.none}</p>}
      <AddButton end onPress={() => change({ kind: "addSet", name: "" })}>
        {v.add}
      </AddButton>
    </div>
  );
}

/** The set's name, saved when it's left (or Enter). */
function SetName({ name, rename }: { name: string; rename: (n: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const save = () => {
    const next = draft?.trim();
    if (next && next !== name) rename(next);
    setDraft(null);
  };
  return (
    <TextField
      aria-label={v.name}
      value={draft ?? name}
      onChange={setDraft}
      onBlur={save}
      className="vs-name"
    >
      <Input
        className="input"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

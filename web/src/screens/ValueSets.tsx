import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { Project, Wizard } from "../api/client";
import { AddButton } from "../components/AddButton";
import { DeleteButton } from "../components/Buttons";
import { Tick } from "../components/Form";
import { useAtOnce } from "../lib/hooks";
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
  // Shown the moment they're asked for (AGENTS.md): a new set's placeholder while it's made, a deleted set greyed
  // out while it goes.
  const [adding, setAdding] = useState(0);
  const [deleting, setDeleting] = useState<string[]>([]);
  const add = () => {
    setAdding((n) => n + 1);
    change({ kind: "addSet", name: "" })
      .catch(() => {})
      .finally(() => setAdding((n) => n - 1));
  };
  const remove = (id: string) => {
    setDeleting((d) => [...d, id]);
    change({ kind: "removeSet", id })
      .catch(() => {})
      .finally(() => setDeleting((d) => d.filter((x) => x !== id)));
  };
  return (
    <div className="vs">
      {data.value_sets.map((s) =>
        deleting.includes(s.id) ? (
          <Pending key={s.id} text={v.deleting({ name: s.name })} />
        ) : (
          <section key={s.id} className="vs-set" aria-label={s.name}>
            <div className="vs-head">
              <SetName name={s.name} rename={(name) => change({ kind: "setChange", id: s.id, name })} />
              <Tick isSelected={s.roll} onChange={(roll) => change({ kind: "setChange", id: s.id, roll })}>
                {v.roll}
              </Tick>
              <span className="vs-grow" />
              <DeleteButton confirm={v.deleteConfirm({ name: s.name })} onDelete={() => remove(s.id)}>
                {v.deleteSet}
              </DeleteButton>
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
        ),
      )}
      {Array.from({ length: adding }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: placeholders, each the same
        <Pending key={`adding-${i}`} text={v.adding} />
      ))}
      {data.value_sets.length === 0 && adding === 0 && <p className="wiz-from">{v.none}</p>}
      <AddButton end onPress={add}>
        {v.add}
      </AddButton>
    </div>
  );
}

/** A set on its way in or out: its outline at once, a bar while the server works. */
function Pending({ text }: { text: string }) {
  return (
    <section className="vs-set vs-pending" aria-busy="true" aria-label={text}>
      <span className="vs-pending-text">{text}</span>
      <span className="engine-bar opening-bar opening-bar-busy" aria-hidden="true">
        <i />
      </span>
    </section>
  );
}

/** The set's name, saved when it's left (or Enter). */
function SetName({ name, rename }: { name: string; rename: (n: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  // What was saved stays shown while it saves, not the old value (AGENTS.md).
  const [held, hold] = useAtOnce(name);
  const save = () => {
    const next = draft?.trim();
    if (next && next !== held) {
      hold(next);
      rename(next);
    }
    setDraft(null);
  };
  return (
    <TextField
      aria-label={v.name}
      value={draft ?? held}
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

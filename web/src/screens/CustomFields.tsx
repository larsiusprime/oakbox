import { X } from "lucide-react";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import type { Wizard } from "../api/client";
import { Choice } from "../components/Form";
import { ValuesButton } from "../components/ValuesButton";
import { t } from "../strings";

const c = t.wizard.custom;
type Group = "land" | "building" | "other";
type Kind = "category" | "number";
export type CustomChange = {
  kind: "custom";
  name: string;
  file: string | null;
  column: string | null;
  group: Group;
  type: Kind;
};

/** "lot_shape" from "LOT SHAPE": a starting name the user can change. */
function nameFor(column: string): string {
  const n = column
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return /^[a-z]/.test(n) ? n : `f_${n}`;
}

/** F3d, on Land use & building type: any other parcel column, named by the user and classified as land,
 * building or other, and as a category or a number (OpenAVMKit's field_classification). One table: the
 * fields added so far, then a row to add one. */
export function CustomFields({
  projectId,
  data,
  change,
}: {
  projectId: string;
  data: Wizard;
  change: (c: CustomChange, options?: { onSuccess?: () => void }) => void;
}) {
  const files = data.files.filter((f) => f.holds === "parcels");
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [group, setGroup] = useState<Group>("other");
  const [kind, setKind] = useState<Kind>("category");
  const options = files.flatMap((f) =>
    f.columns
      .filter((col) => col.type !== "geometry")
      .map((col) => {
        const key = data.used[f.name]?.[col.name];
        // What it's loaded as, by name ("Building units"), not OpenAVMKit's key.
        const as = key && (data.fields.find((x) => x.key === key)?.name ?? key);
        return [
          `${f.name}\u0000${col.name}`,
          as ? `${col.name} · ${f.name} (${as})` : `${col.name} · ${f.name}`,
        ] as const;
      }),
  );
  const [file, column] = picked ? picked.split("\u0000") : [null, null];
  const groups = Object.entries(c.groups) as [Group, string][];
  const kinds = Object.entries(c.types) as [Kind, string][];
  const add = () => {
    if (!file || !column || !name) return;
    // Cleared once it's added; a refusal (a name already used) keeps what was typed.
    change(
      { kind: "custom", name, file, column, group, type: kind },
      {
        onSuccess: () => {
          setPicked(null);
          setName("");
        },
      },
    );
  };
  return (
    <section className="wiz-section">
      <h3 className="wiz-group">{c.title}</h3>
      <p className="wiz-lede">{c.lede}</p>
      <table className="cf-tbl">
        <thead>
          <tr>
            <th className="cf-th">{c.column}</th>
            <th className="cf-th">{c.name}</th>
            <th className="cf-th">{c.group}</th>
            <th className="cf-th">{c.type}</th>
            <th className="cf-th">{c.values}</th>
            <th className="cf-th">
              <span className="visually-hidden">{c.actions}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data.custom.map((x) => {
            const set = (patch: Partial<CustomChange>) =>
              change({
                kind: "custom",
                name: x.name,
                file: x.file,
                column: x.column,
                group: x.group,
                type: x.type,
                ...patch,
              });
            return (
              <tr key={x.name}>
                <td className="cf-td">
                  <span className="mono">{x.column}</span> <span className="wiz-from">· {x.file}</span>
                </td>
                <td className="cf-td mono">{x.name}</td>
                <td className="cf-td">
                  <Choice
                    label={`${c.group}: ${x.name}`}
                    hideLabel
                    value={x.group}
                    options={groups}
                    onChange={(g) => set({ group: g })}
                  />
                </td>
                <td className="cf-td">
                  <Choice
                    label={`${c.type}: ${x.name}`}
                    hideLabel
                    value={x.type}
                    options={kinds}
                    onChange={(k) => set({ type: k })}
                  />
                </td>
                <td className="cf-td">
                  <span className="cf-vals">
                    <ValuesButton
                      projectId={projectId}
                      file={x.file}
                      column={x.column}
                      distinct={x.distinct}
                    />
                    {(x.check.warn || !x.check.ok) && <span className="wiz-warn">{x.check.text}</span>}
                  </span>
                </td>
                <td className="cf-td">
                  <Button
                    className="rc-x"
                    aria-label={c.remove(x.name)}
                    onPress={() => set({ file: null, column: null })}
                  >
                    <X size="0.9em" />
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="cf-add">
            <td className="cf-td cf-add-td">
              <Choice
                label={c.column}
                hideLabel
                value={picked}
                placeholder={c.pickColumn}
                options={options}
                onChange={(val) => {
                  setPicked(val);
                  const [f, col] = val.split("\u0000");
                  setName(nameFor(col ?? ""));
                  const type = files.find((x) => x.name === f)?.columns.find((x) => x.name === col)?.type;
                  setKind(type === "number" ? "number" : "category");
                }}
              />
            </td>
            <td className="cf-td cf-add-td">
              <TextField aria-label={c.name} value={name} onChange={setName} className="cf-name">
                <Input
                  className="input cf-name-input"
                  placeholder={c.namePlaceholder}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") add();
                  }}
                />
              </TextField>
            </td>
            <td className="cf-td cf-add-td">
              <Choice label={c.group} hideLabel value={group} options={groups} onChange={setGroup} />
            </td>
            <td className="cf-td cf-add-td">
              <Choice label={c.type} hideLabel value={kind} options={kinds} onChange={setKind} />
            </td>
            <td className="cf-td cf-add-td" colSpan={2}>
              <Button className="button" isDisabled={!file || !name} onPress={add}>
                {c.add}
              </Button>
            </td>
          </tr>
        </tfoot>
      </table>
    </section>
  );
}

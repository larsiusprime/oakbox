import { X } from "lucide-react";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import type { Wizard } from "../api/client";
import { Choice } from "../components/Form";
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
 * building or other, and as a category or a number (OpenAVMKit's field_classification). */
export function CustomFields({
  data,
  change,
}: {
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
        const as = data.used[f.name]?.[col.name];
        return [
          `${f.name}\u0000${col.name}`,
          as ? `${col.name} · ${f.name} (${as})` : `${col.name} · ${f.name}`,
        ] as const;
      }),
  );
  const [file, column] = picked ? picked.split("\u0000") : [null, null];
  const groups = Object.entries(c.groups) as [Group, string][];
  const kinds = Object.entries(c.types) as [Kind, string][];
  return (
    <section className="wiz-section">
      <h3 className="wiz-group">{c.title}</h3>
      <p className="wiz-lede">{c.lede}</p>
      {data.custom.length > 0 && (
        <div className="wiz-grid">
          {data.custom.map((x) => (
            <div key={x.name} className="wiz-loc wiz-custom">
              <span className="mono">{x.name}</span>
              <span className="wiz-from">
                {x.column} · {x.file}
              </span>
              <Choice
                label={`${c.group}: ${x.name}`}
                hideLabel
                value={x.group}
                options={groups}
                onChange={(g) =>
                  change({
                    kind: "custom",
                    name: x.name,
                    file: x.file,
                    column: x.column,
                    group: g,
                    type: x.type,
                  })
                }
              />
              <Choice
                label={`${c.type}: ${x.name}`}
                hideLabel
                value={x.type}
                options={kinds}
                onChange={(k) =>
                  change({
                    kind: "custom",
                    name: x.name,
                    file: x.file,
                    column: x.column,
                    group: x.group,
                    type: k,
                  })
                }
              />
              <span className={x.check.warn || !x.check.ok ? "wiz-warn" : "wiz-ok"}>{x.check.text}</span>
              <Button
                className="rc-x"
                aria-label={c.remove(x.name)}
                onPress={() =>
                  change({
                    kind: "custom",
                    name: x.name,
                    file: null,
                    column: null,
                    group: x.group,
                    type: x.type,
                  })
                }
              >
                <X size="0.9em" />
              </Button>
              <span className="wiz-sample-values wiz-custom-samples">{x.samples.slice(0, 5).join(", ")}</span>
            </div>
          ))}
        </div>
      )}
      <form
        className="wiz-loc-add"
        onSubmit={(e) => {
          e.preventDefault();
          if (file && column && name) {
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
          }
        }}
      >
        <Choice
          label={c.column}
          hideLabel
          value={picked}
          placeholder={c.pickColumn}
          options={options}
          onChange={(v) => {
            setPicked(v);
            const [f, col] = v.split("\u0000");
            setName(nameFor(col ?? ""));
            const type = files.find((x) => x.name === f)?.columns.find((x) => x.name === col)?.type;
            setKind(type === "number" ? "number" : "category");
          }}
        />
        <TextField aria-label={c.name} value={name} onChange={setName} className="rl-mini">
          <Input className="input rl-input" placeholder={c.namePlaceholder} />
        </TextField>
        <Choice label={c.group} hideLabel value={group} options={groups} onChange={setGroup} />
        <Choice label={c.type} hideLabel value={kind} options={kinds} onChange={setKind} />
        <Button type="submit" className="button" isDisabled={!file || !name}>
          {c.add}
        </Button>
      </form>
    </section>
  );
}

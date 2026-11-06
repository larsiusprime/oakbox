/** Check sales' calls as cards: its own steps, and the fills and folding it makes for step 5 (Prepare the fields). */
import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { CleanPatch, CleanSetup, FillRow } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { num, short } from "../lib/format";
import { say, t } from "../wording";

const s = t.sales;
type Patch = CleanPatch;

export type CardProps = { v: CleanSetup; set: (body: Patch) => void };

export function Card({
  title,
  sub,
  children,
}: {
  title: React.ReactNode;
  sub: string;
  children: React.ReactNode;
}) {
  // In a step, the step says what it is: a card only shows its on/off control (a tick) and how it stands.
  return (
    <section className="cs-step">
      {typeof title !== "string" && (
        <div className="cs-head">
          <h3>{title}</h3>
          <span className="wiz-from">{sub}</span>
        </div>
      )}
      {children}
    </section>
  );
}

const METHODS = ["median", "mean", "mode", "zero", "min", "max", "leave"] as const;

// Fills that take a value from the group's own: with none there, its blanks stay blank.
const FROM_VALUES = new Set(["median", "mean", "min", "max"]);

/** What the fill puts in, as OpenAVMKit works it out for who it's for: an example (the model group with the most of
 * those blanks), then the blanks it leaves. */
function putsIn(row: FillRow): { text: string; notes: string[] } {
  const m = row.fill.method;
  if (m === "leave") return { text: s.fill.leaveNote, notes: [] };
  const scope = row.fill.scope;
  const ex = row.examples[scope];
  const notes: string[] = [];
  const left = row.blanks - (ex?.blanks ?? 0);
  if (scope !== "all" && left > 0) notes.push(s.fill.outside[scope]({ n: num(left) }));
  if (!ex || ex.blanks === 0) return { text: s.fill.nothing, notes };
  if (FROM_VALUES.has(m) && ex.empty.length) notes.push(s.fill.emptyGroups({ groups: ex.empty.join(", ") }));
  if (m === "zero") return { text: "0", notes };
  const v = ex.values[m];
  const text =
    v === undefined
      ? "—"
      : s.fill.example({
          method: s.fill.methods[m],
          among: s.fill.among[scope],
          v: num(v, Math.abs(v) < 10 ? 1 : 0),
          group: ex.group,
        });
  return { text, notes };
}

function PutsIn({ row }: { row: FillRow }) {
  const { text, notes } = putsIn(row);
  return (
    <>
      {text}
      {notes.map((n) => (
        <div key={n} className="cs-why-fill">
          {n}
        </div>
      ))}
    </>
  );
}

export function FillCard({ v, set }: CardProps) {
  return (
    <Card title={s.fill.title} sub={s.fill.sub}>
      <p className="cs-text wiz-from">{s.fill.what}</p>
      {v.fills.length > 0 ? (
        <table className="tbl">
          <thead>
            <tr>
              <th>{s.fill.field}</th>
              <th className="cs-n">{s.fill.blank}</th>
              <th>{s.fill.with}</th>
              <th>{s.fill.puts}</th>
              <th>{s.fill.for}</th>
            </tr>
          </thead>
          <tbody>
            {v.fills.map((row) => (
              <tr key={row.field}>
                <td>
                  {row.name} <span className="mono wiz-from">{row.field}</span>
                  <div className="wiz-from cs-why-fill">{row.why}</div>
                </td>
                <td className="cs-n">{num(row.blanks)}</td>
                <td>
                  <Choice
                    label={s.fill.with}
                    hideLabel
                    value={row.fill.method}
                    options={METHODS.map((m) => [m, s.fill.methods[m]] as const)}
                    onChange={(method) => set({ fill: { field: row.field, method, scope: row.fill.scope } })}
                  />
                </td>
                <td className="wiz-from">
                  <PutsIn row={row} />
                </td>
                <td>
                  <Choice
                    label={s.fill.for}
                    hideLabel
                    isDisabled={row.fill.method === "leave"}
                    value={row.fill.scope}
                    options={[
                      ["all", s.fill.scopes.all],
                      ["impr", s.fill.scopes.impr],
                      ["vacant", s.fill.scopes.vacant],
                    ]}
                    onChange={(scope) => set({ fill: { field: row.field, method: row.fill.method, scope } })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="wiz-ok">{s.fill.none}</p>
      )}
      <details className="bi-details">
        <summary>{say.sales.fill.auto(v.auto.length)}</summary>
        <ul>
          {v.auto.map((a) => (
            <li key={a}>{a}</li>
          ))}
          <li>{s.fill.area}</li>
        </ul>
      </details>
    </Card>
  );
}

export function CollapseCard({ v, set }: CardProps) {
  return (
    <Card
      title={
        <Tick isSelected={v.collapse} onChange={(on) => set({ collapse: on })}>
          {s.collapse.title}
        </Tick>
      }
      sub={v.collapse ? s.collapse.on : s.collapse.off}
    >
      <p className="cs-text wiz-from">{s.collapse.what}</p>
      {v.collapse && (
        <>
          <div className="cs-row">
            <NumberBox
              key={`s${v.collapse_sales_min}`}
              label={s.collapse.salesMin}
              value={v.collapse_sales_min}
              onChange={(n) => set({ collapse_sales_min: n })}
            />
            <NumberBox
              key={`u${v.collapse_univ_min}`}
              label={s.collapse.univMin}
              value={v.collapse_univ_min}
              onChange={(n) => set({ collapse_univ_min: n })}
            />
          </div>
          {v.folds.length ? (
            <table className="tbl">
              <thead>
                <tr>
                  <th>{s.fill.field}</th>
                  <th className="cs-n">{s.collapse.values}</th>
                  <th className="cs-n">{s.collapse.fold}</th>
                  <th className="cs-n">{s.collapse.parcels}</th>
                  <th>{s.collapse.which}</th>
                </tr>
              </thead>
              <tbody>
                {v.folds.map((f) => (
                  <tr key={f.field}>
                    <td>
                      {f.name} <span className="mono wiz-from">{f.field}</span>
                    </td>
                    <td className="cs-n">{num(f.values)}</td>
                    <td className="cs-n">{num(f.folded.length)}</td>
                    <td className="cs-n">{num(f.parcels)}</td>
                    <td className="cs-folds">
                      {f.folded.length === 0
                        ? s.collapse.none
                        : f.folded
                            .slice(0, 8)
                            .map((x) => short(x))
                            .join(", ") +
                          (f.folded.length > 8 ? s.collapse.more({ n: f.folded.length - 8 }) : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="cs-text">{s.collapse.noFields}</p>
          )}
        </>
      )}
    </Card>
  );
}

export function NumberBox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  // Keyed on the value by its parent: a new value starts it afresh.
  const [text, setText] = useState(String(value));
  const commit = () => {
    const n = Math.round(Number(text));
    if (Number.isFinite(n) && n >= 1 && n !== value) onChange(n);
    else setText(String(value));
  };
  return (
    <TextField
      className="field field-short"
      value={text}
      onChange={setText}
      onBlur={commit}
      aria-label={label}
    >
      <span className="field-label">{label}</span>
      <Input className="input" inputMode="numeric" onKeyDown={(e) => e.key === "Enter" && commit()} />
    </TextField>
  );
}

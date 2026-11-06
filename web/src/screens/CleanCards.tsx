/** Check sales' calls as cards: its own steps, and the fills and folding it makes for step 5 (Prepare the fields). */
import { useState } from "react";
import { Input, TextField } from "react-aria-components";
import type { CleanPatch, CleanSetup, FillPart, FillRow } from "../api/client";
import { Choice, Tick } from "../components/Form";
import { num, short } from "../lib/format";
import { t } from "../wording";

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
type Method = (typeof METHODS)[number];
type Kind = FillRow["kind"];

// The kinds' marks and the parcels' (SPEC F7): a house, a hill, a ring; an empty lot, the two side by side.
const ICONS = {
  building: (
    <>
      <path
        d="M2 8 L8 2.5 L14 8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M4 7.3 V13.5 H12 V7.3" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <rect x="7" y="9.5" width="2.2" height="4" fill="currentColor" />
    </>
  ),
  land: <path d="M1.5 12 L6 6 L9 9.5 L11 7 L14.5 12 Z" fill="currentColor" />,
  other: <circle cx="8" cy="8" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />,
  vacant: (
    <>
      <rect
        x="2"
        y="4"
        width="12"
        height="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="2.2 1.6"
      />
      <path d="M4 11 q2 -2 4 0 t4 0" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </>
  ),
  all: (
    <>
      <rect x="1.5" y="3" width="13" height="10.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 3 V13.5" stroke="currentColor" strokeWidth="1.5" />
    </>
  ),
};

function Icon({ name, size = 14 }: { name: keyof typeof ICONS; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className="fill-icon">
      {ICONS[name]}
    </svg>
  );
}

function KindTag({ kind }: { kind: Kind }) {
  return (
    <span className={`fill-kind fill-kind-${kind}`} title={s.fill.kindTips[kind]}>
      <Icon name={kind} size={12} />
      {s.fill.kinds[kind]}
    </span>
  );
}

/** A method's dropdown: Auto (what's proposed) first, then each method; an Other field's All has Split too. */
function MethodChoice({
  label,
  value,
  auto,
  split,
  onChange,
}: {
  label: string;
  value: string;
  auto: Method;
  split?: boolean;
  onChange: (v: string) => void;
}) {
  const options: (readonly [string, string])[] = [
    ["auto", s.fill.autoMethod({ method: s.fill.methods[auto] })],
    ...METHODS.map((m) => [m, s.fill.methods[m]] as const),
    ...(split ? [["split", s.fill.split] as const] : []),
  ];
  return <Choice label={label} hideLabel value={value} options={options} onChange={onChange} />;
}

export function FillCard({ v, set }: CardProps) {
  const fill = (field: string, body: Omit<NonNullable<Patch["fill"]>, "field">) =>
    set({ fill: { field, ...body } });
  return (
    <Card title={s.fill.title} sub={s.fill.sub}>
      <p className="cs-text wiz-from">{s.fill.what}</p>
      {v.fills.length > 0 ? (
        <table className="tbl fill-tbl">
          <thead>
            <tr>
              <th>{s.fill.field}</th>
              <th>{s.fill.kind}</th>
              <th className="cs-n">{s.fill.blank}</th>
              <th>
                <Icon name="building" /> {s.fill.parcels.impr}
              </th>
              <th>
                <Icon name="vacant" /> {s.fill.parcels.vacant}
              </th>
              <th>
                <Icon name="all" /> {s.fill.parcels.all}
              </th>
            </tr>
          </thead>
          <tbody>
            {v.fills.map((row) => {
              const f = row.fill;
              const building = row.kind === "building";
              // Only an Other field splits: a land field (census figures among them) is the same built on or not.
              const split = f.split && row.kind === "other";
              const label = (part: string) => `${row.name}: ${part}`;
              return (
                <tr key={row.field}>
                  <td>
                    {row.name} <span className="mono wiz-from">{row.field}</span>
                  </td>
                  <td>
                    <KindTag kind={row.kind} />
                  </td>
                  <td className="cs-n">{num(row.blanks)}</td>
                  {building || split ? (
                    <td>
                      <MethodChoice
                        label={label(s.fill.parcels.impr)}
                        value={f.method ?? "auto"}
                        auto={row.auto}
                        onChange={(method) => fill(row.field, { method: method as Method })}
                      />
                    </td>
                  ) : (
                    <td className="fill-off" />
                  )}
                  {building ? (
                    <td className="fill-off" title={s.fill.locked}>
                      <span className="fill-lock" aria-hidden="true">
                        🔒
                      </span>
                      <span className="visually-hidden">{s.fill.locked}</span>
                    </td>
                  ) : split ? (
                    <td>
                      <MethodChoice
                        label={label(s.fill.parcels.vacant)}
                        value={f.vacant ?? "auto"}
                        auto={row.auto}
                        onChange={(vacant) => fill(row.field, { vacant: vacant as Method })}
                      />
                    </td>
                  ) : (
                    <td className="fill-off" />
                  )}
                  {building ? (
                    <td className="fill-off" />
                  ) : (
                    <td>
                      <MethodChoice
                        label={label(s.fill.parcels.all)}
                        value={split ? "split" : (f.method ?? "auto")}
                        auto={row.auto}
                        split={row.kind === "other"}
                        onChange={(m) =>
                          m === "split"
                            ? // Each starts from what every parcel had.
                              fill(row.field, { split: true, vacant: f.method ?? "auto" })
                            : fill(row.field, { split: false, method: m as Method })
                        }
                      />
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="wiz-ok">{s.fill.none}</p>
      )}
    </Card>
  );
}

function value(x: number) {
  return num(x, Math.abs(x) < 10 && !Number.isInteger(x) ? 1 : 0);
}

function Part({ p }: { p: FillPart }) {
  if (p.left) return <span className="wiz-from">{s.fill.left}</span>;
  if (p.value == null)
    return (
      <span className="fill-stays" title={s.fill.staysTip}>
        {s.fill.stays}
      </span>
    );
  return <>{value(p.value)}</>;
}

/** What each model group gets (SPEC F7): the value that goes into its blanks, per field. */
export function FillGroups({ v }: { v: CleanSetup }) {
  const p = v.fill_preview;
  if (!p.rows.length) return <p className="wiz-ok">{s.fill.noGroups}</p>;
  return (
    <table className="tbl fill-groups">
      <thead>
        <tr>
          <th>{s.fill.groupsField}</th>
          {p.groups.map((g) => (
            <th key={g.value} className="cs-n">
              {g.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {p.rows.map((r) => (
          <tr key={r.field}>
            <td>{r.name}</td>
            {r.cells.map((c, i) => (
              <td key={p.groups[i]?.value ?? i} className="cs-n">
                {c.main ? <Part p={c.main} /> : !c.vacant && <span className="fill-none">—</span>}
                {c.vacant && (
                  <span className="fill-vacant">
                    {s.fill.parcels.vacant}: <Part p={c.vacant} />
                  </span>
                )}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
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

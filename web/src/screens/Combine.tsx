/** The duplicates dialog's third way (F3d): a parcel file whose rows each say something different about the
 * parcel (one row per amenity) combined into one row per parcel. What each row is about becomes a yes/no field per
 * group of its values; each number column one number per parcel; and, if asked, the main value by priority. The
 * server works out the counts (wizard/combine.py); groups and the order are set in a dialog each. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Button,
  Dialog,
  Heading,
  Input,
  Menu,
  MenuItem,
  MenuTrigger,
  Modal,
  ModalOverlay,
  Popover,
  TextField,
} from "react-aria-components";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { AddButton } from "../components/AddButton";
import { DialogFoot } from "../components/DialogParts";
import { Choice, Tick } from "../components/Form";
import { num } from "../lib/format";
import { t } from "../wording";
import type { CombineHow } from "./wizardChange";

const c = t.wizard.combine;
type Group = components["schemas"]["CombineGroup-Output"];
type Preview = components["schemas"]["CombinePreview"];
type Measure = { how: CombineHow; used: boolean };
const HOWS: CombineHow[] = ["max", "min", "sum", "mean", "count"];

/** A value as compared: capitals and extra spaces ignored; "" for none (as the server's norm). */
export function norm(v: string): string {
  const n = v.toUpperCase().split(/\s+/).filter(Boolean).join(" ");
  return ["", "NULL", "NONE", "NAN", "N/A", "NA", "-"].includes(n) ? "" : n;
}

async function fetchPreview(
  projectId: string,
  name: string,
  body: Record<string, unknown>,
): Promise<Preview> {
  return unwrap(
    await api.POST("/api/projects/{project_id}/wizard/files/{name}/combine/preview", {
      params: { path: { project_id: projectId, name } },
      body,
    }),
  );
}

/** The combine choices as they stand in the dialog (unsaved), with the server's counts for them. */
export function useCombine(projectId: string, name: string, enabled: boolean) {
  const [about, setAbout] = useState<string | null>(null);
  const [groups, setGroups] = useState<Group[] | null>(null);
  // The column groups total: undefined, as set (or suggested); "", none.
  const [measure, setMeasure] = useState<string | undefined>(undefined);
  const [rowsOn, setRowsOn] = useState<boolean | null>(null);
  const [measures, setMeasures] = useState<Record<string, Measure> | null>(null);
  const [main, setMain] = useState<string[] | null>(null);
  const [mainOn, setMainOn] = useState<boolean | null>(null);
  const body = {
    about,
    groups,
    measure: measure ?? null,
    rows_on: rowsOn,
    main,
    main_on: mainOn,
    measures: measures
      ? Object.fromEntries(Object.entries(measures).flatMap(([k, m]) => (m.used ? [[k, m.how]] : [])))
      : null,
  };
  const q = useQuery({
    queryKey: ["combine", projectId, name, body],
    queryFn: () => fetchPreview(projectId, name, body),
    enabled,
    placeholderData: keepPreviousData,
  });
  const p = q.data;
  const effGroups = groups ?? p?.groups ?? [];
  const effMeasure = measure === undefined ? (p?.measure ?? null) : measure || null;
  const effMeasures: Record<string, Measure> =
    measures ?? Object.fromEntries((p?.measures ?? []).map((m) => [m.column, { how: m.how, used: m.used }]));
  const order = main ?? p?.main ?? [];
  const isMainOn = mainOn ?? p?.main_on ?? false;
  return {
    preview: p,
    pending: q.isFetching,
    about: about ?? p?.about ?? null,
    groups: effGroups,
    measure: effMeasure,
    rowsOn: rowsOn ?? p?.rows_on ?? false,
    measures: effMeasures,
    order,
    mainOn: isMainOn,
    setAbout: (v: string) => {
      setAbout(v);
      setGroups(null);
      setMain(null);
    },
    setGroups,
    setMeasure: (v: string | null) => setMeasure(v ?? ""),
    setRowsOn,
    setNumber: (column: string, m: Measure) => setMeasures({ ...effMeasures, [column]: m }),
    setMain,
    setMainOn,
    /** What Save sends. */
    saved: () =>
      p?.about
        ? {
            about: p.about,
            groups: effGroups.filter((g) => g.values.length && g.makes.length),
            measure: effMeasure,
            rows: rowsOn ?? p.rows_on,
            measures: Object.fromEntries(
              Object.entries(effMeasures).flatMap(([k, m]) => (m.used ? [[k, m.how]] : [])),
            ) as Record<string, CombineHow>,
            main: isMainOn ? order : null,
          }
        : null,
  };
}

export type CombineState = ReturnType<typeof useCombine>;

/** The options under "Combine each parcel's rows into one". */
export function CombineOptions({
  projectId,
  name,
  s,
  example,
}: {
  projectId: string;
  name: string;
  s: CombineState;
  /** The first example ID's rows (columns and cells), for "10003922 becomes: …". */
  example: { columns: string[]; rows: string[][] } | null;
}) {
  const [editing, setEditing] = useState<"groups" | "order" | null>(null);
  // A file with many number columns (a building's year, number, floor...) shows the ticked ones, the rest on asking.
  const [allNumbers, setAllNumbers] = useState(false);
  const p = s.preview;
  if (!p) return <p className="wiz-from">{c.working}</p>;
  const many = p.measures.length > 4;
  const shownNumbers =
    many && !allNumbers ? p.measures.filter((m) => (s.measures[m.column] ?? m).used) : p.measures;
  const inGroups = new Set(s.groups.flatMap((g) => g.values));
  const left = p.values.filter((v) => !inGroups.has(v.value)).length;
  return (
    <div className="wiz-indent cb-opts">
      <div className="cb-row">
        <span className="cb-label">{c.about}</span>
        {p.abouts.length ? (
          <Choice
            label={c.about}
            hideLabel
            value={s.about}
            options={p.abouts.map((a) => [a, a] as const)}
            onChange={(v) => s.setAbout(v)}
          />
        ) : (
          <span className="wiz-warn">{c.noAbout}</span>
        )}
        {p.about && <span className="wiz-from">{c.values({ n: p.values.length })}</span>}
      </div>
      {p.about && (
        <>
          {p.numbers.length > 0 && (
            <div className="cb-row">
              <span className="cb-label">{c.measuredIn}</span>
              <Choice
                label={c.measuredIn}
                hideLabel
                value={s.measure ?? ""}
                options={[["", c.noMeasure] as const, ...p.numbers.map((n) => [n, n] as const)]}
                onChange={(v) => s.setMeasure(v || null)}
              />
              <span className="wiz-from">{c.measuredNote}</span>
            </div>
          )}
          <div className="cb-row">
            <span className="cb-label">{c.groupsLabel}</span>
            <span className="pill pill-info">
              {c.groupsPill({ n: s.groups.length, fields: groupFieldCount(s.groups, s.measure) })}
            </span>
            <Button className="button button-small" onPress={() => setEditing("groups")}>
              {c.editGroups}
            </Button>
            {left > 0 && <span className="wiz-from">{c.leftNote({ n: left })}</span>}
          </div>
          {s.groups.length > 0 && (
            <p className="cb-groupline">
              {s.groups.map((g, i) => (
                <span key={g.name}>
                  {i > 0 && " · "}
                  <b>{g.name}</b> <span className="wiz-from">{makesText(g, s.measure)}</span>
                </span>
              ))}
            </p>
          )}
          <div className="cb-row">
            <span className="cb-sub">{c.numbers}</span>
            {many && !allNumbers && (
              <Button className="button button-small" onPress={() => setAllNumbers(true)}>
                {c.moreNumbers({ n: p.measures.length })}
              </Button>
            )}
          </div>
          {shownNumbers.map((m) => {
            const mine = s.measures[m.column] ?? { how: m.how, used: m.used };
            return (
              <div key={m.column} className="cb-row cb-measure">
                <Tick isSelected={mine.used} onChange={(used) => s.setNumber(m.column, { ...mine, used })}>
                  <span className="mono">{m.column}</span>
                </Tick>
                <Choice
                  label={c.howLabel({ column: m.column })}
                  hideLabel
                  value={mine.how}
                  isDisabled={!mine.used}
                  options={HOWS.map((h) => [h, c.how[h]] as const)}
                  onChange={(how) => s.setNumber(m.column, { ...mine, how })}
                />
                <span className="wiz-from">{c.have({ n: m.parcels })}</span>
              </div>
            );
          })}
          <div className="cb-row cb-measure">
            <Tick isSelected={s.rowsOn} onChange={(v) => s.setRowsOn(v)}>
              {c.rowsTick}
            </Tick>
          </div>
          <div className="cb-row">
            <Tick isSelected={s.mainOn} onChange={s.setMainOn}>
              <WithColumn text={c.mainTick({ about: p.about })} column={p.about} />
            </Tick>
            {s.mainOn && (
              <Button className="button button-small" onPress={() => setEditing("order")}>
                {c.setOrder}
              </Button>
            )}
          </div>
          <Becomes s={s} example={example} />
          <p className="wiz-from cb-note">{c.fieldsNote}</p>
        </>
      )}
      {editing === "groups" && p.about && (
        <GroupsDialog
          projectId={projectId}
          name={name}
          about={p.about}
          values={p.values}
          groups={s.groups}
          measure={s.measure}
          onDone={(g) => {
            s.setGroups(g);
            setEditing(null);
          }}
          close={() => setEditing(null)}
        />
      )}
      {editing === "order" && p.about && (
        <OrderDialog
          projectId={projectId}
          name={name}
          about={p.about}
          order={s.order}
          onDone={(o) => {
            s.setMain(o);
            setEditing(null);
          }}
          close={() => setEditing(null)}
        />
      )}
    </div>
  );
}

/** What the first example ID becomes, worked out here from its rows as shown. */
function Becomes({
  s,
  example,
}: {
  s: CombineState;
  example: { columns: string[]; rows: string[][] } | null;
}) {
  const about = s.about;
  if (!example || !about || example.rows.length === 0) return null;
  const at = example.columns.indexOf(about);
  if (at < 0) return null;
  const id = example.rows[0]?.[0] ?? "";
  const rows = example.rows.filter((r) => r[0] === id);
  const values = rows.map((r) => norm(r[at] ?? ""));
  const mAt = s.measure ? example.columns.indexOf(s.measure) : -1;
  const yes: string[] = [];
  const counts: [string, string][] = [];
  for (const g of s.groups) {
    const mine = rows.filter((_, i) => g.values.includes(values[i] ?? ""));
    if (g.makes.includes("has") && mine.length) yes.push(g.name);
    if (g.makes.includes("count")) counts.push([`${slug(g.name)}_count`, String(mine.length)]);
    if (g.makes.includes("total") && s.measure && mAt >= 0) {
      const total = mine.map((r) => Number.parseFloat(r[mAt] ?? "")).filter(Number.isFinite);
      counts.push([`${slug(g.name)}_${slug(s.measure)}`, num(total.reduce((a, b) => a + b, 0))]);
    }
  }
  const nums = Object.entries(s.measures).flatMap(([col, m]) => {
    const i = example.columns.indexOf(col);
    if (!m.used || i < 0) return [];
    const xs = rows.map((r) => Number.parseFloat(r[i] ?? "")).filter((x) => Number.isFinite(x));
    if (m.how === "count") return [[col, String(xs.length)] as const];
    if (!xs.length) return [];
    const v =
      m.how === "max"
        ? Math.max(...xs)
        : m.how === "min"
          ? Math.min(...xs)
          : m.how === "sum"
            ? xs.reduce((a, b) => a + b, 0)
            : xs.reduce((a, b) => a + b, 0) / xs.length;
    return [[col, num(v, 1)] as const];
  });
  const main = s.mainOn ? s.order.find((v) => values.includes(v)) : undefined;
  return (
    <p className="cb-becomes">
      <b>{c.becomes({ id })}</b> {yes.join(", ") || (counts.length ? "" : c.nothing)}
      {counts.map(([field, v], i) => (
        <span key={field}>
          {yes.length || i ? " · " : ""}
          <code>{field}</code> {v}
        </span>
      ))}
      {nums.map(([col, v]) => (
        <span key={col}>
          {" · "}
          <code>{col}</code> {v}
        </span>
      ))}
      {main && (
        <>
          {" · "}
          {c.main}: <code>{main}</code>
        </>
      )}
    </p>
  );
}

function GroupsDialog({
  projectId,
  name,
  about,
  values,
  groups,
  measure,
  onDone,
  close,
}: {
  projectId: string;
  name: string;
  about: string;
  values: Preview["values"];
  groups: Group[];
  /** The column a group's total is of; null: none, so no totals. */
  measure: string | null;
  onDone: (g: Group[]) => void;
  close: () => void;
}) {
  const [draft, setDraft] = useState<Group[]>(groups);
  // Values in no group ticked, to make a group of them.
  const [picked, setPicked] = useState<string[]>([]);
  // A new group makes the total of the measure if there is one (an area), else yes/no.
  const firstMakes: Group["makes"] = measure ? ["total"] : ["has"];
  const q = useQuery({
    queryKey: ["combine", projectId, name, "groups", about, draft],
    queryFn: () => fetchPreview(projectId, name, { about, groups: draft }),
    placeholderData: keepPreviousData,
  });
  const counts = new Map(values.map((v) => [v.value, v.parcels]));
  const inGroup = new Set(draft.flatMap((g) => g.values));
  const left = values.map((v) => v.value).filter((v) => !inGroup.has(v));
  const move = (value: string, to: number | "own" | "out") => {
    const without = draft.map((g) => ({ ...g, values: g.values.filter((v) => v !== value) }));
    if (to === "out") setDraft(without);
    else if (to === "own")
      setDraft([...without, { name: titleCase(value), values: [value], makes: firstMakes }]);
    else setDraft(without.map((g, i) => (i === to ? { ...g, values: [...g.values, value] } : g)));
  };
  const chip = (value: string, from: number | null) => (
    <MenuTrigger key={value}>
      <Button className="cb-chip" aria-label={c.moveTo({ value })}>
        <span className="mono">{value}</span> <span className="cb-chip-n">{num(counts.get(value) ?? 0)}</span>{" "}
        ▾
      </Button>
      <Popover className="popover" placement="bottom start" offset={2}>
        <Menu
          className="choice-list"
          aria-label={c.moveTo({ value })}
          onAction={(k) => {
            const key = String(k);
            move(value, key === "own" || key === "out" ? key : Number(key));
          }}
        >
          {draft.map((g, i) =>
            i === from ? null : (
              <MenuItem key={`g${i}`} id={String(i)} className="choice-item">
                {g.name}
              </MenuItem>
            ),
          )}
          <MenuItem id="own" className="choice-item">
            {c.ownGroup}
          </MenuItem>
          {from !== null && (
            <MenuItem id="out" className="choice-item">
              {c.leaveOut}
            </MenuItem>
          )}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal wiz-modal wiz-modal-wide">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            <WithColumn text={c.groupsTitle({ about })} column={about} />
          </Heading>
          <p className="wiz-from">{c.groupsNote}</p>
          <div className="cb-groups">
            <table className="tbl wiz-table">
              <thead>
                <tr>
                  <th>{c.groupName}</th>
                  <th className="num">{c.parcelsHead}</th>
                  <th>{c.valuesHead}</th>
                  <th>{c.makes.has}</th>
                  <th>{c.makes.count}</th>
                  <th>{measure ? c.makes.total({ measure }) : c.makes.noTotal}</th>
                </tr>
              </thead>
              <tbody>
                {draft.map((g, i) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: a group is its place (its name is edited)
                  <tr key={i}>
                    <td className="cb-gname">
                      <TextField
                        aria-label={c.groupName}
                        value={g.name}
                        onChange={(v) => setDraft(draft.map((x, j) => (j === i ? { ...x, name: v } : x)))}
                      >
                        <Input className="input" />
                      </TextField>
                    </td>
                    <td className="num cb-gn">
                      {q.isFetching || q.isPlaceholderData ? "…" : num(q.data?.group_parcels[i] ?? 0)}
                    </td>
                    <td className="cb-gvals">{g.values.map((v) => chip(v, i))}</td>
                    {(["has", "count", "total"] as const).map((m) => (
                      <td key={m} className="cb-make">
                        <Tick
                          isSelected={g.makes.includes(m)}
                          isDisabled={m === "total" && !measure}
                          onChange={(on) =>
                            setDraft(
                              draft.map((x, j) =>
                                j === i
                                  ? {
                                      ...x,
                                      makes: (["has", "count", "total"] as const).filter((k) =>
                                        k === m ? on : x.makes.includes(k),
                                      ),
                                    }
                                  : x,
                              ),
                            )
                          }
                        >
                          <span className="sr-only">{`${g.name}: ${m === "total" && measure ? c.makes.total({ measure }) : m === "total" ? c.makes.noTotal : c.makes[m]}`}</span>
                        </Tick>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {left.length > 0 && (
            <div className="cb-left">
              <div className="cb-row">
                <span className="cb-sub">{c.leftTitle({ n: left.length })}</span>
                <span className="wiz-from">{c.leftHint}</span>
                <Button
                  className="button button-small"
                  isDisabled={picked.length === 0}
                  onPress={() => {
                    const first = picked[0] ?? "";
                    setDraft([...draft, { name: titleCase(first), values: picked, makes: firstMakes }]);
                    setPicked([]);
                  }}
                >
                  {c.makeGroup}
                </Button>
              </div>
              <div className="cb-left-list">
                {left.map((v) => (
                  <Tick
                    key={v}
                    isSelected={picked.includes(v)}
                    onChange={(on) => setPicked(on ? [...picked, v] : picked.filter((x) => x !== v))}
                  >
                    <span className="mono">{v}</span>{" "}
                    <span className="cb-chip-n">{num(counts.get(v) ?? 0)}</span>
                  </Tick>
                ))}
              </div>
            </div>
          )}
          <div className="cb-row">
            <AddButton
              onPress={() => setDraft([...draft, { name: c.newGroup, values: [], makes: firstMakes }])}
            >
              {c.newGroup}
            </AddButton>
            <span className="dlg-grow" />
            <Button
              className="button button-small"
              onPress={() =>
                setDraft(
                  values.map((v) => ({ name: titleCase(v.value), values: [v.value], makes: firstMakes })),
                )
              }
            >
              {c.perValue}
            </Button>
          </div>
          <DialogFoot>
            <Button
              className="button button-primary"
              onPress={() => onDone(draft.filter((g) => g.values.length && g.makes.length))}
            >
              {c.done}
            </Button>
            <Button className="button" onPress={close}>
              {t.wizard.cancel}
            </Button>
          </DialogFoot>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function OrderDialog({
  projectId,
  name,
  about,
  order,
  onDone,
  close,
}: {
  projectId: string;
  name: string;
  about: string;
  order: string[];
  onDone: (o: string[]) => void;
  close: () => void;
}) {
  const [draft, setDraft] = useState<string[]>(order);
  const q = useQuery({
    queryKey: ["combine", projectId, name, "order", about, draft],
    queryFn: () => fetchPreview(projectId, name, { about, main: draft, main_on: true }),
    placeholderData: keepPreviousData,
  });
  const counts = new Map((q.data?.main ?? []).map((v, i) => [v, q.data?.main_parcels[i] ?? 0]));
  const most = Math.max(1, ...counts.values());
  const shift = (i: number, to: number) => {
    const next = draft.filter((_, j) => j !== i);
    next.splice(to, 0, draft[i] as string);
    setDraft(next);
  };
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal wiz-modal">
        <Dialog className="modal-body">
          <Heading slot="title" className="modal-title">
            <WithColumn text={c.orderTitle({ about })} column={about} />
          </Heading>
          <p className="wiz-from">{c.orderNote}</p>
          <div className="cb-order">
            <table className="tbl wiz-table">
              <thead>
                <tr>
                  <th />
                  <th />
                  <th>
                    <code>{about}</code>
                  </th>
                  <th className="num" colSpan={2}>
                    {c.mainFor}
                  </th>
                </tr>
              </thead>
              <tbody>
                {draft.map((v, i) => (
                  <tr key={v}>
                    <td className="num wiz-from">{i + 1}</td>
                    <td className="cb-moves">
                      <Button
                        className="tool-plain"
                        aria-label={c.top({ value: v })}
                        isDisabled={i === 0}
                        onPress={() => shift(i, 0)}
                      >
                        ⤒
                      </Button>
                      <Button
                        className="tool-plain"
                        aria-label={c.up({ value: v })}
                        isDisabled={i === 0}
                        onPress={() => shift(i, i - 1)}
                      >
                        ↑
                      </Button>
                      <Button
                        className="tool-plain"
                        aria-label={c.down({ value: v })}
                        isDisabled={i === draft.length - 1}
                        onPress={() => shift(i, i + 1)}
                      >
                        ↓
                      </Button>
                    </td>
                    <td className="mono">{v}</td>
                    <td className="num">{num(counts.get(v) ?? 0)}</td>
                    <td className="cb-bar-cell">
                      <span className="cb-bar" style={{ width: `${((counts.get(v) ?? 0) / most) * 100}%` }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <DialogFoot>
            <Button className="button button-primary" onPress={() => onDone(draft)}>
              {c.done}
            </Button>
            <Button className="button" onPress={close}>
              {t.wizard.cancel}
            </Button>
          </DialogFoot>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

/** A sentence naming a column: the column set off as code (it's the file's own name for it, not a word of ours). */
function WithColumn({ text, column }: { text: string; column: string }) {
  const at = text.indexOf(column);
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <code>{column}</code>
      {text.slice(at + column.length)}
    </>
  );
}

/** A field name from a group's or column's name, as the server makes it (wizard/combine.py slug). */
export function slug(text: string): string {
  const s = text
    .toLowerCase()
    .replace(/[^0-9a-z]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return s && /^[a-z]/.test(s) ? s : `f_${s}`;
}

/** What a group makes, in a few words: "yes/no, how many, total TotalArea". */
function makesText(g: Group, measure: string | null): string {
  return g.makes
    .filter((m) => m !== "total" || measure)
    .map((m) => (m === "total" ? c.makes.total({ measure: measure ?? "" }) : c.makes[m]))
    .join(", ");
}

function groupFieldCount(groups: Group[], measure: string | null): number {
  return groups.reduce((n, g) => n + g.makes.filter((m) => m !== "total" || measure).length, 0);
}

function titleCase(v: string): string {
  return v.toLowerCase().replace(/\b\w/g, (m) => m.toUpperCase());
}

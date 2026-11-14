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
type Group = components["schemas"]["CombineGroup"];
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
  const [groupsOn, setGroupsOn] = useState(true);
  const [measures, setMeasures] = useState<Record<string, Measure> | null>(null);
  const [main, setMain] = useState<string[] | null>(null);
  const [mainOn, setMainOn] = useState<boolean | null>(null);
  const body = {
    about,
    groups: groupsOn ? groups : [],
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
  const effGroups = groupsOn ? (groups ?? p?.groups ?? []) : [];
  const effMeasures: Record<string, Measure> =
    measures ?? Object.fromEntries((p?.measures ?? []).map((m) => [m.column, { how: m.how, used: m.used }]));
  const order = main ?? p?.main ?? [];
  const isMainOn = mainOn ?? p?.main_on ?? false;
  return {
    preview: p,
    pending: q.isFetching,
    about: about ?? p?.about ?? null,
    groups: effGroups,
    groupsOn,
    measures: effMeasures,
    order,
    mainOn: isMainOn,
    setAbout: (v: string) => {
      setAbout(v);
      setGroups(null);
      setMain(null);
    },
    setGroups,
    setGroupsOn,
    setMeasure: (column: string, m: Measure) => setMeasures({ ...effMeasures, [column]: m }),
    setMain,
    setMainOn,
    /** What Save sends. */
    saved: () =>
      p?.about
        ? {
            about: p.about,
            groups: effGroups.filter((g) => g.values.length),
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
  const p = s.preview;
  if (!p) return <p className="wiz-from">{c.working}</p>;
  const top = s.groups
    .map((g, i) => [g.name, p.group_parcels[i] ?? 0] as const)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
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
          <div className="cb-row">
            <Tick isSelected={s.groupsOn} onChange={s.setGroupsOn}>
              {c.groupsTick}
            </Tick>
            {s.groupsOn && (
              <>
                <span className="pill pill-info">{c.groupsPill({ n: s.groups.length })}</span>
                <Button className="button button-small" onPress={() => setEditing("groups")}>
                  {c.editGroups}
                </Button>
                <span className="wiz-from cb-top">{top.map(([g, n]) => `${g} ${num(n)}`).join(" · ")}</span>
              </>
            )}
          </div>
          {p.measures.length > 0 && <div className="cb-sub">{c.numbers}</div>}
          {p.measures.map((m) => {
            const mine = s.measures[m.column] ?? { how: m.how, used: m.used };
            return (
              <div key={m.column} className="cb-row cb-measure">
                <Tick isSelected={mine.used} onChange={(used) => s.setMeasure(m.column, { ...mine, used })}>
                  <span className="mono">{m.column}</span>
                </Tick>
                <Choice
                  label={c.howLabel({ column: m.column })}
                  hideLabel
                  value={mine.how}
                  isDisabled={!mine.used}
                  options={HOWS.map((h) => [h, c.how[h]] as const)}
                  onChange={(how) => s.setMeasure(m.column, { ...mine, how })}
                />
                <span className="wiz-from">{c.have({ n: m.parcels })}</span>
              </div>
            );
          })}
          <div className="cb-row">
            <Tick isSelected={s.mainOn} onChange={s.setMainOn}>
              {c.mainTick({ about: p.about })}
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
  const yes = s.groups.filter((g) => g.values.some((v) => values.includes(v))).map((g) => g.name);
  const nums = Object.entries(s.measures).flatMap(([col, m]) => {
    const i = example.columns.indexOf(col);
    if (!m.used || i < 0) return [];
    const xs = rows.map((r) => Number.parseFloat(r[i] ?? "")).filter((x) => Number.isFinite(x));
    if (m.how === "count") return [`${col} ${xs.length}`];
    if (!xs.length) return [];
    const v =
      m.how === "max"
        ? Math.max(...xs)
        : m.how === "min"
          ? Math.min(...xs)
          : m.how === "sum"
            ? xs.reduce((a, b) => a + b, 0)
            : xs.reduce((a, b) => a + b, 0) / xs.length;
    return [`${col} ${num(v, 1)}`];
  });
  const main = s.mainOn ? s.order.find((v) => values.includes(v)) : undefined;
  const parts = [yes.join(", ") || c.nothing, ...nums, ...(main ? [`${c.main}: ${main}`] : [])];
  return (
    <p className="cb-becomes">
      <b>{c.becomes({ id })}</b> {parts.join(" · ")}
    </p>
  );
}

function GroupsDialog({
  projectId,
  name,
  about,
  values,
  groups,
  onDone,
  close,
}: {
  projectId: string;
  name: string;
  about: string;
  values: Preview["values"];
  groups: Group[];
  onDone: (g: Group[]) => void;
  close: () => void;
}) {
  const [draft, setDraft] = useState<Group[]>(groups);
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
    else if (to === "own") setDraft([...without, { name: titleCase(value), values: [value] }]);
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
            {c.groupsTitle({ about })}
          </Heading>
          <p className="wiz-from">{c.groupsNote}</p>
          <div className="cb-groups">
            <table className="tbl wiz-table">
              <thead>
                <tr>
                  <th>{c.groupName}</th>
                  <th className="num">{c.parcelsHead}</th>
                  <th>{c.valuesHead}</th>
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
                    <td className="num cb-gn">{num(q.data?.group_parcels[i] ?? 0)}</td>
                    <td className="cb-gvals">{g.values.map((v) => chip(v, i))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {left.length > 0 && (
            <div className="cb-left">
              <span className="cb-sub">{c.left}</span> {left.map((v) => chip(v, null))}
            </div>
          )}
          <div className="cb-row">
            <AddButton onPress={() => setDraft([...draft, { name: c.newGroup, values: [] }])}>
              {c.newGroup}
            </AddButton>
            <span className="dlg-grow" />
            <Button
              className="button button-small"
              onPress={() => setDraft(values.map((v) => ({ name: titleCase(v.value), values: [v.value] })))}
            >
              {c.perValue}
            </Button>
          </div>
          <DialogFoot>
            <Button
              className="button button-primary"
              onPress={() => onDone(draft.filter((g) => g.values.length))}
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
            {c.orderTitle({ about })}
          </Heading>
          <p className="wiz-from">{c.orderNote}</p>
          <div className="cb-order">
            <table className="tbl wiz-table">
              <thead>
                <tr>
                  <th />
                  <th />
                  <th>{about}</th>
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

function titleCase(v: string): string {
  return v.toLowerCase().replace(/\b\w/g, (m) => m.toUpperCase());
}

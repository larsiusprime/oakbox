/** Variables › Variable lists (SPEC F9): the lists in a table, one open at a time; an open list's name, type and
 * model groups, and every variable with its test scores in one of its groups and whether it's recommended for the
 * list's type, ticked in or out. */
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import type { ListView, TestRow, VarList, VarListsView, VarTestView } from "../api/client";
import { useSetVarLists, useVarLists } from "../api/models";
import { useStep } from "../api/steps";
import { AddButton } from "../components/AddButton";
import { Choice, Tick } from "../components/Form";
import { MultiPick } from "../components/MultiPick";
import { RemoveButton } from "../components/RemoveButton";
import { Seg } from "../components/Seg";
import { num } from "../lib/format";
import { say, t } from "../wording";

const s = t.values.lists;
type Kind = "regression" | "ml";

/** A list as the route takes it back. */
const plain = (x: ListView): VarList => ({
  id: x.id,
  name: x.name,
  kind: x.kind,
  groups: x.groups,
  variables: x.variables,
});

export function VarListsStep({ projectId }: { projectId: string }) {
  const q = useVarLists(projectId);
  const vt = useStep("vartest", projectId).data;
  const put = useSetVarLists(projectId);
  const [open, setOpen] = useState<string | null>(null);
  const v = q.data;
  if (!v) return <p className="empty">{q.error?.message ?? t.project.loading}</p>;
  if (!v.variables.length) return <p className="wiz-from">{s.noVariables}</p>;
  const shown = open ?? v.lists[0]?.id ?? null;
  const save = (lists: VarList[]) => put.mutate(lists);
  const change = (id: string, patch: Partial<VarList>) =>
    save(v.lists.map((x) => (x.id === id ? { ...plain(x), ...patch } : plain(x))));
  // A new list starts empty: the user chooses its groups and ticks its variables.
  const add = () => {
    const name = s.newName({ n: v.lists.length + 1 });
    put.mutate([...v.lists.map(plain), { id: "", name, kind: "regression", groups: [], variables: [] }], {
      onSuccess: (data) => setOpen(data.lists[data.lists.length - 1]?.id ?? null),
    });
  };
  const gname = Object.fromEntries(v.groups.map((g) => [g.id, g]));
  return (
    <div className="cs-step">
      {v.missing.length > 0 && <p className="wiz-warn">{say.values.lists.missing(v.missing)}</p>}
      {!v.tested && <p className="wiz-warn">{s.notTested}</p>}
      {v.lists.length === 0 ? (
        <p className="wiz-from">{s.none}</p>
      ) : (
        <table className="tbl vl-lists">
          <thead>
            <tr>
              <th className="vl-arrow" />
              <th>{s.list}</th>
              <th>{s.type}</th>
              <th>{s.groups}</th>
              <th className="cs-n">{s.count}</th>
              <th>{s.usedBy}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {v.lists.map((x) => {
              const on = x.id === shown;
              const Chevron = on ? ChevronDown : ChevronRight;
              return [
                <tr key={x.id} className={on ? "vl-open" : undefined}>
                  <td className="vl-arrow">
                    <Button
                      className="vl-toggle"
                      aria-expanded={on}
                      aria-label={x.name}
                      onPress={() => setOpen(on ? "" : x.id)}
                    >
                      <Chevron aria-hidden="true" size="1em" />
                    </Button>
                  </td>
                  <td>
                    <Button className="vl-name" onPress={() => setOpen(on ? "" : x.id)}>
                      {x.name}
                    </Button>
                  </td>
                  <td>{s.kindShort[x.kind]}</td>
                  <td>
                    {x.groups.map((g) => (
                      <span key={g} className="vl-chip">
                        <span className="mg-sw ab-sw" style={{ background: gname[g]?.color }} />
                        {gname[g]?.name ?? g}
                      </span>
                    ))}
                  </td>
                  <td className="cs-n">{num(x.variables.length)}</td>
                  <td className="wiz-from">{x.used_by.length ? x.used_by.join(", ") : s.notUsed}</td>
                  <td>
                    <RemoveButton
                      what={x.name}
                      onPress={() => save(v.lists.filter((y) => y.id !== x.id).map(plain))}
                      undo={() => save(v.lists.map(plain))}
                    />
                  </td>
                </tr>,
                on && (
                  <tr key={`${x.id}-open`} className="vl-detail">
                    <td />
                    <td colSpan={6}>
                      <ListEditor list={x} view={v} tests={vt} change={(patch) => change(x.id, patch)} />
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      )}
      <p className="cs-row add-row">
        <AddButton onPress={add}>{s.add}</AddButton>
      </p>
      {put.error && (
        <p className="error" role="alert">
          {put.error.message}
        </p>
      )}
      <p className="wiz-from">{s.written}</p>
    </div>
  );
}

function Name({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [text, setText] = useState<string | null>(null);
  const save = () => {
    const next = text?.trim();
    if (next && next !== value) onCommit(next);
    setText(null);
  };
  return (
    <TextField
      aria-label={s.name}
      value={text ?? value}
      onChange={setText}
      onBlur={save}
      className="vl-namefield"
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

/** A variable's figures in one group: its best value's share of sales, its strongest correlation with price (and
 * which value, for a category), its VIF; each with whether it passed. */
type Figures = {
  rep: TestRow | null;
  corr: TestRow | null;
  vif: TestRow | null;
};

function figures(rows: TestRow[] | undefined, by: (r: TestRow) => number): TestRow | null {
  if (!rows?.length) return null;
  return rows.reduce((a, b) => (by(b) > by(a) ? b : a));
}

function ListEditor({
  list,
  view,
  tests,
  change,
}: {
  list: ListView;
  view: VarListsView;
  tests: VarTestView | undefined;
  change: (patch: Partial<VarList>) => void;
}) {
  const kind = list.kind as Kind;
  const tested = (tests?.receipt?.groups ?? []).filter((g) => Object.keys(g.tests).length > 0);
  // Until its groups are chosen, any tested group's scores can be shown.
  const pool = list.groups.length ? list.groups : view.groups.filter((g) => g.modeled).map((g) => g.id);
  const mine = pool.filter((g) => tested.some((x) => x.id === g));
  const [gid, setGid] = useState<string | null>(null);
  const shown = gid && mine.includes(gid) ? gid : (mine[0] ?? pool[0] ?? null);
  const group = tested.find((x) => x.id === shown);
  const recs = shown ? view.recommend[shown]?.[kind] : undefined;
  const gname = Object.fromEntries(view.groups.map((g) => [g.id, g.name]));
  const byVar = (test: string) => {
    const out: Record<string, TestRow[]> = {};
    for (const r of group?.tests[test] ?? []) {
      out[r.variable] = [...(out[r.variable] ?? []), r];
    }
    return out;
  };
  const rep = byVar("represented");
  const corr = byVar("corr");
  const vif = byVar("vif");
  const fig = (field: string): Figures => ({
    rep: figures(rep[field], (r) => r.value ?? 0),
    corr: figures(corr[field], (r) => Math.abs(r.value ?? 0)),
    vif: vif[field]?.[0] ?? null,
  });
  const chosen = new Set(list.variables);
  // Recommended first, then by how strongly they move with price: the order doesn't move as they're ticked.
  const rows = [...view.variables].sort((a, b) => {
    const ra = recs?.[a.field] == null ? 0 : 1;
    const rb = recs?.[b.field] == null ? 0 : 1;
    if (ra !== rb) return ra - rb;
    return Math.abs(fig(b.field).corr?.value ?? 0) - Math.abs(fig(a.field).corr?.value ?? 0);
  });
  const order = view.variables.map((x) => x.field);
  const set = (fields: Set<string>) => change({ variables: order.filter((f) => fields.has(f)) });
  const names = Object.fromEntries(view.variables.map((x) => [x.field, x.name]));
  const pct = (r: TestRow | null) => (r?.value == null ? "—" : `${Math.round(100 * r.value)}%`);
  return (
    <div className="vl-edit">
      {/* Labels in one column, what's set in the next. */}
      <div className="set-grid">
        <span className="wiz-label">{s.name}</span>
        <span>
          <Name value={list.name} onCommit={(name) => change({ name })} />
        </span>
        <span className="wiz-label">{s.type}</span>
        <span>
          <Seg
            label={s.type}
            value={kind}
            options={[
              ["regression", s.kinds.regression ?? ""],
              ["ml", s.kinds.ml ?? ""],
            ]}
            onChange={(k) => change({ kind: k })}
          />
        </span>
        <span className="wiz-label">{s.groups}</span>
        <span>
          <MultiPick
            label={`${s.groups}: ${list.name}`}
            values={view.groups.filter((g) => g.modeled).map((g) => ({ value: g.id, label: g.name }))}
            chosen={list.groups}
            onChange={(groups) => change({ groups })}
          />
        </span>
      </div>
      {list.groups.length === 0 && <p className="wiz-warn">{s.chooseGroups}</p>}
      <p className="wiz-from">{s.rule[kind]}</p>
      {list.warnings.length > 0 && (
        <div className="vl-warns">
          {list.warnings.map((w) => (
            <p key={`${w.code}-${w.group ?? ""}`} className="wiz-warn">
              {w.code === "few_sales"
                ? s.warn.few_sales({
                    group: gname[w.group ?? ""] ?? w.group ?? "",
                    sales: w.n,
                    vars: list.variables.length,
                  })
                : w.code === "blanks"
                  ? s.warn.blanks({ names: w.variables.map((f) => names[f] ?? f).join(", ") })
                  : s.warn.many_values({
                      names: w.variables.map((f) => names[f] ?? f).join(", "),
                      ml: kind === "ml",
                    })}
            </p>
          ))}
        </div>
      )}
      <div className="vl-editrow">
        {pool.length > 1 && (
          <>
            <span className="vl-label">{s.scoresFor}</span>
            <Choice
              label={s.scoresFor}
              hideLabel
              value={shown}
              options={mine.map((g) => [g, gname[g] ?? g] as const)}
              onChange={setGid}
            />
            {mine.length < pool.length && (
              <span className="wiz-from">
                {say.values.lists.notTestedIn(
                  pool.filter((g) => !mine.includes(g)).map((g) => gname[g] ?? g),
                )}
              </span>
            )}
          </>
        )}
        <span className="vl-grow" />
        <Button
          className="button"
          onPress={() =>
            // What the pills say: recommended for the group shown (without its tests, across the list's groups).
            set(
              new Set(order.filter((f) => (recs && shown ? recs[f] == null : recommendedIn(view, list, f)))),
            )
          }
        >
          {shown && recs ? s.tickRecommendedFor({ group: gname[shown] ?? shown }) : s.tickRecommended}
        </Button>
        <Button className="button" onPress={() => set(new Set())}>
          {s.untickAll}
        </Button>
      </div>
      <div className="vl-scroll">
        <table className="tbl vl-vars">
          <thead>
            <tr>
              <th className="vl-tick">{s.in}</th>
              <th>{s.variable}</th>
              <th>{s.kind}</th>
              <th className="cs-n">{s.represented}</th>
              <th className="cs-n">{s.corr}</th>
              <th className="cs-n">{s.vif}</th>
              <th>{s.forType[kind]}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => {
              const f = fig(x.field);
              const why = recs?.[x.field];
              const on = chosen.has(x.field);
              return (
                <tr key={x.field} className={on ? undefined : "vl-out"}>
                  <td className="vl-tick">
                    <Tick
                      isSelected={on}
                      onChange={(yes) => {
                        const next = new Set(chosen);
                        if (yes) next.add(x.field);
                        else next.delete(x.field);
                        set(next);
                      }}
                    >
                      <span className="visually-hidden">{x.name}</span>
                    </Tick>
                  </td>
                  <td>
                    {x.name} <span className="mono wiz-from">{x.field}</span>
                  </td>
                  <td className="wiz-from">{x.values != null ? s.category({ n: x.values }) : s.number}</td>
                  <td className="cs-n">{pct(f.rep)}</td>
                  <td className="cs-n">
                    {f.corr?.value == null ? (
                      "—"
                    ) : (
                      <>
                        <span className={f.corr.passed ? undefined : "vl-bad"}>{num(f.corr.value, 2)}</span>
                        {f.corr.level && <span className="wiz-from"> ({f.corr.level})</span>}
                      </>
                    )}
                  </td>
                  <td className="cs-n">
                    {f.vif?.value == null ? (
                      "—"
                    ) : (
                      <span className={f.vif.passed ? undefined : "vl-bad"}>{num(f.vif.value, 1)}</span>
                    )}
                  </td>
                  <td>
                    <span className="rv-cell-pill">
                      {why == null ? (
                        <span className="pill pill-ok">✓ {s.recommended}</span>
                      ) : (
                        <span className="pill pill-bad">× {s.reasons[why] ?? why}</span>
                      )}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Recommended for the list's type in the groups holding most of its sales: before the tests, by blanks and
 * categories alone. */
function recommendedIn(view: VarListsView, list: { groups: string[]; kind: string }, field: string): boolean {
  const sales = Object.fromEntries(view.groups.map((g) => [g.id, g.sales ?? 0]));
  const any = list.groups.some((g) => (sales[g] ?? 0) > 0);
  const weight = (g: string) => (any ? (sales[g] ?? 0) : 1);
  const total = list.groups.reduce((n, g) => n + weight(g), 0);
  const yes = list.groups
    .filter((g) => view.recommend[g]?.[list.kind]?.[field] == null)
    .reduce((n, g) => n + weight(g), 0);
  return total > 0 && 2 * yes > total;
}

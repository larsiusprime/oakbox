import { useState } from "react";
import { Button, Input, Menu, MenuItem, MenuTrigger, Popover, TextField } from "react-aria-components";
import type { ModelEntry, ModelRow, ModelSetup, ModelView, SalesSet } from "../api/client";
import { useSetGroupModels } from "../api/models";
import { AddButton } from "../components/AddButton";
import { type Column, DataTable, useWidths, type Widths } from "../components/DataTable";
import { Choice } from "../components/Form";
import { Pill } from "../components/Pill";
import { RemoveButton } from "../components/RemoveButton";
import { Seg } from "../components/Seg";
import { day, num, signed } from "../lib/format";
import { t } from "../wording";
import { ConfigSummary, ModelOptions } from "./ModelOptions";

const m = t.values.model;

/** Model values › Models: a tab per modeled group (the others greyed, not modeled), its models in a table: each a
 * name, an engine, its variable list and (Multi-MRA, Local area) its location stack, opened in place one at a time;
 * Add a model; copy a group's models to others; back to the default ones. */
export function GroupModelsCard({ projectId, v, gid }: { projectId: string; v: ModelSetup; gid: string }) {
  const put = useSetGroupModels(projectId);
  const [stack, setStack] = useState<string | null>(null);
  const [adding, setAdding] = useState<ModelEntry | null>(null);
  const modeled = v.groups.filter((g) => g.modeled);
  const at = Math.max(
    0,
    modeled.findIndex((x) => x.id === gid),
  );
  const g = modeled[at];
  if (!g) return <p className="wiz-from">{t.groups.notModeled}</p>;
  const engines = Object.fromEntries(v.engines.map((e) => [e.key, e]));
  const lists = Object.fromEntries(v.lists.map((x) => [x.id, x]));
  const entries: ModelEntry[] = g.models.map((e) => ({
    key: e.key,
    name: e.name,
    engine: e.engine,
    list_id: e.list_id ?? null,
    locations: e.locations ?? null,
    log: e.log ?? null,
    intercept: e.intercept ?? null,
    interactions: e.interactions ?? null,
    optimize_vars: e.optimize_vars ?? null,
    n_trials: e.n_trials ?? null,
    use_gpu: e.use_gpu ?? null,
  }));
  const places = Object.fromEntries(v.locations.map((x) => [x.field, x.name]));
  const save = (models: ModelEntry[] | null, group = g.id) => put.mutate({ group, models });
  const change = (i: number, patch: Partial<ModelEntry>) =>
    save(entries.map((e, j) => (j === i ? { ...e, ...patch } : e)));
  const firstList = (engine: string) => {
    const kind = engines[engine]?.kind;
    // As the backend proposes: the first of its type for this group; none, rather than another group's.
    return v.lists.find((x) => x.kind === kind && x.groups.includes(g.id))?.id;
  };
  const listOptions = v.lists.map((x) => [x.id, m.list({ name: x.name, n: x.count })] as const);
  const others = modeled.filter((x) => x.id !== g.id);
  return (
    <div className="cs-step">
      <div className="gm-head">
        <span className="gm-of">{m.groupOf({ n: at + 1, of: modeled.length })}</span>
        <h3 className="gm-title">
          <span className="mg-sw ab-sw big" style={{ background: g.color }} />
          {g.name}
        </h3>
        <span className="wiz-from">{m.salesTab({ n: g.sales })}</span>
      </div>
      {g.sales < 15 && <p className="wiz-warn">{m.tooFew}</p>}
      {entries.length === 0 && !adding ? (
        <p className="wiz-warn">{m.noModels}</p>
      ) : (
        <table className="tbl gm-models">
          <thead>
            <tr>
              <th>{m.model}</th>
              <th>{m.engine}</th>
              <th>{m.variables}</th>
              <th>{m.configuration}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {g.models.map((e, i) => {
              const eng = engines[e.engine];
              const open = stack === e.key;
              const options = eng?.options ?? [];
              const entry = entries[i] ?? e;
              return [
                <tr key={e.key}>
                  <td>
                    <NameCell value={e.name} label={m.nameLabel} onCommit={(name) => change(i, { name })} />
                  </td>
                  <td>{eng?.name ?? e.engine}</td>
                  <td>
                    {eng?.takes_list ? (
                      <Choice
                        label={`${m.variables}: ${e.name}`}
                        hideLabel
                        value={e.list_id ?? null}
                        options={listOptions}
                        placeholder={m.chooseList}
                        onChange={(list_id) => change(i, { list_id })}
                      />
                    ) : (
                      <span className="wiz-from">{m.takesNoList}</span>
                    )}
                    {e.warnings
                      .filter((w) => w.code !== "no_locations")
                      .map((w) => (
                        <p key={w.code} className="wiz-warn gm-warn">
                          {w.code === "kind_mismatch"
                            ? m.warn.kind_mismatch({
                                engine: eng?.name ?? e.engine,
                                kind: lists[e.list_id ?? ""]?.kind ?? "",
                              })
                            : w.code === "blanks_left_out"
                              ? m.warn.blanks_left_out({ n: w.n })
                              : m.warn[w.code as "list_missing" | "list_empty" | "no_list"]}
                        </p>
                      ))}
                  </td>
                  <td>
                    {options.length ? (
                      <>
                        <ConfigSummary e={e} options={options} defaults={v.defaults} places={places} />{" "}
                        <Button className="button button-small" onPress={() => setStack(open ? null : e.key)}>
                          {open ? m.done : m.change}
                        </Button>
                      </>
                    ) : (
                      <span className="wiz-from">{m.noSettings}</span>
                    )}
                    {e.warnings
                      .filter((w) => w.code === "no_locations")
                      .map((w) => (
                        <p key={w.code} className="wiz-warn gm-warn">
                          {m.warn.no_locations({ engine: e.engine })}
                        </p>
                      ))}
                  </td>
                  <td>
                    <RemoveButton
                      what={e.engine}
                      onPress={() => save(entries.filter((_, j) => j !== i))}
                      undo={() => save(entries)}
                    />
                  </td>
                </tr>,
                open && (
                  <tr key={`${e.key}-config`} className="gm-detail">
                    <td colSpan={5}>
                      <ModelOptions
                        projectId={projectId}
                        group={g.id}
                        e={entry}
                        name={e.name}
                        options={options}
                        defaults={v.defaults}
                        offered={v.locations}
                        change={(patch) => change(i, patch)}
                      />
                    </td>
                  </tr>
                ),
              ];
            })}
            {adding && (
              <tr className="gm-adding">
                <td>
                  <TextField
                    aria-label={m.nameLabel}
                    value={adding.name ?? ""}
                    onChange={(name) => setAdding({ ...adding, name })}
                  >
                    <Input
                      className="input"
                      placeholder={engines[adding.engine]?.name ?? m.namePlaceholder}
                    />
                  </TextField>
                </td>
                <td>
                  <Choice
                    label={m.engine}
                    hideLabel
                    value={adding.engine}
                    options={v.engines.map((x) => [x.key, x.name] as const)}
                    onChange={(engine) =>
                      setAdding({ ...adding, engine, list_id: firstList(engine) ?? null })
                    }
                  />
                </td>
                <td>
                  {engines[adding.engine]?.takes_list ? (
                    <Choice
                      label={m.variables}
                      hideLabel
                      value={adding.list_id ?? null}
                      options={listOptions}
                      placeholder={m.chooseList}
                      onChange={(list_id) => setAdding({ ...adding, list_id })}
                    />
                  ) : (
                    <span className="wiz-from">{m.takesNoList}</span>
                  )}
                  <p className="wiz-from gm-warn">{engines[adding.engine]?.note}</p>
                </td>
                <td className="wiz-from">{m.configLater}</td>
                <td>
                  <div className="gm-addtools">
                    <Button
                      className="button button-primary"
                      onPress={() => {
                        save([...entries, { ...adding, key: "" }]);
                        setAdding(null);
                      }}
                    >
                      {m.addIt}
                    </Button>
                    <Button className="button button-small" onPress={() => setAdding(null)}>
                      {m.cancel}
                    </Button>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
      <p className="cs-row add-row">
        {!adding && (
          <AddButton
            onPress={() =>
              setAdding({
                key: "",
                name: "",
                engine: "lightgbm",
                list_id: firstList("lightgbm") ?? null,
                locations: null,
              })
            }
          >
            {m.add}
          </AddButton>
        )}
        {others.length > 0 && (
          <MenuTrigger>
            <Button className="button button-small">{m.copy}</Button>
            <Popover className="popover rc-menu" placement="bottom start">
              <Menu
                className="choice-list"
                onAction={(key) => {
                  for (const x of key === "*" ? others : others.filter((o) => o.id === key))
                    save(entries, x.id);
                }}
              >
                {[{ id: "*", name: m.everyOther }, ...others].map((x) => (
                  <MenuItem key={x.id} id={x.id} className="choice-item rc-menu-item" textValue={x.name}>
                    {x.name}
                  </MenuItem>
                ))}
              </Menu>
            </Popover>
          </MenuTrigger>
        )}
        {g.custom && (
          <Button className="button button-small" onPress={() => save(null)}>
            {m.backToDefault}
          </Button>
        )}
      </p>
      {put.error && (
        <p className="error" role="alert">
          {put.error.message}
        </p>
      )}
      <p className="wiz-from">{m.written({ group: g.id })}</p>
    </div>
  );
}

function NameCell({
  value,
  label,
  onCommit,
}: {
  value: string;
  label: string;
  onCommit: (v: string) => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const save = () => {
    const next = text?.trim();
    if (next && next !== value) onCommit(next);
    setText(null);
  };
  return (
    <TextField aria-label={label} value={text ?? value} onChange={setText} onBlur={save} className="gm-name">
      <Input
        className="input"
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
        }}
      />
    </TextField>
  );
}

/** Each model group: its models on the holdout, the ensemble first, the roll's value above them on the same sales. */
type How = "iaao" | "academic";
type Fig = ModelRow;

const h = m.how;

/** A figure by its column (a trimmed figure as its untrimmed one), written as step 4 writes it: ratios to three
 * decimals, the COD and the VEI to one, the VEI in percent; counts whole, a big number shortened. */
function fmt(key: string, v: number | null | undefined): string {
  if (v == null) return "—";
  if (key.startsWith("count")) return num(v);
  if (key === "mape") return `${num(100 * v, 1)}%`;
  if (key === "mse")
    return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(v);
  if (key === "rmse") return num(v);
  if (key === "prb") return signed(v, 3);
  if (key === "vei") return `${signed(v, 1)}%`;
  if (key === "vei_sig") return `${num(v, 1)}%`;
  if (key === "utility_score" || key === "cod") return num(v, 1);
  if (key === "median_ratio" || key === "mean_ratio" || key === "prd" || key === "slope") return num(v, 3);
  return num(v, 2);
}

/** A column of one of OpenAVMKit's figures (read from `from`: a trimmed table's COD is in the COD column);
 * judged ones get their pill, pinned left. */
function fig(key: string, label: string, tip?: string, from = key): Column<Fig> {
  return {
    key,
    label,
    ...(tip ? { tip } : {}),
    numeric: true,
    value: (r) => r.values[from] ?? null,
    cell: (r) => {
      const j = r.judged[from];
      return (
        <span className="rv-cell">
          <span className="rv-cell-pill">{j && <Pill v={j} title={h.verdict[j]} />}</span>
          <span>{fmt(key, r.values[from])}</span>
        </span>
      );
    },
  };
}

/** A blank column where the main table has one this table hasn't, so the two line up. */
function blank(key: string): Column<Fig> {
  return { key, label: "", spacer: true, value: () => null };
}

const MODEL: Column<Fig> = {
  key: "model",
  label: m.model,
  width: 200,
  value: (r) => r.name,
  cell: (r) => (
    <>
      {r.name}
      {r.model === "ensemble" && <span className="wiz-from"> · {m.shipped}</span>}
    </>
  ),
};

const IAAO_COLUMNS = [
  MODEL,
  fig("utility_score", h.col.utility, h.tip.utility),
  fig("count_univ", h.col.parcels, h.tip.parcels),
  fig("count_sales", h.col.sales, h.tip.sales),
  fig("median_ratio", h.col.median, h.tip.median),
  fig("cod", h.col.cod, h.tip.cod),
  fig("prd", h.col.prd, h.tip.prd),
  fig("prb", h.col.prb, h.tip.prb),
  fig("vei", h.col.vei, h.tip.vei),
  fig("vei_sig", h.col.veiSig, h.tip.veiSig),
  fig("chd", h.col.chd, h.tip.chd),
];
// The trimmed table, in the same columns: its figures under theirs, blanks where it has none.
const IAAO_TRIMMED = [
  MODEL,
  blank("utility_score"),
  blank("count_univ"),
  fig("count_sales", h.col.sales, h.tip.salesTrimmed, "count_trim"),
  fig("median_ratio", h.col.median, h.tip.median, "median_ratio_trim"),
  fig("cod", h.col.cod, h.tip.cod, "cod_trim"),
  fig("prd", h.col.prd, h.tip.prd, "prd_trim"),
  fig("prb", h.col.prb, h.tip.prb, "prb_trim"),
  fig("vei", h.col.vei, h.tip.vei, "vei_trim"),
  fig("vei_sig", h.col.veiSig, h.tip.veiSig, "vei_sig_trim"),
  blank("chd"),
];
const ACADEMIC = [
  MODEL,
  fig("count", h.col.sales, h.tip.sales),
  fig("mape", h.col.mape, h.tip.mape),
  fig("mse", h.col.mse, h.tip.mse),
  fig("rmse", h.col.rmse, h.tip.rmse),
  fig("median_ratio", h.col.median, h.tip.median),
  fig("mean_ratio", h.col.mean, h.tip.mean),
  fig("slope", h.col.slope, h.tip.slope),
];
// Under either view, sharing its widths: the model column lines up; the rest are its own.
const TIMINGS = [
  MODEL,
  fig("time_total", h.col.total, undefined, "total"),
  fig("time_param", h.col.param, h.tip.param, "param"),
  fig("time_train", h.col.train, undefined, "train"),
  fig("time_test", h.col.test, h.tip.test, "test"),
  fig("time_univ", h.col.univ, h.tip.univ, "univ"),
  fig("time_chd", h.col.chd, h.tip.chdTime, "chd"),
];

/** The columns with a figure in any of a view's tables (CHD, say, is only figured on the study set): every table
 * in the view shows the same ones, so they line up. */
function shown(tables: [Column<Fig>[], Fig[]][]): Set<string> {
  const keys = new Set(["model"]);
  for (const [columns, rows] of tables)
    for (const c of columns) if (!c.spacer && rows.some((r) => c.value(r) != null)) keys.add(c.key);
  return keys;
}

/** One collapsible table: its title, a line on what it is, the table. */
function Section({
  id,
  title,
  sub,
  open = true,
  children,
}: {
  id: string;
  title: string;
  sub?: string;
  open?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="md-sec" open={open} data-sec={id}>
      <summary>
        <span className="md-sec-title">{title}</span>
        {sub && <span className="wiz-from"> · {sub}</span>}
      </summary>
      {children}
    </details>
  );
}

function Table({
  columns,
  rows,
  keys,
  widths,
}: {
  columns: Column<Fig>[];
  rows: Fig[];
  keys: Set<string>;
  widths: Widths;
}) {
  return (
    <DataTable
      id="how"
      widths={widths}
      columns={columns.filter((c) => keys.has(c.key))}
      rows={rows}
      rowKey={(r) => r.model}
      rowClass={(r) => (r.model === "assessor" ? "md-roll" : r.model === "ensemble" ? "md-ship" : undefined)}
    />
  );
}

function span(s: SalesSet) {
  const n = m.salesCount2({ n: s.sales });
  return s.first && s.last ? `${n}, ${day(s.first)} – ${day(s.last)}` : n;
}

/** How they did, as OpenAVMKit's benchmark has it, a model group at a time: the IAAO figures on each set of
 * sales (the roll only on the study set), or the academic ones; each untrimmed, then trimmed; and the timings. */
export function HowTheyDid({ view }: { view: ModelView }) {
  const r = view.receipt;
  const [gid, setGid] = useState<string | null>(null);
  const [how, setHow] = useState<How>("iaao");
  const iaaoWidths = useWidths("how-iaao");
  const academicWidths = useWidths("how-academic");
  if (!r) return null;
  const g = r.groups.find((x) => x.id === gid) ?? r.groups.find((x) => !x.skipped) ?? r.groups[0];
  if (!g) return null;
  const widths = how === "iaao" ? iaaoWidths : academicWidths;
  const keys =
    how === "iaao"
      ? shown(
          g.sets
            .flatMap((s) => [[IAAO_COLUMNS, s.rows] as const, [IAAO_TRIMMED, s.trimmed] as const])
            .map((x) => [...x]),
        )
      : shown([
          [ACADEMIC, g.academic],
          [ACADEMIC, g.academic_trimmed],
        ]);
  const timed = shown([[TIMINGS, g.timings]]);
  return (
    <div className="cs-receipt">
      {view.stale && <p className="wiz-warn">{m.stale}</p>}
      <div className="md-how-bar">
        <Choice
          label={m.group}
          value={g.id}
          options={r.groups.map(
            (x) =>
              [
                x.id,
                x.skipped ? `${x.name} · ${h.notModeled}` : `${x.name} · ${m.salesCount2({ n: x.sales })}`,
              ] as [string, string],
          )}
          onChange={setGid}
        />
        <Seg
          label={h.which}
          value={how}
          options={[
            ["iaao", h.iaao],
            ["academic", h.academic],
          ]}
          onChange={setHow}
        />
      </div>
      {g.skipped ? (
        <p className="wiz-warn">{m.skipped({ why: g.skipped })}</p>
      ) : how === "iaao" ? (
        g.sets.map((s) => (
          <div key={s.key}>
            <Section id={s.key} title={h.set[s.key]} sub={span(s)}>
              <p className="wiz-from md-sec-note">{h.setWhy[s.key]}</p>
              {s.rows.length && s.sales ? (
                <Table columns={IAAO_COLUMNS} rows={s.rows} keys={keys} widths={widths} />
              ) : (
                <p className="md-empty">{h.empty[s.key]}</p>
              )}
            </Section>
            {s.sales > 0 && (
              <Section id={`${s.key}-trim`} title={h.trimmed({ what: h.set[s.key] })} sub={h.trimmedWhy}>
                <Table columns={IAAO_TRIMMED} rows={s.trimmed} keys={keys} widths={widths} />
              </Section>
            )}
          </div>
        ))
      ) : (
        <>
          <Section id="academic" title={h.academicTitle} sub={span(g.sets[0] as SalesSet)}>
            <p className="wiz-from md-sec-note">{h.academicWhy}</p>
            <Table columns={ACADEMIC} rows={g.academic} keys={keys} widths={widths} />
          </Section>
          <Section id="academic-trim" title={h.trimmed({ what: h.academicTitle })} sub={h.trimmedWhy}>
            <Table columns={ACADEMIC} rows={g.academic_trimmed} keys={keys} widths={widths} />
          </Section>
        </>
      )}
      {!g.skipped && (
        <Section id="timings" title={h.timings} sub={h.timingsWhy} open={false}>
          <Table columns={TIMINGS} rows={g.timings} keys={timed} widths={widths} />
        </Section>
      )}
      <p className="wiz-from">{m.nextSlice}</p>
      {r.notes.length > 0 && (
        <details className="cs-step">
          <summary>{m.notesTitle}</summary>
          <ul className="cs-list-plain">
            {r.notes.map((n) => (
              <li key={n} className="wiz-from">
                {n}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

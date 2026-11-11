import { useState } from "react";
import type { ModelRow, ModelView, SalesSet } from "../api/client";
import { type Column, DataTable, useWidths, type Widths } from "../components/DataTable";
import { ExcludedSince } from "../components/ExcludedSince";
import { Choice } from "../components/Form";
import { OnTheMap } from "../components/OnTheMap";
import { Pill } from "../components/Pill";
import { Seg } from "../components/Seg";
import { day, num, signed } from "../lib/format";
import { usePlace } from "../lib/place";
import { t } from "../wording";
import { ModelMap, ModelOnMap, useMapModel } from "./ModelMap";

const m = t.values.model;

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
// A set's tables (untrimmed and trimmed): each model's Map shows its ratios on that set's sales. The timings, none.
const withMap = (columns: Column<Fig>[], set: string) =>
  columns.flatMap((c) =>
    c.key === "model"
      ? [
          c,
          {
            key: "map",
            label: t.mapWindow.step.showOnMap,
            plain: true,
            width: 34,
            value: () => null,
            cell: (r: Fig) => <ModelOnMap set={set} model={r.model} />,
          },
        ]
      : [c],
  );

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
  const keys = new Set(["model", "map"]);
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
  const projectId = usePlace().where?.projectId ?? "";
  const mapModel = useMapModel();
  if (!r) return null;
  const g = r.groups.find((x) => x.id === gid) ?? r.groups.find((x) => !x.skipped) ?? r.groups[0];
  if (!g) return null;
  const mapSet = g.sets.find((x) => x.key === mapModel.set) ?? g.sets[0];
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
      <ExcludedSince n={view.excluded_since} />
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
      {!g.skipped && (
        <OnTheMap projectId={projectId} step={h.mapStep} title={h.mapInstruction} sub={h.mapInstructionSub}>
          <ModelMap
            projectId={projectId}
            group={g.id}
            groupName={g.name}
            model={mapModel.model}
            modelName={
              g.sets.flatMap((x) => x.rows).find((x) => x.model === mapModel.model)?.name ?? mapModel.model
            }
            set={{
              key: mapSet?.key ?? "holdout",
              name: h.set[(mapSet?.key ?? "holdout") as keyof typeof h.set],
              first: mapSet?.first ?? null,
              last: mapSet?.last ?? null,
            }}
          />
        </OnTheMap>
      )}
      {g.skipped ? (
        <p className="wiz-warn">{m.skipped({ why: g.skipped })}</p>
      ) : how === "iaao" ? (
        g.sets.map((s) => (
          <div key={s.key}>
            <Section id={s.key} title={h.set[s.key]} sub={span(s)}>
              <p className="wiz-from md-sec-note">{h.setWhy[s.key]}</p>
              {s.rows.length && s.sales ? (
                <Table columns={withMap(IAAO_COLUMNS, s.key)} rows={s.rows} keys={keys} widths={widths} />
              ) : (
                <p className="md-empty">{h.empty[s.key]}</p>
              )}
            </Section>
            {s.sales > 0 && (
              <Section id={`${s.key}-trim`} title={h.trimmed({ what: h.set[s.key] })} sub={h.trimmedWhy}>
                <Table columns={withMap(IAAO_TRIMMED, s.key)} rows={s.trimmed} keys={keys} widths={widths} />
              </Section>
            )}
          </div>
        ))
      ) : (
        <>
          <Section id="academic" title={h.academicTitle} sub={span(g.sets[0] as SalesSet)}>
            <p className="wiz-from md-sec-note">{h.academicWhy}</p>
            <Table columns={withMap(ACADEMIC, "holdout")} rows={g.academic} keys={keys} widths={widths} />
          </Section>
          <Section id="academic-trim" title={h.trimmed({ what: h.academicTitle })} sub={h.trimmedWhy}>
            <Table
              columns={withMap(ACADEMIC, "holdout")}
              rows={g.academic_trimmed}
              keys={keys}
              widths={widths}
            />
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

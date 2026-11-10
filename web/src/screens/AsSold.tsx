/** Data › Sales record fields (SPEC F3d, 2026-11-07): how sales and parcels each get their characteristics, then the sales
 * file's columns that describe the property beside the parcel fields they mirror, and what the sales use: as sold,
 * or today's. And the same choice, one field at a time, on that field's own screen (AsSoldLine). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap, type WizardField } from "../api/client";
import type { components } from "../api/schema";
import { stepChanged } from "../api/steps";
import { Disclose } from "../components/Disclose";
import { Choice } from "../components/Form";
import { ValuesButton } from "../components/ValuesButton";
import { Waiting } from "../components/Waiting";
import { pct } from "../lib/format";
import { t } from "../wording";
import { FieldHistogram } from "./FieldHistogram";

type Row = components["schemas"]["AsSoldRow"];
type AreaUnit = components["schemas"]["AsSoldChoice"]["area_unit"] & string;
const a = t.wizard.asSold;

function useAsSold(projectId: string) {
  return useQuery({
    queryKey: ["as-sold", projectId],
    meta: { quiet: true }, // its own Waiting
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/as-sold", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
  });
}

function useChoose(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      key,
      column,
      area_unit,
    }: {
      key: string;
      column: string | null;
      area_unit?: string;
    }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/wizard/as-sold/{key}", {
          params: { path: { project_id: projectId, key } },
          body: { column, ...(area_unit ? { area_unit: area_unit as AreaUnit } : {}) },
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["as-sold", projectId], data);
      void qc.invalidateQueries({ queryKey: ["wizard", projectId] });
      stepChanged(qc, projectId, "bring-in");
    },
  });
}

const TODAY = "__today";
const share = (n: number, of: number) => (of ? pct(n / of) : "—");
/** A value as read: a number with its thousands separated (a year as a year), else as written. */
const show = (v: string, key: string) =>
  v.trim() !== "" && Number.isFinite(Number(v)) && !key.includes("year")
    ? Number(v).toLocaleString(undefined, { maximumFractionDigits: Math.abs(Number(v)) < 100 ? 2 : 0 })
    : v;

/** The step: the explanation first, then the columns. */
export function AsSoldStep({ projectId, go }: { projectId: string; go: (step: string) => void }) {
  const [page, setPage] = useState<"explain" | "columns">("explain");
  return page === "explain" ? (
    <div className="as-explain">
      <h3>{a.explainTitle}</h3>
      <ol>
        <li>{a.point1}</li>
        <li>{a.point2}</li>
        <li>{a.point3}</li>
        <li>{a.point4}</li>
        <li>{a.point5}</li>
      </ol>
      <Button className="button button-primary" onPress={() => setPage("columns")}>
        {a.toColumns} ›
      </Button>
    </div>
  ) : (
    <div className="as-sold">
      <Button className="button button-small" onPress={() => setPage("explain")}>
        ‹ {a.back}
      </Button>
      <Columns projectId={projectId} />
      <SalesOnly projectId={projectId} go={go} />
    </div>
  );
}

function Columns({ projectId }: { projectId: string }) {
  const q = useAsSold(projectId);
  const qc = useQueryClient();
  const choose = useChoose(projectId);
  const v = q.data;
  if (!v) {
    if (q.error) return <p className="error">{q.error.message}</p>;
    return (
      <Waiting
        doing={a.loading({ file: "the sales file" })}
        onCancel={() => void qc.cancelQueries({ queryKey: ["as-sold", projectId] })}
      />
    );
  }
  if (!v.sales_file) return <p className="wiz-from">{a.noSales}</p>;
  const file = v.filename ?? v.sales_file;
  if (v.rows.length === 0) return <p className="wiz-note">{a.noneFound({ file })}</p>;
  return (
    <>
      <p className="wiz-from">{a.lede({ file })}</p>
      <table className="tbl as-table">
        <thead>
          <tr>
            <th>{a.cols.field}</th>
            <th>{a.cols.column({ file })}</th>
            <th className="cs-n">{a.cols.have}</th>
            <th>{a.cols.against}</th>
            <th>{a.cols.use}</th>
          </tr>
        </thead>
        <tbody>
          {v.rows.map((r) => (
            <tr key={r.key}>
              <td>
                {r.name}{" "}
                <span className="wiz-from">
                  (<code>{r.parcel_column}</code> · {r.parcel_file})
                </span>
              </td>
              <td>
                <code>{r.column}</code>
              </td>
              <td className="cs-n">{share(r.have, r.sales)}</td>
              <td>
                <Against r={r} />
              </td>
              <td>
                <Picker
                  r={r}
                  columns={v.columns}
                  label={`${a.cols.use}: ${r.name}`}
                  disabled={choose.isPending}
                  pick={(column) => choose.mutate({ key: r.key, column })}
                />
                {r.auto && <span className="pill pill-ok">{a.auto}</span>}
                {!r.auto && r.suggest && r.suggest !== (r.choice ?? "today") && (
                  <span className="pill pill-info">
                    {a.suggested}: {a.sale}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {choose.error && (
        <p className="error" role="alert">
          {choose.error.message}
        </p>
      )}
    </>
  );
}

function Against({ r }: { r: Row }) {
  if (r.written_differently) {
    const [sold = "", today = ""] = r.examples[0] ?? [];
    // A short pill; what's written differently, and what to do, on the line under it.
    return (
      <>
        <span className="pill pill-bad">{a.writtenDifferentlyPill}</span>
        <div className="wiz-from as-eg">{a.writtenDifferently({ sold, today })}</div>
      </>
    );
  }
  const same = r.compared ? r.same / r.compared : 1;
  return (
    <>
      <span className={same >= 0.99 ? "pill pill-ok" : "pill pill-warn"}>
        {same >= 0.5 ? a.same({ pct: pct(same) }) : a.differs({ pct: pct(1 - same) })}
      </span>
      {r.compared > r.same && (
        <div className="wiz-from as-eg">{a.differsFor({ n: r.compared - r.same })}</div>
      )}
    </>
  );
}

/** The sales' column for a field: none (today's), the one found (suggested, not used until picked), or any of the
 * sales file's columns. The same picker on the step's table, a field's At the sale box, and More details' table. */
function Picker({
  r,
  columns,
  label,
  pick,
  disabled,
}: {
  r: Row;
  columns: string[];
  label: string;
  pick: (column: string | null) => void;
  disabled: boolean;
}) {
  const used = r.choice === "sale";
  const options: [string, string][] = [
    [TODAY, a.noneToday],
    ...(r.column && !used ? [[r.column, a.suggestedOption({ column: r.column })] as [string, string]] : []),
    ...columns.filter((c) => !(c === r.column && !used)).map((c) => [c, c] as [string, string]),
  ];
  return (
    <Choice
      label={label}
      hideLabel
      value={used && r.column ? r.column : TODAY}
      options={options}
      onChange={(c: string) => pick(c === TODAY ? null : c)}
      isDisabled={disabled}
    />
  );
}

/** On a characteristic's own screen, beside the parcels' column (Today's): the sales' (At the sale), the same widget
 * reading the sales file. Its column (none: today's; the one found suggested), an area's unit, its values and spread,
 * and against today's: the share the same, the sales that differ, and what that suggests. */
export function AtSale({ projectId, field }: { projectId: string; field: WizardField }) {
  const q = useAsSold(projectId);
  const choose = useChoose(projectId);
  const [open, setOpen] = useState(false);
  const v = q.data;
  const r = v?.rows.find((x) => x.key === field.key);
  const file = v?.filename ?? v?.sales_file ?? "";
  const mark = r?.auto ? (
    <span className="pill pill-ok">{a.auto}</span>
  ) : r?.column && r.how ? (
    <span className="pill pill-info">{a.how[r.how]}</span>
  ) : null;
  const head = <CapHead kind="sr" mark={mark} />;
  if (!v)
    return (
      <div className="frame as-cap as-side">
        {head}
        <Waiting doing={a.loading({ file: "the sales file" })} />
      </div>
    );
  if (!r || !v.sales_file) return null;
  const used = r.choice === "sale";
  const area = r.today_unit != null;
  const units = t.wizard.areaUnits as Record<string, string>;
  const showValue = (x: string, unit: string | null) =>
    area && unit ? `${show(x, r.key)} ${units[unit] ?? unit}` : show(x, r.key);
  const pick = (c: string, unit?: string) =>
    choose.mutate({ key: r.key, column: c === TODAY ? null : c, ...(unit ? { area_unit: unit } : {}) });
  const same = r.compared ? r.same / r.compared : 1;
  const differ = r.compared - r.same;
  return (
    <div className="frame as-cap as-side">
      {head}
      {/* One row, as the parcel universe's: the column, its unit, its values; its spread right under it, level with
          the parcel universe's; then, below the dotted line, how it compares. */}
      <div className="as-row">
        <span className="wiz-label">{a.column}</span>
        <div className="wiz-pair as-sr-pair">
          <Picker
            r={r}
            columns={v.columns}
            label={`${a.srTitle}: ${field.name}`}
            disabled={choose.isPending}
            pick={(c) => pick(c ?? TODAY)}
          />
          {area && r.column && (
            <div className="wiz-unit">
              <Choice
                label={`${a.unit}: ${r.column}`}
                hideLabel
                value={r.unit ?? r.today_unit ?? "sqft"}
                options={Object.entries(units)}
                onChange={(u: string) => pick(r.column ?? TODAY, u)}
                isDisabled={choose.isPending}
              />
            </div>
          )}
        </div>
        <span>
          {r.column && (
            <ValuesButton projectId={projectId} file={v.sales_file} column={r.column} distinct={r.distinct} />
          )}
        </span>
      </div>
      {used && r.column && (area || r.key.includes("year")) && (
        <FieldHistogram
          projectId={projectId}
          field={field}
          sale={{ column: r.column, unit: r.unit ?? null }}
          pair
        />
      )}
      {!r.column ? (
        <div className="as-against">
          <p className="wiz-from">{a.notFound({ file })}</p>
        </div>
      ) : r.written_differently ? (
        <div className="as-against">
          <p>
            <span className="pill pill-bad">{a.writtenDifferentlyPill}</span>{" "}
            {a.writtenDifferentlyWhy({ sold: r.examples[0]?.[0] ?? "", today: r.examples[0]?.[1] ?? "" })}
          </p>
        </div>
      ) : (
        <div className="as-against">
          <p className="wiz-from">
            {a.onSales({ pct: share(r.have, r.sales) })}
            {area && r.unit !== r.today_unit && r.today_unit
              ? ` ${a.unitNote({ today: units[r.today_unit] ?? r.today_unit })}`
              : ""}
          </p>
          <p>
            <b>{a.against}</b>{" "}
            <span className={same >= 0.99 ? "pill pill-ok" : "pill pill-warn"}>
              {a.sameFor({ pct: pct(same) })}
            </span>{" "}
            {differ > 0 && (
              <>
                {a.differsFor({ n: differ })}{" "}
                <Disclose open={open} onPress={() => setOpen(!open)}>
                  {open ? a.hideThem : a.seeThem}
                </Disclose>
              </>
            )}
          </p>
          {open && (
            <table className="tbl as-diffs">
              <thead>
                <tr>
                  <th>{a.diffCols.parcel}</th>
                  <th>{a.diffCols.date}</th>
                  <th className="cs-n">{a.diffCols.sold}</th>
                  <th className="cs-n">{a.diffCols.today}</th>
                </tr>
              </thead>
              <tbody>
                {r.diffs.map((d) => (
                  <tr key={`${d.parcel}-${d.date}-${d.sold}`}>
                    <td>
                      <code>{d.parcel}</code>
                    </td>
                    <td>{d.date || "—"}</td>
                    <td className="cs-n">{showValue(d.sold, r.unit ?? null)}</td>
                    <td className="cs-n">{showValue(d.today, r.today_unit ?? null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {choose.error && (
        <p className="error" role="alert">
          {choose.error.message}
        </p>
      )}
    </div>
  );
}

/** A capsule's header: which dataset it's from, by name and symbol (AGENTS.md), what that dataset is for, and a mark
 * (found, picked for you). */
export function CapHead({ kind, mark }: { kind: "pu" | "sr"; mark?: ReactNode }) {
  return (
    <div className={`as-head as-head-${kind}`}>
      <b>{kind === "pu" ? a.puTitle : a.srTitle}</b>
      {mark}
      <span className="wiz-from as-head-note">{kind === "pu" ? a.puNote : a.srNote}</span>
    </div>
  );
}

/** More details' fields on one step (Land use & building type): each one's At the sale in a table under the step. */
export function AtSaleTable({ projectId, fields }: { projectId: string; fields: WizardField[] }) {
  const q = useAsSold(projectId);
  const choose = useChoose(projectId);
  const v = q.data;
  if (!v) return <Waiting doing={a.loading({ file: "the sales file" })} />;
  const rows = fields.flatMap((f) => {
    const r = v.rows.find((x) => x.key === f.key);
    return r ? [[f, r] as const] : [];
  });
  if (!v.sales_file || rows.length === 0) return null;
  const file = v.filename ?? v.sales_file;
  return (
    <div className="as-table-wrap">
      <h3 className="wiz-group">{a.tableTitle}</h3>
      <p className="wiz-from">{a.tableLede({ file })}</p>
      <table className="tbl as-table">
        <thead>
          <tr>
            <th>{a.cols.field}</th>
            <th>{a.todays}</th>
            <th>{a.atSale}</th>
            <th>{a.against}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([f, r]) => {
            const same = r.compared ? r.same / r.compared : 1;
            return (
              <tr key={r.key}>
                <td>{f.name}</td>
                <td>
                  <code>{r.parcel_column}</code> <span className="wiz-from">· {r.parcel_file}</span>
                </td>
                <td>
                  <Picker
                    r={r}
                    columns={v.columns}
                    label={`${a.atSale}: ${f.name}`}
                    disabled={choose.isPending}
                    pick={(column) => choose.mutate({ key: r.key, column })}
                  />
                </td>
                <td>
                  {!r.column ? (
                    <span className="wiz-from">{a.notFound({ file })}</span>
                  ) : r.written_differently ? (
                    <span className="pill pill-bad">{a.writtenDifferentlyPill}</span>
                  ) : (
                    <span className={same >= 0.99 ? "pill pill-ok" : "pill pill-warn"}>
                      {a.sameFor({ pct: pct(same) })}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The sales file's columns no parcel file has: not for models; for valid-sale rules, and Outliers (2026-11-08). */
function SalesOnly({ projectId, go }: { projectId: string; go: (step: string) => void }) {
  const q = useQuery({
    queryKey: ["sales-only", projectId],
    meta: { quiet: true }, // its own Waiting
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/projects/{project_id}/wizard/sales-only", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
  });
  const v = q.data;
  if (!v) return q.isFetching ? <Waiting doing={a.loading({ file: "the sales file" })} /> : null;
  if (!v.sales_file) return null;
  const file = v.filename ?? v.sales_file;
  return (
    <section className="as-only">
      <h3 className="wiz-group">{a.onlyTitle}</h3>
      <p className="wiz-from">{a.onlyLede({ file })}</p>
      {v.columns.length === 0 ? (
        <p className="wiz-note">{a.onlyNone({ file })}</p>
      ) : (
        <table className="tbl as-table">
          <thead>
            <tr>
              <th>{a.onlyCols.column}</th>
              <th className="cs-n">{a.onlyCols.have}</th>
              <th>{a.onlyCols.values}</th>
            </tr>
          </thead>
          <tbody>
            {v.columns.map((c) => (
              <tr key={c.column}>
                <td>
                  <code>{c.column}</code> {c.in_rule && <span className="pill pill-info">{a.inRule}</span>}
                </td>
                <td className="cs-n">{share(c.have, c.rows)}</td>
                <td>
                  {c.top.map(([val = "", n = ""]) => `${val} (${Number(n).toLocaleString()})`).join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Button className="button" onPress={() => go("valid_sale")}>
        {a.toValid} ›
      </Button>
    </section>
  );
}

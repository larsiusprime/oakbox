/** Data › Sales as sold (SPEC F3d, 2026-11-07): how sales and parcels each get their characteristics, then the sales
 * file's columns that describe the property beside the parcel fields they mirror, and what the sales use: as sold,
 * or today's. And the same choice, one field at a time, on that field's own screen (AsSoldLine). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { stepChanged } from "../api/steps";
import { Seg } from "../components/Seg";
import { Waiting } from "../components/Waiting";
import { num, pct } from "../lib/format";
import { t } from "../wording";

type Row = components["schemas"]["AsSoldRow"];
const a = t.wizard.asSold;

function useAsSold(projectId: string) {
  return useQuery({
    queryKey: ["as-sold", projectId],
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
    mutationFn: async ({ key, column }: { key: string; column: string | null }) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/wizard/as-sold/{key}", {
          params: { path: { project_id: projectId, key } },
          body: { column },
        }),
      ),
    onSuccess: (data) => {
      qc.setQueryData(["as-sold", projectId], data);
      void qc.invalidateQueries({ queryKey: ["wizard", projectId] });
      stepChanged(qc, projectId, "bring-in");
    },
  });
}

const share = (n: number, of: number) => (of ? pct(n / of) : "—");
/** A value as read: a number with its thousands separated (a year as a year), else as written. */
const show = (v: string, key: string) =>
  v.trim() !== "" && Number.isFinite(Number(v)) && !key.includes("year") ? num(Number(v)) : v;

/** The step: the explanation first, then the columns. */
export function AsSoldStep({ projectId }: { projectId: string }) {
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
      <Button className="button primary" onPress={() => setPage("columns")}>
        {a.toColumns} ›
      </Button>
    </div>
  ) : (
    <div className="as-sold">
      <Button className="link-button" onPress={() => setPage("explain")}>
        ‹ {a.back}
      </Button>
      <Columns projectId={projectId} />
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
  const allSame = v.rows.every((r) => r.suggest === "today");
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
                <Choice
                  r={r}
                  disabled={choose.isPending}
                  pick={(column) => choose.mutate({ key: r.key, column })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {allSame && <p className="wiz-from">{a.allSame({ file })}</p>}
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
    return <span className="pill pill-bad">{a.writtenDifferently({ sold, today })}</span>;
  }
  const same = r.compared ? r.same / r.compared : 1;
  return (
    <>
      <span className={same >= 0.99 ? "pill pill-ok" : "pill pill-warn"}>
        {same >= 0.5 ? a.same({ pct: pct(same) }) : a.differs({ pct: pct(1 - same) })}
      </span>
      {r.examples.length > 0 && (
        <div className="wiz-from as-eg">
          {a.examples({
            list: r.examples.map(([s = "", d = ""]) => `${show(s, r.key)} → ${show(d, r.key)}`).join(", "),
          })}
        </div>
      )}
    </>
  );
}

function Choice({ r, pick, disabled }: { r: Row; pick: (column: string | null) => void; disabled: boolean }) {
  const value = r.choice ?? "today";
  return (
    <span className="as-choice">
      <Seg
        label={`${t.wizard.asSold.cols.use}: ${r.name}`}
        value={value}
        options={[
          ["sale", a.sale],
          ["today", a.today],
        ]}
        disabled={disabled || r.written_differently ? ["sale"] : []}
        onChange={(c) => pick(c === "sale" ? r.column : null)}
      />
      {r.suggest && r.suggest !== value && (
        <span className="pill pill-info">
          {a.suggested}: {r.suggest === "sale" ? a.sale : a.today}
        </span>
      )}
    </span>
  );
}

/** On a characteristic's own screen: what its sales use, the same choice as Sales as sold. */
export function AsSoldLine({ projectId, field }: { projectId: string; field: string }) {
  const q = useAsSold(projectId);
  const choose = useChoose(projectId);
  const r = q.data?.rows.find((x) => x.key === field);
  const file = q.data?.filename ?? q.data?.sales_file;
  if (!q.data) return q.isFetching ? <Waiting doing={a.loading({ file: "the sales file" })} /> : null;
  if (!r || !file) return null;
  const value = r.choice ?? "today";
  return (
    <div className="mo-row as-line">
      <span className="mo-label">{a.forSales}</span>
      <span>
        <Seg
          label={a.forSales}
          value={value}
          options={[
            ["sale", a.asSoldOption({ column: r.column ?? "", file })],
            ["today", a.todayOption],
          ]}
          disabled={choose.isPending || r.written_differently ? ["sale"] : []}
          onChange={(c) => choose.mutate({ key: r.key, column: c === "sale" ? r.column : null })}
        />
        <span className="wiz-from as-note">
          {r.written_differently
            ? a.writtenDifferently({ sold: r.examples[0]?.[0] ?? "", today: r.examples[0]?.[1] ?? "" })
            : a.lineNote({ file, have: share(r.have, r.sales), same: share(r.same, r.compared) })}
        </span>
      </span>
    </div>
  );
}

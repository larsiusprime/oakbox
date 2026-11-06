import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderOpen } from "lucide-react";
import { Button } from "react-aria-components";
import { type AssembleView, api, type ModelGroup, unwrap } from "../api/client";
import { stepChanged, stepKey } from "../api/steps";
import { Tick } from "../components/Form";
import { NO_COLOUR } from "../lib/colours";
import { num, size, when } from "../lib/format";
import { t } from "../wording";

const r = t.groups.run;
type Format = AssembleView["exports"][number];
const FORMATS: Format[] = ["gpkg", "shp", "csv"];

/** The formats notebook 1's output is also written in, beside Parquet. */
export function Formats({ projectId, view }: { projectId: string; view: AssembleView }) {
  const queryClient = useQueryClient();
  const formats = useMutation({
    mutationFn: async (exports: Format[]) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/assemble/exports", {
          params: { path: { project_id: projectId } },
          body: { exports },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(stepKey("assemble", projectId), data);
      stepChanged(queryClient, projectId, "assemble", false);
    },
  });
  return (
    <fieldset className="ab-formats-inline">
      <legend className="wiz-group">{r.formats}</legend>
      <p className="wiz-from">{r.formatsHelp}</p>
      {FORMATS.map((f) => (
        <Tick
          key={f}
          isSelected={view.exports.includes(f)}
          onChange={(on) => formats.mutate(on ? [...view.exports, f] : view.exports.filter((x) => x !== f))}
        >
          {r.formatNames[f]}
        </Tick>
      ))}
    </fieldset>
  );
}

/** What OpenAVMKit tagged: parcels and sales per model group, against the builder's preview; the files written. */
export function AssembleResults({
  projectId,
  view,
  groups,
}: {
  projectId: string;
  view: AssembleView;
  groups: ModelGroup[];
}) {
  const rc = view.receipt;
  const show = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/assemble/show", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  if (!rc) return null;
  const colour = (id: string) => groups.find((x) => x.id === id)?.color ?? NO_COLOUR;
  return (
    <div className="ab-results">
      <p className="rc-sub">
        {r.written({
          when: when(rc.ran_at),
          parcels: rc.parcels,
          groups: rc.groups.filter((x) => x.id !== "UNKNOWN" && x.parcels > 0).length,
        })}{" "}
        <span className="wiz-from">
          · {rc.seconds}s · OpenAVMKit {rc.engine}
        </span>
      </p>
      {view.stale && <p className="wiz-warn">{r.stale}</p>}
      <table className="rc-tbl ab-tbl">
        <thead>
          <tr>
            <th className="rc-th">{r.group}</th>
            <th className="rc-th ab-n">{r.parcels}</th>
            <th className="rc-th ab-n">{r.vacant}</th>
            <th className="rc-th ab-n">{r.sales}</th>
            <th className="rc-th ab-n">{r.vacantSales}</th>
            {!rc.matches_preview && <th className="rc-th ab-n">{r.preview}</th>}
          </tr>
        </thead>
        <tbody>
          {rc.groups.map((x) => (
            <tr key={x.id} className={x.id === "UNKNOWN" ? "ab-unknown" : ""}>
              <td className="rc-td">
                <span className="mg-sw ab-sw" style={{ background: colour(x.id) }} />
                {x.id === "UNKNOWN" ? r.unassigned : x.name}
              </td>
              <td className="rc-td ab-n">{num(x.parcels)}</td>
              <td className="rc-td ab-n">{num(x.vacant)}</td>
              <td className="rc-td ab-n">{num(x.sales)}</td>
              <td className="rc-td ab-n">{num(x.vacant_sales)}</td>
              {!rc.matches_preview && (
                <td className={`rc-td ab-n ${x.preview !== x.parcels ? "wiz-warn" : ""}`}>
                  {num(x.preview)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p className={rc.matches_preview ? "wiz-ok" : "wiz-warn"}>
        {rc.matches_preview ? r.matches : r.differs}
      </p>
      <h3 className="ab-h">{r.writtenTitle}</h3>
      <ul className="ab-files">
        {rc.written.map((w) => (
          <li key={w.path}>
            <span className="mono">{w.path}</span> <span className="wiz-from">· {size(w.bytes)}</span>
            {w.what && <span className="wiz-from"> · {w.what}</span>}
          </li>
        ))}
      </ul>
      {rc.notes.length > 0 && (
        <details className="rc-writes">
          <summary>{r.notes({ n: rc.notes.length })}</summary>
          <ul>
            {rc.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      <div>
        <Button className="button" onPress={() => show.mutate()}>
          <FolderOpen aria-hidden="true" size="1em" />
          {r.show}
        </Button>
      </div>
    </div>
  );
}

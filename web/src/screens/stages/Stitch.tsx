import { useQuery } from "@tanstack/react-query";
import { Lightbulb } from "lucide-react";
import { Button, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import {
  type Collapse,
  type FileReport,
  type IdFix,
  type SourceFile,
  type Stitch,
  type StitchReport,
  unwrap,
} from "../../api/client";
import { CheckList, Choice, Tick } from "../../components/Form";
import {
  CheckRunner,
  LooksRight,
  Part,
  StageFrame,
  StageStatusMark,
  StaleNote,
  UnderTheHood,
} from "../../components/Stage";
import { t } from "../../strings";
import { api, type StageProps, useSave } from "./common";

type FixOp = IdFix["op"];
const FIX_OPS: readonly FixOp[] = ["strip_leading_zeros", "remove_non_alnum", "upper"];

export function StitchStage({ detail }: StageProps) {
  const { project, running_job } = detail;
  const status = project.stages.stitch;
  const setup = project.setup;
  const stitch = setup.stitch;
  const save = useSave(project.id, (body: Stitch) =>
    api.PUT("/api/projects/{project_id}/stitch", { params: { path: { project_id: project.id } }, body }),
  );
  const check = useQuery({
    queryKey: ["check", project.id, "stitch"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/stages/{stage}/check", {
          params: { path: { project_id: project.id, stage: "stitch" } },
        }),
      ),
  });
  const maps = setup.files.filter((f) => f.uses.includes("parcel_map"));
  const attached = setup.files.filter((f) => f.uses.includes("parcels") || f.uses.includes("sales"));
  const checking = running_job?.step === "check_stitch" ? running_job : null;
  const setFixes = (fileId: string, ops: FixOp[]) =>
    save.mutate({
      ...stitch,
      id_fixes: { ...stitch.id_fixes, [fileId]: ops.map((op) => ({ op, width: null })) },
    });
  const applyEverywhere = (fixes: IdFix[]) => {
    const ids = [...maps, ...attached].map((f) => f.id);
    const next = { ...stitch.id_fixes };
    for (const id of ids) {
      const have = next[id] ?? [];
      next[id] = [...have, ...fixes.filter((fx) => !have.some((h) => h.op === fx.op))];
    }
    save.mutate({ ...stitch, id_fixes: next });
  };

  return (
    <StageFrame
      title={t.stages.stitch.title}
      what={t.stages.stitch.what}
      status={<StageStatusMark status={status} />}
      note={project.notes.stitch}
    >
      <StaleNote status={status} />
      <Part title={t.frame.decide}>
        {maps.length === 0 ? (
          <p className="stale-note">{t.stitch.noMap}</p>
        ) : (
          <div className="form-grid">
            <Choice
              label={t.stitch.spine}
              value={stitch.spine}
              options={maps.map((f) => [f.id, f.name] as const)}
              onChange={(spine) => save.mutate({ ...stitch, spine })}
            />
            <Tick isSelected={stitch.dissolve} onChange={(dissolve) => save.mutate({ ...stitch, dissolve })}>
              {t.stitch.mergePolygons}
            </Tick>
          </div>
        )}
        <div className="plan">
          {[...maps, ...attached].map((f) => (
            <PlanFile
              key={f.id}
              file={f}
              fixes={(stitch.id_fixes[f.id] ?? []).map((x) => x.op)}
              collapse={stitch.collapse[f.id] ?? null}
              onFixes={(ops) => setFixes(f.id, ops)}
              onCollapse={(c) => save.mutate({ ...stitch, collapse: { ...stitch.collapse, [f.id]: c } })}
            />
          ))}
        </div>
        {save.error && (
          <p className="error" role="alert">
            {save.error.message}
          </p>
        )}
      </Part>
      <Part title={t.frame.check}>
        <p className="row-meta">{t.stitch.checkWhat}</p>
        <CheckRunner
          projectId={project.id}
          stage="stitch"
          runningJob={checking}
          ran={check.data?.ran ?? false}
          fresh={check.data?.fresh ?? false}
          disabled={maps.length === 0 || (running_job !== null && checking === null)}
        />
      </Part>
      {check.data?.stitch && (
        <Part title={t.frame.receipt}>
          <Report report={check.data.stitch} onApply={applyEverywhere} stale={!check.data.fresh} />
        </Part>
      )}
      <LooksRight projectId={project.id} stage="stitch" status={status} />
      <UnderTheHood projectId={project.id} stage="stitch" />
    </StageFrame>
  );
}

function PlanFile(props: {
  file: SourceFile;
  fixes: FixOp[];
  collapse: Collapse | null;
  onFixes: (ops: FixOp[]) => void;
  onCollapse: (c: Collapse) => void;
}) {
  const f = props.file;
  const p = f.profile;
  const several = p && p.distinct_ids !== null && p.rows - (p.blank_ids ?? 0) > p.distinct_ids;
  const numeric =
    p?.columns.filter((c) => c.type === "number" && !f.id_columns.includes(c.name)).map((c) => c.name) ?? [];
  const sort = props.collapse?.sort_by[0] ?? null;
  const aggs = Object.entries(props.collapse?.fields ?? {});
  return (
    <div className="plan-file">
      <div className="plan-file-head">
        <span className="file-name">{f.name}</span>
        <span className="row-meta">
          {f.uses.map((u) => t.files.uses[u]).join(" · ")} · {t.files.idColumn}: {f.id_columns[0]}
        </span>
      </div>
      <CheckList
        label={t.stitch.idFixes}
        value={props.fixes}
        options={FIX_OPS.map((op) => [op, t.stitch.fixes[op]] as const)}
        onChange={props.onFixes}
      />
      {f.keep_rows && (
        <p className="row-meta">{t.files.keepRows(f.keep_rows.column, f.keep_rows.values.join(", "))}</p>
      )}
      {several && f.uses.includes("parcels") && (
        <div className="several">
          <span className="field-label">{t.stitch.severalRows}</span>
          <div className="several-row">
            <Choice
              label={t.stitch.severalRows}
              hideLabel
              value={sort ? `${sort.column}|${sort.descending ? "d" : "a"}` : "__file"}
              options={[
                ["__file", t.stitch.keepFileOrder] as const,
                ...numeric.flatMap((c) => [
                  [`${c}|d`, t.stitch.keepFirst(t.stitch.highest(c))] as const,
                  [`${c}|a`, t.stitch.keepFirst(t.stitch.lowest(c))] as const,
                ]),
              ]}
              onChange={(v) => {
                const fields = props.collapse?.fields ?? {};
                if (v === "__file") return props.onCollapse({ sort_by: [], fields });
                const [column = "", dir] = v.split("|");
                props.onCollapse({
                  sort_by: [{ column, descending: dir === "d" }, ...(props.collapse?.sort_by.slice(1) ?? [])],
                  fields,
                });
              }}
            />
          </div>
          {aggs.length > 0 && (
            <p className="row-meta">
              {t.stitch.aggregations(aggs.length)}
              {aggs.map(([c, op]) => `${c} (${t.stitch.agg[op]})`).join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Report({
  report,
  onApply,
  stale,
}: {
  report: StitchReport;
  onApply: (f: IdFix[]) => void;
  stale: boolean;
}) {
  const s = t.stitch;
  const m = report.spine;
  return (
    <div className={stale ? "report report-stale" : "report"}>
      <p className="report-total">{s.total(report.parcels, report.sales, report.sales_unmatched)}</p>
      {report.map_parcels_without_details > 0 && <p>{s.mapOnly(report.map_parcels_without_details)}</p>}
      {report.warnings.map((w) => (
        <p key={w} className="stale-note">
          {w}
        </p>
      ))}
      {m && (
        <div className="report-file">
          <h4>
            {s.map}: {m.name}
          </h4>
          <p>{s.mapLine(m.rows_in, m.rows_out)}</p>
          <ul className="report-lines">
            {m.filtered_out > 0 && <li>{s.filtered(m.filtered_out, m.filter_description ?? "")}</li>}
            {m.blank_ids > 0 && <li>{s.blankDropped(m.blank_ids)}</li>}
            {m.polygons_merged > 0 && <li>{s.merged(m.polygons_merged)}</li>}
          </ul>
        </div>
      )}
      {report.files.map((f) => (
        <FileResult key={`${f.file}-${f.use}`} rep={f} onApply={onApply} />
      ))}
      {report.columns.length > 0 && (
        <Disclosure className="disclosure">
          <Heading>
            <Button slot="trigger" className="disclosure-trigger">
              {s.columnsTitle(report.columns.length)}
            </Button>
          </Heading>
          <DisclosurePanel>
            <p className="columns-list">
              {report.columns.map((c) => (
                <span key={c.name} className="column-chip" title={`${c.source}: ${c.source_column}`}>
                  {c.name}
                </span>
              ))}
            </p>
          </DisclosurePanel>
        </Disclosure>
      )}
    </div>
  );
}

function FileResult({ rep, onApply }: { rep: FileReport; onApply: (f: IdFix[]) => void }) {
  const s = t.stitch;
  const total = rep.matched + rep.only_here;
  const share = total ? rep.matched / total : 0;
  return (
    <div className="report-file">
      <h4>
        {rep.name} <span className="row-meta">({t.files.uses[rep.use]})</span>
      </h4>
      <div className="match">
        <div className="meter" aria-hidden="true">
          <div className="meter-fill" style={{ width: `${share * 100}%` }} />
        </div>
        <p>{s.matchedOf(rep.matched, total)}</p>
      </div>
      <ul className="report-lines">
        {rep.filtered_out > 0 && <li>{s.filtered(rep.filtered_out, rep.filter_description ?? "")}</li>}
        {rep.blank_ids > 0 && <li>{s.blankDropped(rep.blank_ids)}</li>}
        {rep.only_here > 0 && (
          <li>
            {s.onlyHere(rep.only_here)}. {s.examples}:{" "}
            <span className="mono">{rep.only_here_examples.join(", ")}</span>
          </li>
        )}
        {rep.use === "parcels" && rep.only_on_map > 0 && (
          <li>
            {s.onlyOnMap(rep.only_on_map)}. {s.examples}:{" "}
            <span className="mono">{rep.only_on_map_examples.join(", ")}</span>
          </li>
        )}
        {rep.use === "parcels" && rep.collapsed_away > 0 && (
          <li>{s.collapsed(rep.rows_after, rep.rows_after - rep.collapsed_away)}</li>
        )}
      </ul>
      {rep.suggestion && (
        <div className="suggestion">
          <Lightbulb aria-hidden="true" size="1.1em" />
          <span>{s.suggestion(rep.suggestion.description, rep.suggestion.gain)}</span>
          <Button className="button" onPress={() => rep.suggestion && onApply(rep.suggestion.fixes)}>
            {s.applySuggestion}
          </Button>
        </div>
      )}
      {rep.only_here_breakdown && (
        <div className="breakdown">
          <p className="field-label">{s.breakdownTitle(rep.only_here_breakdown.column)}</p>
          <ul className="report-lines">
            {rep.only_here_breakdown.rows.map((r) => (
              <li key={r.value}>
                {s.breakdownRow(r.value, r.count, r.share_of_unmatched, r.share_of_matched)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

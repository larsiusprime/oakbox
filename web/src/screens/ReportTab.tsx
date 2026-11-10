/** Step 7, Report (SPEC §4): the model values out of OAK box. Export writes every parcel's value as a file; Report
 * shows the printable report, judged on the sets of sales picked, to open in the browser and print or save as PDF. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "react-aria-components";
import { api, unwrap } from "../api/client";
import type { components } from "../api/schema";
import { CheckList, Field } from "../components/Form";
import { Seg } from "../components/Seg";
import { type Step, StepBody, StepFoot, StepFrame } from "../components/Steps";
import { LoadingBar } from "../components/Waiting";
import { lastStep } from "../lib/place";
import { t } from "../wording";

type View = components["schemas"]["ReportView"];
type Format = components["schemas"]["ExportBody"]["format"];
type SetKey = View["sets"][number];
type RStep = "export" | "report";
const STEPS: RStep[] = ["export", "report"];
const r = t.report;

function size(bytes: number): string {
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} KB`;
}

export function ReportTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const key = ["report", projectId];
  const q = useQuery({
    queryKey: key,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/report", { params: { path: { project_id: projectId } } }),
      ),
  });
  const [at, setAt] = useState<RStep>(
    () => (lastStep(projectId, "report")?.key as RStep | undefined) ?? "export",
  );
  const v = q.data;
  if (!v) return <LoadingBar error={q.error} />;
  const steps: Step[] = STEPS.map((k) => ({
    key: k,
    title: r.steps[k],
    status: "blank",
    disabled: !v.ready,
  }));
  const i = STEPS.indexOf(at);
  return (
    <StepFrame steps={steps} current={at} go={(k) => setAt(k as RStep)} landing="report">
      {!v.ready ? (
        <StepBody title={r.steps[at]}>
          <p className="wiz-from">{r.notReady}</p>
        </StepBody>
      ) : at === "export" ? (
        <ExportStep projectId={projectId} v={v} />
      ) : (
        <ReportStep
          projectId={projectId}
          v={v}
          saved={(data) => queryClient.setQueryData(key, data)}
          version={q.dataUpdatedAt}
        />
      )}
      <StepFoot
        back={i > 0 ? () => setAt(STEPS[i - 1] ?? at) : null}
        next={i < STEPS.length - 1 ? { label: t.step.next, onPress: () => setAt(STEPS[i + 1] ?? at) } : null}
      />
    </StepFrame>
  );
}

function useShow(projectId: string) {
  return useMutation({
    mutationFn: async (path: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/report/show", {
          params: { path: { project_id: projectId } },
          body: { path },
        }),
      ),
  });
}

function ExportStep({ projectId, v }: { projectId: string; v: View }) {
  const [fmt, setFmt] = useState<Format>("csv");
  const write = useMutation({
    mutationFn: async (format: Format) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/report/export", {
          params: { path: { project_id: projectId } },
          body: { format },
        }),
      ),
  });
  const show = useShow(projectId);
  const done = write.data;
  return (
    <StepBody title={r.steps.export} lede={r.exportLede}>
      {!v.accepted && <p className="wiz-warn">{r.notAccepted}</p>}
      <div className="rp-row">
        <span className="mo-label">{r.format}</span>
        <Seg
          label={r.format}
          value={fmt}
          options={v.formats.map(
            ({ id }) =>
              [id, id === "xlsx" ? "Excel" : id === "shp" ? "Shapefile" : id.toUpperCase()] as const,
          )}
          onChange={(k) => {
            setFmt(k);
            write.reset();
          }}
        />
      </div>
      <p className="wiz-from">{v.formats.find((x) => x.id === fmt)?.label}</p>
      <p className="wiz-from">{r.columns}</p>
      <div className="rp-row">
        <Button
          className="button button-primary"
          onPress={() => write.mutate(fmt)}
          isDisabled={write.isPending}
        >
          {write.isPending ? r.writing : r.write}
        </Button>
        {done && (
          <Button className="button" onPress={() => show.mutate(done.path)}>
            {r.show}
          </Button>
        )}
      </div>
      {done && (
        <>
          <p className="wiz-ok">{r.wrote({ rows: done.rows, size: size(done.bytes), path: done.path })}</p>
          {done.notes.map((n) => (
            <p key={n} className="wiz-from">
              {n}
            </p>
          ))}
        </>
      )}
      {(write.error || show.error) && (
        <p className="error" role="alert">
          {(write.error ?? show.error)?.message}
        </p>
      )}
    </StepBody>
  );
}

function ReportStep({
  projectId,
  v,
  saved,
  version,
}: {
  projectId: string;
  v: View;
  saved: (v: View) => void;
  version: number;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: async (body: { sets?: SetKey[]; title?: string }) =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}/report", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: saved,
  });
  const open = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/report/open", {
          params: { path: { project_id: projectId } },
        }),
      ),
  });
  const show = useShow(projectId);
  const keepTitle = () => {
    if (draft !== null && draft !== v.title) change.mutate({ title: draft });
    setDraft(null);
  };
  const empty = v.sets.filter((k) => !v.available.includes(k));
  return (
    <StepBody title={r.steps.report} lede={r.reportLede}>
      {!v.accepted && <p className="wiz-warn">{r.notAccepted}</p>}
      <div className="rp-opts">
        <Field label={r.title} value={draft ?? v.title} onChange={setDraft} onBlur={keepTitle} width="long" />
        <CheckList
          label={r.sets}
          value={v.sets}
          options={(["oof", "held", "valued"] as const).map((k) => [k, r.setNames[k] ?? k] as const)}
          onChange={(sets) => sets.length && change.mutate({ sets })}
        />
        {empty.length > 0 && (
          <p className="wiz-from">
            {r.noSales({ names: empty.map((k) => (r.setNames[k] ?? k).split(":")[0]).join(", ") })}
          </p>
        )}
      </div>
      <div className="rp-row">
        <Button className="button button-primary" onPress={() => open.mutate()} isDisabled={open.isPending}>
          {r.open}
        </Button>
        {open.data && (
          <Button className="button" onPress={() => show.mutate(open.data)}>
            {r.show}
          </Button>
        )}
      </div>
      {open.data && <p className="wiz-ok">{r.opened({ path: open.data })}</p>}
      {(change.error || open.error || show.error) && (
        <p className="error" role="alert">
          {(change.error ?? open.error ?? show.error)?.message}
        </p>
      )}
      <iframe
        className="rp-preview"
        title={r.preview}
        src={`/api/projects/${encodeURIComponent(projectId)}/report/html?v=${version}`}
      />
    </StepBody>
  );
}

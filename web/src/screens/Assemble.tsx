import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { Button, Dialog, DialogTrigger, Heading, Modal, ModalOverlay, Popover } from "react-aria-components";
import { navigate } from "../App";
import { type AssembleView, api, type ModelGroup, unwrap } from "../api/client";
import { Tick } from "../components/Form";
import { t } from "../strings";

const r = t.groups.run;
type Format = AssembleView["exports"][number];
const FORMATS: Format[] = ["gpkg", "shp", "csv"];

function when(iso: string): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return new Date().toDateString() === d.toDateString()
    ? `today at ${time}`
    : `${d.toLocaleDateString()} at ${time}`;
}

function size(bytes: number): string {
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} KB`;
}

export function useAssemble(projectId: string) {
  return useQuery({
    queryKey: ["assemble", projectId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/assemble", { params: { path: { project_id: projectId } } }),
      ),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 600 : false),
  });
}

/** The end of notebook 1, above the builder: tag the parcels and write the output; its receipt; Looks right. */
export function RunBar({
  projectId,
  groups,
  dirty,
}: {
  projectId: string;
  groups: ModelGroup[];
  dirty: boolean;
}) {
  const queryClient = useQueryClient();
  const state = useAssemble(projectId);
  const [open, setOpen] = useState(false);
  const act = useMutation({
    mutationFn: async (what: "run" | "stop" | "accept") => {
      const path = `/api/projects/{project_id}/assemble/${what}` as const;
      return unwrap(await api.POST(path, { params: { path: { project_id: projectId } } }));
    },
    onSuccess: (data, what) => {
      queryClient.setQueryData(["assemble", projectId], data);
      if (what === "accept") {
        setOpen(false);
        navigate({ name: "project", id: projectId, tab: "sales" });
      }
    },
  });
  const formats = useMutation({
    mutationFn: async (exports: Format[]) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/assemble/exports", {
          params: { path: { project_id: projectId } },
          body: { exports },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(["assemble", projectId], data),
  });
  const v = state.data;
  if (!v) return null;
  const running = v.status === "running";
  const rc = v.receipt;
  const named = rc ? rc.groups.filter((x) => x.id !== "UNKNOWN" && x.parcels > 0).length : 0;
  const status = v.blocked[0]
    ? { cls: "wiz-warn", text: v.blocked[0] }
    : dirty
      ? { cls: "wiz-warn", text: r.dirty }
      : running
        ? { cls: "", text: v.job?.steps.at(-1)?.message ?? "…" }
        : v.status === "failed"
          ? { cls: "error", text: r.failed(v.job?.error ?? "") }
          : rc && v.stale
            ? { cls: "wiz-warn", text: r.stale }
            : rc && v.accepted
              ? { cls: "wiz-ok", text: r.accepted }
              : rc
                ? { cls: "wiz-ok", text: r.written(when(rc.ran_at), rc.parcels, named) }
                : { cls: "wiz-from", text: r.never };
  return (
    <div className="ab">
      <span className="ab-what">{r.what}</span>
      <span className={`ab-status ${status.cls}`}>{status.text}</span>
      {rc && !running && (
        <Button className="wiz-link" onPress={() => setOpen(true)}>
          {r.receipt}
        </Button>
      )}
      <DialogTrigger>
        <Button className="ly-add">
          {r.formats}
          <ChevronDown aria-hidden="true" size="0.8em" />
        </Button>
        <Popover className="popover" placement="bottom end">
          <Dialog className="popover-body ab-formats" aria-label={r.formats}>
            <p className="wiz-from ly-help">{r.formatsHelp}</p>
            {FORMATS.map((f) => (
              <Tick
                key={f}
                isSelected={v.exports.includes(f)}
                onChange={(on) => formats.mutate(on ? [...v.exports, f] : v.exports.filter((x) => x !== f))}
              >
                {r.formatNames[f]}
              </Tick>
            ))}
          </Dialog>
        </Popover>
      </DialogTrigger>
      {running ? (
        <Button className="button" onPress={() => act.mutate("stop")}>
          {r.stop}
        </Button>
      ) : (
        <Button
          className={rc && !v.stale ? "button" : "button button-primary"}
          isDisabled={v.blocked.length > 0 || dirty || act.isPending}
          onPress={() => act.mutate("run")}
        >
          {rc ? r.again : r.run}
        </Button>
      )}
      {act.error && (
        <span className="error" role="alert">
          {act.error.message}
        </span>
      )}
      {open && rc && (
        <ReceiptDialog
          projectId={projectId}
          view={v}
          groups={groups}
          close={() => setOpen(false)}
          accept={() => act.mutate("accept")}
        />
      )}
    </div>
  );
}

function ReceiptDialog({
  projectId,
  view,
  groups,
  close,
  accept,
}: {
  projectId: string;
  view: AssembleView;
  groups: ModelGroup[];
  close: () => void;
  accept: () => void;
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
  const colour = (id: string) => groups.find((x) => x.id === id)?.color ?? "#9a9a9a";
  return (
    <ModalOverlay className="modal-overlay" isDismissable isOpen onOpenChange={(o) => !o && close()}>
      <Modal className="modal ab-modal">
        <Dialog className="modal-body rc-body">
          <Heading slot="title" className="modal-title">
            {r.title}
          </Heading>
          <p className="rc-sub">
            {when(rc.ran_at)} · {rc.seconds}s · OpenAVMKit {rc.engine}
          </p>
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
                  <td className="rc-td ab-n">{x.parcels.toLocaleString()}</td>
                  <td className="rc-td ab-n">{x.vacant.toLocaleString()}</td>
                  <td className="rc-td ab-n">{x.sales.toLocaleString()}</td>
                  <td className="rc-td ab-n">{x.vacant_sales.toLocaleString()}</td>
                  {!rc.matches_preview && (
                    <td className={`rc-td ab-n ${x.preview !== x.parcels ? "wiz-warn" : ""}`}>
                      {x.preview?.toLocaleString() ?? "—"}
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
              <summary>{r.notes(rc.notes.length)}</summary>
              <ul>
                {rc.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </details>
          )}
          <div className="form-actions rc-actions">
            <Button className="button" onPress={() => show.mutate()}>
              {r.show}
            </Button>
            <span className="ab-grow" />
            <Button className="button" onPress={close}>
              {r.close}
            </Button>
            <Button
              className="button button-primary"
              isDisabled={view.stale || view.accepted}
              onPress={accept}
            >
              {view.accepted ? r.accepted : r.looksRight}
            </Button>
          </div>
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

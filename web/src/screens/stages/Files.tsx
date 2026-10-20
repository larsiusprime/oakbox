import { useMutation, useQuery } from "@tanstack/react-query";
import { FolderOpen, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button, Disclosure, DisclosurePanel, Heading } from "react-aria-components";
import { type FileUse, type Inspection, type SourceFile, unwrap } from "../../api/client";
import { CheckList, Choice, Field, Tick } from "../../components/Form";
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

const USES: readonly (readonly [FileUse, string])[] = (["parcel_map", "parcels", "sales"] as const).map(
  (u) => [u, t.files.uses[u]] as const,
);

declare global {
  interface Window {
    pywebview?: { api?: { pick_paths?: (kind: "files" | "folder") => Promise<string[] | null> } };
  }
}

function size(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function FilesStage({ detail }: StageProps) {
  const { project, running_job } = detail;
  const status = project.stages.files;
  const check = useQuery({
    queryKey: ["check", project.id, "files"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/stages/{stage}/check", {
          params: { path: { project_id: project.id, stage: "files" } },
        }),
      ),
  });
  const files = project.setup.files;
  const checking = running_job?.step === "check_files" ? running_job : null;

  return (
    <StageFrame
      title={t.stages.files.title}
      what={t.stages.files.what}
      status={<StageStatusMark status={status} />}
      note={project.notes.files}
    >
      <StaleNote status={status} />
      <Part title={t.frame.decide}>
        {files.length === 0 && <p className="empty-inline">{t.files.empty}</p>}
        <ul className="file-list">
          {files.map((f) => (
            <FileRow key={f.id} projectId={project.id} file={f} locked={running_job !== null} />
          ))}
        </ul>
        {!files.some((f) => f.uses.includes("parcel_map")) && files.length > 0 && (
          <p className="stale-note">{t.files.noMap}</p>
        )}
        <AddFile projectId={project.id} locked={running_job !== null} />
      </Part>
      <Part title={t.frame.check}>
        <p className="row-meta">{t.files.checkWhat}</p>
        <CheckRunner
          projectId={project.id}
          stage="files"
          runningJob={checking}
          ran={check.data?.ran ?? false}
          fresh={check.data?.fresh ?? false}
          disabled={files.length === 0 || (running_job !== null && checking === null)}
        />
      </Part>
      {check.data?.ran && files.some((f) => f.profile) && (
        <Part title={t.frame.receipt}>
          <ul className="receipt-list">
            {files.map((f) => (
              <li key={f.id}>
                <strong>{f.name}</strong>
                {f.profile ? (
                  <ProfileLines file={f} />
                ) : (
                  <span className="row-meta">{t.files.notImported}</span>
                )}
              </li>
            ))}
          </ul>
        </Part>
      )}
      <LooksRight projectId={project.id} stage="files" status={status} />
      <UnderTheHood projectId={project.id} stage="files" />
    </StageFrame>
  );
}

function ProfileLines({ file }: { file: SourceFile }) {
  const p = file.profile;
  if (!p) return null;
  const ids = p.distinct_ids ?? 0;
  return (
    <>
      <span className="row-meta">{t.files.profile(p.rows, ids)}</span>
      {ids > 0 && p.rows - (p.blank_ids ?? 0) > ids && (
        <span className="note-line">{t.files.severalRows(p.rows - (p.blank_ids ?? 0), ids)}</span>
      )}
      {(p.blank_ids ?? 0) > 0 && <span className="note-line">{t.files.blankIds(p.blank_ids ?? 0)}</span>}
    </>
  );
}

function FileRow({ projectId, file, locked }: { projectId: string; file: SourceFile; locked: boolean }) {
  const save = useSave(
    projectId,
    (body: Pick<SourceFile, "name" | "uses" | "id_columns" | "keep_columns" | "keep_rows">) =>
      api.PUT("/api/projects/{project_id}/files/{file_id}", {
        params: { path: { project_id: projectId, file_id: file.id } },
        body,
      }),
  );
  const remove = useSave(projectId, (_: null) =>
    api.DELETE("/api/projects/{project_id}/files/{file_id}", {
      params: { path: { project_id: projectId, file_id: file.id } },
    }),
  );
  const columns = file.profile?.columns.map((c) => c.name) ?? [];
  const decisions = {
    name: file.name,
    uses: file.uses,
    id_columns: file.id_columns,
    keep_columns: file.keep_columns,
    keep_rows: file.keep_rows,
  };
  const total = file.profile?.columns.length;
  return (
    <li className="file-row">
      <Disclosure>
        <Heading className="file-head">
          <Button slot="trigger" className="file-trigger">
            <span className="file-name">{file.name}</span>
            <span className="row-meta">
              {file.uses.map((u) => t.files.uses[u]).join(" · ")}
              {file.id_columns[0] ? ` · ${t.files.idColumn}: ${file.id_columns[0]}` : ""}
              {file.size_bytes !== null ? ` · ${size(file.size_bytes)}` : ""}
            </span>
          </Button>
          <span className={file.imported ? "status status-done" : "status status-not_run"}>
            {file.imported ? t.files.imported : t.files.notImported}
          </span>
        </Heading>
        <DisclosurePanel className="file-editor">
          {file.description && <p className="row-meta">{file.description}</p>}
          <CheckList
            label={t.files.whatIsIt}
            value={file.uses}
            options={USES}
            onChange={(uses) => save.mutate({ ...decisions, uses })}
            help={t.files.usesLater}
          />
          {columns.length > 0 ? (
            <Choice
              label={t.files.idColumn}
              value={file.id_columns[0] ?? null}
              options={columns.map((c) => [c, c] as const)}
              onChange={(c) => save.mutate({ ...decisions, id_columns: [c] })}
            />
          ) : (
            <p className="row-meta">
              {t.files.idColumn}: {file.id_columns[0]}
            </p>
          )}
          {file.keep_columns && total !== undefined && (
            <p className="row-meta">{t.files.columnsKept(file.keep_columns.length, total)}</p>
          )}
          {file.keep_rows && (
            <Tick isSelected onChange={(on) => !on && save.mutate({ ...decisions, keep_rows: null })}>
              {t.files.keepRows(file.keep_rows.column, file.keep_rows.values.join(", "))}
            </Tick>
          )}
          <div className="row-actions">
            <Button
              className="button"
              isDisabled={locked || remove.isPending}
              onPress={() => remove.mutate(null)}
            >
              <Trash2 aria-hidden="true" size="1em" />
              {t.files.remove}
            </Button>
          </div>
          {(save.error || remove.error) && (
            <p className="error" role="alert">
              {(save.error ?? remove.error)?.message}
            </p>
          )}
        </DisclosurePanel>
      </Disclosure>
    </li>
  );
}

function AddFile({ projectId, locked }: { projectId: string; locked: boolean }) {
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");
  const look = useMutation({
    mutationFn: async (p: string) => unwrap(await api.POST("/api/inspect", { body: { path: p } })),
  });
  const pick = async (kind: "files" | "folder") => {
    const paths = await window.pywebview?.api?.pick_paths?.(kind);
    const first = paths?.[0];
    if (first) {
      setPath(first);
      look.mutate(first);
    }
  };
  const reset = () => {
    setOpen(false);
    setPath("");
    look.reset();
  };
  if (!open)
    return (
      <Button className="button" isDisabled={locked} onPress={() => setOpen(true)}>
        <Plus aria-hidden="true" size="1em" />
        {t.files.add}
      </Button>
    );
  const canBrowse = Boolean(window.pywebview?.api?.pick_paths);
  return (
    <div className="add-file">
      <div className="add-file-path">
        <Field
          label={t.files.pathLabel}
          help={t.files.pathHelp}
          value={path}
          onChange={setPath}
          width="long"
          autoFocus
        />
        {canBrowse && (
          <>
            <Button className="button" onPress={() => void pick("files")}>
              <FolderOpen aria-hidden="true" size="1em" />
              {t.files.browse}
            </Button>
            <Button className="button" onPress={() => void pick("folder")}>
              {t.files.browseFolder}
            </Button>
          </>
        )}
        <Button
          className="button button-primary"
          isDisabled={!path.trim() || look.isPending}
          onPress={() => look.mutate(path.trim())}
        >
          {t.files.lookInside}
        </Button>
        <Button className="button" onPress={reset}>
          {t.files.cancel}
        </Button>
      </div>
      {look.error && (
        <p className="error" role="alert">
          {look.error.message}
        </p>
      )}
      {look.data?.problem && (
        <p className="error" role="alert">
          {look.data.problem}
        </p>
      )}
      {look.data && !look.data.problem && look.data.export && (
        <ExportPicker projectId={projectId} insp={look.data} onDone={reset} />
      )}
      {look.data && !look.data.problem && !look.data.export && (
        <SingleFile projectId={projectId} insp={look.data} onDone={reset} />
      )}
    </div>
  );
}

function SingleFile({
  projectId,
  insp,
  onDone,
}: {
  projectId: string;
  insp: Inspection;
  onDone: () => void;
}) {
  const [uses, setUses] = useState<FileUse[]>(insp.suggested_uses);
  const [id, setId] = useState<string | null>(insp.suggested_id_column);
  const add = useSave(projectId, (_: null) =>
    api.POST("/api/projects/{project_id}/files", {
      params: { path: { project_id: projectId } },
      body: {
        path: insp.path,
        member: insp.member,
        name: insp.member && insp.layers.length > 1 ? `${insp.name} (${insp.member})` : insp.name,
        uses,
        id_columns: id ? [id] : [],
        keep_columns: null,
        keep_rows: null,
      },
    }),
  );
  const columns = insp.columns.filter((c) => c.type !== "geometry");
  return (
    <div className="inspection">
      <Preview insp={insp} />
      <div className="form-grid">
        <CheckList
          label={t.files.whatIsIt}
          value={uses}
          options={USES}
          onChange={setUses}
          help={t.files.usesLater}
        />
        <Choice
          label={t.files.idColumn}
          value={id}
          placeholder={t.files.chooseId}
          options={columns.map((c) => [c.name, c.name] as const)}
          onChange={setId}
        />
      </div>
      <Button
        className="button button-primary"
        isDisabled={!id || uses.length === 0 || add.isPending}
        onPress={() => add.mutate(null, { onSuccess: onDone })}
      >
        <Plus aria-hidden="true" size="1em" />
        {t.files.addThis}
      </Button>
      {add.error && (
        <p className="error" role="alert">
          {add.error.message}
        </p>
      )}
    </div>
  );
}

function ExportPicker({
  projectId,
  insp,
  onDone,
}: {
  projectId: string;
  insp: Inspection;
  onDone: () => void;
}) {
  const ex = insp.export;
  const [chosen, setChosen] = useState<string[]>(
    ex ? ex.members.filter((m) => m.used_by_default).map((m) => m.member) : [],
  );
  const add = useSave(projectId, (_: null) =>
    api.POST("/api/projects/{project_id}/exports", {
      params: { path: { project_id: projectId } },
      body: { path: insp.path, members: chosen },
    }),
  );
  if (!ex) return null;
  return (
    <div className="inspection">
      <h4>{t.files.exportTitle(ex.name)}</h4>
      <p className="row-meta">{t.files.exportNote}</p>
      <ul className="export-members">
        {ex.members.map((m) => (
          <li key={m.member}>
            <Tick
              isSelected={chosen.includes(m.member)}
              onChange={(on) => setChosen((c) => (on ? [...c, m.member] : c.filter((x) => x !== m.member)))}
            >
              <span className="file-name">{m.member}</span> <span className="row-meta">{m.label}</span>
            </Tick>
            <span className="row-meta member-meta">
              {m.description} · {t.files.records(m.records)} · {size(m.size_bytes)}
            </span>
          </li>
        ))}
      </ul>
      {ex.unknown.length > 0 && <p className="row-meta">{t.files.notInLayout(ex.unknown.join(", "))}</p>}
      <Button
        className="button button-primary"
        isDisabled={chosen.length === 0 || add.isPending}
        onPress={() => add.mutate(null, { onSuccess: onDone })}
      >
        <Plus aria-hidden="true" size="1em" />
        {t.files.addChosen(chosen.length)}
      </Button>
      {add.error && (
        <p className="error" role="alert">
          {add.error.message}
        </p>
      )}
    </div>
  );
}

function Preview({ insp }: { insp: Inspection }) {
  const cols = insp.columns.filter((c) => c.type !== "geometry").map((c) => c.name);
  return (
    <div className="preview">
      <p className="row-meta">{t.files.preview(insp.rows_estimate)}</p>
      <div className="table-wrap preview-wrap">
        <table className="data-table preview-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th scope="col" key={c}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {insp.sample.slice(0, 8).map((row, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: preview rows have no identity
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c}>{row[c]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

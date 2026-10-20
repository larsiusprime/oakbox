import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus } from "lucide-react";
import { useState } from "react";
import { Button, Label, Radio, RadioGroup } from "react-aria-components";
import { api, type FileCheck, type Project, type ProjectDetail, unwrap } from "../api/client";
import { Choice, Field } from "../components/Form";
import { desktop } from "../desktop";
import { t } from "../strings";

function size(bytes: number): string {
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(0)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** F2: the project's data.load entries, and adding a file to in/ (SPEC §3.0). */
export function DataFiles({ project }: { project: Project }) {
  const [adding, setAdding] = useState(false);
  const f = t.dataFiles;
  return (
    <section className="panel" aria-labelledby="files-title">
      <header className="panel-head">
        <h2 id="files-title">{f.title}</h2>
        {!adding && (
          <Button className="button panel-head-action" onPress={() => setAdding(true)}>
            <Plus aria-hidden="true" size="1em" />
            {f.add}
          </Button>
        )}
      </header>
      <p className="row-meta panel-note">{f.note}</p>
      {project.files.length === 0 && !adding && <p className="empty">{f.none}</p>}
      {project.files.length > 0 && (
        <ul className="rows">
          {project.files.map((file) => (
            <li key={file.name} className="row">
              <div className="row-main">
                <span className="row-title mono">{file.name}</span>
                <span className="row-meta">{f.entry(file.filename, file.layer)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {adding && <AddFile project={project} onDone={() => setAdding(false)} />}
    </section>
  );
}

function AddFile({ project, onDone }: { project: Project; onDone: () => void }) {
  const f = t.dataFiles;
  const [path, setPath] = useState("");
  const check = useMutation({
    mutationFn: async (p: string) =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files/check", {
          params: { path: { project_id: project.id } },
          body: { path: p },
        }),
      ),
  });
  const browse = async () => {
    const picked = await desktop.pickFile();
    if (picked) {
      setPath(picked);
      check.mutate(picked);
    }
  };
  return (
    <div className="add-file">
      <div className="setting-line">
        <Field label={f.path} help={f.pathHelp} value={path} onChange={setPath} width="long" autoFocus />
        {desktop.canPickFile() && (
          <Button className="button" onPress={() => void browse()}>
            <FolderOpen aria-hidden="true" size="1em" />
            {f.browse}
          </Button>
        )}
        <Button
          className="button button-primary"
          isDisabled={!path.trim() || check.isPending}
          onPress={() => check.mutate(path.trim())}
        >
          {f.check}
        </Button>
        <Button className="button" onPress={onDone}>
          {f.cancel}
        </Button>
      </div>
      {check.error && (
        <p className="error" role="alert">
          {check.error.message}
        </p>
      )}
      {check.data?.problem && (
        <p className="error" role="alert">
          {check.data.problem}
        </p>
      )}
      {check.data && !check.data.problem && (
        // Keyed by path, so checking another file starts its choices afresh.
        <Choices key={check.data.path} project={project} found={check.data} onDone={onDone} />
      )}
    </div>
  );
}

function Choices({ project, found, onDone }: { project: Project; found: FileCheck; onDone: () => void }) {
  const f = t.dataFiles;
  const queryClient = useQueryClient();
  const [name, setName] = useState(found.suggested_name);
  const [mode, setMode] = useState<"move" | "copy">("copy");
  const [layer, setLayer] = useState<string | null>(
    found.layers.length === 1 ? (found.layers[0] ?? null) : null,
  );
  const stem = found.filename.replace(/\.[^.]+$/, "");
  const [filename, setFilename] = useState(found.filename_taken ? `${stem}_2` : "");
  const add = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files", {
          params: { path: { project_id: project.id } },
          body: {
            path: found.path,
            mode,
            name: name.trim(),
            layer,
            filename: found.filename_taken ? filename.trim() : null,
          },
        }),
      ),
    onSuccess: (p) => {
      queryClient.setQueryData<ProjectDetail>(["project", project.id], (old) =>
        old ? { ...old, project: p } : old,
      );
      onDone();
    },
  });
  const ready =
    name.trim() && (found.layers.length === 0 || layer) && (!found.filename_taken || filename.trim());
  return (
    <div className="file-choices">
      <p>
        <strong>{found.filename}</strong> · {f.format(found.format ?? "", size(found.size_bytes))}
      </p>
      {found.files.length > 1 && <p className="row-meta">{f.together(found.files.join(", "))}</p>}
      {found.layers.length > 1 && (
        <Choice
          label={f.layer}
          value={layer}
          options={found.layers.map((l) => [l, l] as const)}
          onChange={setLayer}
        />
      )}
      <Field label={f.name} help={f.nameHelp} value={name} onChange={setName} />
      {found.filename_taken && (
        <Field
          label={f.newFilename}
          help={f.newFilenameHelp(found.filename)}
          value={filename}
          onChange={setFilename}
        />
      )}
      {found.already_in_project ? (
        <p className="row-meta">{f.already}</p>
      ) : (
        <RadioGroup className="field radios" value={mode} onChange={(v) => setMode(v as "move" | "copy")}>
          <Label className="field-label">{f.how}</Label>
          <Radio value="copy" className="radio">
            <span className="radio-dot" aria-hidden="true" />
            {f.copy}
          </Radio>
          <Radio value="move" className="radio">
            <span className="radio-dot" aria-hidden="true" />
            {f.move}
          </Radio>
        </RadioGroup>
      )}
      <div className="form-actions">
        <Button
          className="button button-primary"
          isDisabled={!ready || add.isPending}
          onPress={() => add.mutate()}
        >
          <Plus aria-hidden="true" size="1em" />
          {add.isPending ? f.adding(mode) : f.addButton}
        </Button>
      </div>
      {add.error && (
        <p className="error" role="alert">
          {add.error.message}
        </p>
      )}
    </div>
  );
}

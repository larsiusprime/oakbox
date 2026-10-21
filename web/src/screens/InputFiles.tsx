import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus } from "lucide-react";
import { useState } from "react";
import { Button, Label, Radio, RadioGroup } from "react-aria-components";
import { api, type FileCheck, type Project, type ProjectDetail, unwrap } from "../api/client";
import { Choice, Field } from "../components/Form";
import { TipOn } from "../components/Tip";
import { desktop, useCanPickFile } from "../desktop";
import { useAddFileRequest } from "../menu";
import { t } from "../strings";
import { InputFileList, size } from "./InputFileList";

/** F3: the Input files tab, the project's data.load entries (SPEC §3.0). */
export function InputFilesTab({ detail }: { detail: ProjectDetail }) {
  const f = t.inputFiles;
  const { project, files } = detail;
  const canPick = useCanPickFile();
  // The file picker drives adding: nothing opens until a file is picked (SPEC F2).
  const [picked, setPicked] = useState<string | null>(null);
  const pick = async () => {
    const path = await desktop.pickFile();
    if (path) setPicked(path);
  };
  useAddFileRequest(() => void pick()); // Project → Add a file… (SPEC §3.14)
  const addButton = canPick ? (
    <Button className="button" onPress={() => void pick()}>
      <Plus aria-hidden="true" size="1em" />
      {f.add}
    </Button>
  ) : (
    <TipOn text={f.needsWindow}>
      <Button className="button" isDisabled>
        <Plus aria-hidden="true" size="1em" />
        {f.add}
      </Button>
    </TipOn>
  );
  return (
    <div className="input-files">
      {files.length > 0 && picked === null && <div className="tab-actions">{addButton}</div>}
      {picked !== null && (
        <AddFile
          project={project}
          path={picked}
          onBrowse={() => void pick()}
          onDone={() => setPicked(null)}
        />
      )}
      {files.length === 0 && picked === null && (
        <div className="tab-empty">
          <p className="empty">{f.none}</p>
          {addButton}
        </div>
      )}
      {files.length > 0 && <InputFileList project={project} files={files} />}
    </div>
  );
}

function AddFile(props: { project: Project; path: string; onBrowse: () => void; onDone: () => void }) {
  const f = t.inputFiles;
  const { project, path } = props;
  const check = useQuery({
    queryKey: ["file-check", project.id, path],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/projects/{project_id}/files/check", {
          params: { path: { project_id: project.id } },
          body: { path },
        }),
      ),
    gcTime: 0,
    staleTime: 0,
  });
  const found = check.data && !check.data.problem ? check.data : null;
  const problem = check.error?.message ?? check.data?.problem ?? null;
  return (
    <div className="add-file">
      <div className="pick-line">
        <div className="pick-file">
          <div className="pick-head">
            <span className="field-label">{f.path}</span>
            {found && <Pills found={found} />}
          </div>
          <TipOn text={path} className="path-box">
            {/* Isolated, so the right-to-left box only moves the "…", not the path's characters. */}
            <bdi>{path}</bdi>
          </TipOn>
        </div>
        <Button className="button" onPress={props.onBrowse}>
          <FolderOpen aria-hidden="true" size="1em" />
          {f.browse}
        </Button>
        <Button className="button" onPress={props.onDone}>
          {f.cancel}
        </Button>
      </div>
      {problem && (
        <p className="error" role="alert">
          {problem}
        </p>
      )}
      {found ? (
        // Keyed by path, so picking another file starts its choices afresh.
        <Choices key={found.path} project={project} found={found} onDone={props.onDone} />
      ) : (
        <div className="form-actions">
          <Button className="button button-primary" isDisabled>
            <Plus aria-hidden="true" size="1em" />
            {f.addButton}
          </Button>
        </div>
      )}
    </div>
  );
}

function Pills({ found }: { found: FileCheck }) {
  const companions = found.files
    .filter((name) => name !== found.filename)
    .map((name) => name.slice(name.lastIndexOf(".")));
  return (
    <span className="pills">
      <span className="pill">{found.format}</span>
      <span className="pill">{size(found.size_bytes)}</span>
      {companions.length > 0 && <span className="pill">{f_companions(companions)}</span>}
    </span>
  );
}

const f_companions = (exts: string[]) => t.inputFiles.companions(exts.join(" "));

function Choices({ project, found, onDone }: { project: Project; found: FileCheck; onDone: () => void }) {
  const f = t.inputFiles;
  const queryClient = useQueryClient();
  const [name, setName] = useState(found.suggested_name);
  const [mode, setMode] = useState<"move" | "copy">("copy");
  const [layer, setLayer] = useState<string | null>(
    found.layers.length === 1 ? (found.layers[0] ?? null) : null,
  );
  const stem = found.filename.replace(/\.[^.]+$/, "");
  const ext = found.filename.slice(stem.length);
  const [filename, setFilename] = useState(found.filename_taken ? `${stem}_2${ext}` : "");
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
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["project", project.id] });
      onDone();
    },
  });
  const ready =
    name.trim() && (found.layers.length === 0 || layer) && (!found.filename_taken || filename.trim());
  return (
    <div className="file-choices">
      <div className="choice-columns">
        <div className="choice-column">
          <Field label={f.name} tip={f.nameHelp} value={name} onChange={setName} />
          {found.filename_taken && (
            <Field
              label={f.newFilename}
              tip={f.newFilenameHelp(found.filename)}
              value={filename}
              onChange={setFilename}
            />
          )}
        </div>
        {found.layers.length > 1 && (
          <Choice
            label={f.layer}
            value={layer}
            options={found.layers.map((l) => [l, l] as const)}
            onChange={setLayer}
          />
        )}
        {found.already_in_project ? (
          <div className="field">
            <span className="field-label">{f.how}</span>
            <span className="already">{f.already}</span>
          </div>
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
      </div>
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
